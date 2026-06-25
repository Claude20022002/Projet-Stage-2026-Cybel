package com.cybel.visitorkiosk.test;

import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.NetworkInterface;
import java.net.URL;
import java.util.Enumeration;

/**
 * Démarre le backend CYBEL test (port 8001, ~/cybel-test) dans Termux.
 */
public final class BackendStarter {

    private static final String TAG = "CybelBackendTest";
    private static final String TERMUX_BASH = "/data/data/com.termux/files/usr/bin/bash";
    private static final String START_CMD =
            "CYBEL_HOME=/data/data/com.termux/files/home/cybel-test "
                    + "bash /data/data/com.termux/files/home/cybel-test/scripts/termux/ensure_cybel_backend_test.sh";
    static final int BACKEND_PORT = 8001;
    private static final int MAX_WAIT_MS = 50000;
    private static final int POLL_MS = 1500;

    public interface Callback {
        void onReady();

        void onFailed(String message);
    }

    private BackendStarter() {
    }

    public static void ensureRunning(final Context context, final Callback callback) {
        new Thread(new Runnable() {
            @Override
            public void run() {
                if (isBackendHealthy("127.0.0.1") || isBackendHealthy(getWlanIp())) {
                    Log.i(TAG, "Backend test déjà actif");
                    postReady(callback);
                    return;
                }

                Log.i(TAG, "Lancement backend CYBEL test via Termux…");
                boolean launched = tryTermuxRunCommand(context) || trySuTermuxBash();
                if (!launched) {
                    postFailed(callback,
                            "Impossible de lancer Termux — déployez ~/cybel-test (deploy_termux.py --target test).");
                    return;
                }

                long deadline = System.currentTimeMillis() + MAX_WAIT_MS;
                while (System.currentTimeMillis() < deadline) {
                    String wlan = getWlanIp();
                    if (isBackendHealthy("127.0.0.1") || (wlan != null && isBackendHealthy(wlan))) {
                        postReady(callback);
                        return;
                    }
                    try {
                        Thread.sleep(POLL_MS);
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                        break;
                    }
                }
                postFailed(callback,
                        "Le backend test ne répond pas — voir ~/cybel-test-uvicorn.log");
            }
        }, "CybelBackendTestStart").start();
    }

    private static boolean tryTermuxRunCommand(Context context) {
        try {
            Intent intent = new Intent();
            intent.setComponent(new ComponentName("com.termux", "com.termux.app.RunCommandService"));
            intent.setAction("com.termux.RUN_COMMAND");
            intent.putExtra("com.termux.RUN_COMMAND_PATH", TERMUX_BASH);
            intent.putExtra("com.termux.RUN_COMMAND_ARGUMENTS", new String[]{"-c", START_CMD});
            intent.putExtra("com.termux.RUN_COMMAND_WORKDIR", "/data/data/com.termux/files/home");
            intent.putExtra("com.termux.RUN_COMMAND_BACKGROUND", true);
            context.startService(intent);
            Log.i(TAG, "Intent Termux RUN_COMMAND envoyé");
            return true;
        } catch (Exception e) {
            Log.w(TAG, "Termux RUN_COMMAND indisponible", e);
            return false;
        }
    }

    private static boolean trySuTermuxBash() {
        String[] commands = new String[]{
                "su",
                "-c",
                TERMUX_BASH + " -lc '" + START_CMD + " >> ~/cybel-test-app-start.log 2>&1 &'"
        };
        try {
            Process process = Runtime.getRuntime().exec(commands);
            BufferedReader reader = new BufferedReader(new InputStreamReader(process.getErrorStream()));
            String line;
            while ((line = reader.readLine()) != null) {
                Log.d(TAG, "su: " + line);
            }
            Log.i(TAG, "Démarrage via su lancé");
            return true;
        } catch (Exception e) {
            Log.w(TAG, "su bash échoué", e);
            return false;
        }
    }

    static boolean isBackendHealthy(String host) {
        if (host == null || host.isEmpty()) {
            return false;
        }
        HttpURLConnection connection = null;
        try {
            URL url = new URL("http://" + host + ":" + BACKEND_PORT + "/api/health");
            connection = (HttpURLConnection) url.openConnection();
            connection.setConnectTimeout(2000);
            connection.setReadTimeout(2000);
            connection.setRequestMethod("GET");
            int code = connection.getResponseCode();
            return code >= 200 && code < 300;
        } catch (Exception e) {
            return false;
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

    static String getWlanIp() {
        try {
            Enumeration<NetworkInterface> interfaces = NetworkInterface.getNetworkInterfaces();
            while (interfaces.hasMoreElements()) {
                NetworkInterface ni = interfaces.nextElement();
                if (!"wlan0".equals(ni.getName()) || !ni.isUp()) {
                    continue;
                }
                Enumeration<InetAddress> addrs = ni.getInetAddresses();
                while (addrs.hasMoreElements()) {
                    InetAddress addr = addrs.nextElement();
                    if (addr instanceof Inet4Address && !addr.isLoopbackAddress()) {
                        return addr.getHostAddress();
                    }
                }
            }
        } catch (Exception e) {
            Log.w(TAG, "getWlanIp", e);
        }
        return null;
    }

    private static void postReady(final Callback callback) {
        new Handler(Looper.getMainLooper()).post(new Runnable() {
            @Override
            public void run() {
                callback.onReady();
            }
        });
    }

    private static void postFailed(final Callback callback, final String message) {
        new Handler(Looper.getMainLooper()).post(new Runnable() {
            @Override
            public void run() {
                callback.onFailed(message);
            }
        });
    }
}
