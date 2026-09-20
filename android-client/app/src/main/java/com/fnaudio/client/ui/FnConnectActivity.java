package com.fnaudio.client.ui;

import android.annotation.SuppressLint;
import android.content.Intent;
import android.os.Bundle;
import android.webkit.CookieManager;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebResourceRequest;
import android.webkit.WebViewClient;
import android.widget.Toast;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;

import com.fnaudio.client.R;
import com.fnaudio.client.data.ConnectionProfile;
import com.fnaudio.client.data.SecureProfileStore;

public final class FnConnectActivity extends AppCompatActivity {
    public static final String EXTRA_FN_ID = "fn_id";
    private WebView webView;
    private String fnId;
    private boolean handedOff;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_fn_connect);
        fnId = safeStringExtra(getIntent(), EXTRA_FN_ID);
        if (fnId == null || fnId.trim().isEmpty()) { finish(); return; }
        fnId = fnId.trim().toLowerCase(java.util.Locale.ROOT);
        if (!fnId.matches("[a-z0-9-]{3,64}")) { finish(); return; }
        configure();
        // Match the official FNOS app: resolve the FN ID first, then keep the
        // same WebView session while following the selected direct/relay route.
        webView.loadUrl("https://fnos.net/" + fnId + "/");
    }

    private static String safeStringExtra(@Nullable Intent intent, String key) {
        if (intent == null || key == null) return "";
        try {
            String value = intent.getStringExtra(key);
            return value == null ? "" : value;
        } catch (RuntimeException ignored) {
            return "";
        }
    }

    @SuppressLint({"SetJavaScriptEnabled", "JavascriptInterface"})
    private void configure() {
        webView = findViewById(R.id.fnConnectWebView);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setSupportZoom(false);
        CookieManager cookies = CookieManager.getInstance();
        cookies.setAcceptCookie(true);
        cookies.setAcceptThirdPartyCookies(webView, true);
        webView.setWebViewClient(new WebViewClient() {
            @Override public void onPageFinished(WebView view, String url) {
                if (handedOff || isFinishing() || isDestroyed()) return;
                android.net.Uri uri = android.net.Uri.parse(url);
                String host = uri.getHost() == null ? "" : uri.getHost().toLowerCase(java.util.Locale.ROOT);
                if (isAllowedFnConnectUri(uri) && uri.getPath() != null
                        && uri.getPath().startsWith("/cgi/ThirdParty/fnaudio/index.cgi")) {
                    handedOff = true;
                    cookies.flush();
                    ConnectionProfile profile = ConnectionProfile.create("", "FN Connect - " + fnId,
                            host, 443, true, false, "", "").asWebSession();
                    new SecureProfileStore(FnConnectActivity.this).upsert(profile, true);
                    Intent intent = new Intent(FnConnectActivity.this, MainActivity.class);
                    intent.putExtra(MainActivity.EXTRA_PROFILE_ID, profile.id);
                    startActivity(intent);
                    finish();
                }
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view, String url) {
                android.net.Uri uri = android.net.Uri.parse(url);
                return !isAllowedFnConnectUri(uri);
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return request == null || !isAllowedFnConnectUri(request.getUrl());
            }
            @Override public void onReceivedError(WebView view, int errorCode, String description, String failingUrl) {
                if (isFinishing() || isDestroyed()) return;
                Toast.makeText(FnConnectActivity.this, "FN Connect 加载失败：" + description, Toast.LENGTH_LONG).show();
            }
        });
    }

    private boolean isAllowedFnConnectUri(android.net.Uri uri) {
        if (uri == null || !"https".equalsIgnoreCase(uri.getScheme())) return false;
        String host = uri.getHost() == null ? "" : uri.getHost().toLowerCase(java.util.Locale.ROOT);
        return host.equals(fnId + ".fnos.net") || host.equals("fnos.net");
    }

    @Override
    protected void onDestroy() {
        handedOff = true;
        if (webView != null) {
            webView.stopLoading();
            webView.setWebViewClient(null);
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}
