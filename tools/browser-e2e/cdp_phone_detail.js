// 手机 WebView 不支持 Playwright 的 connectOverCDP（"Browser context management
// is not supported"），所以直接走页面级 DevTools 协议：拿 webSocketDebuggerUrl，
// 用 Runtime.evaluate 在页面里跑一段取值脚本。
const http = require("http");

const EXPRESSION = String.raw`(() => {
  const info = (el, label) => {
    if (!el) return { label, missing: true };
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return {
      label,
      tag: el.tagName.toLowerCase(),
      cls: (el.className || "").toString().slice(0, 70),
      rect: { top: Math.round(r.top), h: Math.round(r.height), w: Math.round(r.width) },
      display: s.display,
      color: s.color,
      bg: s.backgroundColor,
      fontSize: s.fontSize,
      overflow: s.overflowY,
      text: (el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 120),
      childCount: el.children.length,
    };
  };
  const layout = document.querySelector(".album-detail-layout");
  const sidebar = document.querySelector(".album-detail-sidebar");
  const rows = [...document.querySelectorAll(".album-detail-layout .track, .album-detail-layout .track-row")];
  const list = document.getElementById("trackList");
  return JSON.stringify({
    url: location.href,
    htmlClass: document.documentElement.className,
    bodyClass: document.body.className,
    layout: info(layout, "layout"),
    layoutHTML: layout ? layout.outerHTML.slice(0, 1600) : null,
    sidebar: info(sidebar, "sidebar"),
    sidebarHTML: sidebar ? sidebar.outerHTML.slice(0, 900) : null,
    mainHTML: layout ? (layout.querySelector(".album-detail-main") || {}).outerHTML : null,
    trackRowCount: rows.length,
    firstRows: rows.slice(0, 3).map((r) => info(r, "row")),
    list: info(list, "trackList"),
    listClass: list ? list.className : null,
  });
})()`;

function getJson(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let body = "";
      res.on("data", (c) => (body += c));
      res.on("end", () => resolve(JSON.parse(body)));
    }).on("error", reject);
  });
}

(async () => {
  const list = await getJson("http://127.0.0.1:9222/json/list");
  const target = list.find((t) => t.type === "page");
  console.log("target:", target.url);
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  let id = 0;
  const pending = new Map();
  ws.addEventListener("message", (event) => {
    const msg = JSON.parse(event.data);
    if (msg.id && pending.has(msg.id)) {
      pending.get(msg.id)(msg);
      pending.delete(msg.id);
    }
  });
  const send = (method, params) => new Promise((resolve) => {
    const mid = ++id;
    pending.set(mid, resolve);
    ws.send(JSON.stringify({ id: mid, method, params }));
  });

  await new Promise((resolve) => ws.addEventListener("open", resolve));
  const result = await send("Runtime.evaluate", { expression: EXPRESSION, returnByValue: true, awaitPromise: false });
  if (result.result && result.result.exceptionDetails) {
    console.log("exception:", JSON.stringify(result.result.exceptionDetails).slice(0, 600));
  } else {
    const value = result.result.result.value;
    console.log(JSON.stringify(JSON.parse(value), null, 2));
  }
  ws.close();
})();
