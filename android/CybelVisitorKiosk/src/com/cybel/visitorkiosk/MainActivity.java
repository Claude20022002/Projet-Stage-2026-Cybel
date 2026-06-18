package com.cybel.visitorkiosk;

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
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

public class MainActivity extends Activity {

    private static final String TAG = "CybelKiosk";
    private static final String DEFAULT_KIOSK_URL = "http://127.0.0.1:8000/kiosk/";
    private static final String KIOSK_URL_FILE = "Download/cybel_kiosk_url.txt";
    private static final long RETRY_DELAY_MS = 5000;

    private WebView webView;
    private final List<String> urlCandidates = new ArrayList<>();
    private int urlIndex;
    private String kioskUrl = DEFAULT_KIOSK_URL;
    private final Handler retryHandler = new Handler();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        getWindow().addFlags(
                WindowManager.LayoutParams.FLAG_FULLSCREEN
                        | WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        kioskUrl = resolveKioskUrl();
        buildUrlCandidates();
        urlIndex = 0;

        webView = new WebView(this);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setAllowFileAccess(false);

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onConsoleMessage(ConsoleMessage msg) {
                Log.d(TAG, msg.message() + " @" + msg.sourceId() + ":" + msg.lineNumber());
                return true;
            }
        });

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                retryHandler.removeCallbacksAndMessages(null);
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                super.onReceivedError(view, request, error);
                if (request.isForMainFrame()) {
                    showErrorPage(view, error.getDescription().toString());
                    scheduleRetry();
                }
            }
        });

        setContentView(webView);
        loadKiosk();
    }

    private String resolveKioskUrl() {
        File config = new File(Environment.getExternalStorageDirectory(), KIOSK_URL_FILE);
        if (!config.isFile()) {
            return DEFAULT_KIOSK_URL;
        }
        try (BufferedReader reader = new BufferedReader(new FileReader(config))) {
            String line = reader.readLine();
            if (line != null) {
                line = line.trim();
                if (line.startsWith("http://") || line.startsWith("https://")) {
                    Log.i(TAG, "URL kiosk depuis " + config.getAbsolutePath() + " : " + line);
                    return line.endsWith("/") ? line : line + "/";
                }
            }
        } catch (IOException e) {
            Log.w(TAG, "Lecture " + config.getAbsolutePath() + " impossible", e);
        }
        return DEFAULT_KIOSK_URL;
    }

    private void buildUrlCandidates() {
        Set<String> seen = new LinkedHashSet<>();
        seen.add(kioskUrl);
        seen.add(DEFAULT_KIOSK_URL);
        seen.add("http://192.168.20.1:8000/kiosk/");
        urlCandidates.clear();
        urlCandidates.addAll(seen);
    }

    private void loadKiosk() {
        Log.i(TAG, "Chargement " + kioskUrl);
        webView.loadUrl(kioskUrl);
    }

    private void showErrorPage(WebView view, String detail) {
        String html = "<!DOCTYPE html><html><head><meta charset='utf-8'/>"
                + "<meta name='viewport' content='width=device-width,initial-scale=1'/>"
                + "<style>body{font-family:sans-serif;background:#0f172a;color:#e2e8f0;"
                + "padding:24px}h1{font-size:22px}p{color:#94a3b8}</style></head><body>"
                + "<h1>CYBEL — connexion impossible</h1>"
                + "<p>" + escapeHtml(detail) + "</p>"
                + "<p>URL : " + escapeHtml(kioskUrl) + "</p>"
                + "<p>Nouvelle tentative dans quelques secondes…</p>"
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
