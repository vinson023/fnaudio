package com.fnaudio.client.ui;

import android.Manifest;
import android.app.AlertDialog;
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
import android.os.SystemClock;
import android.util.Log;
import android.view.View;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.JsResult;
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
import android.widget.Toast;

import androidx.activity.OnBackPressedCallback;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.annotation.OptIn;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import androidx.core.view.WindowCompat;
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
import com.fnaudio.client.network.HttpClientFactory;
import com.fnaudio.client.network.FnOsAuthClient;
import com.fnaudio.client.network.FnConnectResolver;
import com.fnaudio.client.network.FnConnectSettings;
import com.fnaudio.client.network.CertificatePin;
import com.fnaudio.client.playback.PlaybackRuntimeConfig;
import com.fnaudio.client.playback.PlaybackService;
import com.fnaudio.client.web.NativePlaybackBridge;
import com.google.common.util.concurrent.ListenableFuture;

import org.json.JSONObject;
import org.json.JSONArray;

import java.io.ByteArrayInputStream;
import java.io.FilterInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;
import com.fnaudio.client.network.SessionCookies;
import java.net.URLConnection;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Iterator;
import java.util.ArrayDeque;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.RejectedExecutionException;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.ExecutionException;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import okhttp3.Headers;
import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;
import okhttp3.ResponseBody;

@OptIn(markerClass = UnstableApi.class)
public final class MainActivity extends AppCompatActivity implements NativePlaybackBridge.ControllerProvider, NativePlaybackBridge.HttpRequestHandler {
    public static final String EXTRA_PROFILE_ID = "profile_id";
    public static final String ACTION_OPEN_PLAYBACK = "com.fnaudio.client.action.OPEN_PLAYBACK";
    private static final long ROOT_BACK_CONFIRM_WINDOW_MS = 2200L;
    private static final int MAX_COVER_BYTES = 1024 * 1024;
    private static final int MAX_NATIVE_HTTP_RESPONSE_BYTES = 512 * 1024;
    private static final int MAX_NATIVE_HTTP_HEADERS_BYTES = 64 * 1024;
    private static final int MAX_NATIVE_HTTP_REQUEST_BODY_BYTES = 512 * 1024;
    private static final int MAX_NATIVE_HTTP_SERIALIZED_RESPONSE_CHARS = 4 * 1024 * 1024;
    private static final int MAX_NATIVE_HTTP_RESPONSE_CHUNKS = 256;
    private static final int MAX_NATIVE_HTTP_RESPONSE_HEADER_COUNT = 128;
    private static final int MAX_NATIVE_HTTP_RESPONSE_HEADER_VALUE_CHARS = 4096;
    private static final int MAX_NATIVE_HTTP_RESPONSE_HEADERS_BYTES = 64 * 1024;
    private static final int MAX_NATIVE_HTTP_CALLS = 32;
    private static final int MAX_NATIVE_HTTP_REQUEST_ID_CHARS = 256;
    private static final int MAX_PENDING_CONTROLLER_COMMANDS = 64;
    private static final int MAX_BUNDLED_TEXT_BYTES = 4 * 1024 * 1024;
    private static final int MAX_BUNDLED_ASSET_BYTES = 8 * 1024 * 1024;

    private WebView webView;
    private ProgressBar pageProgress;
    private View errorPanel;
    private TextView errorMessage;
    private ConnectionProfile profile;
    private OkHttpClient webResourceClient;
    private final ConcurrentHashMap<String, Call> nativeHttpCalls = new ConcurrentHashMap<>();
    private AuthenticatedCoverCache coverCache;
    private FnConnectResolver fnConnectResolver;
    private final FnOsAuthClient authClient = new FnOsAuthClient();
    private ListenableFuture<MediaController> controllerFuture;
    private MediaController mediaController;
    private final ArrayDeque<NativePlaybackBridge.ControllerCommand> pendingControllerCommands = new ArrayDeque<>();
    private final Handler uiHandler = new Handler(Looper.getMainLooper());
    private boolean pageLoaded;
    private volatile boolean sessionCookiesReady;
    private boolean webBackDispatchInFlight;
    private long rootBackConfirmUntil;
    private volatile boolean destroyed;

    private final Runnable playbackStateTicker = new Runnable() {
        @Override
        public void run() {
            if (destroyed) return;
            pushPlaybackStateToWeb();
            if (destroyed) return;
            uiHandler.postDelayed(this, 500);
        }
    };

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        destroyed = false;
        configureSystemBars();
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_NOTHING);
        setContentView(R.layout.activity_main);
        WindowInsetsHelper.applySafePadding(findViewById(R.id.mainRoot));

        profile = resolveProfile();
        bindViews();
        coverCache = new AuthenticatedCoverCache(this);
        installBackHandler();
        if (profile == null || (!profile.webSession && profile.token.isEmpty() && profile.longToken.isEmpty() && profile.password.isEmpty())) {
            openConnectionChooser();
            return;
        }
        pageProgress.setVisibility(View.VISIBLE);
        if (profile.webSession) {
            boolean switchingServer = PlaybackRuntimeConfig.activate(profile);
            if (switchingServer) stopService(new Intent(this, PlaybackService.class));
            configureWebView();
            connectMediaController();
            requestNotificationPermission();
            return;
        }
        restoreFnConnectRelayThenAuthenticate(profile);
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        // A notification tap should only bring the existing WebView task to
        // the foreground. Recreating here reloads its current fnAudio page.
        if (ACTION_OPEN_PLAYBACK.equals(intent.getAction())) return;
        setIntent(intent);
        recreate();
    }

    private void bindViews() {
        webView = findViewById(R.id.webView);
        pageProgress = findViewById(R.id.pageProgress);
        errorPanel = findViewById(R.id.errorPanel);
        errorMessage = findViewById(R.id.errorMessage);
        findViewById(R.id.retryButton).setOnClickListener(view -> retryLoadOrAuthentication());
        findViewById(R.id.switchConnectionButton).setOnClickListener(view -> openConnectionChooser());
    }

    private void authenticateBeforeLoading(ConnectionProfile candidate, boolean passwordFallback) {
        String password = passwordFallback ? candidate.password : null;
        authClient.authenticate(this, candidate, password, new FnOsAuthClient.Callback() {
            @Override
            public void onSuccess(ConnectionProfile authenticatedProfile) {
                if (isFinishing() || isDestroyed()) return;
                SecureProfileStore store = new SecureProfileStore(MainActivity.this);
                store.upsert(authenticatedProfile, true);
                profile = authenticatedProfile;
                boolean switchingServer = PlaybackRuntimeConfig.activate(profile);
                if (switchingServer) stopService(new Intent(MainActivity.this, PlaybackService.class));
                configureWebView();
                connectMediaController();
                requestNotificationPermission();
            }

            @Override
            public void onError(String message) {
                if (isFinishing() || isDestroyed()) return;
                showError("连接 NAS 失败：" + message);
            }

            @Override
            public void onCredentialRejected(String message) {
                if (isFinishing() || isDestroyed()) return;
                if (!passwordFallback && !candidate.password.isEmpty()) {
                    authenticateBeforeLoading(candidate, true);
                    return;
                }
                SecureProfileStore store = new SecureProfileStore(MainActivity.this);
                store.upsert(candidate.withTokens("", ""), true);
                openConnectionChooser();
            }
        });
    }

    private void retryLoadOrAuthentication() {
        errorPanel.setVisibility(View.GONE);
        pageProgress.setVisibility(View.VISIBLE);
        if (profile != null && !profile.webSession && webResourceClient == null) {
            restoreFnConnectRelayThenAuthenticate(profile);
            return;
        }
        loadFnAudio();
    }

    private void restoreFnConnectRelayThenAuthenticate(ConnectionProfile candidate) {
        if (!isFnConnectProfile(candidate)) {
            authenticateBeforeLoading(candidate, false);
            return;
        }
        String fnId = fnConnectId(candidate);
        if (fnId.isEmpty()) {
            showError("FN Connect 历史记录缺少 FN ID，请重新登录。");
            return;
        }
        pageProgress.setVisibility(View.VISIBLE);
        if (fnConnectResolver != null) fnConnectResolver.close();
        fnConnectResolver = new FnConnectResolver(this);
        FnConnectResolver.Mode connectMode = FnConnectSettings.resolverMode(candidate.fnConnectMode);
        fnConnectResolver.resolve(fnId, connectMode, new FnConnectResolver.Callback() {
            @Override public void onResolved(ConnectionProfile route) {
                if (isFinishing() || isDestroyed()) return;
                ConnectionProfile refreshed = candidate.withEndpoint(route.host, route.port, route.https);
                profile = refreshed;
                new SecureProfileStore(MainActivity.this).upsert(refreshed, true);
                authenticateBeforeLoading(refreshed, false);
            }
            @Override public void onError(String message) {
                if (isFinishing() || isDestroyed()) return;
                showError("FN Connect 连接地址重新解析失败：" + message);
            }
        });
    }

    private static boolean isFnConnectProfile(ConnectionProfile candidate) {
        return candidate != null && (candidate.id.startsWith("fnconnect:")
                || candidate.name.startsWith("FN Connect - "));
    }

    private static String fnConnectId(ConnectionProfile candidate) {
        if (candidate == null) return "";
        String prefix = "fnconnect:";
        if (candidate.id.startsWith(prefix)) {
            String rest = candidate.id.substring(prefix.length());
            int separator = rest.indexOf(':');
            return (separator >= 0 ? rest.substring(0, separator) : rest).trim();
        }
        String namePrefix = "FN Connect - ";
        return candidate.name.startsWith(namePrefix) ? candidate.name.substring(namePrefix.length()).trim() : "";
    }

    private void configureSystemBars() {
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);
        getWindow().setStatusBarColor(0xffffffff);
        getWindow().setNavigationBarColor(0xffffffff);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            int flags = getWindow().getDecorView().getSystemUiVisibility() | View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) flags |= View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
            getWindow().getDecorView().setSystemUiVisibility(flags);
        }
    }

    @SuppressLint({"SetJavaScriptEnabled", "JavascriptInterface"})
    private void configureWebView() {
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setMediaPlaybackRequiresUserGesture(false);
        // An HTTPS fnAudio profile must never silently downgrade a script,
        // cover, or API subresource to HTTP. Plain-HTTP NAS profiles are
        // unaffected by this setting because they are not mixed content.
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setSupportZoom(false);
        settings.setUserAgentString(settings.getUserAgentString() + " fnAudio-Android/" + BuildConfig.VERSION_NAME);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) settings.setSafeBrowsingEnabled(true);

        webResourceClient = HttpClientFactory.create(this, profile);

        CookieManager cookies = CookieManager.getInstance();
        cookies.setAcceptCookie(true);
        cookies.setAcceptThirdPartyCookies(webView, false);
        if (profile.webSession) {
            sessionCookiesReady = true;
            maybeLoadFnAudio();
        } else installSessionCookies(cookies, () -> {
            if (destroyed || webView == null) return;
            sessionCookiesReady = true;
            maybeLoadFnAudio();
        });

        webView.addJavascriptInterface(new NativePlaybackBridge(this, this, this), "FnAudioNative");
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                pageProgress.setProgress(newProgress);
                pageProgress.setVisibility(newProgress >= 100 ? View.GONE : View.VISIBLE);
            }

            @Override
            public boolean onJsAlert(WebView view, String url, String message, JsResult result) {
                if (isFinishing() || isDestroyed()) {
                    result.cancel();
                    return true;
                }
                new AlertDialog.Builder(MainActivity.this)
                        .setTitle("fnAudio")
                        .setMessage(message)
                        .setPositiveButton(android.R.string.ok, (dialog, which) -> result.confirm())
                        .setOnCancelListener(dialog -> result.cancel())
                        .show();
                return true;
            }
        });
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                pageProgress.setVisibility(View.VISIBLE);
                errorPanel.setVisibility(View.GONE);
                // Keep the last committed frame (or the WebView's white
                // background on first launch) visible while navigating. Some
                // WebView versions omit or delay onPageFinished after a
                // redirect, which previously left the whole activity blank.
                webView.setVisibility(View.VISIBLE);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                pageLoaded = true;
                pageProgress.setVisibility(View.GONE);
                injectNativeEnvironment();
                webView.setVisibility(View.VISIBLE);
                String path = Uri.parse(url).getPath();
                if (!profile.webSession && path != null && !path.contains("/cgi/ThirdParty/fnaudio/index.cgi")) {
                    showError("fnOS 没有接受当前会话，页面被转到了系统入口。请返回连接页重新登录。 ");
                }
            }

            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                WebResourceResponse response = interceptAuthenticatedGet(request);
                return response == null ? super.shouldInterceptRequest(view, request) : response;
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
                String observedPin = CertificatePin.of(error.getCertificate());
                Uri errorUri = error.getUrl() == null ? null : Uri.parse(error.getUrl());
                if (profile != null && profile.https && profile.trustSelfSigned
                        && sameProfileOrigin(profile, errorUri)
                        && !profile.certificatePinSha256.isEmpty()
                        && profile.certificatePinSha256.equals(observedPin)) {
                    handler.proceed();
                } else {
                    handler.cancel();
                    String message = profile.trustSelfSigned && !profile.certificatePinSha256.isEmpty()
                            ? "服务器证书已变更或无法验证指纹，已拒绝加载页面。请确认 NAS 证书后重新建立连接。"
                            : "HTTPS 证书校验失败。请检查证书，或仅对可信 NAS 开启自签名证书兼容。";
                    showError(message);
                }
            }
        });
    }

    private void installSessionCookies(CookieManager cookies, Runnable onComplete) {
        String encoded = encodeCookie(profile.token);
        String flags = "; Path=/; SameSite=Lax" + (profile.https ? "; Secure" : "");
        String[] names = {"fnaudio_trim_token", "trim_token", "token", "fnos-token"};
        AtomicInteger remaining = new AtomicInteger(names.length);
        for (String name : names) {
            cookies.setCookie(profile.httpOrigin(), name + "=" + encoded + flags, ignored -> {
                if (remaining.decrementAndGet() == 0) {
                    cookies.flush();
                    if (!destroyed && webView != null) webView.post(onComplete);
                }
            });
        }
    }

    @Nullable
    private WebResourceResponse interceptAuthenticatedGet(@Nullable WebResourceRequest request) {
        // WebView invokes this on its own worker. Keep local references after
        // the lifecycle check: onDestroy can clear fields while this interceptor
        // is still building the authenticated request.
        OkHttpClient client = webResourceClient;
        AuthenticatedCoverCache thumbnailCache = coverCache;
        ConnectionProfile requestProfile = profile;
        if (request == null || !"GET".equalsIgnoreCase(request.getMethod())
                || !sameProfileOrigin(requestProfile, request.getUrl()) || client == null) return null;
        if (!isCurrentWebResourceClient(client)) return null;
        WebResourceResponse bundled = bundledAppAsset(request.getUrl(), requestProfile);
        if (bundled != null) {
            if (isCurrentWebResourceClient(client)) return bundled;
            closeWebResourceResponse(bundled);
            return null;
        }
        // WebView does not reliably attach programmatically installed cookies
        // or custom CGI routing headers on every Android/WebView version.
        // Proxy the main document and sub-resources through the same authenticated
        // OkHttp path; thumbnails still benefit from the native disk cache below.
        Uri uri = canonicalFnAudioResourceUri(request.getUrl());
        Request.Builder builder = new Request.Builder().url(uri.toString()).get();
        String routedPath = cgiRoutedPath(uri);
        if (!routedPath.isEmpty()) builder.header("X-Fnaudio-Path", routedPath);
        for (Map.Entry<String, String> header : request.getRequestHeaders().entrySet()) {
            String name = header.getKey();
            if (name == null || header.getValue() == null) continue;
            String lower = name.toLowerCase(Locale.ROOT);
            if (lower.equals("host") || lower.equals("connection") || lower.equals("content-length")
                    || lower.equals("accept-encoding") || lower.equals("cookie")
                    || lower.equals("authorization") || lower.equals("x-fnaudio-trim-token")
                    || lower.equals("x-fnaudio-path")) continue;
            builder.header(name, header.getValue());
        }
        if (!requestProfile.webSession) {
            builder.header("Authorization", "Bearer " + requestProfile.token);
            builder.header("X-Fnaudio-Trim-Token", requestProfile.token);
        }
        String requestCookie = request.getRequestHeaders().get("Cookie");
        if (requestProfile.webSession && (requestCookie == null || requestCookie.trim().isEmpty())) {
            requestCookie = CookieManager.getInstance().getCookie(uri.toString());
        }
        builder.header("Cookie", requestProfile.webSession
                ? (requestCookie == null ? "" : requestCookie)
                : authenticatedCookie(requestProfile, requestCookie));
        Response response = null;
        boolean responseOwnedByWebView = false;
        try {
            if (isListThumbnail(uri)) {
                InputStream cached = thumbnailCache == null ? null : thumbnailCache.open(profileCacheScope(requestProfile), uri.toString());
                if (cached != null) {
                    if (!isCurrentWebResourceClient(client)) {
                        try {
                            cached.close();
                        } catch (IOException ignored) {
                        }
                        return null;
                    }
                    return new WebResourceResponse("image/jpeg", null, cached);
                }
            }
            response = client.newCall(builder.build()).execute();
            // The request can outlive the Activity while OkHttp is connecting.
            // Do not hand an old response to a WebView that teardown has detached.
            if (!isCurrentWebResourceClient(client)) return null;
            final int responseCode = response.code();
            final String responseMessage = response.message();
            final Map<String, String> responseHeaderValues = responseHeaders(response.headers());
            if (request.isForMainFrame()) {
                Log.i("FnAudioWeb", "Authenticated main-frame GET status=" + responseCode
                        + ", route=" + routedPath + ", url=" + uri);
            }
            if (responseCode >= 400 && isCriticalUiAsset(uri)) {
                uiHandler.post(() -> showError("fnAudio 界面资源加载失败（HTTP " + responseCode + "）。请确认 NAS 已安装配套版本的 FPK。"));
            }
            syncResponseCookies(response.headers("Set-Cookie"), requestProfile);
            ResponseBody body = response.body();
            MediaType mediaType = body == null ? null : body.contentType();
            InputStream stream;
            if (isListThumbnail(uri) && responseCode == 200 && body != null) {
                byte[] bytes;
                try {
                    bytes = readBoundedBytes(body, MAX_COVER_BYTES);
                } catch (IOException exception) {
                    return null;
                }
                if (thumbnailCache != null) thumbnailCache.put(profileCacheScope(requestProfile), uri.toString(), bytes);
                response.close();
                response = null;
                stream = new ByteArrayInputStream(bytes);
            } else {
                stream = new ResponseClosingInputStream(
                        body == null ? new ByteArrayInputStream(new byte[0]) : body.byteStream(), response);
            }
            String contentType = mediaType == null ? guessContentType(uri) : mediaType.toString();
            String mime = contentType;
            String charset = null;
            int semicolon = contentType.indexOf(';');
            if (semicolon >= 0) mime = contentType.substring(0, semicolon).trim();
            charset = responseCharset(mediaType, mime);
            if (charset == null && isTextMime(mime)) charset = "UTF-8";
            WebResourceResponse webResponse = new WebResourceResponse(mime, charset, stream);
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.LOLLIPOP) {
                webResponse.setStatusCodeAndReasonPhrase(responseCode, responseMessage.isEmpty() ? reason(responseCode) : responseMessage);
                webResponse.setResponseHeaders(responseHeaderValues);
            }
            responseOwnedByWebView = true;
            return webResponse;
        } catch (IOException | RuntimeException exception) {
            // A WebView resource callback can race Activity teardown (which
            // shuts down the dispatcher) or carry a rejected header value.
            // Let WebView handle this as an unavailable resource instead of
            // crashing its callback thread.
            return null;
        } finally {
            if (response != null && !responseOwnedByWebView) response.close();
        }
    }

    private boolean isCurrentWebResourceClient(OkHttpClient client) {
        synchronized (nativeHttpCalls) {
            return !destroyed && webResourceClient == client;
        }
    }

    private static String profileCacheScope(@Nullable ConnectionProfile requestProfile) {
        if (requestProfile == null || requestProfile.id == null || requestProfile.id.length() > 4096) return "";
        return requestProfile.id;
    }

    private static void closeWebResourceResponse(@Nullable WebResourceResponse response) {
        if (response == null || response.getData() == null) return;
        try {
            response.getData().close();
        } catch (IOException ignored) {
        }
    }

    private static boolean isListThumbnail(Uri uri) {
        if (uri == null || uri.getPath() == null) return false;
        String path = uri.getPath().toLowerCase(Locale.ROOT);
        if (!path.contains("/cover/") && !path.contains("/cover-asset/")) return false;
        String size = uri.getQueryParameter("size");
        return "160".equals(size);
    }

    @Nullable
    private WebResourceResponse bundledAppAsset(Uri uri, @Nullable ConnectionProfile requestProfile) {
        if (requestProfile == null || uri == null || !sameProfileOrigin(requestProfile, uri)) return null;
        String path = uri.getPath();
        if (path == null) return null;
        String lower = path.toLowerCase(Locale.ROOT);
        String relative;
        if (lower.endsWith("/app.css")) relative = "app.css";
        else if (lower.endsWith("/app.js")) relative = "app.js";
        else if (lower.endsWith("/images/icon_64.png")) relative = "images/icon_64.png";
        else if (lower.endsWith("/images/icon_256.png")) relative = "images/icon_256.png";
        else return null;
        try {
            InputStream stream = new BoundedInputStream(getAssets().open(relative), MAX_BUNDLED_ASSET_BYTES);
            String mime = relative.endsWith(".css") ? "text/css"
                    : relative.endsWith(".js") ? "application/javascript" : "image/png";
            return new WebResourceResponse(mime, mime.startsWith("text/") || mime.contains("javascript") ? "UTF-8" : null, stream);
        } catch (IOException ignored) {
            return null;
        }
    }

    private boolean isFnConnectProfile() {
        return profile.id.startsWith("fnconnect:") || profile.name.startsWith("FN Connect - ");
    }

    private String readBundledText(String name) throws IOException {
        try (InputStream input = new BoundedInputStream(getAssets().open(name), MAX_BUNDLED_TEXT_BYTES);
             ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[16 * 1024];
            int count;
            while ((count = input.read(buffer)) != -1) {
                if (count == 0) continue;
                output.write(buffer, 0, count);
            }
            return output.toString(StandardCharsets.UTF_8.name());
        }
    }

    private static byte[] readBoundedBytes(ResponseBody body, int maxBytes) throws IOException {
        if (body == null || maxBytes <= 0) throw new IOException("empty response body");
        long declared = body.contentLength();
        if (declared > maxBytes) throw new IOException("response body is too large");
        InputStream input = body.byteStream();
        ByteArrayOutputStream output = new ByteArrayOutputStream(
                (int) Math.min(Math.max(declared, 0L), maxBytes));
        byte[] buffer = new byte[8192];
        int total = 0;
        int count;
        while ((count = input.read(buffer)) != -1) {
            if (count == 0) continue;
            if (count > maxBytes - total) throw new IOException("response body is too large");
            output.write(buffer, 0, count);
            total += count;
        }
        return output.toByteArray();
    }

    private static String readBoundedText(ResponseBody body, int maxBytes) throws IOException {
        return new String(readBoundedBytes(body, maxBytes), StandardCharsets.UTF_8);
    }

    private static int utf8Length(@Nullable String value) {
        if (value == null || value.isEmpty()) return 0;
        return value.getBytes(StandardCharsets.UTF_8).length;
    }

    private static String authenticatedCookie(ConnectionProfile requestProfile, @Nullable String existing) {
        String value = existing == null ? "" : existing.trim();
        String encoded = encodeCookie(requestProfile.token);
        String auth = "fnaudio_trim_token=" + encoded + "; trim_token=" + encoded + "; token=" + encoded + "; fnos-token=" + encoded;
        String access = accessCodeCookie(requestProfile);
        String combined = value.isEmpty() ? auth : value + "; " + auth;
        return access.isEmpty() ? combined : combined + "; " + access;
    }

    private static String accessCodeCookie(ConnectionProfile requestProfile) {
        if (requestProfile == null) return "";
        String cookies = CookieManager.getInstance().getCookie(requestProfile.httpOrigin());
        if (cookies == null || cookies.trim().isEmpty()) return "";
        for (String cookie : cookies.split(";")) {
            String pair = cookie.trim();
            if (pair.startsWith("os-access-code=") && pair.length() > "os-access-code=".length()) {
                return pair;
            }
        }
        return "";
    }

    @Override
    public void requestJson(String requestId, String method, String url, String headersJson, String body) {
        final String safeRequestId = requestId == null ? "" : requestId.trim();
        if (safeRequestId.isEmpty() || safeRequestId.length() > MAX_NATIVE_HTTP_REQUEST_ID_CHARS) return;
        OkHttpClient client;
        ConnectionProfile requestProfile;
        synchronized (nativeHttpCalls) {
            if (destroyed) {
                deliverNativeHttpFailure(safeRequestId, "原生网络服务正在关闭，请稍后重试");
                return;
            }
            client = webResourceClient;
            requestProfile = profile;
        }
        if (client == null || requestProfile == null) {
            deliverNativeHttpFailure(safeRequestId, "原生网络服务尚未就绪");
            return;
        }
        if (utf8Length(headersJson) > MAX_NATIVE_HTTP_HEADERS_BYTES) {
            deliverNativeHttpFailure(safeRequestId, "原生请求头过大");
            return;
        }
        if (utf8Length(body) > MAX_NATIVE_HTTP_REQUEST_BODY_BYTES) {
            deliverNativeHttpFailure(safeRequestId, "原生请求体过大");
            return;
        }
        Uri uri;
        try {
            uri = canonicalFnAudioResourceUri(Uri.parse(url));
        } catch (Exception exception) {
            deliverNativeHttpFailure(safeRequestId, "请求地址无效");
            return;
        }
        String path = uri.getPath();
        if (!sameProfileOrigin(requestProfile, uri) || path == null
                || !path.startsWith("/cgi/ThirdParty/fnaudio/index.cgi/api/")) {
            deliverNativeHttpFailure(safeRequestId, "原生认证请求仅允许访问当前 fnAudio API");
            return;
        }

        String normalizedMethod = method == null ? "GET" : method.trim().toUpperCase(Locale.ROOT);
        if (!(normalizedMethod.equals("GET") || normalizedMethod.equals("HEAD")
                || normalizedMethod.equals("POST") || normalizedMethod.equals("PUT")
                || normalizedMethod.equals("PATCH") || normalizedMethod.equals("DELETE"))) {
            deliverNativeHttpFailure(safeRequestId, "原生认证请求不支持 " + normalizedMethod);
            return;
        }

        String routedPath = cgiRoutedPath(uri);
        Uri transportUri = cgiQueryRoutedUri(uri, routedPath);
        Request.Builder builder = new Request.Builder().url(transportUri.toString());
        if (!routedPath.isEmpty()) builder.header("X-Fnaudio-Path", routedPath);
        String contentType = "application/json; charset=utf-8";
        try {
            JSONObject headers = new JSONObject(headersJson == null ? "{}" : headersJson);
            Iterator<String> names = headers.keys();
            while (names.hasNext()) {
                String name = names.next();
                Object rawValue = headers.opt(name);
                if (!(rawValue instanceof String)) throw new IllegalArgumentException("header value is not text");
                String value = (String) rawValue;
                String lower = name.toLowerCase(Locale.ROOT);
                if (lower.equals("host") || lower.equals("connection") || lower.equals("content-length")
                        || lower.equals("accept-encoding") || lower.equals("cookie")
                        || lower.equals("authorization") || lower.equals("x-fnaudio-trim-token")
                        || lower.equals("x-fnaudio-path")) continue;
                if (lower.equals("content-type") && !value.trim().isEmpty()) contentType = value;
                builder.header(name, value);
            }
        } catch (Exception exception) {
            deliverNativeHttpFailure(safeRequestId, "请求头格式无效");
            return;
        }
        MediaType mediaType = MediaType.parse(contentType);
        if (normalizedMethod.equals("GET") || normalizedMethod.equals("HEAD")) {
            builder.method(normalizedMethod, null);
        } else {
            RequestBody requestBody = RequestBody.create(body == null ? "" : body, mediaType);
            builder.method(normalizedMethod, requestBody);
        }
        if (!requestProfile.webSession) {
            builder.header("Authorization", "Bearer " + requestProfile.token);
            builder.header("X-Fnaudio-Trim-Token", requestProfile.token);
            builder.header("Cookie", authenticatedCookie(requestProfile, null));
        } else {
            String cookie = CookieManager.getInstance().getCookie(uri.toString());
            if (cookie == null || cookie.trim().isEmpty()) {
                deliverNativeHttpFailure(safeRequestId, "FN Connect 登录会话已失效，请重新登录");
                return;
            }
            builder.header("Cookie", cookie);
        }

        Call call = client.newCall(builder.build());
        Call previous;
        boolean rejected;
        synchronized (nativeHttpCalls) {
            if (destroyed || webResourceClient != client) {
                call.cancel();
                deliverNativeHttpFailure(safeRequestId, "原生网络服务正在关闭，请稍后重试");
                return;
            }
            previous = nativeHttpCalls.put(safeRequestId, call);
            // The new call is inserted before the capacity check. A request-id
            // replacement reuses an existing slot and must remain legal even
            // when the pool is full; only a genuinely new slot may exceed the
            // hard limit.
            rejected = nativeHttpCalls.size() > MAX_NATIVE_HTTP_CALLS;
            if (rejected) nativeHttpCalls.remove(safeRequestId, call);
        }
        if (previous != null) previous.cancel();
        if (rejected) {
            call.cancel();
            deliverNativeHttpFailure(safeRequestId, "原生网络请求过多，请稍后重试");
            return;
        }
        try {
            call.enqueue(new Callback() {
            @Override
            public void onFailure(@NonNull Call call, @NonNull IOException exception) {
                if (!nativeHttpCalls.remove(safeRequestId, call)) return;
                deliverNativeHttpFailure(safeRequestId, exception.getMessage() == null ? "网络请求失败" : exception.getMessage());
            }

            @Override
            public void onResponse(@NonNull Call call, @NonNull Response response) {
                if (!nativeHttpCalls.remove(safeRequestId, call)) {
                    response.close();
                    return;
                }
                try (Response closeable = response) {
                    syncResponseCookies(closeable.headers("Set-Cookie"), requestProfile);
                    ResponseBody responseBody = closeable.body();
                    String responseText = responseBody == null ? ""
                            : readBoundedText(responseBody, MAX_NATIVE_HTTP_RESPONSE_BYTES);
                    JSONObject payload = new JSONObject();
                    payload.put("requestId", safeRequestId);
                    payload.put("status", SessionCookies.responseStatus(closeable.code(), responseText));
                    payload.put("statusText", closeable.message());
                    payload.put("url", closeable.request().url().toString());
                    payload.put("body", responseText);
                    JSONObject responseHeaders = new JSONObject();
                    for (Map.Entry<String, String> header : responseHeaders(closeable.headers()).entrySet()) {
                        responseHeaders.put(header.getKey(), header.getValue());
                    }
                    payload.put("headers", responseHeaders);
                    deliverNativeHttpResponse(payload);
                } catch (Exception exception) {
                    deliverNativeHttpFailure(safeRequestId, exception.getMessage() == null ? "响应读取失败" : exception.getMessage());
                }
            }
            });
        } catch (RejectedExecutionException error) {
            nativeHttpCalls.remove(safeRequestId, call);
            deliverNativeHttpFailure(safeRequestId, "原生网络服务正在关闭，请稍后重试");
        }
    }

    @Override
    public void rejectRequestJson(String requestId, String message) {
        deliverNativeHttpFailure(requestId, message == null ? "原生网络请求无效" : message);
    }

    @Override
    public void cancelRequestJson(String requestId) {
        String safeRequestId = requestId == null ? "" : requestId.trim();
        if (safeRequestId.isEmpty() || safeRequestId.length() > MAX_NATIVE_HTTP_REQUEST_ID_CHARS) return;
        Call call = nativeHttpCalls.remove(safeRequestId);
        if (call != null) call.cancel();
    }

    private void deliverNativeHttpFailure(String requestId, String message) {
        try {
            JSONObject payload = new JSONObject();
            String safeRequestId = requestId == null ? "" : requestId.trim();
            payload.put("requestId", safeRequestId.length() > MAX_NATIVE_HTTP_REQUEST_ID_CHARS
                    ? safeRequestId.substring(0, MAX_NATIVE_HTTP_REQUEST_ID_CHARS) : safeRequestId);
            payload.put("status", 0);
            payload.put("statusText", "");
            payload.put("url", "");
            payload.put("body", "");
            payload.put("headers", new JSONObject());
            payload.put("networkError", message == null ? "网络请求失败" : message);
            deliverNativeHttpResponse(payload);
        } catch (Exception ignored) {
        }
    }

    private void deliverNativeHttpResponse(JSONObject payload) {
        if (destroyed) return;
        String serialized = payload.toString();
        final int chunkSize = 24 * 1024;
        int total = Math.max(1, (serialized.length() + chunkSize - 1) / chunkSize);
        if (serialized.length() > MAX_NATIVE_HTTP_SERIALIZED_RESPONSE_CHARS || total > MAX_NATIVE_HTTP_RESPONSE_CHUNKS) {
            Object rawRequestId = payload.opt("requestId");
            String requestId = rawRequestId instanceof String ? (String) rawRequestId : "";
            if (requestId.length() > MAX_NATIVE_HTTP_REQUEST_ID_CHARS) {
                requestId = requestId.substring(0, MAX_NATIVE_HTTP_REQUEST_ID_CHARS);
            }
            try {
                JSONObject fallback = new JSONObject();
                fallback.put("requestId", requestId);
                fallback.put("status", 0);
                fallback.put("statusText", "");
                fallback.put("url", "");
                fallback.put("body", "");
                fallback.put("headers", new JSONObject());
                fallback.put("networkError", "响应序列化结果过大");
                serialized = fallback.toString();
                total = 1;
            } catch (Exception ignored) {
                return;
            }
        }
        String transferId = "native-http-" + System.nanoTime();
        // Lambda captures must be stable: the oversized-response fallback can
        // replace both values above before this work reaches the UI thread.
        final String responsePayload = serialized;
        final int responseChunkCount = total;
        uiHandler.post(() -> {
            if (destroyed || webView == null || isFinishing() || isDestroyed()) return;
            for (int index = 0; index < responseChunkCount; index++) {
                // Activity destruction can happen between chunk evaluations.
                // Stop the transfer before touching a WebView that is no
                // longer owned by this Activity.
                if (destroyed || webView == null || isFinishing() || isDestroyed()) return;
                int start = index * chunkSize;
                int end = Math.min(responsePayload.length(), start + chunkSize);
                String chunk = responsePayload.substring(start, end);
                String script = "window.fnAudioNativeOnHttpChunk && window.fnAudioNativeOnHttpChunk("
                        + JSONObject.quote(transferId) + "," + index + "," + responseChunkCount + ","
                        + JSONObject.quote(chunk) + ");";
                try {
                    webView.evaluateJavascript(script, null);
                } catch (RuntimeException ignored) {
                    return;
                }
            }
        });
    }

    private Uri canonicalFnAudioResourceUri(Uri original) {
        String path = original.getEncodedPath();
        String prefix = "/cgi/ThirdParty/fnaudio/";
        String cgiPrefix = prefix + "index.cgi/";
        if (path != null && path.startsWith(prefix) && !path.startsWith(cgiPrefix)
                && !path.equals(prefix + "index.cgi")) {
            return original.buildUpon().encodedPath(cgiPrefix + path.substring(prefix.length())).build();
        }
        return original;
    }

    /**
     * fnOS releases differ in whether a CGI sub-resource reaches PATH_INFO.
     * The CGI proxy accepts this same-origin header as the authoritative suffix.
     */
    private String cgiRoutedPath(Uri uri) {
        if (uri == null) return "";
        String path = uri.getEncodedPath();
        String marker = "/cgi/ThirdParty/fnaudio/index.cgi";
        if (path == null || !path.startsWith(marker)) return "";
        String suffix = path.substring(marker.length());
        return suffix.isEmpty() ? "/" : (suffix.startsWith("/") ? suffix : "/" + suffix);
    }

    private Uri cgiQueryRoutedUri(Uri uri, String routedPath) {
        if (uri == null || routedPath == null || routedPath.isEmpty()) return uri;
        String marker = "/cgi/ThirdParty/fnaudio/index.cgi";
        String path = uri.getEncodedPath();
        if (path == null || !path.startsWith(marker)) return uri;
        return uri.buildUpon()
                .encodedPath(marker + "/")
                .appendQueryParameter("__fnaudio_path", routedPath)
                .build();
    }

    private boolean isCriticalUiAsset(Uri uri) {
        String path = uri.getPath();
        return path != null && (path.endsWith("/app.css") || path.endsWith("/app.js"));
    }

    private boolean isDirectImageResource(Uri uri) {
        String path = uri == null ? "" : uri.getPath();
        if (path == null) return false;
        String lower = path.toLowerCase(Locale.ROOT);
        return lower.endsWith(".png") || lower.endsWith(".jpg") || lower.endsWith(".jpeg")
                || lower.endsWith(".webp") || lower.endsWith(".gif") || lower.endsWith(".avif")
                || lower.contains("/cover/") || lower.contains("/covers/");
    }

    private void syncResponseCookies(List<String> setCookies, @Nullable ConnectionProfile requestProfile) {
        if (destroyed || setCookies == null || setCookies.isEmpty() || webView == null) return;
        webView.post(() -> {
            if (destroyed || webView == null || profile == null || profile != requestProfile) return;
            CookieManager manager = CookieManager.getInstance();
            for (String cookie : setCookies) manager.setCookie(requestProfile.httpOrigin(), cookie);
            manager.flush();
        });
    }

    private Map<String, String> responseHeaders(Headers headers) {
        Map<String, String> result = new HashMap<>();
        int totalBytes = 0;
        for (String name : headers.names()) {
            String lower = name.toLowerCase(Locale.ROOT);
            if (lower.equals("connection") || lower.equals("transfer-encoding")
                    || lower.equals("content-encoding") || lower.equals("content-length")
                    || lower.equals("set-cookie") || lower.equals("authorization")
                    || lower.equals("proxy-authenticate") || lower.equals("proxy-authorization")) continue;
            if (result.size() >= MAX_NATIVE_HTTP_RESPONSE_HEADER_COUNT) break;
            String value = headers.get(name);
            if (value == null) value = "";
            if (value.length() > MAX_NATIVE_HTTP_RESPONSE_HEADER_VALUE_CHARS) {
                value = value.substring(0, MAX_NATIVE_HTTP_RESPONSE_HEADER_VALUE_CHARS);
            }
            int entryBytes = utf8Length(name) + utf8Length(value) + 4;
            if (entryBytes > MAX_NATIVE_HTTP_RESPONSE_HEADERS_BYTES - totalBytes) break;
            result.put(name, value);
            totalBytes += entryBytes;
        }
        return result;
    }

    private String guessContentType(Uri uri) {
        String guessed = URLConnection.guessContentTypeFromName(uri.getPath());
        return guessed == null ? "application/octet-stream" : guessed;
    }

    static String responseCharset(@Nullable MediaType mediaType, String mime) {
        return mediaType == null || mediaType.charset() == null
                ? null : mediaType.charset().name();
    }

    private boolean isTextMime(String mime) {
        String lower = mime == null ? "" : mime.toLowerCase(Locale.ROOT);
        return lower.startsWith("text/") || lower.contains("javascript") || lower.contains("json")
                || lower.contains("xml") || lower.contains("svg");
    }

    private String reason(int status) {
        return status == 200 ? "OK" : "HTTP " + status;
    }

    private void maybeLoadFnAudio() {
        if (sessionCookiesReady && mediaController != null && webView != null && webView.getUrl() == null) loadFnAudio();
    }

    private void loadFnAudio() {
        if (webView == null) return;
        pageLoaded = false;
        errorPanel.setVisibility(View.GONE);
        webView.setVisibility(View.VISIBLE);
        loadBundledAppPage();
    }

    private void loadBundledAppPage() {
        try {
            String html = readBundledText("index.html");
            String css = readBundledText("app.css");
            String tokensCss = readBundledText("design-tokens.css");
            String themeCss = readBundledText("fnos-theme.css");
            String viewPresentation = readBundledText("view_presentation.js");
            String trackPresentation = readBundledText("track_presentation.js");
            String uiSyncScheduler = readBundledText("ui_sync_scheduler.js");
            String repeatModePolicy = readBundledText("repeat_mode_policy.js");
            String trackSortPolicy = readBundledText("track_sort_policy.js");
            String librarySortOptionsPolicy = readBundledText("library_sort_options_policy.js");
            String folderLabelPolicy = readBundledText("folder_label_policy.js");
            String hostPrivacyPolicy = readBundledText("host_privacy_policy.js");
            String javascript = readBundledText("app.js");
            html = html.replaceFirst("(?s)<link\\s+rel=\"stylesheet\"[^>]*>", Matcher.quoteReplacement(
                    "<style id=\"fnaudio-bundled-css\">" + css.replace("</style", "<\\/style") + "</style>"));
            String[] additionalStyles = {"design-tokens.css", "fnos-theme.css"};
            String[] styleSources = {tokensCss, themeCss};
            for (int i = 0; i < additionalStyles.length; i++) {
                html = inlineBundledStylesheet(html, additionalStyles[i], styleSources[i]);
            }
            html = html.replaceFirst("(?s)<script\\s+src=\"view_presentation\\.js[^\"]*\"[^>]*></script>", Matcher.quoteReplacement(
                    "<script>" + viewPresentation.replace("</script", "<\\/script") + "</script>"));
            html = html.replaceFirst("(?s)<script\\s+src=\"track_presentation\\.js[^\"]*\"[^>]*></script>", Matcher.quoteReplacement(
                    "<script>" + trackPresentation.replace("</script", "<\\/script") + "</script>"));
            html = html.replaceFirst("(?s)<script\\s+src=\"ui_sync_scheduler\\.js[^\"]*\"[^>]*></script>", Matcher.quoteReplacement(
                    "<script>" + uiSyncScheduler.replace("</script", "<\\/script") + "</script>"));
            html = html.replaceFirst("(?s)<script\\s+src=\"repeat_mode_policy\\.js[^\"]*\"[^>]*></script>", Matcher.quoteReplacement(
                    "<script>" + repeatModePolicy.replace("</script", "<\\/script") + "</script>"));
            html = html.replaceFirst("(?s)<script\\s+src=\"track_sort_policy\\.js[^\"]*\"[^>]*></script>", Matcher.quoteReplacement(
                    "<script>" + trackSortPolicy.replace("</script", "<\\/script") + "</script>"));
            html = html.replaceFirst("(?s)<script\\s+src=\"library_sort_options_policy\\.js[^\"]*\"[^>]*></script>", Matcher.quoteReplacement(
                    "<script>" + librarySortOptionsPolicy.replace("</script", "<\\/script") + "</script>"));
            html = html.replaceFirst("(?s)<script\\s+src=\"folder_label_policy\\.js[^\"]*\"[^>]*></script>", Matcher.quoteReplacement(
                    "<script>" + folderLabelPolicy.replace("</script", "<\\/script") + "</script>"));
            html = html.replaceFirst("(?s)<script\\s+src=\"host_privacy_policy\\.js[^\"]*\"[^>]*></script>", Matcher.quoteReplacement(
                    "<script>" + hostPrivacyPolicy.replace("</script", "<\\/script") + "</script>"));
            // Keep every policy module version-matched with app.js. The first
            // ten scripts above are retained as explicit replacements for
            // older source checks; these are the remaining modules declared
            // by index.html that must not be fetched from a possibly older NAS.
            String[] additionalScripts = {
                    "track_table_presentation.js", "queue_presentation.js", "lru_cache.js",
                    "album_metadata_cache.js", "item_cache.js", "item_negative_cache.js", "item_lookup.js",
                    "item_hydration_policy.js", "item_hydration_request.js",
                    "library_item_request_loader.js", "batch_request_pool.js",
                    "library_page_plan.js", "library_pager_visibility.js",
                    "library_pager_presentation.js", "library_page_merge.js",
                    "library_response_policy.js", "library_render_policy.js",
                    "library_row_signature_policy.js", "library_snapshot_reuse_policy.js",
                    "library_page_snapshot_policy.js", "metadata_row_patch_policy.js",
                    "library_page_size_policy.js", "creator_view_policy.js",
                    "user_media_state_policy.js", "lyrics_parse_policy.js",
                    "metadata_response_policy.js", "playback_target_policy.js",
                    "library_track_filter_policy.js", "library_root_label_policy.js",
                    "library_query_params.js", "library_reference_items.js",
                    "track_search_text.js", "device_target_presentation.js", "device_caps_presentation.js",
                    "cover_load_scheduler.js", "shuffle_policy.js", "host_playback_session.js",
                    "library_response_loader.js", "response_json_loader.js", "metadata_request_loader.js", "library_status_refresh_policy.js",
                    "visible_metadata_prefetch_policy.js", "ui_metrics_policy.js",
                    "library_metadata_merge_policy.js", "library_empty_response_policy.js",
                    "metadata_projection_policy.js", "metadata_candidate_presentation_policy.js",
                    "library_load_key.js", "library_page_cursor_policy.js",
                    "access_profile_loader.js", "library_full_list_policy.js", "fnos-ui.js"
            };
            for (String scriptName : additionalScripts) {
                html = inlineBundledScript(html, scriptName, readBundledText(scriptName));
            }
            html = html.replaceFirst("(?s)<script\\s+src=\"app\\.js[^\"]*\"[^>]*></script>", Matcher.quoteReplacement(
                    "<script>" + javascript.replace("</script", "<\\/script") + "</script>"));
            webView.loadDataWithBaseURL(profile.fnAudioUrl(), html, "text/html", "UTF-8", profile.fnAudioUrl());
        } catch (IOException exception) {
            showError("fnAudio 界面资源读取失败：" + exception.getMessage());
        }
    }

    private static String inlineBundledStylesheet(String html, String name, String source) {
        String pattern = "(?s)<link\\s+rel=\"stylesheet\"\\s+href=\""
                + Pattern.quote(name) + "(?:\\?[^\"]*)?\"[^>]*>";
        return html.replaceFirst(pattern, Matcher.quoteReplacement(
                "<style data-fnaudio-bundled=\"" + name + "\">"
                        + source.replace("</style", "<\\/style") + "</style>"));
    }

    private static String inlineBundledScript(String html, String name, String source) {
        String pattern = "(?s)<script\\s+src=\"" + Pattern.quote(name)
                + "(?:\\?[^\"]*)?\"[^>]*></script>";
        return html.replaceFirst(pattern, Matcher.quoteReplacement(
                "<script>" + source.replace("</script", "<\\/script") + "</script>"));
    }

    private void connectMediaController() {
        // Profile/server changes can reconnect while the previous controller
        // is still non-null. Release that session before creating its
        // replacement so commands cannot cross the connection boundary.
        if (controllerFuture != null || mediaController != null) {
            pendingControllerCommands.clear();
            if (controllerFuture != null) {
                MediaController.releaseFuture(controllerFuture);
                controllerFuture = null;
            }
            if (mediaController != null) {
                mediaController.release();
                mediaController = null;
            }
        }
        SessionToken token = new SessionToken(this, new ComponentName(this, PlaybackService.class));
        final ListenableFuture<MediaController> connectingFuture =
                new MediaController.Builder(this, token).buildAsync();
        controllerFuture = connectingFuture;
        connectingFuture.addListener(() -> {
            if (controllerFuture != connectingFuture || isFinishing() || isDestroyed()) return;
            try {
                mediaController = connectingFuture.get();
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
                while (!pendingControllerCommands.isEmpty()) {
                    NativePlaybackBridge.ControllerCommand command = pendingControllerCommands.removeFirst();
                    command.run(mediaController);
                }
                pushPlaybackStateToWeb();
                maybeLoadFnAudio();
            } catch (ExecutionException | InterruptedException exception) {
                if (exception instanceof InterruptedException) Thread.currentThread().interrupt();
                if (controllerFuture != connectingFuture || isFinishing() || isDestroyed()) return;
                showError("原生播放服务启动失败：" + String.valueOf(exception.getCause() == null ? exception.getMessage() : exception.getCause().getMessage()));
            }
        }, ContextCompat.getMainExecutor(this));
    }

    private void injectNativeEnvironment() {
        if (destroyed || webView == null || isFinishing() || isDestroyed()) return;
        WebView target = webView;
        try {
            target.evaluateJavascript(
                    "document.documentElement.classList.add('fnaudio-android-client');" +
                            "window.dispatchEvent(new CustomEvent('fnaudio-native-ready'));",
                    null
            );
        } catch (RuntimeException ignored) {
            return;
        }
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
        WebView target = webView;
        target.post(() -> {
            if (destroyed || webView != target || isFinishing() || isDestroyed()) return;
            try {
                target.evaluateJavascript(script, null);
            } catch (RuntimeException ignored) {
                return;
            }
        });
    }

    private boolean sameServer(Uri uri) {
        return sameProfileOrigin(profile, uri);
    }

    private boolean sameProfileOrigin(Uri uri) {
        return sameProfileOrigin(profile, uri);
    }

    private static boolean sameProfileOrigin(@Nullable ConnectionProfile candidate, Uri uri) {
        if (candidate == null) return false;
        if (candidate.webSession) {
            if (uri == null || !"https".equalsIgnoreCase(uri.getScheme())
                    || uri.getHost() == null
                    || !(comparableHost(candidate.host).equals(comparableHost(uri.getHost()))
                    || "fnos.net".equals(comparableHost(uri.getHost())))) return false;
            int actualPort = uri.getPort() < 0 ? 443 : uri.getPort();
            int expectedPort = candidate.port > 0 ? candidate.port : 443;
            return actualPort == expectedPort;
        }
        if (uri == null || uri.getHost() == null || uri.getScheme() == null) return false;
        String expectedScheme = candidate.https ? "https" : "http";
        if (!expectedScheme.equalsIgnoreCase(uri.getScheme())
                || !comparableHost(candidate.host).equals(comparableHost(uri.getHost()))) return false;
        int defaultPort = candidate.https ? 443 : 80;
        int actualPort = uri.getPort() < 0 ? defaultPort : uri.getPort();
        int expectedPort = candidate.port > 0 ? candidate.port : defaultPort;
        return actualPort == expectedPort;
    }

    private static String comparableHost(@Nullable String rawHost) {
        String host = rawHost == null ? "" : rawHost.trim().toLowerCase(Locale.ROOT);
        if (host.startsWith("[") && host.endsWith("]") && host.length() > 2) {
            host = host.substring(1, host.length() - 1);
        }
        return host;
    }

    private void showError(String message) {
        if (destroyed || isFinishing() || errorPanel == null) return;
        runOnUiThread(() -> {
            if (destroyed || isFinishing() || errorPanel == null || errorMessage == null || webView == null || pageProgress == null) return;
            errorMessage.setText(message);
            errorPanel.setVisibility(View.VISIBLE);
            webView.setVisibility(View.GONE);
            pageProgress.setVisibility(View.GONE);
        });
    }

    private ConnectionProfile resolveProfile() {
        SecureProfileStore store = new SecureProfileStore(this);
        String id = safeStringExtra(getIntent(), EXTRA_PROFILE_ID);
        ConnectionProfile selected = id == null ? null : store.find(id);
        return selected == null ? store.active() : selected;
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

    private void openConnectionChooser() {
        Intent intent = new Intent(this, LoginActivity.class);
        intent.putExtra(LoginActivity.EXTRA_SKIP_AUTO_RESUME, true);
        intent.putExtra(LoginActivity.EXTRA_PREFILL_ACTIVE_PROFILE, true);
        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        startActivity(intent);
        finish();
    }

    @Override
    public void logout() {
        runOnUiThread(() -> {
            if (destroyed || isFinishing() || isDestroyed()) return;
            ConnectionProfile signedOutProfile = profile;
            SecureProfileStore store = new SecureProfileStore(this);
            try {
                if (signedOutProfile != null) store.upsert(signedOutProfile.withTokens("", ""), false);
                store.setActive("");
            } catch (RuntimeException error) {
                Log.w("fnAudio", "Could not fully persist logout state", error);
            }
            PlaybackRuntimeConfig.activate(null);

            Intent intent = new Intent(this, LoginActivity.class)
                    .putExtra(LoginActivity.EXTRA_SKIP_AUTO_RESUME, true);
            if (signedOutProfile != null) {
                intent.putExtra(LoginActivity.EXTRA_PREFILL_PROFILE_ID, signedOutProfile.id);
            }
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
            startActivity(intent);
            finish();
            stopService(new Intent(this, PlaybackService.class));
            if (signedOutProfile != null) {
                Thread cookieCleanup = new Thread(() -> clearProfileCookies(signedOutProfile),
                        "fnaudio-cookie-cleanup");
                cookieCleanup.setDaemon(true);
                cookieCleanup.start();
            }
        });
    }

    private void clearProfileCookies(ConnectionProfile target) {
        CookieManager cookies = CookieManager.getInstance();
        String currentCookies = cookies.getCookie(target.httpOrigin());
        if (currentCookies == null || currentCookies.isEmpty()) return;
        String secure = target.https ? "; Secure" : "";
        for (String entry : currentCookies.split(";")) {
            int separator = entry.indexOf('=');
            if (separator <= 0) continue;
            String name = entry.substring(0, separator).trim();
            if (name.isEmpty()) continue;
            cookies.setCookie(target.httpOrigin(), name + "=; Max-Age=0; Path=/; SameSite=Lax" + secure);
        }
        cookies.flush();
    }

    private void installBackHandler() {
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                dispatchBackToFnAudio();
            }
        });
    }

    private void dispatchBackToFnAudio() {
        if (webBackDispatchInFlight) return;
        if (destroyed || webView == null || isFinishing() || isDestroyed()) {
            handleRootBackPress();
            return;
        }
        WebView target = webView;
        webBackDispatchInFlight = true;
        try {
            target.evaluateJavascript(
                    "Boolean(window.fnAudioHandleAndroidBack && window.fnAudioHandleAndroidBack())",
                    handled -> {
                        webBackDispatchInFlight = false;
                        if (destroyed || isFinishing() || isDestroyed()) return;
                        if ("true".equals(handled)) {
                            rootBackConfirmUntil = 0L;
                        } else {
                            handleRootBackPress();
                        }
                    }
            );
        } catch (RuntimeException ignored) {
            webBackDispatchInFlight = false;
            handleRootBackPress();
        }
    }

    private void handleRootBackPress() {
        long now = SystemClock.elapsedRealtime();
        if (rootBackConfirmUntil >= now) {
            rootBackConfirmUntil = 0L;
            openConnectionChooser();
            return;
        }
        rootBackConfirmUntil = now + ROOT_BACK_CONFIRM_WINDOW_MS;
        Toast.makeText(this, "APP 即将退出，再按一次返回登录界面", Toast.LENGTH_SHORT).show();
    }

    private void requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33 && ActivityCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.POST_NOTIFICATIONS}, 301);
        }
    }

    private static String encodeCookie(String value) {
        return SessionCookies.encodeToken(value);
    }

    @Nullable
    @Override
    public MediaController controller() {
        return mediaController;
    }

    @Override
    public void dispatchWhenReady(NativePlaybackBridge.ControllerCommand command) {
        if (command == null) return;
        uiHandler.post(() -> {
            if (destroyed || isFinishing() || isDestroyed()) return;
            if (mediaController == null) {
                if (pendingControllerCommands.size() >= MAX_PENDING_CONTROLLER_COMMANDS) {
                    pendingControllerCommands.removeFirst();
                }
                pendingControllerCommands.addLast(command);
                return;
            }
            command.run(mediaController);
        });
    }

    @Override
    protected void onResume() {
        super.onResume();
        uiHandler.removeCallbacks(playbackStateTicker);
        uiHandler.post(playbackStateTicker);
    }

    @Override
    protected void onPause() {
        rootBackConfirmUntil = 0L;
        uiHandler.removeCallbacks(playbackStateTicker);
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        destroyed = true;
        authClient.cancel();
        uiHandler.removeCallbacks(playbackStateTicker);
        pendingControllerCommands.clear();
        if (fnConnectResolver != null) {
            fnConnectResolver.close();
            fnConnectResolver = null;
        }
        if (controllerFuture != null) {
            MediaController.releaseFuture(controllerFuture);
            controllerFuture = null;
        }
        if (mediaController != null) {
            mediaController.release();
            mediaController = null;
        }
        if (webView != null) {
            webView.removeJavascriptInterface("FnAudioNative");
            webView.stopLoading();
            webView.setWebChromeClient(null);
            webView.setWebViewClient(null);
            webView.destroy();
            webView = null;
        }
        if (webResourceClient != null) {
            OkHttpClient client;
            synchronized (nativeHttpCalls) {
                client = webResourceClient;
                nativeHttpCalls.clear();
                webResourceClient = null;
            }
            Thread cleanup = new Thread(() -> {
                try {
                    client.dispatcher().cancelAll();
                    client.connectionPool().evictAll();
                } finally {
                    client.dispatcher().executorService().shutdown();
                }
            }, "fnaudio-http-cleanup");
            cleanup.setDaemon(true);
            cleanup.start();
        }
        if (coverCache != null) {
            coverCache.shutdown();
            coverCache = null;
        }
        super.onDestroy();
    }

    private static final class ResponseClosingInputStream extends FilterInputStream {
        private final Response response;

        ResponseClosingInputStream(InputStream stream, Response response) {
            super(stream);
            this.response = response;
        }

        @Override
        public void close() throws IOException {
            try {
                super.close();
            } finally {
                response.close();
            }
        }
    }

    private static final class BoundedInputStream extends FilterInputStream {
        private final int limit;
        private int total;

        BoundedInputStream(InputStream stream, int limit) {
            super(stream);
            this.limit = limit;
        }

        @Override
        public int read() throws IOException {
            if (total >= limit) {
                int extra = super.read();
                if (extra >= 0) throw new IOException("bundled asset is too large");
                return -1;
            }
            int value = super.read();
            if (value >= 0) total++;
            return value;
        }

        @Override
        public int read(byte[] buffer, int offset, int length) throws IOException {
            if (length == 0) return 0;
            if (total >= limit) {
                int extra = super.read();
                if (extra >= 0) throw new IOException("bundled asset is too large");
                return -1;
            }
            int count = super.read(buffer, offset, Math.min(length, limit - total));
            if (count > 0) total += count;
            return count;
        }
    }
}
