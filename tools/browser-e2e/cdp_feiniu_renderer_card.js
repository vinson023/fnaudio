// 在飞牛 app（com.trim.app）的 WebView 里复验 0.2.173：
// 「作为播放器被其他设备推送」开关与「Renderer 名称」是否真的挨在一起。
//
// R621 的负责人原话是「renderer开关应该和renderer名称放在一起，不然用户两头找」。
// R619 已经把它们放进了同一个 settings-block，但中间夹着两行 <small> 和一段
// dialog-help，所以「同一分类」这个断言过不了这一关。这里量的是距离：
//   ① 两者是否同处一张 .renderer-identity 卡片；
//   ② 开关下沿到名称上沿的像素间隔（要求为负或很小，也就是视觉上贴着）；
//   ③ 两者之间有没有段落或小字（DOM 顺序 + 是否有 <p>/<small> 插在中间）。
//
// 用法（adb forward 必须在同一次调用里建立）：
//   adb forward tcp:9225 localabstract:webview_devtools_remote_<pidof com.trim.app>
//   node tools/browser-e2e/cdp_feiniu_renderer_card.js 9225 <输出png>
const fs = require("fs");
const path = require("path");
const http = require("http");

const PORT = process.argv[2] || "9225";
const SHOT = process.argv[3] || "artifacts/0.2.173/device/feiniu-renderer-card.png";

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
  const versions = Array.from(document.querySelectorAll("script[src], link[href]"))
    .map(node => node.getAttribute("src") || node.getAttribute("href"))
    .filter(value => value && value.includes("v="));
  out.assetVersions = Array.from(new Set(versions.map(value => (value.match(/v=[^&]+/) || [""])[0]))).slice(0, 4);

  const rect = node => {
    if (!node) return null;
    const box = node.getBoundingClientRect();
    return { x: Math.round(box.x), y: Math.round(box.y), w: Math.round(box.width), h: Math.round(box.height), bottom: Math.round(box.bottom) };
  };

  const dialog = document.getElementById("folderDialog");
  if (dialog && !dialog.open) {
    try { await window.openFolderBrowser(); } catch (error) { out.openError = String(error && error.message); }
  }
  await new Promise(resolve => setTimeout(resolve, 400));
  const tab = document.querySelector('[data-settings-tab="playback"]');
  if (tab) { tab.click(); await new Promise(resolve => setTimeout(resolve, 300)); }
  if (typeof window.openSettingsDetail === "function") window.openSettingsDetail();
  await new Promise(resolve => setTimeout(resolve, 600));

  const switchInput = document.getElementById("dlnaRendererEnabledInput");
  const nameInput = document.getElementById("rendererNameInput");
  out.switchExists = Boolean(switchInput);
  out.nameExists = Boolean(nameInput);
  if (!switchInput || !nameInput) return out;

  out.switchRect = rect(switchInput);
  out.nameRect = rect(nameInput);
  out.nameLabelRect = rect(nameInput.closest("label"));

  // ① 同一张卡片
  const card = switchInput.closest(".renderer-identity");
  out.cardExists = Boolean(card);
  out.nameInSameCard = Boolean(card && card.contains(nameInput));
  out.cardRect = rect(card);
  const cardBox = card ? card.getBoundingClientRect() : null;
  const nameBox = nameInput.getBoundingClientRect();
  const switchBox = switchInput.getBoundingClientRect();
  out.cardContainsBoth = Boolean(cardBox &&
    cardBox.top <= switchBox.top && cardBox.bottom >= nameBox.bottom &&
    cardBox.left <= switchBox.left && cardBox.right >= nameBox.right);

  // ② 距离：开关（整行 label）下沿到名称标签上沿
  const switchRow = switchInput.closest("label");
  const switchRowBox = switchRow ? switchRow.getBoundingClientRect() : switchBox;
  const nameLabelBox = nameInput.closest("label").getBoundingClientRect();
  out.gapPx = Math.round(nameLabelBox.top - switchRowBox.bottom);
  out.verticalSpanPx = Math.round(nameLabelBox.bottom - switchRowBox.top);

  // ③ 中间有没有东西：DOM 顺序 + 是否夹着 <p>/<small>
  const order = switchRow.compareDocumentPosition(nameInput);
  out.switchBeforeName = Boolean(order & Node.DOCUMENT_POSITION_FOLLOWING);
  const between = [];
  if (card) {
    const walker = document.createTreeWalker(card, NodeFilter.SHOW_ELEMENT);
    let seenSwitch = false;
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (node === switchRow) { seenSwitch = true; continue; }
      if (!seenSwitch) continue;
      if (node === nameInput || node.contains(nameInput)) break;
      if (["P", "SMALL"].includes(node.tagName) && (node.textContent || "").trim()) {
        between.push(node.tagName + ":" + node.textContent.replace(/\\s+/g, " ").trim().slice(0, 30));
      }
    }
  }
  out.blockersBetween = between;

  // 可见与可点
  out.switchVisible = Boolean(switchBox.width && switchBox.height);
  const hit = document.elementFromPoint(switchBox.x + switchBox.width / 2, switchBox.y + switchBox.height / 2);
  out.switchHitIsSelf = hit === switchInput || Boolean(hit && switchInput.contains(hit));
  out.switchChecked = switchInput.checked;
  out.nameVisible = Boolean(nameBox.width && nameBox.height);

  // 说明文字现在应当整段落在卡片底部，也就是在名称之后
  const help = card ? card.querySelector("p.dialog-help") : null;
  out.helpAfterName = Boolean(help && (help.compareDocumentPosition(nameInput) & Node.DOCUMENT_POSITION_PRECEDING));
  out.helpText = help ? help.textContent.replace(/\\s+/g, " ").trim().slice(0, 80) : null;
  out.cardText = card ? card.textContent.replace(/\\s+/g, " ").trim().slice(0, 160) : null;

  // 反证：这两件东西都还在「播放与输出」里，服务与网络里没有
  const pane = switchInput.closest("[id^='settings-pane']");
  out.paneId = pane ? pane.id : null;
  const networkPane = document.getElementById("settings-pane-network");
  out.stillInNetworkPane = Boolean(networkPane && networkPane.querySelector("#dlnaRendererEnabledInput"));
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

  await send("Page.enable");
  await send("Page.reload", { ignoreCache: true });
  await new Promise(resolve => setTimeout(resolve, 7000));
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
    fs.mkdirSync(path.dirname(SHOT), { recursive: true });
    fs.writeFileSync(SHOT, Buffer.from(data, "base64"));
    console.log("screenshot:", SHOT);
  }
  process.exit(0);
})().catch(error => { console.error("ERR", error.message); process.exit(2); });
