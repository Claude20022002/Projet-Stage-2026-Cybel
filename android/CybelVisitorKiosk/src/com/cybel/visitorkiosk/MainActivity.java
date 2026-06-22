package com.cybel.visitorkiosk;

import android.graphics.Bitmap;
import android.app.Activity;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.util.Log;
import android.view.View;
import android.view.WindowManager;
import android.webkit.ConsoleMessage;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.IOException;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.NetworkInterface;
import java.util.ArrayList;
import java.util.Enumeration;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

public class MainActivity extends Activity {

    private static final String TAG = "CybelKiosk";
    private static final int BACKEND_PORT = 8000;
    private static final String KIOSK_PATH = "/kiosk/";
    private static final String KIOSK_URL_FILE = "Download/cybel_kiosk_url.txt";
    private static final long RETRY_DELAY_MS = 5000;

    private WebView webView;
    private final List<String> urlCandidates = new ArrayList<>();
    private int urlIndex;
    private String kioskUrl = "";
    private final Handler retryHandler = new Handler();
    private boolean firstLoad = true;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        getWindow().addFlags(
                WindowManager.LayoutParams.FLAG_FULLSCREEN
                        | WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        webView = new WebView(this);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setCacheMode(WebSettings.LOAD_NO_CACHE);
        settings.setAllowFileAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);

        if (firstLoad) {
            webView.clearCache(true);
        }

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onConsoleMessage(ConsoleMessage msg) {
                Log.d(TAG, "console: " + msg.message()
                        + " @" + msg.sourceId() + ":" + msg.lineNumber());
                return true;
            }
        });

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                super.onPageStarted(view, url, favicon);
                Log.i(TAG, "onPageStarted: " + url);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                Log.i(TAG, "onPageFinished: " + url);
                retryHandler.removeCallbacksAndMessages(null);
            }

            @Override
            public void onReceivedHttpError(WebView view, WebResourceRequest request,
                                            WebResourceResponse errorResponse) {
                super.onReceivedHttpError(view, request, errorResponse);
                if (request.isForMainFrame()) {
                    String msg = "HTTP " + errorResponse.getStatusCode();
                    Log.e(TAG, "onReceivedHttpError: " + msg + " url=" + request.getUrl());
                    showErrorPage(view, msg);
                    scheduleRetry();
                }
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request,
                                        WebResourceError error) {
                super.onReceivedError(view, request, error);
                if (request.isForMainFrame()) {
                    String msg = error.getDescription() + " (code " + error.getErrorCode() + ")";
                    Log.e(TAG, "onReceivedError: " + msg + " url=" + request.getUrl());
                    showErrorPage(view, msg);
                    scheduleRetry();
                }
            }
        });

        setContentView(webView);
        refreshUrlCandidates();
        loadKiosk();
    }

    /** Reconstruit la liste d'URLs : fichier config, IP locales, loopback en dernier. */
    private void refreshUrlCandidates() {
        Set<String> seen = new LinkedHashSet<>();

        String fromFile = readKioskUrlFile();
        if (fromFile != null) {
            seen.add(fromFile);
        }

        String wlan = ipv4ForInterface("wlan0");
        if (wlan != null) {
            seen.add(kioskBaseUrl(wlan));
        }

        String eth = ipv4ForInterface("eth0");
        if (eth != null) {
            seen.add(kioskBaseUrl(eth));
        }

        seen.add(kioskBaseUrl("192.168.20.1"));
        seen.add(kioskBaseUrl("127.0.0.1"));

        urlCandidates.clear();
        urlCandidates.addAll(seen);

        if (urlIndex >= urlCandidates.size()) {
            urlIndex = 0;
        }
        kioskUrl = urlCandidates.get(urlIndex);

        Log.i(TAG, "URL candidates (" + urlCandidates.size() + "): " + urlCandidates);
    }

    private static String kioskBaseUrl(String host) {
        return "http://" + host + ":" + BACKEND_PORT + KIOSK_PATH;
    }

    private String readKioskUrlFile() {
        File config = new File(Environment.getExternalStorageDirectory(), KIOSK_URL_FILE);
        if (!config.isFile()) {
            Log.w(TAG, "Fichier absent: " + config.getAbsolutePath());
            return null;
        }
        try (BufferedReader reader = new BufferedReader(new FileReader(config))) {
            String line = reader.readLine();
            if (line != null) {
                line = line.trim();
                if (line.startsWith("http://") || line.startsWith("https://")) {
                    if (!line.endsWith("/")) {
                        line = line + "/";
                    }
                    Log.i(TAG, "URL depuis fichier: " + line);
                    return line;
                }
            }
        } catch (IOException e) {
            Log.w(TAG, "Lecture " + config.getAbsolutePath(), e);
        }
        return null;
    }

    private static String ipv4ForInterface(String ifaceName) {
        try {
            Enumeration<NetworkInterface> interfaces = NetworkInterface.getNetworkInterfaces();
            while (interfaces.hasMoreElements()) {
                NetworkInterface ni = interfaces.nextElement();
                if (!ni.getName().equals(ifaceName) || !ni.isUp()) {
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
            Log.w(TAG, "ipv4ForInterface " + ifaceName, e);
        }
        return null;
    }

    private void loadKiosk() {
        Log.i(TAG, "Chargement [" + (urlIndex + 1) + "/" + urlCandidates.size() + "] " + kioskUrl);
        webView.loadUrl(kioskUrl);
        firstLoad = false;
    }

    private void showErrorPage(WebView view, String detail) {
        StringBuilder urls = new StringBuilder();
        for (int i = 0; i < urlCandidates.size(); i++) {
            String marker = (i == urlIndex) ? " → " : "    ";
            urls.append(marker).append(urlCandidates.get(i)).append("<br/>");
        }
        String html = "<!DOCTYPE html><html><head><meta charset='utf-8'/>"
                + "<meta name='viewport' content='width=device-width,initial-scale=1'/>"
                + "<style>body{font-family:sans-serif;background:#0f172a;color:#e2e8f0;"
                + "padding:24px;font-size:16px}h1{font-size:22px}p{color:#94a3b8}"
                + ".urls{font-size:13px;line-height:1.6}</style></head><body>"
                + "<h1>CYBEL — connexion impossible</h1>"
                + "<p><b>Erreur :</b> " + escapeHtml(detail) + "</p>"
                + "<p><b>URL actuelle :</b> " + escapeHtml(kioskUrl) + "</p>"
                + "<p class='urls'><b>URLs testées :</b><br/>" + urls + "</p>"
                + "<p>Vérifiez que Termux exécute le backend "
                + "(<code>bash ~/cybel/scripts/termux/start_cybel.sh</code>)."
                + " Nouvelle tentative dans quelques secondes…</p>"
                + "</body></html>";
        view.loadDataWithBaseURL(null, html, "text/html", "UTF-8", null);
    }

    private static String escapeHtml(String text) {
        if (text == null) {
            return "";
        }
        return text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\"", "&quot;");
    }

    private void scheduleRetry() {
        retryHandler.removeCallbacksAndMessages(null);
        retryHandler.postDelayed(new Runnable() {
            @Override
            public void run() {
                urlIndex = (urlIndex + 1) % urlCandidates.size();
                refreshUrlCandidates();
                kioskUrl = urlCandidates.get(urlIndex);
                loadKiosk();
            }
        }, RETRY_DELAY_MS);
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        }
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            hideSystemUi();
        }
    }

    private void hideSystemUi() {
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                        | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
    }

    @Override
    protected void onDestroy() {
        retryHandler.removeCallbacksAndMessages(null);
        webView.destroy();
        super.onDestroy();
    }
}
