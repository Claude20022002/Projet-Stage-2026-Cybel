package com.cybel.facebridge;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.graphics.Bitmap;
import android.media.FaceDetector;
import android.os.Build;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.IBinder;
import android.util.Log;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Orchestrateur : Service foreground headless (pas d'Activity, pas d'icône) qui fait
 * tourner en continu détection + embedding + identification/enrôlement, tant que la
 * tablette est allumée. Toute la logique de reconnaissance reste sur l'appareil ;
 * seul un vecteur d'embedding (jamais une image) est envoyé au backend local.
 */
public class FaceRecognitionService extends Service {
    static final String ACTION_ENROLL = "com.cybel.facebridge.ACTION_ENROLL";

    private static final String TAG = "CybelFaceService";
    private static final String CHANNEL_ID = "cybel_face";
    private static final int CROP_TARGET_SIZE = 160;
    private static final long ENROLL_WINDOW_MS = 15000;

    private HandlerThread cameraThread;
    private Handler cameraHandler;
    private ExecutorService workExecutor;
    private CameraPipeline cameraPipeline;
    private FaceEmbedder faceEmbedder;
    private FaceDetector faceDetector;
    private BackendClient backendClient;
    private boolean started;

    private volatile PendingEnrollment pendingEnrollment;

    private static final class PendingEnrollment {
        final String name;
        final String civility;
        final long deadlineMs;

        PendingEnrollment(String name, String civility, long deadlineMs) {
            this.name = name;
            this.civility = civility;
            this.deadlineMs = deadlineMs;
        }

        boolean expired() {
            return System.currentTimeMillis() > deadlineMs;
        }
    }

    @Override
    public void onCreate() {
        super.onCreate();
        startForeground(1, buildNotification("CYBEL", "Reconnaissance visiteurs active"));

        cameraThread = new HandlerThread("CybelFaceCamera");
        cameraThread.start();
        cameraHandler = new Handler(cameraThread.getLooper());
        workExecutor = Executors.newSingleThreadExecutor();
        backendClient = new BackendClient();
        faceDetector = new FaceDetector(CameraPipeline.TARGET_WIDTH, CameraPipeline.TARGET_HEIGHT, 1);

        try {
            faceEmbedder = new FaceEmbedder(this);
        } catch (Exception e) {
            Log.e(TAG, "Modèle d'embedding indisponible (assets/face_embedding.tflite) — "
                    + "voir README.md. Reconnaissance désactivée.", e);
        }

        cameraPipeline = new CameraPipeline(this, cameraHandler, workExecutor, this::onFrame);
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_ENROLL.equals(intent.getAction())) {
            String name = intent.getStringExtra("name");
            String civility = intent.getStringExtra("civility");
            pendingEnrollment = new PendingEnrollment(
                    name, civility, System.currentTimeMillis() + ENROLL_WINDOW_MS);
            Log.i(TAG, "Fenêtre d'enrôlement ouverte pour " + name);
        }
        if (!started) {
            started = true;
            cameraPipeline.start();
        }
        return START_STICKY;
    }

    /** Appelé sur workExecutor (jamais le thread caméra ni le thread principal). */
    private void onFrame(byte[] nv21, int width, int height) {
        PendingEnrollment enrollment = pendingEnrollment;
        if (enrollment != null && enrollment.expired()) {
            pendingEnrollment = null;
            postNotification("CybelFaceBridge", "Aucun visage détecté — enrôlement annulé");
            enrollment = null;
        }

        if (faceEmbedder == null) {
            return;
        }

        Bitmap frame = ImageConversions.nv21ToRgb565(nv21, width, height);
        FaceDetector.Face[] faces = new FaceDetector.Face[1];
        int found = faceDetector.findFaces(frame, faces);
        if (found <= 0) {
            return;
        }

        Bitmap faceCrop = ImageConversions.cropFaceRegion(frame, faces[0], CROP_TARGET_SIZE);
        float[] embedding = faceEmbedder.embed(faceCrop);
        float confidence = faces[0].confidence();

        if (enrollment != null) {
            pendingEnrollment = null;
            boolean ok = backendClient.enroll(enrollment.name, enrollment.civility, embedding);
            postNotification("CybelFaceBridge", ok
                    ? "Visiteur enregistré : " + enrollment.name
                    : "Échec de l'enrôlement de " + enrollment.name);
            return;
        }

        backendClient.identify(embedding, confidence);
    }

    private void postNotification(String title, String text) {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (nm != null) {
            nm.notify((int) System.currentTimeMillis(), buildNotification(title, text));
        }
    }

    private Notification buildNotification(String title, String text) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationManager nm = getSystemService(NotificationManager.class);
            if (nm != null) {
                nm.createNotificationChannel(new NotificationChannel(
                        CHANNEL_ID, "Cybel Face Bridge", NotificationManager.IMPORTANCE_LOW));
            }
            return new Notification.Builder(this, CHANNEL_ID)
                    .setContentTitle(title)
                    .setContentText(text)
                    .setSmallIcon(android.R.drawable.ic_menu_camera)
                    .build();
        }
        return new Notification.Builder(this)
                .setContentTitle(title)
                .setContentText(text)
                .setSmallIcon(android.R.drawable.ic_menu_camera)
                .build();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        if (cameraPipeline != null) {
            cameraPipeline.stop();
        }
        if (workExecutor != null) {
            workExecutor.shutdownNow();
        }
        if (cameraThread != null) {
            cameraThread.quitSafely();
        }
        if (faceEmbedder != null) {
            faceEmbedder.close();
        }
        super.onDestroy();
    }
}
