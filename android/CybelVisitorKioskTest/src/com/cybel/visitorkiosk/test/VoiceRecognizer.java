package com.cybel.visitorkiosk.test;

import android.content.Context;
import android.content.res.AssetManager;
import android.util.Log;

import org.json.JSONObject;
import org.vosk.Model;
import org.vosk.Recognizer;
import org.vosk.android.RecognitionListener;
import org.vosk.android.SpeechService;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

/**
 * Reconnaissance vocale hors-ligne via Vosk (STT français embarqué).
 *
 * Le modèle est livré dans assets/vosk-model-fr/ et copié une fois vers filesDir
 * au premier usage (Vosk a besoin d'un vrai répertoire, pas d'un asset compressé).
 * L'initialisation du modèle (~2 s, 41 Mo) se fait en arrière-plan.
 */
public class VoiceRecognizer {
    private static final String TAG = "CybelVoice";
    private static final String MODEL_ASSET_DIR = "vosk-model-fr";
    private static final float SAMPLE_RATE = 16000.0f;
    private static final int LISTEN_TIMEOUT_MS = 8000;

    public interface Callback {
        /** Résultat final du STT. `ok=false` si erreur/timeout sans texte. */
        void onResult(String transcript, boolean ok);
    }

    private final Context context;
    private Model model;
    private SpeechService speechService;
    private volatile boolean modelReady;
    private volatile boolean listening;

    public VoiceRecognizer(Context context) {
        this.context = context.getApplicationContext();
    }

    /** Copie/charge le modèle en arrière-plan. À appeler tôt (onCreate). */
    public void prepareAsync() {
        new Thread(() -> {
            try {
                File modelDir = ensureModelUnpacked();
                model = new Model(modelDir.getAbsolutePath());
                modelReady = true;
                Log.i(TAG, "Modèle Vosk prêt : " + modelDir.getAbsolutePath());
            } catch (Throwable t) {
                Log.e(TAG, "Chargement du modèle Vosk impossible — STT désactivé", t);
            }
        }, "VoskModelInit").start();
    }

    public boolean isReady() {
        return modelReady;
    }

    /** Démarre une écoute unique (~8 s max ou fin d'énoncé détectée). */
    public synchronized void listen(final Callback callback) {
        if (!modelReady || model == null) {
            callback.onResult("", false);
            return;
        }
        if (listening) {
            return;
        }
        try {
            Recognizer recognizer = new Recognizer(model, SAMPLE_RATE);
            speechService = new SpeechService(recognizer, SAMPLE_RATE);
            listening = true;
            speechService.startListening(new RecognitionListener() {
                @Override
                public void onResult(String hypothesis) {
                    // Fin d'un énoncé : on récupère le texte et on arrête.
                    String text = extractText(hypothesis, "text");
                    if (text != null && !text.isEmpty()) {
                        finish(text, true, callback);
                    }
                }

                @Override
                public void onFinalResult(String hypothesis) {
                    String text = extractText(hypothesis, "text");
                    finish(text == null ? "" : text, text != null && !text.isEmpty(), callback);
                }

                @Override
                public void onPartialResult(String hypothesis) {
                    // Ignoré (on ne renvoie que le résultat final).
                }

                @Override
                public void onError(Exception e) {
                    Log.e(TAG, "Erreur STT", e);
                    finish("", false, callback);
                }

                @Override
                public void onTimeout() {
                    finish("", false, callback);
                }
            }, LISTEN_TIMEOUT_MS);
        } catch (Throwable t) {
            Log.e(TAG, "Démarrage écoute impossible", t);
            listening = false;
            callback.onResult("", false);
        }
    }

    private synchronized void finish(String text, boolean ok, Callback callback) {
        if (!listening) {
            return;
        }
        listening = false;
        if (speechService != null) {
            speechService.stop();
            speechService.shutdown();
            speechService = null;
        }
        callback.onResult(text, ok);
    }

    public void shutdown() {
        if (speechService != null) {
            speechService.shutdown();
            speechService = null;
        }
        if (model != null) {
            model.close();
            model = null;
        }
        modelReady = false;
    }

    private static String extractText(String hypothesisJson, String key) {
        try {
            return new JSONObject(hypothesisJson).optString(key, "").trim();
        } catch (Exception e) {
            return null;
        }
    }

    /** Copie récursive du modèle depuis assets/ vers filesDir (une seule fois). */
    private File ensureModelUnpacked() throws IOException {
        File target = new File(context.getFilesDir(), MODEL_ASSET_DIR);
        File marker = new File(target, ".unpacked");
        if (marker.exists()) {
            return target;
        }
        copyAssetDir(context.getAssets(), MODEL_ASSET_DIR, target);
        // Marqueur pour ne pas recopier les 41 Mo à chaque démarrage.
        try (OutputStream out = new FileOutputStream(marker)) {
            out.write('1');
        }
        return target;
    }

    private static void copyAssetDir(AssetManager assets, String assetPath, File dest) throws IOException {
        String[] children = assets.list(assetPath);
        if (children == null || children.length == 0) {
            // Fichier (pas un dossier) : copie directe.
            copyAssetFile(assets, assetPath, dest);
            return;
        }
        if (!dest.exists() && !dest.mkdirs()) {
            throw new IOException("mkdir échoué : " + dest);
        }
        for (String child : children) {
            copyAssetDir(assets, assetPath + "/" + child, new File(dest, child));
        }
    }

    private static void copyAssetFile(AssetManager assets, String assetPath, File dest) throws IOException {
        File parent = dest.getParentFile();
        if (parent != null && !parent.exists()) {
            parent.mkdirs();
        }
        try (InputStream in = assets.open(assetPath);
             OutputStream out = new FileOutputStream(dest)) {
            byte[] buffer = new byte[8192];
            int read;
            while ((read = in.read(buffer)) != -1) {
                out.write(buffer, 0, read);
            }
        }
    }
}
