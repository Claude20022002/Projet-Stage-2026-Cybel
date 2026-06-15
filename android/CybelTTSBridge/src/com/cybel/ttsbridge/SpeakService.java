package com.cybel.ttsbridge;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.util.Log;

import java.util.Locale;

public class SpeakService extends Service implements TextToSpeech.OnInitListener {

    private static final String TAG = "CybelTTSBridge";
    private static final String CHANNEL_ID = "cybel_tts";

    private TextToSpeech tts;
    private String pendingText;

    @Override
    public void onCreate() {
        super.onCreate();
        tts = new TextToSpeech(this, this);
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        startForegroundNotification();
        String text = intent != null ? intent.getStringExtra("text") : null;
        if (text != null) {
            speak(text);
        }
        return START_NOT_STICKY;
    }

    private void startForegroundNotification() {
        Notification notification;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationManager nm = getSystemService(NotificationManager.class);
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID, "Cybel TTS", NotificationManager.IMPORTANCE_LOW);
            nm.createNotificationChannel(channel);
            notification = new Notification.Builder(this, CHANNEL_ID)
                    .setContentTitle("Cybel")
                    .setContentText("Synthese vocale en cours")
                    .setSmallIcon(android.R.drawable.ic_btn_speak_now)
                    .build();
        } else {
            notification = new Notification.Builder(this)
                    .setContentTitle("Cybel")
                    .setContentText("Synthese vocale en cours")
                    .setSmallIcon(android.R.drawable.ic_btn_speak_now)
                    .build();
        }
        startForeground(1, notification);
    }

    @Override
    public void onInit(int status) {
        if (status == TextToSpeech.SUCCESS) {
            tts.setLanguage(Locale.FRENCH);
            if (pendingText != null) {
                final String text = pendingText;
                pendingText = null;
                // TextToSpeech.onInit can fire slightly before the
                // service connection is fully usable; give it a moment.
                new Handler().postDelayed(new Runnable() {
                    @Override
                    public void run() {
                        doSpeak(text);
                    }
                }, 300);
            }
        } else {
            Log.e(TAG, "TTS init failed: " + status);
            stopForeground(true);
            stopSelf();
        }
    }

    private void speak(String text) {
        if (tts == null) {
            pendingText = text;
            return;
        }
        doSpeak(text);
    }

    private void doSpeak(String text) {
        tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
            @Override
            public void onStart(String utteranceId) {
            }

            @Override
            public void onDone(String utteranceId) {
                stopForeground(true);
                stopSelf();
            }

            @Override
            public void onError(String utteranceId) {
                stopForeground(true);
                stopSelf();
            }
        });
        Bundle params = new Bundle();
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, params, "cybel_utt");
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        if (tts != null) {
            tts.shutdown();
        }
        super.onDestroy();
    }
}
