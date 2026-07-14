package com.cybel.facebridge;

import android.content.Context;
import android.hardware.camera2.CameraAccessException;
import android.hardware.camera2.CameraCaptureSession;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraDevice;
import android.hardware.camera2.CameraManager;
import android.hardware.camera2.CaptureRequest;
import android.graphics.ImageFormat;
import android.media.Image;
import android.media.ImageReader;
import android.os.Handler;
import android.util.Log;
import android.util.Range;

import java.util.Collections;
import java.util.concurrent.ExecutorService;

/**
 * Capture caméra Camera2 entièrement headless : la seule cible de sortie est un
 * ImageReader, il n'existe aucune SurfaceView/TextureView de prévisualisation — ce
 * qui permet à ce Service de tourner sans jamais afficher de fenêtre ni voler le
 * focus au kiosque.
 *
 * Débit volontairement très bas (throttle logiciel + plage FPS caméra réduite) :
 * pour détecter un visiteur qui s'approche, la latence n'a pas besoin d'être
 * meilleure qu'~1s, alors que la consommation CPU/batterie compte sur un kiosque
 * qui tourne des heures d'affilée.
 */
final class CameraPipeline {
    private static final String TAG = "CybelCameraPipeline";
    static final int TARGET_WIDTH = 640;
    static final int TARGET_HEIGHT = 480;
    private static final long MIN_PROCESS_INTERVAL_MS = 800;
    private static final long REOPEN_DELAY_MS = 5000;

    interface FrameListener {
        void onFrame(byte[] nv21, int width, int height);
    }

    private final Context context;
    private final Handler cameraHandler;
    private final ExecutorService workExecutor;
    private final FrameListener listener;

    private CameraManager cameraManager;
    private CameraDevice cameraDevice;
    private CameraCaptureSession captureSession;
    private ImageReader imageReader;
    private String openCameraId;
    private CameraCharacteristics openCameraCharacteristics;
    private volatile boolean busy;
    private volatile boolean stopped;
    private long lastProcessedAtMs;

    CameraPipeline(Context context, Handler cameraHandler, ExecutorService workExecutor, FrameListener listener) {
        this.context = context;
        this.cameraHandler = cameraHandler;
        this.workExecutor = workExecutor;
        this.listener = listener;
    }

    void start() {
        stopped = false;
        cameraManager = (CameraManager) context.getSystemService(Context.CAMERA_SERVICE);
        openCamera();
    }

    void stop() {
        stopped = true;
        cameraHandler.removeCallbacks(reopenRunnable);
        closeCameraQuietly();
    }

    /**
     * Ferme session/device/reader s'ils existent encore. Appelé avant CHAQUE tentative
     * d'ouverture : sans ça, un échec de createCaptureSession/setRepeatingRequest laissait
     * le CameraDevice ouvert, et la tentative suivante se bloquait elle-même en conflit
     * avec sa propre instance précédente (constaté sur le châssis réel : CAMERA_IN_USE,
     * "Conflicts with: ... client package com.cybel.facebridge" — soi-même).
     */
    private void closeCameraQuietly() {
        if (captureSession != null) {
            captureSession.close();
            captureSession = null;
        }
        if (cameraDevice != null) {
            cameraDevice.close();
            cameraDevice = null;
        }
        if (imageReader != null) {
            imageReader.close();
            imageReader = null;
        }
    }

    private void openCamera() {
        if (stopped) {
            return;
        }
        closeCameraQuietly();
        try {
            String cameraId = findBestCameraId();
            if (cameraId == null) {
                Log.e(TAG, "Aucune caméra disponible — abandon");
                return;
            }
            openCameraId = cameraId;
            imageReader = ImageReader.newInstance(TARGET_WIDTH, TARGET_HEIGHT, ImageFormat.YUV_420_888, 2);
            imageReader.setOnImageAvailableListener(this::onImageAvailable, cameraHandler);
            cameraManager.openCamera(cameraId, stateCallback, cameraHandler);
        } catch (CameraAccessException | SecurityException e) {
            Log.e(TAG, "openCamera échoué", e);
            scheduleReopen();
        }
    }

    /**
     * Préfère une caméra FRONT si disponible (téléphone/tablette générique), mais se
     * rabat sur la première caméra trouvée sinon : certains robots de réception
     * n'exposent qu'une seule caméra via Camera2, physiquement tournée vers le
     * visiteur mais classée "BACK" par Android (constaté sur le châssis CIOT
     * TY1251D-03195 — RK3399, module RK29_ICS_CameraHal, une seule caméra déclarée).
     */
    private String findBestCameraId() throws CameraAccessException {
        String[] ids = cameraManager.getCameraIdList();
        String fallback = null;
        CameraCharacteristics fallbackChars = null;
        for (String id : ids) {
            CameraCharacteristics chars = cameraManager.getCameraCharacteristics(id);
            Integer facing = chars.get(CameraCharacteristics.LENS_FACING);
            if (facing != null && facing == CameraCharacteristics.LENS_FACING_FRONT) {
                openCameraCharacteristics = chars;
                return id;
            }
            if (fallback == null) {
                fallback = id;
                fallbackChars = chars;
            }
        }
        if (fallback != null) {
            Log.w(TAG, "Aucune caméra FRONT — utilisation de la caméra " + fallback
                    + " (facing non-FRONT, matériel à caméra unique probable)");
        }
        openCameraCharacteristics = fallbackChars;
        return fallback;
    }

    /**
     * Certains capteurs (constaté : RK29_ICS_CameraHal, une seule plage 25-30 fps
     * annoncée) rejettent une CONTROL_AE_TARGET_FPS_RANGE arbitraire — on choisit donc
     * la plage la plus basse réellement supportée plutôt que d'en imposer une, pour
     * éviter un setRepeatingRequest en échec sur ce matériel. Réutilise les
     * CameraCharacteristics mises en cache par findBestCameraId() plutôt que d'appeler
     * getCameraCharacteristics() une seconde fois pendant que la caméra est déjà
     * ouverte : sur ce matériel (HAL LEGACY), cet appel tente une reconnexion interne
     * via l'API Camera1 qui entre en conflit avec notre propre connexion Camera2 déjà
     * active (constaté : CAMERA_IN_USE contre soi-même).
     */
    private Range<Integer> findLowestSupportedFpsRange() {
        if (openCameraCharacteristics == null) {
            return null;
        }
        Range<Integer>[] ranges =
                openCameraCharacteristics.get(CameraCharacteristics.CONTROL_AE_AVAILABLE_TARGET_FPS_RANGES);
        if (ranges == null || ranges.length == 0) {
            return null;
        }
        Range<Integer> lowest = ranges[0];
        for (Range<Integer> range : ranges) {
            if (range.getUpper() < lowest.getUpper()) {
                lowest = range;
            }
        }
        return lowest;
    }

    private final CameraDevice.StateCallback stateCallback = new CameraDevice.StateCallback() {
        @Override
        public void onOpened(CameraDevice device) {
            cameraDevice = device;
            createCaptureSession();
        }

        @Override
        public void onDisconnected(CameraDevice device) {
            device.close();
            cameraDevice = null;
            scheduleReopen();
        }

        @Override
        public void onError(CameraDevice device, int error) {
            Log.e(TAG, "Erreur périphérique caméra : " + error);
            device.close();
            cameraDevice = null;
            scheduleReopen();
        }
    };

    private void createCaptureSession() {
        try {
            final CaptureRequest.Builder builder =
                    cameraDevice.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW);
            builder.addTarget(imageReader.getSurface());
            Range<Integer> lowestFpsRange = findLowestSupportedFpsRange();
            if (lowestFpsRange != null) {
                builder.set(CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE, lowestFpsRange);
            }
            // Sinon : aucune tentative de réduire le FPS matériel — le throttle logiciel
            // dans onImageAvailable() borne déjà le coût CPU/batterie indépendamment.

            cameraDevice.createCaptureSession(
                    Collections.singletonList(imageReader.getSurface()),
                    new CameraCaptureSession.StateCallback() {
                        @Override
                        public void onConfigured(CameraCaptureSession session) {
                            captureSession = session;
                            try {
                                session.setRepeatingRequest(builder.build(), null, cameraHandler);
                            } catch (CameraAccessException e) {
                                Log.e(TAG, "setRepeatingRequest échoué", e);
                                scheduleReopen();
                            }
                        }

                        @Override
                        public void onConfigureFailed(CameraCaptureSession session) {
                            Log.e(TAG, "Configuration session caméra échouée");
                            scheduleReopen();
                        }
                    },
                    cameraHandler
            );
        } catch (CameraAccessException e) {
            Log.e(TAG, "createCaptureSession échoué", e);
            scheduleReopen();
        }
    }

    private void onImageAvailable(ImageReader reader) {
        Image image = reader.acquireLatestImage();
        if (image == null) {
            return;
        }
        long now = System.currentTimeMillis();
        if (busy || (now - lastProcessedAtMs) < MIN_PROCESS_INTERVAL_MS) {
            image.close();
            return;
        }
        busy = true;
        lastProcessedAtMs = now;

        final int width = image.getWidth();
        final int height = image.getHeight();
        final byte[] nv21;
        try {
            nv21 = ImageConversions.yuv420ToNv21(image);
        } catch (Exception e) {
            Log.e(TAG, "Extraction NV21 échouée", e);
            busy = false;
            image.close();
            return;
        }
        image.close();

        workExecutor.execute(() -> {
            try {
                listener.onFrame(nv21, width, height);
            } catch (Exception e) {
                Log.e(TAG, "Traitement frame échoué", e);
            } finally {
                busy = false;
            }
        });
    }

    private final Runnable reopenRunnable = this::openCamera;

    /**
     * Sans dédoublonnage, plusieurs échecs rapprochés empilaient plusieurs
     * callbacks postDelayed : l'un d'eux finissait par retarder la fermeture
     * d'une connexion caméra qui, entre-temps, avait fini par s'ouvrir avec
     * succès — la détruisant puis échouant contre elle-même en boucle
     * (constaté sur le châssis réel : CAMERA_IN_USE toutes les 5s malgré une
     * session active et fonctionnelle entre-temps).
     */
    private void scheduleReopen() {
        if (stopped) {
            return;
        }
        cameraHandler.removeCallbacks(reopenRunnable);
        cameraHandler.postDelayed(reopenRunnable, REOPEN_DELAY_MS);
    }
}
