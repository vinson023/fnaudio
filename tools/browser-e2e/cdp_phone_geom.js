// 同一次 CDP 会话里：取几何 + 命中测试 + 截图，避免「DOM 有、屏幕没有」是
// 时间差或缩放造成的错觉。
const http = require("http");
const fs = require("fs");

const EXPR = String.raw`(() => {
  const R = (el) => {
    const r = el.getBoundingClientRect();
    return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)];
  };
  const style = (el) => {
    const s = getComputedStyle(el);
    return { display: s.display, vis: s.visibility, op: s.opacity, color: s.color, bg: s.backgroundColor, z: s.zIndex, pos: s.position, tr: s.transform === "none" ? "none" : s.transform, filter: s.filter };
  };
  const pick = (sel) => {
    const el = document.querySelector(sel);
    return el ? { sel, rect: R(el), style: style(el), text: (el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 60) } : { sel, missing: true };
  };
  const pts = [[200, 400], [200, 500], [300, 300], [60, 300]].map(([x, y]) => {
    const el = document.elementFromPoint(x, y);
    return { x, y, hit: el ? el.tagName.toLowerCase() + "." + (el.className || "").toString().slice(0, 40) : null };
  });
  return JSON.stringify({
    dpr: window.devicePixelRatio,
    inner: [window.innerWidth, window.innerHeight],
    scroll: { y: window.scrollY, docH: document.documentElement.scrollHeight },
    parts: [
      pick(".album-detail-layout"),
      pick(".album-detail-sidebar"),
      pick(".album-detail-sidebar .album-detail-cover"),
      pick(".album-detail-sidebar h2"),
      pick(".album-detail-sidebar p"),
      pick(".album-detail-tracks"),
      pick(".album-detail-breadcrumb"),
      pick(".album-detail-table-head"),
      pick(".album-detail-tracks .track"),
      pick("#libraryScroll"),
      pick("#trackList"),
    ],
    points: pts,
    trackListScrollTop: (document.getElementById("trackList") || {}).scrollTop,
    libScrollTop: (document.getElementById("libraryScroll") || {}).scrollTop,
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
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  let id = 0;
  const pending = new Map();
  ws.addEventListener("message", (e) => {
    const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  });
  const send = (method, params) => new Promise((r) => { const mid = ++id; pending.set(mid, r); ws.send(JSON.stringify({ id: mid, method, params })); });
  await new Promise((r) => ws.addEventListener("open", r));

  const res = await send("Runtime.evaluate", { expression: EXPR, returnByValue: true });
  console.log(JSON.stringify(JSON.parse(res.result.result.value), null, 2));

  const shot = await send("Page.captureScreenshot", { format: "png" });
  if (shot.result && shot.result.data) {
    fs.writeFileSync("D:/fnAudio/artifacts/0.2.167/phone-detail-cdp.png", Buffer.from(shot.result.data, "base64"));
    console.log("screenshot saved");
  } else {
    console.log("screenshot failed:", JSON.stringify(shot).slice(0, 300));
  }
  ws.close();
})();
