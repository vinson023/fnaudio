const fs = require("fs");
const path = require("path");

const source = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "app.js"), "utf8");
const cgi = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "cgi_proxy.py"), "utf8");
const mainActivity = fs.readFileSync(path.join(
  __dirname, "..", "..", "android-client", "app", "src", "main", "java", "com", "fnaudio", "client", "ui", "MainActivity.java"
), "utf8");
const nativeBridge = fs.readFileSync(path.join(
  __dirname, "..", "..", "android-client", "app", "src", "main", "java", "com", "fnaudio", "client", "web", "NativePlaybackBridge.java"
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

function requireText(text, message) {
  if (!source.includes(text)) throw new Error(message || `Missing app.js text: ${text}`);
}

requireText("window.FnAudioNative", "Android bridge detection is missing");
requireText('nativePlaybackCall("setQueue"', "Native queue handoff is missing");
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
  "api/fnos/shared-folders/sync",
  "api/playback/target",
  "api/playback/load",
].forEach(endpoint => requireText(`apiFetch("${endpoint}"`, `${endpoint} must use the native-aware API client`));
requireText('state.playSourceKind = "native"', "Native playback mode is not selected in loadCurrent");
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

console.log("Android bridge and CGI auth regression checks passed.");
