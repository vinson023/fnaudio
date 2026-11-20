// 量「应用窗口拉到最窄时右下角图标会不会左移」。
//
// 负责人的原话是「应用窗口拉到最窄时右下角图标排往左移动」。R603 定位到
// fnos-theme.css 里 761–1100px 那段把 .player-actions 设成了居中，改成 end。
// 这个探针在真机 WebView 里用 CDP 的 Emulation.setDeviceMetricsOverride
// 逐个宽度改视口，量「播放条右边缘 − 最后一个可见图标右边缘」，并读出
// 该元素实际生效的 justify-content —— 只看样式表写了什么是不够的，
// 断点叠在一起时真正生效的可能是另一条规则。
//
// 用法（adb forward 必须在同一次调用里建立）：
//   adb forward tcp:9226 localabstract:webview_devtools_remote_<pidof com.trim.app>
//   node tools/browser-e2e/cdp_player_actions_widths.js 9226
const http = require("http");

const PORT = process.argv[2] || "9226";
const WIDTHS = [1440, 1200, 1100, 1000, 900, 820, 780, 761];

function getJson(url) {
  return new Promise((resolve, reject) => {
    http.get(url, res => {
      let body = "";
      res.on("data", chunk => { body += chunk; });
      res.on("end", () => { try { resolve(JSON.parse(body)); } catch (error) { reject(error); } });
    }).on("error", reject);
  });
}

const MEASURE = `(() => {
  const player = document.querySelector(".player");
  const actions = document.querySelector(".player-actions");
  if (!player || !actions) return { error: "player or actions missing" };
  const visible = Array.from(actions.querySelectorAll("button")).filter(node => node.offsetParent !== null);
  const last = visible[visible.length - 1];
  const style = getComputedStyle(actions);
  const playerBox = player.getBoundingClientRect();
  const lastBox = last ? last.getBoundingClientRect() : null;
  return {
    viewportWidth: window.innerWidth,
    justify: style.justifyContent,
    display: style.display,
    visibleButtons: visible.length,
    lastButtonId: last ? (last.id || last.getAttribute("aria-label") || last.className) : null,
    gapToPlayerRight: lastBox ? Math.round((playerBox.right - lastBox.right) * 10) / 10 : null,
    actionsRight: Math.round(actions.getBoundingClientRect().right * 10) / 10,
    playerRight: Math.round(playerBox.right * 10) / 10,
  };
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
  await send("Runtime.enable");

  const rows = [];
  for (const width of WIDTHS) {
    await send("Emulation.setDeviceMetricsOverride", {
      width, height: 900, deviceScaleFactor: 1, mobile: false,
    });
    await new Promise(resolve => setTimeout(resolve, 450));
    const probe = await send("Runtime.evaluate", { expression: MEASURE, returnByValue: true });
    const value = probe.result && probe.result.result && probe.result.result.value;
    rows.push({ width, ...(value || {}) });
  }
  await send("Emulation.clearDeviceMetricsOverride");

  const base = rows[0];
  const report = rows.map(row => ({
    ...row,
    driftFrom1440: row.gapToPlayerRight == null || base.gapToPlayerRight == null
      ? null
      : Math.round((row.gapToPlayerRight - base.gapToPlayerRight) * 10) / 10,
  }));
  console.log(JSON.stringify(report, null, 1));
  const worst = report.reduce((acc, row) => (
    row.driftFrom1440 == null ? acc : Math.max(acc, Math.abs(row.driftFrom1440))
  ), 0);
  console.log(`WORST_DRIFT_PX ${worst}`);
  process.exit(worst <= 3 ? 0 : 4);
})().catch(error => { console.error("ERR", error && error.message); process.exit(5); });
