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
import android.os.SystemClock;
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
import java.net.URLEncoder;
import java.net.URLConnection;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.ExecutionException;
import java.util.regex.Matcher;

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

    private WebView webView;
    private ProgressBar pageProgress;
    private View errorPanel;
    private TextView errorMessage;
    private ConnectionProfile profile;
    private OkHttpClient webResourceClient;
    private AuthenticatedCoverCache coverCache;
    private ListenableFuture<MediaController> controllerFuture;
    private MediaController mediaController;
    private final Handler uiHandler = new Handler(Looper.getMainLooper());
    private boolean pageLoaded;
    private volatile boolean sessionCookiesReady;
    private boolean webBackDispatchInFlight;
    private long rootBackConfirmUntil;

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
            PlaybackRuntimeConfig.activate(profile);
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
        findViewById(R.id.retryButton).setOnClickListener(view -> loadFnAudio());
        findViewById(R.id.switchConnectionButton).setOnClickListener(view -> openConnectionChooser());
    }

    private void authenticateBeforeLoading(ConnectionProfile candidate, boolean passwordFallback) {
        String password = passwordFallback ? candidate.password : null;
        new FnOsAuthClient().authenticate(this, candidate, password, new FnOsAuthClient.Callback() {
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
                if (!passwordFallback && !candidate.password.isEmpty()) {
                    authenticateBeforeLoading(candidate, true);
                    return;
                }
                showError("登录令牌已失效，且自动恢复失败：" + message);
            }
        });
    }

    private void restoreFnConnectRelayThenAuthenticate(ConnectionProfile candidate) {
        if (!isStoredRelayProfile(candidate)) {
            authenticateBeforeLoading(candidate, false);
            return;
        }
        String fnId = fnConnectId(candidate);
        if (fnId.isEmpty()) {
            showError("FN Connect 历史记录缺少 FN ID，请重新登录。");
            return;
        }
        pageProgress.setVisibility(View.VISIBLE);
        new FnConnectResolver().resolve(fnId, new FnConnectResolver.Callback() {
            @Override public void onResolved(ConnectionProfile route) {
                ConnectionProfile refreshed = candidate.withEndpoint(route.host, route.port, route.https);
                profile = refreshed;
                new SecureProfileStore(MainActivity.this).upsert(refreshed, true);
                authenticateBeforeLoading(refreshed, false);
            }
            @Override public void onError(String message) {
                showError("FN Connect 公网地址重新解析失败：" + message);
            }
        });
    }

    private static boolean isStoredRelayProfile(ConnectionProfile candidate) {
        return candidate != null && candidate.id.startsWith("fnconnect:")
                && "127.0.0.1".equals(candidate.host) && candidate.port == 9018;
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
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);
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
        });
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                pageProgress.setVisibility(View.VISIBLE);
                errorPanel.setVisibility(View.GONE);
                webView.setVisibility(isFnConnectProfile() ? View.INVISIBLE : View.VISIBLE);
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
                if (profile.https && profile.trustSelfSigned && error.getUrl() != null
                        && profile.host.equalsIgnoreCase(Uri.parse(error.getUrl()).getHost())
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
        String[] names = {"fnaudio_trim_token", "trim_token", "token"};
        AtomicInteger remaining = new AtomicInteger(names.length);
        for (String name : names) {
            cookies.setCookie(profile.httpOrigin(), name + "=" + encoded + flags, ignored -> {
                if (remaining.decrementAndGet() == 0) {
                    cookies.flush();
                    webView.post(onComplete);
                }
            });
        }
    }

    @Nullable
    private WebResourceResponse interceptAuthenticatedGet(@Nullable WebResourceRequest request) {
        if (request == null || request.isForMainFrame()
                || !"GET".equalsIgnoreCase(request.getMethod())
                || !sameServer(request.getUrl()) || webResourceClient == null) return null;
        WebResourceResponse bundled = bundledFnConnectAsset(request.getUrl());
        if (bundled != null) return bundled;
        // WebView does not reliably attach programmatically installed cookies
        // to private image requests on every Android/WebView version. Proxy
        // covers as authenticated GETs; shouldInterceptRequest is concurrent
        // and OkHttp retains its own connection pool while the server returns
        // persistent 160 px thumbnails with immutable cache headers.
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
                    || lower.equals("authorization") || lower.equals("x-fnaudio-trim-token")) continue;
            builder.header(name, header.getValue());
        }
        if (!profile.webSession) {
            builder.header("Authorization", "Bearer " + profile.token);
            builder.header("X-Fnaudio-Trim-Token", profile.token);
        }
        String requestCookie = request.getRequestHeaders().get("Cookie");
        if (profile.webSession && (requestCookie == null || requestCookie.trim().isEmpty())) {
            requestCookie = CookieManager.getInstance().getCookie(uri.toString());
        }
        builder.header("Cookie", profile.webSession
                ? (requestCookie == null ? "" : requestCookie)
                : authenticatedCookie(requestCookie));
        try {
            if (isListThumbnail(uri)) {
                InputStream cached = coverCache.open(uri.toString());
                if (cached != null) {
                    return new WebResourceResponse("image/jpeg", null, cached);
                }
            }
            Response response = webResourceClient.newCall(builder.build()).execute();
            if (response.code() >= 400 && isCriticalUiAsset(uri)) {
                uiHandler.post(() -> showError("fnAudio 界面资源加载失败（HTTP " + response.code() + "）。请确认 NAS 已安装配套版本的 FPK。"));
            }
            syncResponseCookies(response.headers("Set-Cookie"));
            ResponseBody body = response.body();
            InputStream stream;
            if (isListThumbnail(uri) && response.code() == 200 && body != null) {
                byte[] bytes = body.bytes();
                coverCache.put(uri.toString(), bytes);
                response.close();
                stream = new ByteArrayInputStream(bytes);
            } else {
                stream = new ResponseClosingInputStream(
                        body == null ? new ByteArrayInputStream(new byte[0]) : body.byteStream(), response);
            }
            MediaType mediaType = body == null ? null : body.contentType();
            String contentType = mediaType == null ? guessContentType(uri) : mediaType.toString();
            String mime = contentType;
            String charset = null;
            int semicolon = contentType.indexOf(';');
            if (semicolon >= 0) mime = contentType.substring(0, semicolon).trim();
            if (mediaType != null && mediaType.charset() != null) charset = "UTF-8";
            if (charset == null && isTextMime(mime)) charset = "UTF-8";
            WebResourceResponse webResponse = new WebResourceResponse(mime, charset, stream);
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.LOLLIPOP) {
                webResponse.setStatusCodeAndReasonPhrase(response.code(), response.message().isEmpty() ? reason(response.code()) : response.message());
                webResponse.setResponseHeaders(responseHeaders(response.headers()));
            }
            return webResponse;
        } catch (IOException exception) {
            return null;
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
    private WebResourceResponse bundledFnConnectAsset(Uri uri) {
        if (profile == null || !isFnConnectProfile() || uri == null || !sameProfileOrigin(uri)) return null;
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
            InputStream stream = getAssets().open(relative);
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
        try (InputStream input = getAssets().open(name);
             ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[16 * 1024];
            int count;
            while ((count = input.read(buffer)) >= 0) output.write(buffer, 0, count);
            return output.toString(StandardCharsets.UTF_8.name());
        }
    }

    private String authenticatedCookie(@Nullable String existing) {
        String value = existing == null ? "" : existing.trim();
        String encoded = encodeCookie(profile.token);
        String auth = "fnaudio_trim_token=" + encoded + "; trim_token=" + encoded + "; token=" + encoded;
        return value.isEmpty() ? auth : value + "; " + auth;
    }

    @Override
    public void requestJson(String requestId, String method, String url, String headersJson, String body) {
        OkHttpClient client = webResourceClient;
        if (client == null || profile == null) {
            deliverNativeHttpFailure(requestId, "原生网络服务尚未就绪");
            return;
        }
        Uri uri;
        try {
            uri = canonicalFnAudioResourceUri(Uri.parse(url));
        } catch (Exception exception) {
            deliverNativeHttpFailure(requestId, "请求地址无效");
            return;
        }
        String path = uri.getPath();
        if (!sameProfileOrigin(uri) || path == null
                || !path.startsWith("/cgi/ThirdParty/fnaudio/index.cgi/api/")) {
            deliverNativeHttpFailure(requestId, "原生认证请求仅允许访问当前 fnAudio API");
            return;
        }

        String normalizedMethod = method == null ? "GET" : method.trim().toUpperCase(Locale.ROOT);
        if (!(normalizedMethod.equals("GET") || normalizedMethod.equals("HEAD")
                || normalizedMethod.equals("POST") || normalizedMethod.equals("PUT")
                || normalizedMethod.equals("PATCH") || normalizedMethod.equals("DELETE"))) {
            deliverNativeHttpFailure(requestId, "原生认证请求不支持 " + normalizedMethod);
            return;
        }

        Request.Builder builder = new Request.Builder().url(uri.toString());
        String routedPath = cgiRoutedPath(uri);
        if (!routedPath.isEmpty()) builder.header("X-Fnaudio-Path", routedPath);
        String contentType = "application/json; charset=utf-8";
        try {
            JSONObject headers = new JSONObject(headersJson == null ? "{}" : headersJson);
            Iterator<String> names = headers.keys();
            while (names.hasNext()) {
                String name = names.next();
                String value = headers.optString(name, "");
                String lower = name.toLowerCase(Locale.ROOT);
                if (lower.equals("host") || lower.equals("connection") || lower.equals("content-length")
                        || lower.equals("accept-encoding") || lower.equals("cookie")
                        || lower.equals("authorization") || lower.equals("x-fnaudio-trim-token")) continue;
                if (lower.equals("content-type") && !value.trim().isEmpty()) contentType = value;
                builder.header(name, value);
            }
        } catch (Exception exception) {
            deliverNativeHttpFailure(requestId, "请求头格式无效");
            return;
        }
        MediaType mediaType = MediaType.parse(contentType);
        if (normalizedMethod.equals("GET") || normalizedMethod.equals("HEAD")) {
            builder.method(normalizedMethod, null);
        } else {
            RequestBody requestBody = RequestBody.create(body == null ? "" : body, mediaType);
            builder.method(normalizedMethod, requestBody);
        }
        if (!profile.webSession) {
            builder.header("Authorization", "Bearer " + profile.token);
            builder.header("X-Fnaudio-Trim-Token", profile.token);
            builder.header("Cookie", authenticatedCookie(null));
        } else {
            String cookie = CookieManager.getInstance().getCookie(uri.toString());
            if (cookie == null || cookie.trim().isEmpty()) {
                deliverNativeHttpFailure(requestId, "FN Connect 登录会话已失效，请重新登录");
                return;
            }
            builder.header("Cookie", cookie);
        }

        client.newCall(builder.build()).enqueue(new Callback() {
            @Override
            public void onFailure(@NonNull Call call, @NonNull IOException exception) {
                deliverNativeHttpFailure(requestId, exception.getMessage() == null ? "网络请求失败" : exception.getMessage());
            }

            @Override
            public void onResponse(@NonNull Call call, @NonNull Response response) {
                try (Response closeable = response) {
                    syncResponseCookies(closeable.headers("Set-Cookie"));
                    ResponseBody responseBody = closeable.body();
                    String responseText = responseBody == null ? "" : responseBody.string();
                    JSONObject payload = new JSONObject();
                    payload.put("requestId", requestId);
                    payload.put("status", closeable.code());
                    payload.put("statusText", closeable.message());
                    payload.put("url", closeable.request().url().toString());
                    payload.put("body", responseText);
                    JSONObject responseHeaders = new JSONObject();
                    for (String name : closeable.headers().names()) {
                        if (!name.equalsIgnoreCase("Set-Cookie")) responseHeaders.put(name, closeable.header(name, ""));
                    }
                    payload.put("headers", responseHeaders);
                    deliverNativeHttpResponse(payload);
                } catch (Exception exception) {
                    deliverNativeHttpFailure(requestId, exception.getMessage() == null ? "响应读取失败" : exception.getMessage());
                }
            }
        });
    }

    private void deliverNativeHttpFailure(String requestId, String message) {
        try {
            JSONObject payload = new JSONObject();
            payload.put("requestId", requestId);
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
        String serialized = payload.toString();
        final int chunkSize = 24 * 1024;
        int total = Math.max(1, (serialized.length() + chunkSize - 1) / chunkSize);
        String transferId = "native-http-" + System.nanoTime();
        uiHandler.post(() -> {
            if (webView == null || isFinishing() || isDestroyed()) return;
            for (int index = 0; index < total; index++) {
                int start = index * chunkSize;
                int end = Math.min(serialized.length(), start + chunkSize);
                String chunk = serialized.substring(start, end);
                String script = "window.fnAudioNativeOnHttpChunk && window.fnAudioNativeOnHttpChunk("
                        + JSONObject.quote(transferId) + "," + index + "," + total + ","
                        + JSONObject.quote(chunk) + ");";
                webView.evaluateJavascript(script, null);
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

    private void syncResponseCookies(List<String> setCookies) {
        if (setCookies == null || setCookies.isEmpty() || webView == null) return;
        webView.post(() -> {
            CookieManager manager = CookieManager.getInstance();
            for (String cookie : setCookies) manager.setCookie(profile.httpOrigin(), cookie);
            manager.flush();
        });
    }

    private Map<String, String> responseHeaders(Headers headers) {
        Map<String, String> result = new HashMap<>();
        for (String name : headers.names()) {
            String lower = name.toLowerCase(Locale.ROOT);
            if (lower.equals("connection") || lower.equals("transfer-encoding")
                    || lower.equals("content-encoding") || lower.equals("content-length")
                    || lower.equals("set-cookie")) continue;
            result.put(name, headers.get(name));
        }
        return result;
    }

    private String guessContentType(Uri uri) {
        String guessed = URLConnection.guessContentTypeFromName(uri.getPath());
        return guessed == null ? "application/octet-stream" : guessed;
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
        webView.setVisibility(isFnConnectProfile() ? View.INVISIBLE : View.VISIBLE);
        if (isFnConnectProfile()) {
            loadBundledFnConnectPage();
            return;
        }
        Map<String, String> headers = new LinkedHashMap<>();
        if (profile.webSession) webView.loadUrl(profile.fnAudioUrl());
        else {
            headers.put("Authorization", "Bearer " + profile.token);
            headers.put("X-Fnaudio-Trim-Token", profile.token);
            webView.loadUrl(profile.fnAudioUrl(), headers);
        }
    }

    private void loadBundledFnConnectPage() {
        try {
            String html = readBundledText("index.html");
            String css = readBundledText("app.css");
            String javascript = readBundledText("app.js");
            html = html.replaceFirst("(?s)<link\\s+rel=\"stylesheet\"[^>]*>", Matcher.quoteReplacement(
                    "<style id=\"fnaudio-bundled-css\">" + css.replace("</style", "<\\/style") + "</style>"));
            html = html.replaceFirst("(?s)<script\\s+src=\"app\\.js[^\"]*\"[^>]*></script>", Matcher.quoteReplacement(
                    "<script>" + javascript.replace("</script", "<\\/script") + "</script>"));
            webView.loadDataWithBaseURL(profile.fnAudioUrl(), html, "text/html", "UTF-8", profile.fnAudioUrl());
        } catch (IOException exception) {
            showError("FN Connect 界面资源读取失败：" + exception.getMessage());
        }
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
                maybeLoadFnAudio();
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
        if (profile.webSession) {
            String host = comparableHost(uri.getHost());
            return host.equals(comparableHost(profile.host)) || host.equals("fnos.net");
        }
        if (!comparableHost(profile.host).equals(comparableHost(uri.getHost()))) return false;
        int uriPort = uri.getPort();
        return uriPort < 0 || uriPort == profile.port;
    }

    private boolean sameProfileOrigin(Uri uri) {
        if (profile.webSession) {
            return uri != null && "https".equalsIgnoreCase(uri.getScheme())
                    && uri.getHost() != null
                    && (comparableHost(profile.host).equals(comparableHost(uri.getHost()))
                    || "fnos.net".equals(comparableHost(uri.getHost())));
        }
        if (uri == null || uri.getHost() == null || uri.getScheme() == null) return false;
        String expectedScheme = profile.https ? "https" : "http";
        if (!expectedScheme.equalsIgnoreCase(uri.getScheme())
                || !comparableHost(profile.host).equals(comparableHost(uri.getHost()))) return false;
        int defaultPort = profile.https ? 443 : 80;
        int actualPort = uri.getPort() < 0 ? defaultPort : uri.getPort();
        int expectedPort = profile.port > 0 ? profile.port : defaultPort;
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
        intent.putExtra(LoginActivity.EXTRA_SKIP_AUTO_RESUME, true);
        intent.putExtra(LoginActivity.EXTRA_PREFILL_ACTIVE_PROFILE, true);
        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        startActivity(intent);
        finish();
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
        if (webView == null) {
            handleRootBackPress();
            return;
        }
        webBackDispatchInFlight = true;
        webView.evaluateJavascript(
                "Boolean(window.fnAudioHandleAndroidBack && window.fnAudioHandleAndroidBack())",
                handled -> {
                    webBackDispatchInFlight = false;
                    if ("true".equals(handled)) {
                        rootBackConfirmUntil = 0L;
                    } else {
                        handleRootBackPress();
                    }
                }
        );
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
        rootBackConfirmUntil = 0L;
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
        if (webResourceClient != null) {
            webResourceClient.dispatcher().cancelAll();
            webResourceClient.connectionPool().evictAll();
            webResourceClient.dispatcher().executorService().shutdown();
            webResourceClient = null;
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
}
