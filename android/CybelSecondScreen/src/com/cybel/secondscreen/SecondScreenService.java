package com.cybel.secondscreen;

import android.app.Notification;
import android.app.Presentation;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.hardware.display.DisplayManager;
import android.os.Handler;
import android.os.IBinder;
import android.util.Log;
import android.view.Display;
import android.view.WindowManager;
import android.widget.ImageView;

import java.io.File;

/**
 * Affiche une image plein écran sur l'écran du dessous du robot.
 *
 * Cet écran est un second affichage Android (« HDMI Screen », display 1,
 * FLAG_PRESENTATION — relevé par `dumpsys display` le 2026-10-16), piloté par la
 * même tête que l'écran tactile. Un Service plutôt que le kiosque : l'affichage
 * survit à un plantage de la WebView, à l'ouverture de Deployment Tool par
 * l'opérateur, et ne dépend pas du backend Termux.
 *
 * Commandes (adb ou Termux) :
 *   am startservice -n com.cybel.secondscreen/.SecondScreenService \
 *       --es path /sdcard/Cybel/ecran-dessous.jpg     # change et mémorise l'image
 *   am startservice -n com.cybel.secondscreen/.SecondScreenService \
 *       -a com.cybel.secondscreen.HIDE                  # libère l'écran
 */
public class SecondScreenService extends Service {

    static final String TAG = "CybelSecondScreen";
    static final String ACTION_HIDE = "com.cybel.secondscreen.HIDE";
    static final String EXTRA_PATH = "path";
    static final String DEFAULT_PATH = "/sdcard/Cybel/ecran-dessous.jpg";

    private static final String PREFS = "second_screen";
    private static final String PREF_PATH = "path";
    private static final int NOTIFICATION_ID = 42;
    /** L'écran HDMI peut s'annoncer après le Service au démarrage du robot. */
    private static final long RETRY_DELAY_MS = 5000;

    private final Handler handler = new Handler();
    private DisplayManager displayManager;
    private Presentation presentation;
    private String imagePath = DEFAULT_PATH;

    private final DisplayManager.DisplayListener displayListener =
            new DisplayManager.DisplayListener() {
                @Override
                public void onDisplayAdded(int displayId) {
                    show();
                }

                @Override
                public void onDisplayRemoved(int displayId) {
                    if (presentation != null
                            && presentation.getDisplay().getDisplayId() == displayId) {
                        dismiss();
                    }
                }

                @Override
                public void onDisplayChanged(int displayId) {
                }
            };

    private final Runnable retryShow = new Runnable() {
        @Override
        public void run() {
            show();
        }
    };

    @Override
    public void onCreate() {
        super.onCreate();
        displayManager = (DisplayManager) getSystemService(Context.DISPLAY_SERVICE);
        displayManager.registerDisplayListener(displayListener, handler);
        imagePath = getSharedPreferences(PREFS, MODE_PRIVATE).getString(PREF_PATH, DEFAULT_PATH);
        // Premier plan : évite qu'Android tue le Service et éteigne l'écran du dessous
        // en pleine journée d'accueil.
        Notification notification = new Notification.Builder(this)
                .setContentTitle("CYBEL — écran du dessous")
                .setSmallIcon(android.R.drawable.ic_menu_gallery)
                .build();
        startForeground(NOTIFICATION_ID, notification);
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_HIDE.equals(intent.getAction())) {
            Log.i(TAG, "HIDE — écran du dessous libéré");
            dismiss();
            stopSelf();
            return START_NOT_STICKY;
        }
        if (intent != null && intent.hasExtra(EXTRA_PATH)) {
            String path = intent.getStringExtra(EXTRA_PATH);
            if (path != null && !path.trim().isEmpty()) {
                imagePath = path.trim();
                SharedPreferences.Editor editor =
                        getSharedPreferences(PREFS, MODE_PRIVATE).edit();
                editor.putString(PREF_PATH, imagePath);
                editor.apply();
            }
        }
        dismiss();
        show();
        return START_STICKY;
    }

    private void show() {
        handler.removeCallbacks(retryShow);
        if (presentation != null) {
            return;
        }
        Display[] displays =
                displayManager.getDisplays(DisplayManager.DISPLAY_CATEGORY_PRESENTATION);
        if (displays.length == 0) {
            Log.w(TAG, "Aucun écran de présentation — nouvel essai dans 5 s");
            handler.postDelayed(retryShow, RETRY_DELAY_MS);
            return;
        }
        Bitmap bitmap = BitmapFactory.decodeFile(imagePath);
        if (bitmap == null) {
            Log.w(TAG, "Image illisible : " + imagePath + " — nouvel essai dans 5 s");
            handler.postDelayed(retryShow, RETRY_DELAY_MS);
            return;
        }

        ImageView view = new ImageView(this);
        view.setBackgroundColor(Color.BLACK);
        view.setScaleType(ImageView.ScaleType.CENTER_CROP);
        view.setImageBitmap(bitmap);

        Presentation p = new Presentation(this, displays[0]);
        // Sans Activity, il faut une fenêtre système (permission accordée par appops).
        p.getWindow().setType(WindowManager.LayoutParams.TYPE_SYSTEM_ALERT);
        p.getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        p.setContentView(view);
        try {
            p.show();
            presentation = p;
            Log.i(TAG, "Affiché sur display " + displays[0].getDisplayId() + " : " + imagePath);
        } catch (WindowManager.InvalidDisplayException | WindowManager.BadTokenException e) {
            Log.e(TAG, "Affichage refusé (SYSTEM_ALERT_WINDOW accordé ?) : " + e);
            handler.postDelayed(retryShow, RETRY_DELAY_MS);
        }
    }

    private void dismiss() {
        if (presentation != null) {
            presentation.dismiss();
            presentation = null;
        }
    }

    @Override
    public void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        displayManager.unregisterDisplayListener(displayListener);
        dismiss();
        stopForeground(true);
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
