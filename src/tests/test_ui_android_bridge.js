const fs = require("fs");
const path = require("path");
const assert = require("assert").strict;

const source = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "app.js"), "utf8");
const vm = require("vm");
const playbackSecondsStart = source.indexOf("function playbackSeconds(");
const playbackSecondsEnd = source.indexOf("function mediaUrl(", playbackSecondsStart);
if (playbackSecondsStart < 0 || playbackSecondsEnd < 0) {
  throw new Error("Playback seconds normalizer must remain a standalone UI helper");
}
const playbackContext = {};
vm.runInNewContext(`${source.slice(playbackSecondsStart, playbackSecondsEnd)}; this.playbackSeconds = playbackSeconds;`, playbackContext);
for (const [input, expected] of [["NaN", 0], ["Infinity", 0], [-1, 0], [true, 0], ["12.5", 12.5]]) {
  if (playbackContext.playbackSeconds(input) !== expected) {
    throw new Error(`Playback seconds normalizer mishandled ${String(input)}`);
  }
}
if (!source.includes("function playbackSeconds(value, fallback = 0)")
    || !source.includes("state.remoteBaseSeconds = playbackSeconds(data?.position?.rel_seconds)")
    || !source.includes("const remoteDuration = playbackSeconds(state.remoteStatus?.position?.duration_seconds)")
    || !source.includes("const audioSeconds = playbackSeconds(audio.currentTime)")
    || !source.includes("raw - playbackSeconds(item.cue_start)")) {
  throw new Error("Playback UI must normalize remote and renderer time values before arithmetic");
}
if (!source.includes("state.remoteStateVersion = 0;")
    || !source.includes("function remoteStateVersion(value)")
    || !source.includes("state.remoteStateVersion > 0 && (stateVersion == null || stateVersion < state.remoteStateVersion)")) {
  throw new Error("Web remote snapshots must reject missing, invalid, and out-of-order state versions");
}
if (!source.includes("fnAudioMediaSessionDiagnostics")) {
  throw new Error("Web Media Session diagnostics must be exposed for fnOS host verification");
}
if (!source.includes('navigator.mediaSession.playbackState = isPlayingNow() ? "playing" : (currentItem() ? "paused" : "none")')) {
  throw new Error("Idle Web Media Session state must clear to none");
}
const index = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "index.html"), "utf8");
const responseJsonLoader = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "response_json_loader.js"), "utf8");
const repeatPolicy = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "repeat_mode_policy.js"), "utf8");
const cgi = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "cgi_proxy.py"), "utf8");
const mainActivity = fs.readFileSync(path.join(
  __dirname, "..", "..", "android-client", "app", "src", "main", "java", "com", "fnaudio", "client", "ui", "MainActivity.java"
), "utf8");
const bitmapLoader = fs.readFileSync(path.join(
  __dirname, "..", "..", "android-client", "app", "src", "main", "java", "com", "fnaudio", "client", "playback", "AuthenticatedBitmapLoader.java"
), "utf8");
const coverCache = fs.readFileSync(path.join(
  __dirname, "..", "..", "android-client", "app", "src", "main", "java", "com", "fnaudio", "client", "ui", "AuthenticatedCoverCache.java"
), "utf8");
if (!mainActivity.includes("if (destroyed) return;")) {
  throw new Error("Playback state ticker must stop after Activity destruction");
}
if (!mainActivity.includes("while ((count = input.read(buffer)) != -1)")) {
  throw new Error("Bundled asset reads must terminate on EOF instead of treating zero-byte reads as EOF");
}
if (!bitmapLoader.includes("if (count == 0) continue;")) {
  throw new Error("Cached artwork reads must make progress when the stream returns zero bytes");
}
if (!bitmapLoader.includes('".tmp." + UUID.randomUUID()')
    || !bitmapLoader.includes('file.getName().contains(".tmp.")')) {
  throw new Error("Authenticated notification artwork caching must isolate and clean staging files");
}
if (!coverCache.includes("ArrayBlockingQueue<>(MAX_PENDING_WRITES)")
    || !coverCache.includes("MAX_PENDING_WRITES = 24")
    || !coverCache.includes("writer.execute(() -> write(scope, key, body))")
    || !coverCache.includes('".tmp." + UUID.randomUUID()')
    || !coverCache.includes("void shutdown()")
    || !coverCache.includes("writer.shutdownNow()")
    || !mainActivity.includes("coverCache.shutdown()")) {
  throw new Error("Authenticated thumbnail caching must keep disk writes off WebView callbacks and isolate staging files");
}
if (!mainActivity.includes("AuthenticatedCoverCache thumbnailCache = coverCache;")
    || !mainActivity.includes("thumbnailCache == null ? null : thumbnailCache.open(profileCacheScope(requestProfile), uri.toString())")
    || !mainActivity.includes("if (thumbnailCache != null) thumbnailCache.put(profileCacheScope(requestProfile), uri.toString(), bytes);")) {
  throw new Error("Late WebView cover callbacks must retain a local cache reference across Activity teardown");
}
if (!source.includes("cancelRequestJson(requestId)")
    || !mainActivity.includes("nativeHttpCalls.remove(safeRequestId, call)")
    || !mainActivity.includes("if (!nativeHttpCalls.remove(safeRequestId, call)) return;")) {
  throw new Error("Aborted native HTTP requests must cancel OkHttp and drop late callbacks");
}
if (!/window\.FnAudioNative\.requestJson\(requestId,[\s\S]*?catch \(error\) \{[\s\S]*?const pending = nativeHttpRequests\.get\(requestId\);[\s\S]*?if \(pending\) clearNativeHttpRequest\(requestId, pending, error\);/.test(source)) {
  throw new Error("Synchronous native HTTP bridge failures must cancel the underlying request");
}
if (!/state\.remoteStatusRequestToken = 0;[\s\S]*?state\.remoteStatusController = null;/.test(source)
    || !/function cancelRemoteStatusRequest\(\) \{[\s\S]*?remoteStatusController\?\.abort\(\)[\s\S]*?remoteStatusRequestInFlight = false;/.test(source)
    || !/const targetId = remoteDeviceId\(\);[\s\S]*?fnAudioResponseJsonLoader\.read\(\{[\s\S]*?timeoutMs: 6000,[\s\S]*?onTimeout:[\s\S]*?token !== state\.remoteStatusRequestToken \|\| targetId !== remoteDeviceId\(\)/.test(source)
    || !source.includes("if (!response?.ok) return;")) {
  throw new Error("Remote status polling must be bounded, cancellable, and owned by its target request");
}
if (!/let loadSucceeded = false;[\s\S]*?loadSucceeded = true;[\s\S]*?if \(!loadSucceeded && state\.remoteLoadedKey === loadKey\)[\s\S]*?state\.remoteLoadedAt = 0;/.test(source)) {
  throw new Error("Failed or cancelled remote loads must release their short deduplication key for retry");
}
if (!/state\.transcodeStatusRequestToken = 0;[\s\S]*?state\.transcodeStatusController = null;/.test(source)
    || !/const token = \+\+state\.transcodeStatusRequestToken;[\s\S]*?transcodeStatusController\?\.abort\(\)[\s\S]*?fnAudioResponseJsonLoader\.read\(\{[\s\S]*?timeoutMs: 6000,[\s\S]*?onTimeout:/.test(source)
    || !/token !== state\.transcodeStatusRequestToken[\s\S]*?state\.transcodeStatusController !== controller[\s\S]*?String\(currentItem\(\)\?\.id \|\| ""\) !== trackId/.test(source)) {
  throw new Error("Transcode status polling must be bounded, cancellable, and reject stale responses");
}
if (!/state\.rendererRequestToken = 0;[\s\S]*?state\.rendererRequestController = null;/.test(source)
    || !/const token = \+\+state\.rendererRequestToken;[\s\S]*?fnAudioResponseJsonLoader\.read\(\{[\s\S]*?timeoutMs: 6000,[\s\S]*?onTimeout:/.test(source)
    || !/token !== state\.rendererRequestToken \|\| state\.rendererRequestController !== controller[\s\S]*?if \(!response\.ok\) return;/.test(source)) {
  throw new Error("DLNA renderer status polling must time out, reject stale responses, and preserve a valid snapshot on HTTP failure");
}
if (!/state\.deviceLoadRequestToken = 0;[\s\S]*?state\.deviceLoadController = null;/.test(source)
    || !/if \(state\.deviceLoadInFlight && !forceRefresh\) return;[\s\S]*?if \(state\.deviceLoadInFlight\) cancelDeviceLoad\(\);/.test(source)
    || !/const token = \+\+state\.deviceLoadRequestToken;[\s\S]*?fnAudioResponseJsonLoader\.read\(\{[\s\S]*?timeoutMs: 6000,[\s\S]*?onTimeout:/.test(source)
    || !/function cancelDeviceLoad\(\) \{[\s\S]*?deviceLoadController\?\.abort\(\)[\s\S]*?deviceLoadInFlight = false;/.test(source)
    || !/if \(state\.deviceSwitchInFlight \|\| previousTarget === nextTarget\) return;\s*cancelDeviceLoad\(\);/.test(source)) {
  throw new Error("Playback target discovery must be bounded, replaceable by a forced refresh, and cancelled when its target changes");
}

if (!/await recoverUnavailablePlaybackTarget\(false, reportedTarget\);[\s\S]*?token !== state\.deviceLoadRequestToken[\s\S]*?state\.deviceLoadController !== controller[\s\S]*?targetRevision !== state\.deviceTargetRevision/.test(source)
    || !/async function recoverUnavailablePlaybackTarget\(notify = false, expectedTarget = ""\)[\s\S]*?if \(!response\.ok \|\| data\.ok !== true\) return false;[\s\S]*?expectedTarget[\s\S]*?state\.deviceSwitchInFlight/.test(source)) {
  throw new Error("Device target recovery must re-check request ownership after its async write");
}
if (!responseJsonLoader.includes("response.json()")
    || !responseJsonLoader.includes("Promise.race([operation, timeout])")
    || !index.includes('src="response_json_loader.js?v=__FNAUDIO_ASSET_BUILD__"')) {
  throw new Error("State polling must load the shared response-body timeout boundary before app.js");
}
if (mainActivity.includes("if (isDirectImageResource(request.getUrl())) return null")) {
  throw new Error("Private covers must pass through the authenticated Android resource proxy");
}
if (!mainActivity.includes("loadBundledAppPage();")
    || !mainActivity.includes("webView.loadDataWithBaseURL(profile.fnAudioUrl(), html")) {
  throw new Error("Android must load its version-matched bundled UI with the NAS CGI URL as the API base");
}
for (const script of ["view_presentation.js", "track_presentation.js", "ui_sync_scheduler.js", "repeat_mode_policy.js", "track_sort_policy.js", "library_sort_options_policy.js", "folder_label_policy.js", "host_privacy_policy.js", "app.js"]) {
  if (!mainActivity.includes(`readBundledText("${script}")`)) {
    throw new Error(`Android bundled UI must inline ${script} instead of mixing APK and NAS assets`);
  }
}
if (!mainActivity.includes("CookieManager.getInstance().getCookie(uri.toString())")) {
  throw new Error("Web-session cover requests must recover cookies from CookieManager");
}
if (!mainActivity.includes('.appendQueryParameter("__fnaudio_path", routedPath)')) {
  throw new Error("Android API requests must use the fnOS-compatible CGI query route");
}
const nativeBridge = fs.readFileSync(path.join(
  __dirname, "..", "..", "android-client", "app", "src", "main", "java", "com", "fnaudio", "client", "web", "NativePlaybackBridge.java"
), "utf8");
const playbackService = fs.readFileSync(path.join(
  __dirname, "..", "..", "android-client", "app", "src", "main", "java", "com", "fnaudio", "client", "playback", "PlaybackService.java"
), "utf8");
const remotePlayer = fs.readFileSync(path.join(
  __dirname, "..", "..", "android-client", "app", "src", "main", "java", "com", "fnaudio", "client", "playback", "RemotePlaybackPlayer.java"
), "utf8");
const artworkLoader = fs.readFileSync(path.join(
  __dirname, "..", "..", "android-client", "app", "src", "main", "java", "com", "fnaudio", "client", "playback", "AuthenticatedBitmapLoader.java"
), "utf8");
if (!artworkLoader.includes("readBoundedBody(response.body())")
    || !artworkLoader.includes("Artwork response is too large")
    || artworkLoader.includes("return response.body().bytes()")) {
  throw new Error("Android artwork downloads must enforce the byte budget while streaming unknown-length responses");
}
if (!artworkLoader.includes("RejectedExecutionException")
    || !artworkLoader.includes("Artwork loader is shut down")) {
  throw new Error("Android artwork requests after loader shutdown must complete their Future with an error");
}
if (!artworkLoader.includes("executor.execute(this::pruneCache);")
    || !artworkLoader.includes("} catch (RejectedExecutionException ignored) {")) {
  throw new Error("Artwork cache pruning must not make loader construction fail when its executor rejects work");
}
if (!mainActivity.includes("final ListenableFuture<MediaController> connectingFuture")
    || !mainActivity.includes("controllerFuture != connectingFuture")
    || !mainActivity.includes("mediaController = connectingFuture.get()")) {
  throw new Error("Android MediaController callbacks must be bound to the current connection future across Activity teardown and reconnects");
}
const notificationIcon = fs.readFileSync(path.join(
  __dirname, "..", "..", "android-client", "app", "src", "main", "res", "drawable", "ic_notification.xml"
), "utf8");
const loginActivity = fs.readFileSync(path.join(
  __dirname, "..", "..", "android-client", "app", "src", "main", "java", "com", "fnaudio", "client", "ui", "LoginActivity.java"
), "utf8");
const resolver = fs.readFileSync(path.join(
  __dirname, "..", "..", "android-client", "app", "src", "main", "java", "com", "fnaudio", "client", "network", "FnConnectResolver.java"
), "utf8");
if (!resolver.includes("client.dispatcher().executorService().shutdown()")
    || !resolver.includes("public void close()")) {
  throw new Error("FN Connect resolver must shut down its OkHttp executor when the owner Activity is destroyed");
}
const historyActivity = fs.readFileSync(path.join(
  __dirname, "..", "..", "android-client", "app", "src", "main", "java", "com", "fnaudio", "client", "ui", "ConnectionHistoryActivity.java"
), "utf8");
const connectionProfile = fs.readFileSync(path.join(
  __dirname, "..", "..", "android-client", "app", "src", "main", "java", "com", "fnaudio", "client", "data", "ConnectionProfile.java"
), "utf8");
const declaredPolicyScripts = [...index.matchAll(/<script src="([^?]+)\?v=__FNAUDIO_ASSET_BUILD__"/g)]
  .map(match => match[1]).filter(name => name !== "app.js");
for (const script of declaredPolicyScripts) {
  if (!mainActivity.includes(`"${script}"`)) {
    throw new Error(`Android bundled UI must inline declared policy script ${script}`);
  }
}
const historyLayout = fs.readFileSync(path.join(
  __dirname, "..", "..", "android-client", "app", "src", "main", "res", "layout", "activity_connection_history.xml"
), "utf8");
if (!loginActivity.includes("if (skipAutoResume) clearFormForNewProfile()")) {
  if (!loginActivity.includes("if (skipAutoResume || active == null) clearFormForNewProfile()")) {
    throw new Error("Returning to Android login must start with a blank address instead of the active FN ID");
  }
}
if (!loginActivity.includes('if (!sameAsSelected || requestedName.startsWith("FN Connect - ")) requestedName = address.host')) {
  throw new Error("A manually entered address must not inherit an FN Connect profile identity");
}
if (!mainActivity.includes("EXTRA_PREFILL_ACTIVE_PROFILE, true")
    || !loginActivity.includes("if (prefillActive && active != null) fillForm(active, false)")) {
  throw new Error("Explicit logout must prefill the last active connection without auto-resuming it");
}
if (!mainActivity.includes("isFnConnectProfile(candidate)")
    || mainActivity.includes("isStoredRelayProfile(candidate)")) {
  throw new Error("Every stored FN Connect profile must refresh its official endpoint before token recovery");
}
if (!mainActivity.includes("retryLoadOrAuthentication()")
    || !mainActivity.includes("restoreFnConnectRelayThenAuthenticate(profile);")) {
  throw new Error("The Android error-panel retry must rerun authentication before WebView setup");
}
if (!loginActivity.includes("正在刷新 FN Connect 公网地址")
    || !loginActivity.includes('profile.withTokens("", "")')) {
  throw new Error("FN Connect auto-resume must refresh its route and clear explicitly rejected stale tokens");
}
if (mainActivity.includes("webView.setVisibility(View.INVISIBLE);")
    || !mainActivity.includes("webView.setVisibility(View.VISIBLE);")) {
  throw new Error("Android must keep the WebView visible during navigation so a delayed finish callback cannot leave a blank page");
}

function requireText(text, message) {
  if (!source.includes(text)) throw new Error(message || `Missing app.js text: ${text}`);
}

if (!index.includes('id="metadataEnabledInput" type="checkbox"')
    || index.includes('id="metadataEnabledInput" type="checkbox" checked')) {
  throw new Error("Background metadata completion must have a visible switch that defaults off");
}
if (!index.includes('id="metadataTagWriteEnabledInput" type="checkbox"')
    || index.includes('id="metadataTagWriteEnabledInput" type="checkbox" checked')) {
  throw new Error("Metadata Tag writeback must have a visible switch that defaults off");
}
requireText('data.tag_write_enabled === true', "Metadata Tag writeback status must load explicitly");
requireText('data.enabled === true', "Background metadata completion status must load explicitly");
requireText('tag_write_enabled: $("metadataTagWriteEnabledInput").checked', "Metadata Tag writeback setting must be saved");

requireText("window.FnAudioNative", "Android bridge detection is missing");
requireText("function resolvedDeviceTarget", "Device menu must recover from a stale target during discovery");
requireText('return targets.some(target => String(target.id || "") === targetId) ? targetId : "local"', "Device menu must fall back to local playback when the current target is unavailable");
requireText("async function validateRestoredPlaybackTarget()", "Restored Android playback must validate a saved remote target");
requireText("await validateRestoredPlaybackTarget();", "Playback restoration must wait for remote-target validation");
requireText('data.error === "playback_target_not_found"', "A disappeared Renderer must fall back without exposing an internal error");
if (!mainActivity.includes("public boolean onJsAlert") || !mainActivity.includes('.setTitle("fnAudio")')) {
  throw new Error("Android JavaScript alerts must use the fnAudio title instead of the WebView default");
}
requireText('nativePlaybackCall("setQueue"', "Native queue handoff is missing");
requireText('function nativeQueueNeedsRestore()', "Android playback must detect an empty native queue after app restore");
requireText('nativeLoadQueue(false, 0, true);', "Restored Android sessions must prepare the native queue without auto-playing");
requireText('else if (nativeQueueNeedsRestore()) nativeLoadQueue(true, 0, true);', "Android play must rehydrate an empty native queue before starting");
const nativeQueueSignatureSource = source.match(/function nativeQueueSignature\(rows = nativeQueueItems\(\)\) \{[\s\S]*?\n\}/);
if (!nativeQueueSignatureSource) throw new Error("Native queue signature helper is missing");
const nativeQueueSignatureContext = { JSON };
vm.runInNewContext(`${nativeQueueSignatureSource[0]}; globalThis.signature = nativeQueueSignature;`, nativeQueueSignatureContext);
const nativeQueueSignature = nativeQueueSignatureContext.signature;
assert.notEqual(
  nativeQueueSignature([{ id: "a\\u0000b", uri: "c" }]),
  nativeQueueSignature([{ id: "a", uri: "b\\u0000c" }]),
  "opaque native queue fields must not collide in the bridge signature",
);
if (!nativeBridge.includes("dispatchWhenReady")) throw new Error("Android native playback commands must survive MediaController startup races");
if (nativeBridge.includes("mainHandler.post")) {
  throw new Error("Native playback commands must use the bounded controller dispatch queue directly");
}
if (!nativeBridge.includes('httpRequestHandler.rejectRequestJson(safeRequestId, "原生网络请求输入过大")')) {
  throw new Error("Rejected native HTTP inputs must complete the matching WebView request immediately");
}
if (!nativeBridge.includes("if (httpRequestHandler == null) return;")) {
  throw new Error("Native HTTP bridge must tolerate a missing request handler");
}
if (!mainActivity.includes("public void rejectRequestJson(String requestId, String message)")) {
  throw new Error("Android native HTTP rejection must preserve the actual validation reason");
}
if (!mainActivity.includes("final String responsePayload = serialized;")
    || !mainActivity.includes("final int responseChunkCount = total;")
    || !mainActivity.includes("responsePayload.substring(start, end)")
    || !mainActivity.includes("index < responseChunkCount")) {
  throw new Error("Native HTTP response fallback values must be finalized before the UI lambda captures them");
}
if (!/for \(int index = 0; index < responseChunkCount; index\+\+\) \{[\s\S]*?if \(destroyed \|\| webView == null \|\| isFinishing\(\) \|\| isDestroyed\(\)\) return;[\s\S]*?try \{\s*webView\.evaluateJavascript/.test(mainActivity)) {
  throw new Error("Native HTTP chunk delivery must recheck WebView lifecycle for every chunk");
}
if (!/private void injectNativeEnvironment\(\)[\s\S]*?if \(destroyed \|\| webView == null \|\| isFinishing\(\) \|\| isDestroyed\(\)\) return;[\s\S]*?try \{[\s\S]*?evaluateJavascript/.test(mainActivity)) {
  throw new Error("Native environment injection must tolerate Activity/WebView teardown races");
}
if (!/target\.post\(\(\) -> \{[\s\S]*?if \(destroyed \|\| webView != target \|\| isFinishing\(\) \|\| isDestroyed\(\)\) return;[\s\S]*?try \{[\s\S]*?target\.evaluateJavascript/.test(mainActivity)) {
  throw new Error("Playback state delivery must stop before touching a WebView during Activity teardown");
}
if (!nativeBridge.includes("safeTimeMs(positionSeconds)") || !nativeBridge.includes("safeTimeMs(durationSeconds)")) {
  throw new Error("Remote state updates must reject non-finite or oversized timing values");
}
if (!nativeBridge.includes("long positionMs = safeTimeMs(positionSeconds)")
    || !nativeBridge.includes("controller.seekTo(safeTimeMs(seconds))")
    || !nativeBridge.includes("Double.isFinite(value)")) {
  throw new Error("Native playback controls must sanitize non-finite timing and volume values");
}
requireText('function isApeTrack(item)', "APE playback needs an explicit source-format detector");
requireText('params.set("transcode", "ape_flac")', "Browser and Android native playback must request lossless APE-to-FLAC conversion");
requireText("window.fnAudioNativeOnState", "Native playback state callback is missing");
requireText("window.fnAudioNativeOnHttpResponse", "Native authenticated HTTP callback is missing");
if (!/function nativeHttpResponse\(payload\)[\s\S]*?typeof source\.body === "string"[\s\S]*?catch \(_\) \{ headers = new Headers\(\); \}/.test(source)
    || !/try \{ pending\.resolve\(nativeHttpResponse\(result\)\); \}[\s\S]*?pending\.reject\(error instanceof Error/.test(source)) {
  throw new Error("Malformed native HTTP responses must settle their promise instead of hanging the WebView request");
}
requireText("window.FnAudioNative.requestJson", "Native authenticated HTTP request handoff is missing");
requireText("MAX_NATIVE_HTTP_CHUNKS = 256", "Native HTTP chunk transfers need a hard chunk-count limit");
requireText("MAX_NATIVE_HTTP_CHUNK_CHARS = 256 * 1024", "Native HTTP chunks need a per-fragment size limit");
requireText("MAX_NATIVE_HTTP_RESPONSE_CHARS = 4 * 1024 * 1024", "Native HTTP transfers need a cumulative size limit");
requireText("MAX_NATIVE_HTTP_REQUESTS = 32", "WebView native HTTP promises need a hard in-flight limit");
requireText("function evictOldestNativeHttpRequest()", "WebView native HTTP requests need bounded eviction");
requireText("while (nativeHttpRequests.size >= MAX_NATIVE_HTTP_REQUESTS) evictOldestNativeHttpRequest();", "WebView native HTTP requests must evict before adding a new promise");
requireText("function clearNativeHttpRequest(requestId, pending, error = null)", "Native HTTP request cleanup must release bridge and listener ownership");
requireText("nativeHttpResponseChunks.size >= 32", "Native HTTP transfer bookkeeping needs a bounded entry count");
requireText("timer: setTimeout(() => clearNativeHttpTransfer(key, transfer), 60000)", "Incomplete native HTTP transfers need timeout cleanup");
requireText("function nativeAbortError()", "Native HTTP aborts need an older-WebView-compatible error fallback");
requireText("function clearNativeHttpTransfer(key, transfer)", "Native HTTP transfer cleanup must release timer ownership");
if (!mainActivity.includes("MAX_NATIVE_HTTP_SERIALIZED_RESPONSE_CHARS = 4 * 1024 * 1024")
    || !mainActivity.includes("MAX_NATIVE_HTTP_RESPONSE_CHUNKS = 256")
    || !mainActivity.includes("MAX_NATIVE_HTTP_REQUEST_ID_CHARS = 256")
    || !mainActivity.includes("if (safeRequestId.isEmpty() || safeRequestId.length() > MAX_NATIVE_HTTP_REQUEST_ID_CHARS) return;")
    || !mainActivity.includes("nativeHttpCalls.put(safeRequestId, call)")) {
  throw new Error("Android native responses need serialized-size and chunk-count limits");
}
if (!mainActivity.includes("响应序列化结果过大") || !mainActivity.includes("fallback.put(\"networkError\"")) {
  throw new Error("Oversized native responses must downgrade without recursive failure delivery");
}
if (!mainActivity.includes("MAX_NATIVE_HTTP_CALLS = 32")
    || !mainActivity.includes("previous = nativeHttpCalls.put(safeRequestId, call)")
    || !mainActivity.includes("if (previous != null) previous.cancel()")) {
  throw new Error("Native HTTP calls must bound in-flight memory and cancel request-id replacements");
}
if (!mainActivity.includes("if (destroyed) return;\n        String serialized = payload.toString();")
    || !/for \(Call call : nativeHttpCalls\.values\(\)\) call\.cancel\(\);\s*nativeHttpCalls\.clear\(\);/.test(mainActivity)) {
  throw new Error("Native HTTP responses must be dropped after Activity teardown and calls cancelled before cleanup");
}
if (!mainActivity.includes("MAX_NATIVE_HTTP_HEADERS_BYTES = 64 * 1024")
    || !mainActivity.includes("MAX_NATIVE_HTTP_REQUEST_BODY_BYTES = 512 * 1024")
    || !mainActivity.includes("private static int utf8Length(@Nullable String value)" )
    || !mainActivity.includes("原生请求头过大")
    || !mainActivity.includes("原生请求体过大")) {
  throw new Error("Native HTTP bridge requests need hard input-size limits");
}
const nativeBridgeSource = fs.readFileSync(path.join(__dirname, "..", "..", "android-client", "app", "src", "main", "java", "com", "fnaudio", "client", "web", "NativePlaybackBridge.java"), "utf8");
if (!nativeBridgeSource.includes("MAX_REQUEST_ID_LENGTH = 256")
    || !nativeBridgeSource.includes("safeRequestId.length() > MAX_REQUEST_ID_LENGTH")
    || nativeBridgeSource.includes("boundedText(requestId, MAX_REQUEST_ID_LENGTH)")) {
  throw new Error("Native bridge request IDs must use one strict non-truncating limit");
}
if (!nativeBridgeSource.includes("private static boolean boundedUtf8(String value, int maxBytes)")
    || nativeBridgeSource.includes("value.getBytes(java.nio.charset.StandardCharsets.UTF_8)")
    || !nativeBridgeSource.includes("if (bytes > maxBytes) return false;")) {
  throw new Error("Native bridge UTF-8 limits must stop before allocating a full byte-array copy");
}
if (!nativeBridgeSource.includes("if (value == null || maxLength < 0 || value.length() > maxLength) return \"\";")) {
  throw new Error("Native bridge text limits must reject oversized input before trim allocates a copy");
}
if (!mainActivity.includes("OkHttpClient client = webResourceClient;")
    || !mainActivity.includes("client.newCall(builder.build()).execute()")
    || !mainActivity.includes("catch (IOException | RuntimeException exception)")) {
  throw new Error("WebView resource interception must survive teardown and invalid request-header races");
}
requireText('apiFetch("api/playback/queue"', "Playback queue POST must use the native-aware API client");
requireText('apiFetch("api/state/user"', "User-state POST must use the native-aware API client");
[
  "api/playback/control",
  "api/transcode/warm",
  "api/config/library",
  "api/config/metadata",
  "api/playback/target",
  "api/playback/load",
].forEach(endpoint => requireText(`apiFetch("${endpoint}"`, `${endpoint} must use the native-aware API client`));
requireText('state.playSourceKind = "native"', "Native playback mode is not selected in loadCurrent");
requireText("nativeRemoteEnter(true)", "Remote playback must synchronize the native media session");
requireText("state.remoteLoadController = null;", "Remote load requests need explicit cancellation ownership");
requireText("function cancelRemoteLoad()", "Playback-target switches must cancel a stale remote load");
requireText("state.remoteLoadPromise === loadPromise", "Remote load completion must clear only its own in-flight promise");
requireText("state.remoteLoadController === controller", "Remote load responses must verify their cancellation owner before updating UI state");
requireText("loaded && loadToken === state.playbackLoadToken", "A completed remote load must not schedule status work for a newer track");
requireText("command_id: playbackCommandId()", "Remote loads must carry an idempotency ticket");
requireText("generation: Number(state.remoteGeneration || 0)", "Remote loads must carry their session generation");
requireText("engine_epoch: Number(state.remoteEngineEpoch || 0)", "Remote loads must carry their engine epoch");
requireText("state.remoteCueSegment = data.cue_segment === true", "Remote load responses must not truthiness-coerce cue segment flags");
requireText("state.shuffle = playback.shuffle === true", "Restored playback must not truthiness-coerce shuffle flags");
requireText("item?.is_dsd === true", "Playback format decisions must not truthiness-coerce DSD flags");
requireText("data.ready === true", "Transcode readiness must not truthiness-coerce response flags");
requireText("const refreshing = data.refreshing === true", "Device refresh state must not truthiness-coerce response flags");
requireText("state.libraryStatus?.scanning === true", "Library scanning state must not truthiness-coerce response flags");
requireText("data.available === true", "DLNA availability must not truthiness-coerce response flags");
requireText("data.pending === true", "Lyrics pending state must not truthiness-coerce response flags");
requireText("data.tag_write_in_progress === true", "Metadata write state must not truthiness-coerce response flags");
requireText("snapshot.available !== true", "Native playback state must reject non-boolean availability");
requireText("state.hostPlaybackSession?.available === true", "Host playback activation must reject non-boolean availability");
requireText("currentItem()?.cue_track === true", "Remote cue detection must reject non-boolean cue flags");
requireText("data.refreshing !== true", "Device recovery polling must reject non-boolean refresh flags");
requireText("data.available !== true", "DLNA diagnostics must reject non-boolean availability");
requireText("currentItem()?.is_dsd === true", "DSD error handling must reject non-boolean format flags");
requireText("data.scanning === true", "Library loading state must reject non-boolean scan flags");
requireText("setPlayButton(snapshot.playing === true)", "Native playback UI must reject non-boolean playing flags");
requireText("state.nativePlayback.playing === true", "Native playback resume must reject non-boolean playing flags");
requireText("if (nativePlaybackAvailable()) return state.nativePlayback.playing === true", "Media session playback state must reject non-boolean playing flags");
requireText("data.ok !== true", "Metadata retry and lookup success must reject non-boolean success flags");
requireText("item.cue_track === true ? playbackSeconds", "Transcode transitions must reject non-boolean cue flags");
requireText("currentItem()?.cue_track === true && !state.remoteCueSegment", "Seek transitions must reject non-boolean cue flags");
requireText("item.cue_track === true", "CUE URL and playback decisions must reject non-boolean cue flags");
requireText("item?.cue_track === true", "CUE progress and seek decisions must reject non-boolean cue flags");
requireText("state.remoteGeneration = Date.now() & 0x7fffffff", "Remote entry must establish one shared session generation");
requireText("nativeRemoteUpdate()", "Remote playback status must update the native media session");
if (!playbackService.includes('sessionIdentityMatches(data, "remote_command")')) {
  throw new Error("Remote command responses must use the same session identity gate as status snapshots");
}
if (!playbackService.includes("commandTicketMatches(data)")
    || !playbackService.includes("ticket.isEmpty() || !commandId.equals(ticket)")
    || !playbackService.includes("stale_command_ticket")) {
  throw new Error("Remote command responses must reject mismatched command tickets");
}
if (!playbackService.includes("commandId.isEmpty() || ticket.isEmpty() || !commandId.equals(ticket)")) {
  throw new Error("Remote command responses must reject empty command ids");
}
if (!playbackService.includes("remoteCommandStillCurrent(")
    || !playbackService.includes("commandTargetId, commandGeneration, commandEngineEpoch")
    || !playbackService.includes("clearPendingCommandIfCurrent(")
    || !playbackService.includes("clearPendingCommandIfCurrent(action, requestToken, commandTargetId, commandGeneration, commandEngineEpoch)")) {
  throw new Error("Delayed Android command responses must not clear or apply a newer session");
}
if (!playbackService.includes("private volatile boolean remotePollInFlight")
    || !playbackService.includes("@Nullable private volatile Call remoteStatusCall")
    || !playbackService.includes("cancelRemoteStatusRequest()")
    || !playbackService.includes("remoteRequestStillCurrent(requestTargetId, requestGeneration, requestEngineEpoch)")
    || !playbackService.includes("boolean ownsRequest = remoteStatusCall == call")
    || !playbackService.includes("if (ownsRequest && remoteStatusCall == call)")
    || !playbackService.includes("if (ownsRequest && remoteRequestStillCurrent(")) {
  throw new Error("Remote status polling must cancel and ignore callbacks from an obsolete session");
}
if (playbackService.includes(
    "&& remotePlayer != null && remotePlayer.isRemoteActive()\n                && remoteSessionStillCurrent(generation, engineEpoch);"
)) {
  throw new Error("OkHttp callbacks must not read RemotePlaybackPlayer state off its application thread");
}
if (!playbackService.includes("boolean current = remoteCommandStillCurrent(")
    || !playbackService.includes("if (current) remoteBridgeUpdateAt = 0L")
    || !playbackService.includes("readRemoteEventStream(activeCall, response, targetId, eventGeneration, eventEngineEpoch)")
    || !playbackService.includes("!remoteRequestStillCurrent(targetId, generation, engineEpoch)")) {
  throw new Error("Remote command and event callbacks must not affect a newer session");
}
if (!artworkLoader.includes("pendingFutures")
    || !artworkLoader.includes("future.cancel(false)")
    || !artworkLoader.includes("Artwork loader is shut down")
    || !artworkLoader.includes("synchronized (lifecycleLock)")) {
  throw new Error("Artwork loader shutdown must complete pending Media3 futures");
}
if (!playbackService.includes('if (success && sessionIdentityMatches(data, "remote_command") && commandTicketMatches(data))')) {
  throw new Error("Remote command snapshots must only be applied after a successful HTTP response");
}
if (!playbackService.includes("boolean applied = false")
    || !playbackService.includes("remote_command failed: stale_response")
    || !playbackService.includes("if (success && applied)")) {
  throw new Error("Remote command confirmation logs must reflect snapshot acceptance, not HTTP status alone");
}
if (!playbackService.includes("session_create begin")
    || !playbackService.includes("session_ready media_session")
    || !playbackService.includes("remote_notification published")
    || !playbackService.includes("remote_event_stream failed: network")) {
  throw new Error("Android MediaSession lifecycle and event-stream failures must be observable");
}
if (!playbackService.includes('service_start ignored: unknown_action')) {
  throw new Error("Unknown PlaybackService start actions must expose a bounded diagnostic");
}
const createAt = playbackService.indexOf("session_create begin");
const playerAt = playbackService.indexOf("player = new ExoPlayer.Builder", createAt);
const sessionAt = playbackService.indexOf("mediaSession = new MediaSession.Builder", createAt);
const readyAt = playbackService.indexOf("session_ready media_session", createAt);
const restoreAt = playbackService.indexOf("restorePersistedRemoteSession", readyAt);
if (createAt < 0 || playerAt < 0 || sessionAt < 0 || readyAt < 0 || restoreAt < 0
    || !(createAt < playerAt && playerAt < sessionAt && sessionAt < readyAt && readyAt < restoreAt)) {
  throw new Error("PlaybackService must build player and MediaSession before restoring remote state");
}
const remoteEnableAt = Math.max(
  playbackService.indexOf("private void enableRemoteMode"),
  playbackService.indexOf("private boolean enableRemoteMode")
);
const remoteGuardAt = playbackService.indexOf("if (destroyed || mediaSession == null || remotePlayer == null || player == null)", remoteEnableAt);
const remoteActivateAt = playbackService.indexOf("remotePlayer.activate(", remoteEnableAt);
const remoteNotifyAt = playbackService.indexOf("ensureRemoteForeground();", remoteActivateAt);
if (remoteEnableAt < 0 || remoteGuardAt < 0 || remoteActivateAt < 0 || remoteNotifyAt < 0
    || !(remoteGuardAt < remoteActivateAt && remoteActivateAt < remoteNotifyAt)) {
  throw new Error("Remote mode must validate a ready session before activation and notification");
}
if (!playbackService.includes("remote_command failed: http_")
    || !playbackService.includes("if (success)")) {
  throw new Error("Android command diagnostics must distinguish HTTP failure from confirmation");
}
if (!playbackService.includes("restorePersistedRemoteSession()")
    || !playbackService.includes("persistRemoteSession(items, intent)")
    || !playbackService.includes("MAX_PERSISTED_QUEUE_BYTES")
    || !playbackService.includes("remote_session_restore failed: invalid_snapshot")) {
  throw new Error("Remote MediaSession must persist and safely restore a bounded session snapshot");
}
if (!playbackService.includes("PERSISTED_SESSION_SCHEMA")
    || !playbackService.includes("MAX_PERSISTED_SESSION_AGE_MS")
    || !playbackService.includes("expired_snapshot")) {
  throw new Error("Persisted remote sessions must have a bounded schema and expiry policy");
}
if (!playbackService.includes("remote_session_restore checkpointed: service_destroy")
    || !playbackService.includes("if (remotePlayer != null && remotePlayer.isRemoteActive()) {\n            // Persist before releasing")) {
  throw new Error("PlaybackService must checkpoint an active remote session before destruction");
}
if (!playbackService.includes("persistRemoteStatus(true)")
    || !playbackService.includes("if (synchronous)")
    || !playbackService.includes("editor.commit()")) {
  throw new Error("Service-destroy recovery checkpoints must use synchronous persistence");
}
if (!playbackService.includes("persistRemoteStatus();")
    || !playbackService.includes("ensureRemoteForeground();")
    || !playbackService.includes("remotePlayer.updateStatus(index, positionMs, durationMs, playing);")
    || !playbackService.includes("persistRemoteStatus();")) {
  throw new Error("Remote command and task-removal paths must persist the latest native state");
}
requireText("api/playback/events", "Remote playback must prefer the server-sent playback event stream");
requireText("startRemoteEventStream", "Remote event stream lifecycle is missing");
requireText("stopRemoteEventStream", "Remote event stream must close when the target changes");
requireText("!state.remoteEventConnected", "HTTP remote polling must be a disconnected-event-stream fallback");
const targetSwitchStart = source.indexOf("async function selectPlaybackTarget(id, name)");
const targetSwitchEnd = source.indexOf("function cancelRemoteLoad()", targetSwitchStart);
const targetSwitch = source.slice(targetSwitchStart, targetSwitchEnd);
const targetAccepted = targetSwitch.indexOf("if (!response.ok || data.ok !== true)");
if (targetAccepted < 0 || targetSwitch.includes('remoteControl("stop"') || targetSwitch.includes("stopLocalAudio();")) {
  throw new Error("Playback target switching must rely on the server transaction and must not issue a second stop");
}
if (!source.includes("async function remoteControl(action, position = null, quiet = false) {\n  if (state.deviceSwitchInFlight || !isRemoteTarget()) return false;")
    || !source.includes("async function coreControl(action, position = null, payload = {}) {\n  if (state.deviceSwitchInFlight) return false;")
    || !source.includes("async function pushToDevice(deviceId, item = currentItem()) {\n  if (state.deviceSwitchInFlight) return false;")
    || !source.includes('$("playBtn").onclick = () => {\n  if (state.deviceSwitchInFlight) return;')) {
  throw new Error("Playback commands must be gated while a target transition is in flight");
}
requireText("A browser tab/WebView is a controller", "Leaving a browser/WebView must not stop a remote output");
requireText('window.addEventListener("pageshow", () => { if (isRemoteTarget()) startRemoteEventStream(); });', "Restored browser pages must reconnect their playback event stream");
requireText('globalThis.fnAudioUiSyncScheduler.create', "UI synchronization must use the visibility-aware scheduler module");
if (source.includes('navigator.sendBeacon("api/playback/control"')) {
  throw new Error("Page unload must not stop a remote DAC or Renderer");
}
requireText("command_id: commandId", "Web remote commands must be retry-safe with a command id");
requireText("command_id: playbackCommandId()", "Core controls must be retry-safe with a command id");
requireText('coreControl("repeat", null, { repeat: nextRepeat })', "Repeat changes must send an explicit three-state target");
if (!index.includes('repeat_mode_policy.js?v=__FNAUDIO_ASSET_BUILD__')
    || !repeatPolicy.includes('off: "all", all: "one", one: "off"')
    || !source.includes('fnAudioRepeatModePolicy.next(repeat)')) {
  throw new Error("Repeat mode must cycle off, queue, single through the policy module");
}
if (!repeatPolicy.includes('one: "单曲循环"')) {
  throw new Error("The player must expose the single-repeat state");
}
requireText('[$("repeatBtn"), $("repeatIcon")], [$("mobileRepeatBtn"), $("mobileRepeatIcon")]', "Desktop and mobile repeat buttons must share the current mode");
requireText('function repeatIconMarkup(repeat)', "Repeat states must be rendered with distinct icons");
if (!repeatPolicy.includes('return loop;') || !repeatPolicy.includes('M11 8h2v8h-2v-5')) {
  throw new Error("Repeat icons must be supplied by the repeat policy module");
}
if (source.includes('M4 4l16 16')) {
  throw new Error("Repeat-off must use the neutral Volumio icon rather than a crossed-out repeat icon");
}
requireText('icon.innerHTML = repeatIconMarkup(repeat)', "Repeat controls must redraw their icons after each state change");
requireText("remoteSnapshotFromCore", "Web remote controls must apply the authoritative response snapshot");
if (!/const targetId = remoteDeviceId\(\);[\s\S]*?target_id: targetId[\s\S]*?if \(targetId !== remoteDeviceId\(\)\) return true;[\s\S]*?remoteSnapshotFromCore\(data\.core, targetId\)/.test(source)) {
  throw new Error("Late remote control responses must remain bound to the target that issued the command");
}
requireText("changedTrack && !isRemoteTarget()", "Remote next/previous must not reload a track already advanced by the output");
requireText('nativePlaybackCall("seekTo", seconds)', "Native seek handoff is missing");
requireText('function seekPercent(value, fallback = 0)', "Seek percentage normalization is missing");
requireText('const percent = seekPercent(value)', "Seek preview/commit does not normalize the slider value");
requireText('nativePlaybackCall("setVolume", value)', "Native volume handoff is missing");
requireText("const nativeCurrentId = String(state.nativePlayback.mediaId", "Native current track must win during page restore");
requireText('queue: queue.map(item => String(item?.id || "")).filter(Boolean)', "Playback queue POST must send compact track IDs");
requireText('"X-FnAudio-Path": "/api/playback/queue"', "Playback queue POST must carry a CGI route fallback");
requireText('播放队列保存失败（HTTP ${response.status}）', "Queue failures must expose the HTTP status");
if (!source.includes("looksLikeHtml")) throw new Error("Queue failures should identify an HTML CGI fallback response");
requireText("window.fnAudioHandleAndroidBack", "Android back must be handled inside fnAudio before the task is backgrounded");

if (!cgi.includes('"fnaudio_trim_token"') || !cgi.includes('os.environ.get("HTTP_COOKIE"')) {
  throw new Error("CGI Android session-cookie fallback is missing");
}

if (!nativeBridge.includes("requestJson(String requestId") || !mainActivity.includes("sameProfileOrigin(requestProfile, uri)")
    || !mainActivity.includes('builder.header("Authorization", "Bearer " + requestProfile.token)')) {
  throw new Error("Android authenticated HTTP bridge must attach the fnOS token in the native client");
}
if (!playbackService.includes("notificationProvider.setSmallIcon(R.drawable.ic_notification)")
    || !nativeBridge.includes("metadata.setArtworkUri(fallbackArtworkUri)")
    || !nativeBridge.includes("media_placeholder_white.png")
    || !nativeBridge.includes("paint.setColor(Color.WHITE)")
    || !notificationIcon.includes('android:strokeColor="#FFFFFFFF"')) {
  throw new Error("The native media notification must use a white fallback icon when track artwork is missing");
}
if (!playbackService.includes("setBitmapLoader(bitmapLoader)")
    || !artworkLoader.includes("X-Fnaudio-Trim-Token")
    || !artworkLoader.includes("media-artwork")) {
  throw new Error("Android media notifications must load authenticated artwork through the private cache");
}
if (!artworkLoader.includes('profileScope.length() + ":" + profileScope + uri.toString()')
    || !coverCache.includes('sha256(scope.length() + ":" + scope + key)')
    || !mainActivity.includes('profileCacheScope(requestProfile)')) {
  throw new Error("Android artwork caches must be isolated by connection profile");
}
if (!playbackService.includes("ACTION_REMOTE_ENABLE")
    || !playbackService.includes("mediaSession.setPlayer(remotePlayer)")
    || !playbackService.includes("pollRemoteStatus()")
    || !playbackService.includes("if (remotePlayer != null && remotePlayer.isRemoteActive())")
    || !playbackService.includes("ensureRemoteForeground()")
    || !playbackService.includes("super.onTaskRemoved(rootIntent)")) {
  throw new Error("PlaybackService must keep a native remote MediaSession alive and synchronized");
}
if (!playbackService.includes("private void enableLocalMode() {\n        mainHandler.removeCallbacks(remotePoll);\n        mainHandler.removeCallbacks(remoteEventRetry);")) {
  throw new Error("Switching back to local playback must cancel queued remote SSE retries");
}
if (!playbackService.includes("setSessionActivity(sessionActivity)")
    || !playbackService.includes("PARTIAL_WAKE_LOCK")
    || !playbackService.includes("createWifiLock")
    || !playbackService.includes("return START_STICKY")) {
  throw new Error("PlaybackService must retain the session entry point and network locks for background remote playback");
}
if (!playbackService.includes('payload.put("repeat", repeatName(remotePlayer.getRequestedRepeatMode()))')
    || !playbackService.includes('payload.put("shuffle", remotePlayer.isRequestedShuffleEnabled())')
    || !remotePlayer.includes("getRemoteRepeatMode()")
    || !remotePlayer.includes("isRemoteShuffleEnabled()")) {
  throw new Error("Remote MediaSession repeat/shuffle commands must carry explicit target values");
}
if (!nativeBridge.includes("enterRemoteMode(String targetId")
    || !nativeBridge.includes("updateRemoteState(String targetId")
    || !nativeBridge.includes("exitRemoteMode()")) {
  throw new Error("Android bridge must expose remote MediaSession synchronization");
}
if (!nativeBridge.includes("updateRemoteState(String targetId, int currentIndex, double positionSeconds,")
    || !nativeBridge.includes("long generation")
    || !nativeBridge.includes("EXTRA_SESSION_GENERATION")
    || !nativeBridge.includes("EXTRA_ENGINE_EPOCH")) {
  throw new Error("Android remote state bridge must carry generation and engine epoch");
}
if (!playbackService.includes("EXTRA_SESSION_GENERATION")
    || !playbackService.includes("EXTRA_ENGINE_EPOCH")
    || !playbackService.includes("payload.put(\"generation\", commandGeneration)")
    || !playbackService.includes("payload.put(\"engine_epoch\", commandEngineEpoch)")) {
  throw new Error("Android remote commands must carry the current session generation and engine epoch");
}
if (!playbackService.includes("remote_enable rejected: session_not_ready")
    || !playbackService.includes("remote_enable rejected: empty_queue")
    || !playbackService.includes("remote_command failed: network")) {
  throw new Error("Android MediaSession failures must expose bounded diagnostic reasons");
}
if (!playbackService.includes("remote_session_restore failed: invalid_snapshot oversized")
    || !playbackService.includes("remote_session_restore failed: invalid_snapshot schema")
    || !playbackService.includes("remote_session_restore failed: invalid_snapshot payload")) {
  throw new Error("Persisted remote-session restore must expose bounded rejection reasons");
}
if (!playbackService.includes("remoteLastStateVersion")
    || !playbackService.includes("remote_status ignored: stale_state")
    || !playbackService.includes("stateVersion < remoteLastStateVersion")) {
  throw new Error("Android remote state must reject out-of-order snapshots");
}
if (!playbackService.includes("remote_status ignored: stale_generation")
    || !playbackService.includes("remote_status ignored: stale_engine_epoch")) {
  throw new Error("Android remote state must reject snapshots from an older session identity");
}
if (!playbackService.includes('Log.w(TAG, "remote_status failed: network")')
    || !playbackService.includes('Log.w(TAG, "remote_status failed: http_" + response.code())')
    || !playbackService.includes('Log.w(TAG, "remote_status failed: invalid_payload")')) {
  throw new Error("Android remote status polling must expose bounded network, HTTP, and payload failures");
}
if (!playbackService.includes('if (data == null) {\n            Log.w(TAG, "remote_status failed: invalid_payload");')) {
  throw new Error("Null remote status snapshots must expose an invalid-payload diagnostic");
}
if (!playbackService.includes("MAX_REMOTE_RESPONSE_BYTES")
    || !playbackService.includes("readBoundedBody(response.body(), MAX_REMOTE_RESPONSE_BYTES)")
    || playbackService.includes("response.body().string()")) {
  throw new Error("Android remote JSON responses must use a bounded body reader");
}
if (!playbackService.includes("MAX_REMOTE_EVENT_BYTES")
    || !playbackService.includes("remote_event_stream failed: oversized_payload")
    || !playbackService.includes("remote_event_stream failed: invalid_payload")
    || !playbackService.includes("int dataBytes = 0")
    || !playbackService.includes("dataBytes += fragment.getBytes(StandardCharsets.UTF_8).length")) {
  throw new Error("Android SSE parsing must bound event frames and expose malformed payloads");
}
const sseOpenAt = playbackService.indexOf('Log.d(TAG, "remote_event_stream opened")');
const sseSnapshotAt = playbackService.indexOf("JSONObject snapshot", sseOpenAt);
const sseHeaderConnectedAt = playbackService.indexOf("remoteEventConnected = true", sseOpenAt);
const sseSnapshotConnectedAt = playbackService.indexOf("remoteEventConnected = true", sseSnapshotAt);
if (sseOpenAt < 0 || sseSnapshotAt < 0
    || (sseHeaderConnectedAt >= 0 && sseHeaderConnectedAt < sseSnapshotAt)
    || sseSnapshotConnectedAt < 0) {
  throw new Error("Android SSE must keep HTTP fallback polling until a valid snapshot arrives");
}
if (!nativeBridge.includes("ContextCompat.startForegroundService")
    || nativeBridge.includes("if (playing) ContextCompat.startForegroundService")
    || !playbackService.includes("REMOTE_BRIDGE_GRACE_MS")
    || !playbackService.includes("sinceBridge < REMOTE_BRIDGE_GRACE_MS")
    || !playbackService.includes("api/playback/events?target_id=")
    || !playbackService.includes('.header("Accept", "text/event-stream")')
    || !playbackService.includes("readRemoteEventStream")
    || !playbackService.includes("remoteEventConnected")
    || !playbackService.includes('final String commandId = "android-" + UUID.randomUUID()')
    || !playbackService.includes('payload.put("command_id", commandId)')) {
    throw new Error("Android remote playback must use foreground MediaSession service with bridge-aware fallback polling");
}
if (!playbackService.includes("ensureRemoteForeground()")
    || !playbackService.includes("DefaultMediaNotificationProvider.Builder(this)")
    || !playbackService.includes("setShowNotificationForIdlePlayer(SHOW_NOTIFICATION_FOR_IDLE_PLAYER_ALWAYS)")
    || !playbackService.includes("void onUpdateNotification(MediaSession session, boolean startInForegroundRequired)")
    || !playbackService.includes("publishRemoteMediaNotification()")
    || !playbackService.includes("new Notification.MediaStyle().setMediaSession(mediaSession.getPlatformToken())")
    || !remotePlayer.includes("onRemoteCommand")) {
  throw new Error("Remote mode must immediately create a Media3 foreground media notification and route media buttons to the backend");
}
if (!playbackService.includes("MAX_NOTIFICATION_ARTWORK_BYTES")
    || !playbackService.includes("decodeNotificationArtwork(metadata.artworkData)")
    || !playbackService.includes("builder.setLargeIcon(artwork)")) {
  throw new Error("Remote notifications must attach bounded track artwork when available");
}
if (!playbackService.includes("remote_notification failed: publish")
    || !playbackService.includes("catch (RuntimeException ignored)")) {
  throw new Error("Foreground notification publication failures must be contained and observable");
}
const statusUpdateAt = playbackService.indexOf("remotePlayer.updateStatus(safeIndex, positionMs, durationMs, playing);");
const statusNotifyAt = playbackService.indexOf("ensureRemoteForeground();", statusUpdateAt);
const coreUpdateAt = playbackService.indexOf("remotePlayer.updateStatus(index, positionMs, durationMs, playing);");
const coreNotifyAt = playbackService.indexOf("ensureRemoteForeground();", coreUpdateAt);
if (statusUpdateAt < 0 || statusNotifyAt < statusUpdateAt
    || coreUpdateAt < 0 || coreNotifyAt < coreUpdateAt) {
  throw new Error("Authoritative remote updates must immediately refresh the foreground notification");
}
if (!playbackService.includes("setAction(MainActivity.ACTION_OPEN_PLAYBACK)")
    || !mainActivity.includes('ACTION_OPEN_PLAYBACK.equals(intent.getAction())) return;')
    || !mainActivity.includes("setIntent(intent);\n        recreate();")) {
  throw new Error("Notification app-return intents must restore the existing WebView without recreating it");
}
if (!remotePlayer.includes("extends SimpleBasePlayer")
    || !remotePlayer.includes("No media is downloaded or decoded")
    || !remotePlayer.includes("onRemoteCommand")) {
  throw new Error("Remote playback must use a metadata-only Media3 player");
}
if (!remotePlayer.includes("The backend is authoritative")
    || !remotePlayer.includes("Do not optimistically mutate the")) {
  throw new Error("Remote MediaSession must wait for backend confirmation before publishing state");
}
if (!remotePlayer.includes("getRequestedRepeatMode()")
    || !remotePlayer.includes("isRequestedShuffleEnabled()")
    || !remotePlayer.includes("updateModes(int repeatMode, boolean shuffle)")) {
  throw new Error("Remote repeat/shuffle commands must carry requested values and apply confirmed modes");
}
if (!remotePlayer.includes("pendingPlayWhenReady")
    || !remotePlayer.includes("if (pendingPlayWhenReady != null && pendingPlayWhenReady == playWhenReady)")) {
  throw new Error("Repeated play/pause callbacks must be coalesced until authoritative confirmation");
}
if (!remotePlayer.includes("pendingRepeatMode")
    || !remotePlayer.includes("pendingShuffle")
    || !remotePlayer.includes("if (pendingRepeatMode != null && pendingRepeatMode == repeatMode)")
    || !remotePlayer.includes("if (pendingShuffle != null && pendingShuffle == shuffleModeEnabled)")) {
  throw new Error("Repeated repeat/shuffle callbacks must be coalesced until confirmation");
}
if (!remotePlayer.includes("protected ListenableFuture<?> handlePrepare()")
    || !remotePlayer.includes("protected ListenableFuture<?> handleStop()")
    || !remotePlayer.includes("pendingPlayWhenReady = null;")
    || !remotePlayer.includes("pendingSeekIndex = null;")
    || !remotePlayer.includes("pendingSeekPositionMs = null;")
    || !remotePlayer.includes("pendingStopToken = nextToken();")
    || !remotePlayer.includes("commandHandler.onRemoteCommand(\"stop\", null, null, pendingStopToken);")) {
  throw new Error("Prepare/stop commands must share the play pending-race guard");
}
if (!remotePlayer.includes("clearPendingCommand(String action, long requestToken)")
    || !playbackService.includes("remotePlayer.clearPendingCommand(action, requestToken)")) {
  throw new Error("Failed remote commands must release pending gates so the user can retry");
}
if (!mainActivity.includes("dispatchBackToFnAudio()") || !mainActivity.includes("handleRootBackPress()")
    || !mainActivity.includes("APP 即将退出，再按一次返回登录界面") || mainActivity.includes("moveTaskToBack(true)")) {
  throw new Error("MainActivity must delegate internal back navigation and require a second root back press before returning to login");
}
if (!/public void dispatchWhenReady\(NativePlaybackBridge\.ControllerCommand command\)[\s\S]*?uiHandler\.post\(\(\) -> \{[\s\S]*?if \(destroyed \|\| isFinishing\(\) \|\| isDestroyed\(\)\) return;/.test(mainActivity)) {
  throw new Error("Queued native playback commands must be dropped during Activity teardown");
}
if (!/webBackDispatchInFlight = false;[\s\S]*?if \(destroyed \|\| isFinishing\(\) \|\| isDestroyed\(\)\) return;/.test(mainActivity)) {
  throw new Error("Delayed WebView back callbacks must be ignored after MainActivity destruction");
}
if (!/private void dispatchBackToFnAudio\(\)[\s\S]*?if \(destroyed \|\| webView == null \|\| isFinishing\(\) \|\| isDestroyed\(\)\)[\s\S]*?try \{[\s\S]*?evaluateJavascript[\s\S]*?catch \(RuntimeException ignored\)/.test(mainActivity)) {
  throw new Error("Back navigation WebView calls must tolerate teardown exceptions");
}
if (!loginActivity.includes("startActivity(intent);\n                finish();")) {
  throw new Error("LoginActivity must leave the Android back stack after a successful login");
}
if (!loginActivity.includes("EXTRA_SKIP_AUTO_RESUME") || !mainActivity.includes("LoginActivity.EXTRA_SKIP_AUTO_RESUME")) {
  throw new Error("Returning to the login screen must suppress automatic reconnection");
}
if (!connectionProfile.includes("matchesConnection(") || !loginActivity.includes("profileIdForForm(")
    || !loginActivity.includes("editingExistingProfile")) {
  throw new Error("Changing the server identity must create a new connection unless the user explicitly edits a saved one");
}
if (!historyActivity.includes("RESULT_NEW_PROFILE") || !historyActivity.includes("returnNewProfile()")
    || !loginActivity.includes("clearFormForNewProfile()") || !historyLayout.includes('android:id="@+id/historyAddButton"')) {
  throw new Error("Connection history must provide an explicit new-connection action");
}
if (!source.includes('$("mobileModeBtn").onclick = toggleMp3Transcode')
    || !source.includes('function toggleMp3Transcode()')
    || !source.includes('localStorage.setItem("fnaudio.mp3Transcode", state.mp3Transcode ? "1" : "0")')) {
  throw new Error("Mobile top bar must expose the persisted MP3 transcoding control");
}

console.log("Android bridge and CGI auth regression checks passed.");
