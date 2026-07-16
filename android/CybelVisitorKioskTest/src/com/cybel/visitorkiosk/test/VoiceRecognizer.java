package com.cybel.visitorkiosk.test;

import android.content.Context;
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
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

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

    /**
     * Dézippe le modèle depuis assets/vosk-model-fr.zip vers filesDir (une seule fois).
     *
     * Le modèle est livré en un seul fichier zip et non en arborescence d'assets :
     * AssetManager.list() sur un sous-dossier renvoie vide sur cette tablette
     * (Android 7.1, APK construit hors Gradle — constaté sur le châssis réel),
     * alors que l'ouverture directe d'un fichier asset fonctionne.
     */
    private File ensureModelUnpacked() throws IOException {
        File target = new File(context.getFilesDir(), MODEL_ASSET_DIR);
        File marker = new File(target, ".unpacked");
        if (marker.exists()) {
            return target;
        }
        deleteRecursively(target);
        if (!target.mkdirs()) {
            throw new IOException("mkdir échoué : " + target);
        }
        String canonicalTarget = target.getCanonicalPath();
        try (ZipInputStream zip = new ZipInputStream(
                context.getAssets().open(MODEL_ASSET_DIR + ".zip"))) {
            ZipEntry entry;
            byte[] buffer = new byte[8192];
            while ((entry = zip.getNextEntry()) != null) {
                // L'archive amont contient un dossier racine (vosk-model-small-fr-0.22/) :
                // on le retire pour extraire directement dans vosk-model-fr/.
                String name = stripTopLevelDir(entry.getName());
                if (name.isEmpty()) {
                    continue;
                }
                File out = new File(target, name);
                // Protection zip-slip : l'entrée doit rester sous le dossier cible.
                if (!out.getCanonicalPath().startsWith(canonicalTarget + File.separator)) {
                    throw new IOException("Entrée zip suspecte : " + entry.getName());
                }
                if (entry.isDirectory()) {
                    out.mkdirs();
                    continue;
                }
                File parent = out.getParentFile();
                if (parent != null && !parent.exists() && !parent.mkdirs()) {
                    throw new IOException("mkdir échoué : " + parent);
                }
                try (OutputStream os = new FileOutputStream(out)) {
                    int read;
                    while ((read = zip.read(buffer)) != -1) {
                        os.write(buffer, 0, read);
                    }
                }
            }
        }
        if (!new File(target, "conf/model.conf").exists()) {
            throw new IOException("Extraction incomplète : conf/model.conf absent");
        }
        // Marqueur pour ne pas re-dézipper les 41 Mo à chaque démarrage.
        try (OutputStream out = new FileOutputStream(marker)) {
            out.write('1');
        }
        return target;
    }

    /** "vosk-model-small-fr-0.22/am/final.mdl" -> "am/final.mdl". */
    private static String stripTopLevelDir(String entryName) {
        String normalized = entryName.replace('\\', '/');
        int slash = normalized.indexOf('/');
        if (slash < 0) {
            return "";
        }
        return normalized.substring(slash + 1);
    }

    private static void deleteRecursively(File file) {
        if (file == null || !file.exists()) {
            return;
        }
        File[] children = file.listFiles();
        if (children != null) {
            for (File child : children) {
                deleteRecursively(child);
            }
        }
        file.delete();
    }
}
