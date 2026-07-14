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
        try {
            String cameraId = findFrontCameraId();
            if (cameraId == null) {
                Log.e(TAG, "Aucune caméra frontale disponible — abandon");
                return;
            }
            imageReader = ImageReader.newInstance(TARGET_WIDTH, TARGET_HEIGHT, ImageFormat.YUV_420_888, 2);
            imageReader.setOnImageAvailableListener(this::onImageAvailable, cameraHandler);
            cameraManager.openCamera(cameraId, stateCallback, cameraHandler);
        } catch (CameraAccessException | SecurityException e) {
            Log.e(TAG, "openCamera échoué", e);
            scheduleReopen();
        }
    }

    private String findFrontCameraId() throws CameraAccessException {
        for (String id : cameraManager.getCameraIdList()) {
            CameraCharacteristics chars = cameraManager.getCameraCharacteristics(id);
            Integer facing = chars.get(CameraCharacteristics.LENS_FACING);
            if (facing != null && facing == CameraCharacteristics.LENS_FACING_FRONT) {
                return id;
            }
        }
        return null;
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
            builder.set(CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE, new Range<>(2, 5));

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

    private void scheduleReopen() {
        if (stopped) {
            return;
        }
        cameraHandler.postDelayed(this::openCamera, REOPEN_DELAY_MS);
    }
}
