// 用 CDP 在手机 WebView 里点开一张多曲目专辑，注入修复后逐行量宽度。
const http = require("http");
const fs = require("fs");

const CSS = `@media(max-width:760px){
  .album-detail-track-list .track{grid-template-columns:minmax(0,1fr)!important}
  .album-detail-track-list .track-main{grid-column:1 / -1!important}
}`;

const MEASURE = [
  "(() => {",
  "  const rows = [...document.querySelectorAll('.album-detail-track-list .track')];",
  "  const rect = (el) => { const r = el.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; };",
  "  return JSON.stringify({",
  "    title: (document.querySelector('.album-detail-sidebar h2') || {}).textContent,",
  "    rowCount: rows.length,",
  "    rows: rows.slice(0, 6).map((row) => {",
  "      const main = row.querySelector('.track-main');",
  "      const title = row.querySelector('.track-title');",
  "      return {",
  "        main: main ? rect(main) : null,",
  "        title: title ? rect(title) : null,",
  "        text: (title ? title.textContent : '').trim().slice(0, 24),",
  "        template: getComputedStyle(row).gridTemplateColumns,",
  "      };",
  "    }),",
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
  const evaluate = async (expression) => {
    const res = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    return res.result && res.result.result ? res.result.result.value : null;
  };
  await new Promise((r) => ws.addEventListener("open", r));

  // 注入修复
  await evaluate([
    "(() => {",
    "  const s = document.getElementById('detail-row-fix') || document.createElement('style');",
    "  s.id = 'detail-row-fix';",
    "  s.textContent = " + JSON.stringify(CSS) + ";",
    "  document.head.appendChild(s);",
    "  return 'ok';",
    "})()",
  ].join("\n"));

  // 回到专辑列表
  await evaluate("(() => { const b = document.querySelector('[data-group-back]'); if (b) b.click(); return 'back'; })()");
  await new Promise((r) => setTimeout(r, 2200));

  // 找曲目最多的那张专辑
  const picked = await evaluate([
    "(() => {",
    "  const rows = [...document.querySelectorAll('#trackList .album-group-row')];",
    "  let best = null, bestCount = -1;",
    "  for (const row of rows) {",
    "    const n = Number(row.dataset.groupTrackCount || 0);",
    "    if (n > bestCount) { bestCount = n; best = row; }",
    "  }",
    "  if (!best) return 'no-rows';",
    "  const name = best.dataset.groupName || '';",
    "  best.click();",
    "  return JSON.stringify({ name, count: bestCount });",
    "})()",
  ].join("\n"));
  console.log("打开专辑:", picked);
  await new Promise((r) => setTimeout(r, 2600));

  const measured = await evaluate(MEASURE);
  console.log("测量:", measured);

  const shot = await send("Page.captureScreenshot", { format: "png" });
  if (shot.result && shot.result.data) {
    fs.writeFileSync("D:/fnAudio/artifacts/0.2.167/phone-detail-multi.png", Buffer.from(shot.result.data, "base64"));
    console.log("screenshot saved");
  }
  ws.close();
})();
