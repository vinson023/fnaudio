// 在飞牛 app（com.trim.app）的 WebView 里复验 0.2.171：
// ① 页面是不是新版；② 「作为播放器被其他设备推送」开关是否在「播放与输出」里、
// 可见、可点、命中自身；③ 它有没有还留在「服务与网络」里。
//
// 用法（adb forward 必须在同一次调用里建立）：
//   adb forward tcp:9223 localabstract:webview_devtools_remote_<pidof com.trim.app>
//   node tools/browser-e2e/cdp_feiniu_playback.js 9223 <输出png>
const fs = require("fs");
const http = require("http");

const PORT = process.argv[2] || "9223";
const SHOT = process.argv[3] || "artifacts/0.2.171/device/feiniu-playback.png";

function getJson(url) {
  return new Promise((resolve, reject) => {
    http.get(url, res => {
      let body = "";
      res.on("data", chunk => { body += chunk; });
      res.on("end", () => { try { resolve(JSON.parse(body)); } catch (error) { reject(error); } });
    }).on("error", reject);
  });
}

const INSPECT = `(async () => {
  const out = {};
  out.href = location.href;
  out.hasBridge = Boolean(window.FnAudioNative);
  out.title = document.title;
  const versions = Array.from(document.querySelectorAll("script[src], link[href]"))
    .map(node => node.getAttribute("src") || node.getAttribute("href"))
    .filter(value => value && value.includes("v="));
  out.assetVersions = Array.from(new Set(versions.map(value => (value.match(/v=[^&]+/) || [""])[0]))).slice(0, 4);

  const rect = node => {
    if (!node) return null;
    const box = node.getBoundingClientRect();
    return { x: Math.round(box.x), y: Math.round(box.y), w: Math.round(box.width), h: Math.round(box.height) };
  };

  // 打开设置并切到「播放与输出」
  const dialog = document.getElementById("folderDialog");
  if (dialog && !dialog.open) {
    try { await window.openFolderBrowser(); } catch (error) { out.openError = String(error && error.message); }
  }
  await new Promise(resolve => setTimeout(resolve, 400));
  const tab = document.querySelector('[data-settings-tab="playback"]');
  out.playbackTabExists = Boolean(tab);
  if (tab) {
    tab.click();
    await new Promise(resolve => setTimeout(resolve, 300));
  }
  if (typeof window.openSettingsDetail === "function") window.openSettingsDetail();
  await new Promise(resolve => setTimeout(resolve, 600));

  const shell = document.querySelector("#folderDialog .settings-shell");
  out.shellIsDetail = shell ? shell.classList.contains("is-detail") : null;

  const input = document.getElementById("dlnaRendererEnabledInput");
  out.inputExists = Boolean(input);
  if (input) {
    const box = input.getBoundingClientRect();
    out.inputRect = rect(input);
    out.inputVisible = Boolean(box.width && box.height);
    out.inputChecked = input.checked;
    out.inputDisabled = input.disabled;
    const hit = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2);
    out.inputHit = hit ? (hit.id || hit.tagName) : null;
    out.inputHitIsSelf = hit === input || Boolean(hit && input.contains(hit));
    const label = input.closest("label");
    out.inputLabelText = label ? label.textContent.replace(/\\s+/g, " ").trim().slice(0, 60) : null;
    const block = input.closest("[data-settings-block]");
    out.inputBlock = block ? block.dataset.settingsBlock : null;
    const pane = input.closest("[id^='settings-pane']");
    out.inputPaneId = pane ? pane.id : null;
    out.inputPaneDisplay = pane ? getComputedStyle(pane).display : null;
  }
  // 同一块里的邻居，用来确认「开关 + Renderer 名称」确实在一起
  const identity = document.querySelector('[data-settings-block="playback-identity"]');
  out.identityBlockText = identity ? identity.textContent.replace(/\\s+/g, " ").trim().slice(0, 120) : null;
  out.rendererNameInputExists = Boolean(document.getElementById("rendererNameInput"));
  // 反证：服务与网络里不该再有它
  const networkPane = document.getElementById("settings-pane-network");
  out.switchStillInNetworkPane = Boolean(networkPane && networkPane.querySelector("#dlnaRendererEnabledInput"));
  out.railSummary = (document.getElementById("settingsSummaryPlayback") || {}).textContent || null;
  return out;
})()`;

(async () => {
  const list = await getJson(`http://127.0.0.1:${PORT}/json/list`);
  const target = list.find(item => item.type === "page");
  if (!target) { console.error("ERR no page target"); process.exit(3); }

  const ws = new WebSocket(target.webSocketDebuggerUrl);
  let id = 0;
  const pending = new Map();
  const send = (method, params) => new Promise(resolve => {
    const mid = ++id;
    pending.set(mid, resolve);
    ws.send(JSON.stringify({ id: mid, method, params: params || {} }));
  });
  ws.addEventListener("message", event => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) { pending.get(message.id)(message); pending.delete(message.id); }
  });
  if (ws.readyState !== 1) {
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("ws open timeout")), 8000);
      ws.addEventListener("open", () => { clearTimeout(timer); resolve(); }, { once: true });
    });
  }

  // 先重载，确保拿到的是刚装上的 0.2.171 静态资源
  await send("Page.enable");
  await send("Page.reload", { ignoreCache: true });
  await new Promise(resolve => setTimeout(resolve, 7000));

  // 等页面把设置入口挂上（重载后脚本是异步加载的）
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const probe = await send("Runtime.evaluate", {
      expression: "document.readyState + '|' + typeof window.openFolderBrowser",
      returnByValue: true,
    });
    const value = probe.result && probe.result.result && probe.result.result.value;
    if (value === "complete|function") break;
    await new Promise(resolve => setTimeout(resolve, 1000));
  }

  const result = await send("Runtime.evaluate", { expression: INSPECT, returnByValue: true, awaitPromise: true });
  const value = result.result && result.result.result && result.result.result.value;
  if (value === undefined) { console.log(JSON.stringify(result, null, 2)); process.exit(2); }
  console.log(JSON.stringify(value, null, 2));

  const shot = await send("Page.captureScreenshot", { format: "png" });
  const data = shot.result && shot.result.data;
  if (data) {
    fs.mkdirSync(require("path").dirname(SHOT), { recursive: true });
    fs.writeFileSync(SHOT, Buffer.from(data, "base64"));
    console.log("screenshot:", SHOT);
  }
  process.exit(0);
})().catch(error => { console.error("ERR", error.message); process.exit(2); });
