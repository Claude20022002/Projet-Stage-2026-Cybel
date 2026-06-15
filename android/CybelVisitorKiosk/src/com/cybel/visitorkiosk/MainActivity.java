package com.cybel.visitorkiosk;

import android.app.Activity;
import android.os.Bundle;
import android.os.Handler;
import android.view.View;
import android.view.WindowManager;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public class MainActivity extends Activity {

    // Adresse du backend CYBEL (servant /kiosk/) joignable depuis le
    // reseau Wi-Fi du robot. A adapter avant de lancer build.sh :
    // remplacer par l'IP du PC qui execute `python scripts/dev.py`
    // sur le reseau Wi-Fi du robot (voir docs/VISITOR_KIOSK.md).
    private static final String KIOSK_URL = "http://192.168.1.100:8000/kiosk/";

    private static final long RETRY_DELAY_MS = 5000;

    private WebView webView;
    private final Handler retryHandler = new Handler();

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
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);

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
                    scheduleRetry();
                }
            }
        });

        setContentView(webView);
        webView.loadUrl(KIOSK_URL);
    }

    private void scheduleRetry() {
        retryHandler.removeCallbacksAndMessages(null);
        retryHandler.postDelayed(new Runnable() {
            @Override
            public void run() {
                webView.loadUrl(KIOSK_URL);
            }
        }, RETRY_DELAY_MS);
    }

    @Override
    public void onBackPressed() {
        // Mode kiosque : les visiteurs ne quittent pas l'application.
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
