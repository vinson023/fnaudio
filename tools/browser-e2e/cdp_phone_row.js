// 曲目行只画出封面，文字单元格不见。逐个读行内子元素的矩形与样式。
const http = require("http");

const EXPR = [
  "(() => {",
  "  const row = document.querySelector('.album-detail-tracks .track');",
  "  if (!row) return JSON.stringify({ missing: true });",
  "  const cs = getComputedStyle(row);",
  "  const kids = [...row.children].map((el) => {",
  "    const r = el.getBoundingClientRect();",
  "    const s = getComputedStyle(el);",
  "    return {",
  "      cls: (el.className || '').toString(),",
  "      rect: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)],",
  "      display: s.display, vis: s.visibility, op: s.opacity, color: s.color,",
  "      overflow: s.overflow, gridColumn: s.gridColumn, position: s.position,",
  "      text: (el.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 40),",
  "      html: el.outerHTML.slice(0, 260),",
  "    };",
  "  });",
  "  return JSON.stringify({",
  "    rowRect: (() => { const r = row.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; })(),",
  "    gridTemplate: cs.gridTemplateColumns,",
  "    rowDisplay: cs.display, rowOverflow: cs.overflow, rowColor: cs.color,",
  "    kids,",
  "  });",
  "})()",
].join("\n");

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
  if (res.result.exceptionDetails) {
    console.log("exception:", JSON.stringify(res.result.exceptionDetails).slice(0, 500));
  } else {
    console.log(JSON.stringify(JSON.parse(res.result.result.value), null, 2));
  }
  ws.close();
})();
