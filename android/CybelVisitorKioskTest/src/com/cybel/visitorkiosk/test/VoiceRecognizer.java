package com.cybel.visitorkiosk.test;

import android.content.Context;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;
import org.vosk.Model;
import org.vosk.Recognizer;
import org.vosk.android.RecognitionListener;
import org.vosk.android.SpeechService;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
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

    // Grammaire dédiée au mot d'éveil — volontairement minuscule et distincte
    // de celle des commandes : la détection doit rester très spécifique pour
    // ne pas se déclencher sur une conversation ambiante non adressée au robot.
    //
    // « Cybel » seul échoue systématiquement (constaté sur le robot réel, sur
    // 10+ min d'écoute continue) : ce n'est pas un mot du dictionnaire français,
    // et le modèle Vosk « small » n'a pas de repli phonétique (G2P) pour les mots
    // hors-vocabulaire — il « aimante » le son vers un mot réel proche (« est »).
    // Contournement : « si belle » (/si bɛl/) est la prononciation française la
    // plus proche de « Cybel », composée de deux mots réels déjà dans le
    // dictionnaire du modèle — pas besoin de deviner leur prononciation.
    private static final String WAKE_GRAMMAR_JSON =
            "[\"salut si belle\", \"eh si belle\", \"si belle\", \"cybel\", \"[unk]\"]";
    private static final String[] WAKE_TRIGGERS = {"si belle", "cybel"};

    public interface Callback {
        /** Résultat final du STT. `ok=false` si erreur/timeout sans texte. */
        void onResult(String transcript, boolean ok);
    }

    public interface WakeListener {
        /** Appelé quand « Hé Cybel » est détecté ; l'écoute d'éveil est déjà arrêtée. */
        void onWakeDetected();
    }

    private final Context context;
    private Model model;
    private SpeechService speechService;
    private SpeechService wakeService;
    private volatile boolean modelReady;
    private volatile boolean listening;
    private volatile boolean wakeActive;
    private volatile String grammarJson;

    public VoiceRecognizer(Context context) {
        this.context = context.getApplicationContext();
    }

    /** Copie/charge le modèle en arrière-plan. À appeler tôt (onCreate).
     * `onReady` (thread d'arrière-plan, pas UI) est appelé une fois le modèle
     * chargé — sert par ex. à démarrer la boucle d'écoute du mot d'éveil. */
    public void prepareAsync(final Runnable onReady) {
        new Thread(() -> {
            try {
                File modelDir = ensureModelUnpacked();
                model = new Model(modelDir.getAbsolutePath());
                modelReady = true;
                Log.i(TAG, "Modèle Vosk prêt : " + modelDir.getAbsolutePath());
                if (onReady != null) {
                    onReady.run();
                }
            } catch (Throwable t) {
                Log.e(TAG, "Chargement du modèle Vosk impossible — STT désactivé", t);
            }
        }, "VoskModelInit").start();
        loadVocabularyAsync();
    }

    /**
     * Démarre l'écoute continue du mot d'éveil « Hé Cybel » en arrière-plan.
     * Sans effet si le modèle n'est pas prêt, si l'écoute d'éveil tourne déjà,
     * ou si une capture de commande est en cours (le micro est déjà utilisé).
     */
    public synchronized void startWakeLoop(final WakeListener onWake) {
        if (!modelReady || model == null || wakeActive || listening) {
            Log.i(TAG, "startWakeLoop ignoré (modelReady=" + modelReady + " wakeActive="
                    + wakeActive + " listening=" + listening + ")");
            return;
        }
        try {
            Recognizer recognizer = new Recognizer(model, SAMPLE_RATE, WAKE_GRAMMAR_JSON);
            wakeService = new SpeechService(recognizer, SAMPLE_RATE);
            wakeActive = true;
            Log.i(TAG, "Boucle mot d'éveil démarrée (grammaire : " + WAKE_GRAMMAR_JSON + ")");
            wakeService.startListening(new RecognitionListener() {
                @Override
                public void onResult(String hypothesis) {
                    Log.i(TAG, "Wake onResult brut : " + hypothesis);
                    String text = stripUnknownTokens(extractText(hypothesis, "text"));
                    if (text != null && containsWakeTrigger(text)) {
                        Log.i(TAG, "Mot d'éveil détecté : \"" + text + "\"");
                        stopWakeLoop();
                        onWake.onWakeDetected();
                    }
                }

                @Override
                public void onFinalResult(String hypothesis) {
                    Log.i(TAG, "Wake onFinalResult brut : " + hypothesis);
                }

                @Override
                public void onPartialResult(String hypothesis) {
                    Log.d(TAG, "Wake partiel : " + hypothesis);
                }

                @Override
                public void onError(Exception e) {
                    Log.w(TAG, "Erreur écoute mot d'éveil", e);
                }

                @Override
                public void onTimeout() {
                    Log.d(TAG, "Wake onTimeout");
                }
            });
        } catch (Throwable t) {
            Log.e(TAG, "Démarrage écoute mot d'éveil impossible", t);
            wakeActive = false;
        }
    }

    /** Arrête l'écoute du mot d'éveil (libère le micro pour une capture de commande). */
    public synchronized void stopWakeLoop() {
        if (wakeService != null) {
            wakeService.stop();
            wakeService.shutdown();
            wakeService = null;
        }
        wakeActive = false;
    }

    /**
     * Récupère le vocabulaire fermé (actions, POI, mots-clés FAQ) depuis le
     * backend et construit la grammaire Vosk correspondante, en tâche de fond.
     * Le dictaphone générique ne connaît pas les noms propres du site
     * (« HESTIM », noms de salles) — contraindre la reconnaissance à ce
     * périmètre au lieu de la dictée libre corrige ces confusions. Échec
     * silencieux : sans grammaire, `listen()` retombe sur la dictée libre.
     */
    private void loadVocabularyAsync() {
        new Thread(() -> {
            String body = fetchVocabularyJson();
            if (body == null) {
                Log.w(TAG, "Vocabulaire STT indisponible — reconnaissance en dictée libre");
                return;
            }
            try {
                JSONArray words = new JSONObject(body).optJSONArray("words");
                if (words == null || words.length() == 0) {
                    return;
                }
                JSONArray grammar = new JSONArray();
                for (int i = 0; i < words.length(); i++) {
                    grammar.put(words.getString(i));
                }
                grammar.put("[unk]");
                grammarJson = grammar.toString();
                Log.i(TAG, "Vocabulaire STT chargé (" + words.length() + " mots)");
            } catch (Exception e) {
                Log.w(TAG, "Vocabulaire STT : réponse invalide", e);
            }
        }, "VoiceVocabularyFetch").start();
    }

    private static String fetchVocabularyJson() {
        String[] hosts = {"127.0.0.1", BackendStarter.getWlanIp()};
        for (String host : hosts) {
            if (host == null || host.isEmpty()) {
                continue;
            }
            String result = httpGet("http://" + host + ":" + BackendStarter.BACKEND_PORT
                    + "/api/voice/vocabulary");
            if (result != null) {
                return result;
            }
        }
        return null;
    }

    private static String httpGet(String urlStr) {
        HttpURLConnection connection = null;
        try {
            URL url = new URL(urlStr);
            connection = (HttpURLConnection) url.openConnection();
            connection.setConnectTimeout(3000);
            connection.setReadTimeout(3000);
            connection.setRequestMethod("GET");
            int code = connection.getResponseCode();
            if (code < 200 || code >= 300) {
                return null;
            }
            InputStream is = connection.getInputStream();
            ByteArrayOutputStream buffer = new ByteArrayOutputStream();
            byte[] chunk = new byte[4096];
            int read;
            while ((read = is.read(chunk)) != -1) {
                buffer.write(chunk, 0, read);
            }
            return buffer.toString("UTF-8");
        } catch (Exception e) {
            return null;
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
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
        stopWakeLoop();
        try {
            String grammar = grammarJson;
            Recognizer recognizer = grammar != null
                    ? new Recognizer(model, SAMPLE_RATE, grammar)
                    : new Recognizer(model, SAMPLE_RATE);
            speechService = new SpeechService(recognizer, SAMPLE_RATE);
            listening = true;
            speechService.startListening(new RecognitionListener() {
                @Override
                public void onResult(String hypothesis) {
                    // Fin d'un énoncé : on récupère le texte et on arrête.
                    Log.i(TAG, "Vosk onResult brut : " + hypothesis);
                    String text = stripUnknownTokens(extractText(hypothesis, "text"));
                    if (text != null && !text.isEmpty()) {
                        finish(text, true, callback);
                    }
                }

                @Override
                public void onFinalResult(String hypothesis) {
                    Log.i(TAG, "Vosk onFinalResult brut : " + hypothesis);
                    String text = stripUnknownTokens(extractText(hypothesis, "text"));
                    finish(text == null ? "" : text, text != null && !text.isEmpty(), callback);
                }

                @Override
                public void onPartialResult(String hypothesis) {
                    // Debug uniquement : confirme que le micro capte de l'audio en direct
                    // même si le résultat final échoue ensuite.
                    Log.d(TAG, "Vosk partiel : " + hypothesis);
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
        stopWakeLoop();
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

    /** Retire les jetons "[unk]" (hors grammaire) qu'une reconnaissance
     * contrainte peut renvoyer à la place d'un mot non reconnu. */
    private static String stripUnknownTokens(String text) {
        if (text == null) {
            return null;
        }
        return text.replace("[unk]", "").replaceAll("\\s+", " ").trim();
    }

    private static boolean containsWakeTrigger(String text) {
        for (String trigger : WAKE_TRIGGERS) {
            if (text.contains(trigger)) {
                return true;
            }
        }
        return false;
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
