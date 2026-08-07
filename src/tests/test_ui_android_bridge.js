const fs = require("fs");
const path = require("path");

const source = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "app.js"), "utf8");
const cgi = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "cgi_proxy.py"), "utf8");
const mainActivity = fs.readFileSync(path.join(
  __dirname, "..", "..", "android-client", "app", "src", "main", "java", "com", "fnaudio", "client", "ui", "MainActivity.java"
), "utf8");
const loginActivity = fs.readFileSync(path.join(
  __dirname, "..", "..", "android-client", "app", "src", "main", "java", "com", "fnaudio", "client", "ui", "LoginActivity.java"
), "utf8");

function requireText(text, message) {
  if (!source.includes(text)) throw new Error(message || `Missing app.js text: ${text}`);
}

requireText("window.FnAudioNative", "Android bridge detection is missing");
requireText('nativePlaybackCall("setQueue"', "Native queue handoff is missing");
requireText("window.fnAudioNativeOnState", "Native playback state callback is missing");
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

if (!mainActivity.includes("dispatchBackToFnAudio()") || !mainActivity.includes("moveTaskToBack(true)")) {
  throw new Error("MainActivity must delegate back presses to fnAudio and background the task at the root");
}
if (!loginActivity.includes("startActivity(intent);\n                finish();")) {
  throw new Error("LoginActivity must leave the Android back stack after a successful login");
}

console.log("Android bridge and CGI auth regression checks passed.");
