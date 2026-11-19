// 把修好的两条规则注入手机 WebView，验证曲目行的标题是否回到整行宽度。
const http = require("http");
const fs = require("fs");

const CSS = `@media(max-width:760px){
  .album-detail-track-list .track{grid-template-columns:minmax(0,1fr)!important}
  .album-detail-track-list .track-main{grid-column:1 / -1!important}
}`;

const MEASURE = [
  "(() => {",
  "  const row = document.querySelector('.album-detail-track-list .track');",
  "  const main = row && row.querySelector('.track-main');",
  "  const title = row && row.querySelector('.track-title');",
  "  const rect = (el) => { if (!el) return null; const r = el.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; };",
  "  return JSON.stringify({",
  "    row: rect(row), main: rect(main), title: rect(title),",
  "    rowTemplate: row ? getComputedStyle(row).gridTemplateColumns : null,",
  "    titleText: title ? (title.textContent || '').trim().slice(0, 30) : null,",
  "    titleVisible: title ? getComputedStyle(title).display !== 'none' : false,",
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

  const before = await send("Runtime.evaluate", { expression: MEASURE, returnByValue: true });
  console.log("注入前:", before.result.result.value);

  const inject = [
    "(() => {",
    "  const s = document.getElementById('detail-row-fix') || document.createElement('style');",
    "  s.id = 'detail-row-fix';",
    "  s.textContent = " + JSON.stringify(CSS) + ";",
    "  document.head.appendChild(s);",
    "  return 'injected';",
    "})()",
  ].join("\n");
  await send("Runtime.evaluate", { expression: inject, returnByValue: true });
  await new Promise((r) => setTimeout(r, 600));

  const after = await send("Runtime.evaluate", { expression: MEASURE, returnByValue: true });
  console.log("注入后:", after.result.result.value);

  const shot = await send("Page.captureScreenshot", { format: "png" });
  if (shot.result && shot.result.data) {
    fs.writeFileSync("D:/fnAudio/artifacts/0.2.167/phone-detail-fixed.png", Buffer.from(shot.result.data, "base64"));
    console.log("screenshot saved");
  }
  ws.close();
})();
