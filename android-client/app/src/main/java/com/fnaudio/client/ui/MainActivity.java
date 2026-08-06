package com.fnaudio.client.ui;

import android.Manifest;
import android.annotation.SuppressLint;
import android.content.ComponentName;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.SslErrorHandler;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.ProgressBar;
import android.widget.TextView;

import androidx.activity.OnBackPressedCallback;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.annotation.OptIn;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import androidx.media3.common.C;
import androidx.media3.common.MediaItem;
import androidx.media3.common.Player;
import androidx.media3.common.util.UnstableApi;
import androidx.media3.session.MediaController;
import androidx.media3.session.SessionToken;

import com.fnaudio.client.BuildConfig;
import com.fnaudio.client.R;
import com.fnaudio.client.data.ConnectionProfile;
import com.fnaudio.client.data.SecureProfileStore;
import com.fnaudio.client.playback.PlaybackRuntimeConfig;
import com.fnaudio.client.playback.PlaybackService;
import com.fnaudio.client.web.NativePlaybackBridge;
import com.google.common.util.concurrent.ListenableFuture;

import org.json.JSONObject;
import org.json.JSONArray;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ExecutionException;

@OptIn(markerClass = UnstableApi.class)
public final class MainActivity extends AppCompatActivity implements NativePlaybackBridge.ControllerProvider {
    public static final String EXTRA_PROFILE_ID = "profile_id";

    private WebView webView;
    private ProgressBar pageProgress;
    private View errorPanel;
    private TextView errorMessage;
    private ConnectionProfile profile;
    private ListenableFuture<MediaController> controllerFuture;
    private MediaController mediaController;
    private final Handler uiHandler = new Handler(Looper.getMainLooper());
    private boolean pageLoaded;

    private final Runnable playbackStateTicker = new Runnable() {
        @Override
        public void run() {
            pushPlaybackStateToWeb();
            uiHandler.postDelayed(this, 500);
        }
    };

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_NOTHING);
        setContentView(R.layout.activity_main);

        profile = resolveProfile();
        if (profile == null || profile.token.isEmpty()) {
            openConnectionChooser();
            return;
        }

        boolean switchingServer = PlaybackRuntimeConfig.activate(profile);
        if (switchingServer) stopService(new Intent(this, PlaybackService.class));
        new SecureProfileStore(this).setActive(profile.id);

        bindViews();
        configureWebView();
        connectMediaController();
        requestNotificationPermission();
        installBackHandler();
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        recreate();
    }

    private void bindViews() {
        webView = findViewById(R.id.webView);
        pageProgress = findViewById(R.id.pageProgress);
        errorPanel = findViewById(R.id.errorPanel);
        errorMessage = findViewById(R.id.errorMessage);
        findViewById(R.id.retryButton).setOnClickListener(view -> loadFnAudio());
        findViewById(R.id.switchConnectionButton).setOnClickListener(view -> openConnectionChooser());
    }

    @SuppressLint({"SetJavaScriptEnabled", "JavascriptInterface"})
    private void configureWebView() {
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setSupportZoom(false);
        settings.setUserAgentString(settings.getUserAgentString() + " fnAudio-Android/" + BuildConfig.VERSION_NAME);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) settings.setSafeBrowsingEnabled(true);

        CookieManager cookies = CookieManager.getInstance();
        cookies.setAcceptCookie(true);
        cookies.setAcceptThirdPartyCookies(webView, false);
        installSessionCookies(cookies);

        webView.addJavascriptInterface(new NativePlaybackBridge(this), "FnAudioNative");
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                pageProgress.setProgress(newProgress);
                pageProgress.setVisibility(newProgress >= 100 ? View.GONE : View.VISIBLE);
            }
        });
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                pageProgress.setVisibility(View.VISIBLE);
                errorPanel.setVisibility(View.GONE);
                webView.setVisibility(View.VISIBLE);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                pageLoaded = true;
                pageProgress.setVisibility(View.GONE);
                injectNativeEnvironment();
                String path = Uri.parse(url).getPath();
                if (path != null && !path.contains("/cgi/ThirdParty/fnaudio/index.cgi")) {
                    showError("fnOS 没有接受当前会话，页面被转到了系统入口。请返回连接页重新登录。 ");
                }
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (sameServer(uri)) return false;
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, uri));
                } catch (Exception ignored) {
                }
                return true;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) showError("页面加载失败：" + error.getDescription());
            }

            @Override
            public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse errorResponse) {
                if (!request.isForMainFrame()) return;
                int status = errorResponse.getStatusCode();
                if (status == 401 || status == 403) showError("登录会话无效或没有 fnAudio 访问权限（HTTP " + status + "）。");
                else if (status >= 500) showError("fnAudio 服务暂时不可用（HTTP " + status + "）。");
            }

            @Override
            public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
                if (profile.https && profile.trustSelfSigned && error.getUrl() != null
                        && profile.host.equalsIgnoreCase(Uri.parse(error.getUrl()).getHost())) {
                    handler.proceed();
                } else {
                    handler.cancel();
                    showError("HTTPS 证书校验失败。请检查证书，或仅对可信 NAS 开启自签名证书兼容。");
                }
            }
        });
    }

    private void installSessionCookies(CookieManager cookies) {
        String encoded = encodeCookie(profile.token);
        String flags = "; Path=/; SameSite=Lax" + (profile.https ? "; Secure" : "");
        for (String name : new String[]{"fnaudio_trim_token", "trim_token", "token"}) {
            cookies.setCookie(profile.httpOrigin(), name + "=" + encoded + flags);
        }
        cookies.flush();
    }

    private void loadFnAudio() {
        if (webView == null) return;
        pageLoaded = false;
        errorPanel.setVisibility(View.GONE);
        webView.setVisibility(View.VISIBLE);
        Map<String, String> headers = new LinkedHashMap<>();
        headers.put("Authorization", "Bearer " + profile.token);
        headers.put("X-Fnaudio-Trim-Token", profile.token);
        webView.loadUrl(profile.fnAudioUrl(), headers);
    }

    private void connectMediaController() {
        SessionToken token = new SessionToken(this, new ComponentName(this, PlaybackService.class));
        controllerFuture = new MediaController.Builder(this, token).buildAsync();
        controllerFuture.addListener(() -> {
            try {
                mediaController = controllerFuture.get();
                mediaController.addListener(new Player.Listener() {
                    @Override
                    public void onEvents(@NonNull Player player, @NonNull Player.Events events) {
                        pushPlaybackStateToWeb();
                    }

                    @Override
                    public void onMediaItemTransition(@Nullable MediaItem mediaItem, int reason) {
                        pushPlaybackStateToWeb();
                    }
                });
                pushPlaybackStateToWeb();
                if (webView != null && webView.getUrl() == null) loadFnAudio();
            } catch (ExecutionException | InterruptedException exception) {
                if (exception instanceof InterruptedException) Thread.currentThread().interrupt();
                showError("原生播放服务启动失败：" + String.valueOf(exception.getCause() == null ? exception.getMessage() : exception.getCause().getMessage()));
            }
        }, ContextCompat.getMainExecutor(this));
    }

    private void injectNativeEnvironment() {
        if (webView == null) return;
        webView.evaluateJavascript(
                "document.documentElement.classList.add('fnaudio-android-client');" +
                        "window.dispatchEvent(new CustomEvent('fnaudio-native-ready'));",
                null
        );
        pushPlaybackStateToWeb();
    }

    private void pushPlaybackStateToWeb() {
        if (!pageLoaded || webView == null || mediaController == null) return;
        JSONObject state = new JSONObject();
        try {
            MediaItem item = mediaController.getCurrentMediaItem();
            long duration = mediaController.getDuration();
            state.put("available", true);
            state.put("mediaId", item == null ? "" : item.mediaId);
            state.put("index", mediaController.getCurrentMediaItemIndex());
            JSONArray queueIds = new JSONArray();
            for (int i = 0; i < mediaController.getMediaItemCount(); i++) {
                queueIds.put(mediaController.getMediaItemAt(i).mediaId);
            }
            state.put("queueIds", queueIds);
            state.put("position", Math.max(0L, mediaController.getCurrentPosition()) / 1000d);
            state.put("duration", duration == C.TIME_UNSET ? 0d : Math.max(0L, duration) / 1000d);
            state.put("buffered", Math.max(0L, mediaController.getBufferedPosition()) / 1000d);
            state.put("playing", mediaController.isPlaying());
            state.put("playWhenReady", mediaController.getPlayWhenReady());
            state.put("playbackState", mediaController.getPlaybackState());
            state.put("repeatMode", mediaController.getRepeatMode());
            state.put("shuffle", mediaController.getShuffleModeEnabled());
        } catch (Exception ignored) {
            return;
        }
        String script = "window.fnAudioNativeOnState && window.fnAudioNativeOnState(" + JSONObject.quote(state.toString()) + ");";
        webView.post(() -> webView.evaluateJavascript(script, null));
    }

    private boolean sameServer(Uri uri) {
        if (uri == null || uri.getHost() == null) return false;
        if (!profile.host.equalsIgnoreCase(uri.getHost())) return false;
        int uriPort = uri.getPort();
        return uriPort < 0 || uriPort == profile.port;
    }

    private void showError(String message) {
        if (isFinishing() || errorPanel == null) return;
        runOnUiThread(() -> {
            errorMessage.setText(message);
            errorPanel.setVisibility(View.VISIBLE);
            webView.setVisibility(View.GONE);
            pageProgress.setVisibility(View.GONE);
        });
    }

    private ConnectionProfile resolveProfile() {
        SecureProfileStore store = new SecureProfileStore(this);
        String id = getIntent().getStringExtra(EXTRA_PROFILE_ID);
        ConnectionProfile selected = id == null ? null : store.find(id);
        return selected == null ? store.active() : selected;
    }

    private void openConnectionChooser() {
        Intent intent = new Intent(this, LoginActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        startActivity(intent);
        finish();
    }

    private void installBackHandler() {
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                if (webView != null && webView.canGoBack()) webView.goBack();
                else finish();
            }
        });
    }

    private void requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33 && ActivityCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.POST_NOTIFICATIONS}, 301);
        }
    }

    private static String encodeCookie(String value) {
        try {
            return URLEncoder.encode(value, "UTF-8");
        } catch (Exception ignored) {
            return value;
        }
    }

    @Nullable
    @Override
    public MediaController controller() {
        return mediaController;
    }

    @Override
    protected void onResume() {
        super.onResume();
        uiHandler.removeCallbacks(playbackStateTicker);
        uiHandler.post(playbackStateTicker);
    }

    @Override
    protected void onPause() {
        uiHandler.removeCallbacks(playbackStateTicker);
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        uiHandler.removeCallbacks(playbackStateTicker);
        if (controllerFuture != null) {
            MediaController.releaseFuture(controllerFuture);
            controllerFuture = null;
        }
        mediaController = null;
        if (webView != null) {
            webView.removeJavascriptInterface("FnAudioNative");
            webView.stopLoading();
            webView.setWebChromeClient(null);
            webView.setWebViewClient(null);
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}
