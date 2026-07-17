package com.cybel.facebridge;

import android.util.Log;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * HttpURLConnection brut (pas d'OkHttp/Retrofit, cohérent avec le reste du projet —
 * voir BackendStarter dans CybelVisitorKiosk). Cible toujours 127.0.0.1 : ce bridge et
 * le backend Termux tournent sur la même tablette physique, contrairement au kiosque
 * WebView qui doit découvrir l'IP Wi-Fi.
 *
 * Le port est auto-adaptatif : le kiosque de test tourne sur 8001, le kiosque de
 * production sur 8000. On essaie les candidats dans l'ordre et on mémorise le premier
 * qui répond, pour ne pas tester les deux à chaque requête.
 */
final class BackendClient {
    private static final String TAG = "CybelBackendClient";
    private static final int[] CANDIDATE_PORTS = {8001, 8000};
    private static final int TIMEOUT_MS = 2000;

    /** Port retenu après la première réponse valide (0 = pas encore déterminé). */
    private volatile int learnedPort = 0;

    /** Envoie l'embedding pour identification. Échec silencieux : le prochain cycle réessaiera. */
    void identify(float[] embedding, float confidence) {
        JSONObject body = new JSONObject();
        try {
            body.put("embedding", toJsonArray(embedding));
            body.put("confidence", confidence);
        } catch (Exception e) {
            Log.e(TAG, "JSON identify invalide", e);
            return;
        }
        post("/api/visitors/identify", body);
    }

    boolean enroll(String name, String civility, float[] embedding) {
        JSONObject body = new JSONObject();
        try {
            body.put("name", name);
            body.put("civility", civility == null ? "" : civility);
            body.put("embedding", toJsonArray(embedding));
            body.put("consent", true);
        } catch (Exception e) {
            Log.e(TAG, "JSON enroll invalide", e);
            return false;
        }
        Integer code = post("/api/visitors/enroll", body);
        return code != null && code >= 200 && code < 300;
    }

    private Integer post(String path, JSONObject body) {
        // Port déjà appris : on l'utilise directement. Sinon on essaie les candidats.
        if (learnedPort != 0) {
            return postTo(learnedPort, path, body);
        }
        for (int port : CANDIDATE_PORTS) {
            Integer code = postTo(port, path, body);
            if (code != null) {
                learnedPort = port;
                Log.i(TAG, "Backend détecté sur le port " + port);
                return code;
            }
        }
        return null;
    }

    private Integer postTo(int port, String path, JSONObject body) {
        HttpURLConnection connection = null;
        try {
            URL url = new URL("http://127.0.0.1:" + port + path);
            connection = (HttpURLConnection) url.openConnection();
            connection.setRequestMethod("POST");
            connection.setDoOutput(true);
            connection.setConnectTimeout(TIMEOUT_MS);
            connection.setReadTimeout(TIMEOUT_MS);
            connection.setRequestProperty("Content-Type", "application/json");
            try (OutputStream out = connection.getOutputStream()) {
                out.write(body.toString().getBytes(StandardCharsets.UTF_8));
            }
            int code = connection.getResponseCode();
            if (code >= 400) {
                Log.w(TAG, path + " (:" + port + ") -> HTTP " + code);
            }
            return code;
        } catch (IOException e) {
            Log.w(TAG, path + " (:" + port + ") indisponible : " + e.getMessage());
            return null;
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

    private static JSONArray toJsonArray(float[] values) throws JSONException {
        JSONArray array = new JSONArray();
        for (float v : values) {
            array.put(v);
        }
        return array;
    }
}
