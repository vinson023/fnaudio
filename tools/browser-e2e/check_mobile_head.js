// 窄屏表头验收（第二轮）：上一版把整份 app.css 追加到 head 末尾，反而盖掉了
// 排在后面的 fnos-theme.css 里的窄屏播放器定位，把播放器顶到了顶部，测出来的
// 是测试脚本自己的错，不是页面的样子。
// 这一版只注入新增的那一小段规则，其余样式原样不动，再量位置、再截图。
const fs = require("fs");
const { chromium } = require("playwright");

const BASE = "http://192.168.5.2:5666";
const PROXY = "/cgi/ThirdParty/fnaudio/index.cgi";
const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = "D:/fnAudio/artifacts/0.2.167";

// 与 src/app/ui/app.css 里新增块逐字一致。
const DELTA = `
@media(max-width:760px){
  .table-head{display:none!important}
  .table-head[data-table-mode="album-collection"],
  .table-head[data-table-mode="group"]{
    display:flex!important;
    align-items:center;
    gap:18px;
    padding:0 14px!important;
    overflow-x:auto;
    overflow-y:hidden;
    scrollbar-width:none;
  }
  .table-head[data-table-mode="album-collection"]::-webkit-scrollbar,
  .table-head[data-table-mode="group"]::-webkit-scrollbar{display:none}
  .table-head[data-table-mode="album-collection"] .album-header-cell,
  .table-head[data-table-mode="group"] .album-header-cell{flex:0 0 auto!important}
}
`;

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.fill("#username", "admin");
  await page.fill("#password", "vinson520");
  await page.click("button:has-text('登录')");
  await page.waitForTimeout(3500);
  await page.goto(`${BASE}${PROXY}/`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  await page.evaluate(() => {
    const t = document.querySelector('[data-view="albums"]');
    if (t) t.click();
  });
  await page.waitForTimeout(2000);

  const box = async () => page.evaluate(() => {
    const b = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { top: Math.round(r.top), bottom: Math.round(r.bottom), h: Math.round(r.height), w: Math.round(r.width) };
    };
    const head = document.getElementById("tableHead");
    return {
      player: b("footer.player"),
      topbar: b(".topbar"),
      search: b(".search"),
      head: b("#tableHead"),
      headMode: head ? head.dataset.tableMode || "(none)" : "(missing)",
      headDisplay: head ? getComputedStyle(head).display : "-",
      headButtons: head ? [...head.querySelectorAll("button[data-track-sort]")].map((x) => x.textContent.trim()) : [],
      count: b(".library-count") || b(".album-count"),
    };
  });

  console.log("注入前:", JSON.stringify(await box()));

  await page.evaluate((css) => {
    const style = document.createElement("style");
    style.id = "mobile-head-delta";
    style.textContent = css;
    document.head.appendChild(style);
    // 线上 app.js 还没有这行属性（0.2.167 发布版），手动补上，
    // 并用 observer 钉住——播放中 render() 会不停重建这行。
    const head = document.getElementById("tableHead");
    const apply = () => {
      if (head && head.dataset.tableMode !== "album-collection") head.dataset.tableMode = "album-collection";
    };
    apply();
    new MutationObserver(apply).observe(head, { attributes: true, childList: true, subtree: true });
  }, DELTA);
  await page.waitForTimeout(800);
  console.log("注入后:", JSON.stringify(await box()));
  await page.screenshot({ path: `${OUT}/mobile-head-after.png` });

  // 真点一下「歌手」，确认它接的是排序而不是摆设。
  const clicked = await page.evaluate(async () => {
    const btn = document.querySelector('#tableHead button[data-track-sort="artist"]');
    if (!btn) return "no-button";
    btn.click();
    await new Promise((r) => setTimeout(r, 1600));
    const head = document.getElementById("tableHead");
    const active = head.querySelector(".track-sort-indicator");
    const firstRows = [...document.querySelectorAll("#trackList .album-row, #trackList .group-row")]
      .slice(0, 3).map((r) => (r.textContent || "").replace(/\s+/g, " ").trim().slice(0, 24));
    return { indicator: active ? "present" : "missing", firstRows };
  });
  console.log("点「歌手」后:", JSON.stringify(clicked));
  await page.screenshot({ path: `${OUT}/mobile-head-sorted-by-artist.png` });

  // 类别（歌手/流派）列表同样要留着这行。
  const groupMode = await page.evaluate(async () => {
    const t = document.querySelector('[data-view="artists"]');
    if (!t) return "no-artists-view";
    t.click();
    await new Promise((r) => setTimeout(r, 2200));
    const head = document.getElementById("tableHead");
    if (!head) return "no-head";
    if (head.dataset.tableMode !== "group") head.dataset.tableMode = "group";
    const r = head.getBoundingClientRect();
    return { display: getComputedStyle(head).display, top: Math.round(r.top), h: Math.round(r.height), buttons: [...head.querySelectorAll("button[data-track-sort]")].map((x) => x.textContent.trim()) };
  });
  console.log("歌手视图:", JSON.stringify(groupMode));
  await page.screenshot({ path: `${OUT}/mobile-head-artists.png` });

  await browser.close();
})();
