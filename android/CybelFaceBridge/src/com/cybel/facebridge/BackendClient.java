package com.cybel.facebridge;

import android.util.Log;

import org.json.JSONArray;
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
 */
final class BackendClient {
    private static final String TAG = "CybelBackendClient";
    private static final String BASE_URL = "http://127.0.0.1:8000";
    private static final int TIMEOUT_MS = 2000;

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
        HttpURLConnection connection = null;
        try {
            URL url = new URL(BASE_URL + path);
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
                Log.w(TAG, path + " -> HTTP " + code);
            }
            return code;
        } catch (IOException e) {
            Log.w(TAG, path + " indisponible : " + e.getMessage());
            return null;
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

    private static JSONArray toJsonArray(float[] values) {
        JSONArray array = new JSONArray();
        for (float v : values) {
            array.put(v);
        }
        return array;
    }
}
