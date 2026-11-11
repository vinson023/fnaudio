package com.fnaudio.client.ui;

import android.annotation.SuppressLint;
import android.app.AlertDialog;
import android.content.Intent;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.SslErrorHandler;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;

import com.fnaudio.client.R;
import com.fnaudio.client.data.ConnectionProfile;
import com.fnaudio.client.data.SecureProfileStore;

/**
 * Signs in through fnOS's own web page instead of re-implementing the handshake.
 *
 * <p>This exists because the native path kept losing to details that only the
 * official page gets right: the certificate situation (the NAS may serve a
 * public-CA certificate for {@code <fnid>.fnos.net} and the built-in
 * {@code CN=fnOS} self-signed one for anything else), the access-code challenge,
 * forced HTTPS, and which of the device's addresses is actually reachable from
 * the current network. A WebView lets fnOS answer all of that itself — the user
 * sees the real fnOS login form, and we only wait for the session cookie.
 *
 * <p>What we do not do: type credentials ourselves, talk to {@code /access_code_verify},
 * or resolve FN Connect addresses. Everything up to "the browser has a session"
 * is the official page's job.
 */
public final class WebLoginActivity extends AppCompatActivity {

    private static final String TAG = "WebLogin";
    public static final String EXTRA_START_URL = "start_url";

    /** fnOS sets one of these once a real session exists; the access code is not one of them. */
    private static final String[] SESSION_COOKIES = {
            "trim_token", "fnos-token", "fnaudio_trim_token", "token"
    };

    private static final long POLL_INTERVAL_MS = 700L;
    private static final long GIVE_UP_AFTER_MS = 6L * 60L * 1000L;

    /** A host whose certificate the user already chose to accept in this session. */
    private String allowedCertificateHost = "";

    private WebView webView;
    private ProgressBar progress;
    private TextView title;
    private TextView hint;
    private final Handler handler = new Handler(Looper.getMainLooper());

    private String startUrl = "";
    private boolean finishing;
    private long startedAt;

    private final Runnable cookieProbe = new Runnable() {
        @Override
        public void run() {
            if (finishing) return;
            if (System.currentTimeMillis() - startedAt > GIVE_UP_AFTER_MS) {
                Toast.makeText(WebLoginActivity.this, "登录超时，请重试", Toast.LENGTH_LONG).show();
                finish();
                return;
            }
            try {
                Uri current = Uri.parse(String.valueOf(webView.getUrl()));
                String host = current.getHost();
                if (host != null && !host.isEmpty()) {
                    String cookies = CookieManager.getInstance().getCookie(currentOrigin(current));
                    String token = sessionToken(cookies);
                    if (!token.isEmpty()) {
                        complete(current, token);
                        return;
                    }
                }
            } catch (RuntimeException error) {
                Log.w(TAG, "cookie probe failed", error);
            }
            handler.postDelayed(this, POLL_INTERVAL_MS);
        }
    };

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_web_login);
        webView = findViewById(R.id.webLoginWebView);
        progress = findViewById(R.id.webLoginProgress);
        title = findViewById(R.id.webLoginTitle);
        hint = findViewById(R.id.webLoginHint);
        findViewById(R.id.webLoginCancel).setOnClickListener(view -> finish());

        startUrl = getIntent() == null ? "" : String.valueOf(getIntent().getStringExtra(EXTRA_START_URL));
        if (startUrl.isEmpty()) {
            finish();
            return;
        }
        configureWebView();
        startedAt = System.currentTimeMillis();
        webView.loadUrl(startUrl);
        handler.postDelayed(cookieProbe, POLL_INTERVAL_MS);
    }

    @SuppressLint({"SetJavaScriptEnabled"})
    private void configureWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        // fnOS serves a self-signed certificate for every host name it has no
        // certificate file for, so strict blocking here would make the official
        // login page unreachable on exactly the setups this screen exists for.
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);
        // The page carries its own session; nothing may be attached to it from here.
        settings.setSaveFormData(false);
        settings.setSavePassword(false);
        settings.setUserAgentString(settings.getUserAgentString() + " fnAudio-Android/" + com.fnaudio.client.BuildConfig.VERSION_NAME);

        CookieManager cookies = CookieManager.getInstance();
        cookies.setAcceptCookie(true);

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                if (progress == null) return;
                progress.setProgress(newProgress);
                progress.setVisibility(newProgress >= 100 ? View.INVISIBLE : View.VISIBLE);
            }
        });

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
                Uri uri = Uri.parse(String.valueOf(url));
                if (title != null && uri.getHost() != null) title.setText(uri.getHost());
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                CookieManager.getInstance().flush();
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                // Stay inside the WebView for anything web; hand the rest to the OS.
                return !("http".equalsIgnoreCase(uri.getScheme()) || "https".equalsIgnoreCase(uri.getScheme()));
            }

            @Override
            public void onReceivedSslError(WebView view, SslErrorHandler sslHandler, SslError error) {
                // The fnOS page is reached over whatever certificate this NAS
                // happens to serve. Ask once per host, remember the answer, and
                // never silently proceed.
                String host = error == null ? "" : hostOf(error.getUrl());
                if (!host.isEmpty() && host.equalsIgnoreCase(allowedCertificateHost)) {
                    sslHandler.proceed();
                    return;
                }
                String message = host.isEmpty()
                        ? "这台设备的 HTTPS 证书无法验证。继续登录会让连接失去证书保护。"
                        : "这台设备（" + host + "）的 HTTPS 证书无法验证，通常是自签名证书或域名与证书不匹配。\n\n"
                        + "如果这是你自己的 NAS，可以选择「继续」。";
                new AlertDialog.Builder(WebLoginActivity.this)
                        .setTitle("证书无法验证")
                        .setMessage(message)
                        .setPositiveButton("继续", (dialog, which) -> {
                            allowedCertificateHost = host;
                            sslHandler.proceed();
                        })
                        .setNegativeButton("取消", (dialog, which) -> {
                            sslHandler.cancel();
                            Toast.makeText(WebLoginActivity.this,
                                    "已取消：证书未通过验证，登录页面无法加载", Toast.LENGTH_LONG).show();
                        })
                        .setCancelable(false)
                        .show();
            }
        });
    }

    private static String hostOf(String url) {
        try {
            String host = Uri.parse(String.valueOf(url)).getHost();
            return host == null ? "" : host;
        } catch (RuntimeException error) {
            return "";
        }
    }

    private static String currentOrigin(Uri uri) {
        String scheme = uri.getScheme() == null ? "https" : uri.getScheme();
        String host = uri.getHost() == null ? "" : uri.getHost();
        int port = uri.getPort();
        return scheme + "://" + host + (port > 0 ? ":" + port : "");
    }

    /**
     * First value of the session cookies fnOS uses, or empty.
     *
     * <p>{@code os-access-code} is deliberately not in the list: it is issued
     * before anyone signs in, so treating it as a session would close this screen
     * on the challenge page with no account behind it.
     */
    private static String sessionToken(@Nullable String cookies) {
        if (cookies == null || cookies.isEmpty()) return "";
        for (String pair : cookies.split(";")) {
            String value = pair.trim();
            for (String name : SESSION_COOKIES) {
                String prefix = name + "=";
                if (!value.startsWith(prefix)) continue;
                String token = value.substring(prefix.length()).trim();
                if (!token.isEmpty()) return token;
            }
        }
        return "";
    }

    private void complete(Uri uri, String token) {
        if (finishing) return;
        finishing = true;
        handler.removeCallbacks(cookieProbe);
        try { CookieManager.getInstance().flush(); } catch (RuntimeException ignored) { }

        String host = uri.getHost() == null ? "" : uri.getHost();
        int port = uri.getPort() > 0 ? uri.getPort() : 443;
        boolean https = !"http".equalsIgnoreCase(String.valueOf(uri.getScheme()));
        if (host.isEmpty()) {
            Toast.makeText(this, "登录成功但取不到设备地址，请重试", Toast.LENGTH_LONG).show();
            finish();
            return;
        }

        String id = "web:" + host + ":" + port;
        ConnectionProfile profile = ConnectionProfile.create(
                id, "网页登录 - " + host, host, port, https, false, "", "")
                .withTokens(token, "")
                .asWebSession();

        try {
            new SecureProfileStore(this).upsert(profile, true);
        } catch (RuntimeException error) {
            // Losing the record costs one extra sign-in; crashing here would
            // cost the session that was just established.
            Log.e(TAG, "could not persist the web session profile", error);
        }

        Toast.makeText(this, "登录成功", Toast.LENGTH_SHORT).show();
        Intent intent = new Intent(this, MainActivity.class);
        intent.putExtra(MainActivity.EXTRA_PROFILE_ID, profile.id);
        startActivity(intent);
        finish();
    }

    @Override
    protected void onDestroy() {
        finishing = true;
        handler.removeCallbacks(cookieProbe);
        if (webView != null) {
            try {
                webView.stopLoading();
                webView.setWebChromeClient(null);
                webView.setWebViewClient(null);
                webView.destroy();
            } catch (RuntimeException ignored) { }
            webView = null;
        }
        super.onDestroy();
    }
}
