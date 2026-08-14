const fs = require("fs");
const path = require("path");

const source = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "app.js"), "utf8");
const cgi = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "cgi_proxy.py"), "utf8");
const mainActivity = fs.readFileSync(path.join(
  __dirname, "..", "..", "android-client", "app", "src", "main", "java", "com", "fnaudio", "client", "ui", "MainActivity.java"
), "utf8");
if (mainActivity.includes("if (isDirectImageResource(request.getUrl())) return null")) {
  throw new Error("Private covers must pass through the authenticated Android resource proxy");
}
if (!mainActivity.includes("CookieManager.getInstance().getCookie(uri.toString())")) {
  throw new Error("Web-session cover requests must recover cookies from CookieManager");
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
const notificationIcon = fs.readFileSync(path.join(
  __dirname, "..", "..", "android-client", "app", "src", "main", "res", "drawable", "ic_notification.xml"
), "utf8");
const loginActivity = fs.readFileSync(path.join(
  __dirname, "..", "..", "android-client", "app", "src", "main", "java", "com", "fnaudio", "client", "ui", "LoginActivity.java"
), "utf8");
const historyActivity = fs.readFileSync(path.join(
  __dirname, "..", "..", "android-client", "app", "src", "main", "java", "com", "fnaudio", "client", "ui", "ConnectionHistoryActivity.java"
), "utf8");
const connectionProfile = fs.readFileSync(path.join(
  __dirname, "..", "..", "android-client", "app", "src", "main", "java", "com", "fnaudio", "client", "data", "ConnectionProfile.java"
), "utf8");
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

function requireText(text, message) {
  if (!source.includes(text)) throw new Error(message || `Missing app.js text: ${text}`);
}

requireText("window.FnAudioNative", "Android bridge detection is missing");
requireText("function resolvedDeviceTarget", "Device menu must recover from a stale target during discovery");
requireText('return targets.some(target => String(target.id || "") === targetId) ? targetId : "local"', "Device menu must fall back to local playback when the current target is unavailable");
requireText('nativePlaybackCall("setQueue"', "Native queue handoff is missing");
requireText('function isApeTrack(item)', "APE playback needs an explicit source-format detector");
requireText('params.set("transcode", "ape_flac")', "Browser and Android native playback must request lossless APE-to-FLAC conversion");
requireText("window.fnAudioNativeOnState", "Native playback state callback is missing");
requireText("window.fnAudioNativeOnHttpResponse", "Native authenticated HTTP callback is missing");
requireText("window.FnAudioNative.requestJson", "Native authenticated HTTP request handoff is missing");
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
requireText("nativeRemoteUpdate()", "Remote playback status must update the native media session");
requireText("api/playback/events", "Remote playback must prefer the server-sent playback event stream");
requireText("startRemoteEventStream", "Remote event stream lifecycle is missing");
requireText("stopRemoteEventStream", "Remote event stream must close when the target changes");
requireText("!state.remoteEventConnected", "HTTP remote polling must be a disconnected-event-stream fallback");
requireText("A browser tab/WebView is a controller", "Leaving a browser/WebView must not stop a remote output");
requireText('window.addEventListener("pageshow", () => { if (isRemoteTarget()) startRemoteEventStream(); });', "Restored browser pages must reconnect their playback event stream");
if (source.includes('navigator.sendBeacon("api/playback/control"')) {
  throw new Error("Page unload must not stop a remote DAC or Renderer");
}
requireText("command_id: commandId", "Web remote commands must be retry-safe with a command id");
requireText("command_id: playbackCommandId()", "Core controls must be retry-safe with a command id");
requireText('coreControl("repeat", null, { repeat: nextRepeat })', "Repeat changes must send an explicit three-state target");
requireText('return { off: "all", all: "one", one: "off" }', "Repeat mode must cycle off, queue, single");
requireText('one: "单曲循环"', "The player must expose the single-repeat state");
requireText('[$("repeatBtn"), $("repeatIcon")], [$("mobileRepeatBtn"), $("mobileRepeatIcon")]', "Desktop and mobile repeat buttons must share the current mode");
requireText('function repeatIconMarkup(repeat)', "Repeat states must be rendered with distinct icons");
requireText('return loop;', "Repeat-off and queue-repeat must use the standard Volumio repeat silhouette");
requireText('M11 8h2v8h-2v-5', "Single-repeat icon must visibly show one track");
if (source.includes('M4 4l16 16')) {
  throw new Error("Repeat-off must use the neutral Volumio icon rather than a crossed-out repeat icon");
}
requireText('icon.innerHTML = repeatIconMarkup(repeat)', "Repeat controls must redraw their icons after each state change");
requireText("remoteSnapshotFromCore", "Web remote controls must apply the authoritative response snapshot");
requireText("changedTrack && !isRemoteTarget()", "Remote next/previous must not reload a track already advanced by the output");
requireText('nativePlaybackCall("seekTo", seconds)', "Native seek handoff is missing");
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

if (!nativeBridge.includes("requestJson(String requestId") || !mainActivity.includes("sameProfileOrigin(uri)")
    || !mainActivity.includes('builder.header("Authorization", "Bearer " + profile.token)')) {
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
if (!playbackService.includes("ACTION_REMOTE_ENABLE")
    || !playbackService.includes("mediaSession.setPlayer(remotePlayer)")
    || !playbackService.includes("pollRemoteStatus()")
    || !playbackService.includes("if (remotePlayer != null && remotePlayer.isRemoteActive()) return")) {
  throw new Error("PlaybackService must keep a native remote MediaSession alive and synchronized");
}
if (!playbackService.includes('payload.put("repeat", repeatName')
    || !playbackService.includes('payload.put("shuffle", remotePlayer.isRemoteShuffleEnabled())')
    || !remotePlayer.includes("getRemoteRepeatMode()")
    || !remotePlayer.includes("isRemoteShuffleEnabled()")) {
  throw new Error("Remote MediaSession repeat/shuffle commands must carry explicit target values");
}
if (!nativeBridge.includes("enterRemoteMode(String targetId")
    || !nativeBridge.includes("updateRemoteState(String targetId")
    || !nativeBridge.includes("exitRemoteMode()")) {
  throw new Error("Android bridge must expose remote MediaSession synchronization");
}
if (!nativeBridge.includes("ContextCompat.startForegroundService")
    || nativeBridge.includes("if (playing) ContextCompat.startForegroundService")
    || !playbackService.includes("REMOTE_BRIDGE_GRACE_MS")
    || !playbackService.includes("sinceBridge < REMOTE_BRIDGE_GRACE_MS")
    || !playbackService.includes("api/playback/events?target_id=")
    || !playbackService.includes('.header("Accept", "text/event-stream")')
    || !playbackService.includes("readRemoteEventStream")
    || !playbackService.includes("remoteEventConnected")
    || !playbackService.includes('payload.put("command_id", "android-" + UUID.randomUUID())')) {
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
if (!mainActivity.includes("dispatchBackToFnAudio()") || !mainActivity.includes("handleRootBackPress()")
    || !mainActivity.includes("APP 即将退出，再按一次返回登录界面") || mainActivity.includes("moveTaskToBack(true)")) {
  throw new Error("MainActivity must delegate internal back navigation and require a second root back press before returning to login");
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
