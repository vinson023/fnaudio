// 播放条「右下角图标」位置探针（R623）。
//
// 量两件事，逐宽度扫：
//   1. 播放条右边缘 − 最后一个可见图标右边缘（应恒定 ≈20px，不随宽度变）
//   2. 传输键组的中心相对视口中心的偏移（应 ≈0，播放键要留在条的中线上）
//
// 三段的期望不同，不是「越一致越好」：
//   ≥761   桌面单行三列，7 个图标靠右
//   600–760 窄窗两行版，7 个图标整行靠右（R623 新增；这之前整排是 display:none）
//   <600    真手机版，整排隐藏、5 键居中传输组——这是有意的约定，不是缺陷
//
// 用法：node measure_player_narrow_band.js [--shots]
//   退出码 0 = 全部符合期望；1 = 有宽度不符合（打印是哪一档）
const path = require("path");
const fs = require("fs");
const { spawn } = require("child_process");
const { chromium } = require("@playwright/test");

const WIDTHS = [1440, 1200, 1101, 1100, 900, 820, 780, 761, 760, 740, 700, 660, 620, 600, 599, 560, 430, 360];
const SHOTS = process.argv.includes("--shots");
const SHOT_DIR = path.resolve("artifacts", "narrow-shots");

const EXPECT = width => (width >= 761 ? "desktop" : width >= 600 ? "narrow" : "phone");

(async () => {
  if (SHOTS) fs.mkdirSync(SHOT_DIR, { recursive: true });
  const script = path.resolve("..", "ui_e2e_fixture.py");
  const fixture = spawn(process.env.PYTHON || "python", ["-B", script, "--port", "0"], {
    cwd: path.resolve(".."), stdio: ["ignore", "pipe", "pipe"],
  });
  const baseUrl = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("fixture timeout")), 8000);
    fixture.stderr.on("data", d => process.stderr.write(d));
    fixture.stdout.once("data", d => { clearTimeout(timer); resolve(String(d).trim()); });
  });
  const exe = ["C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"].find(c => fs.existsSync(c));
  if (!exe) throw new Error("no Chromium found");

  const browser = await chromium.launch({ executablePath: exe });
  const page = await browser.newPage();
  const failures = [];
  const rows = [];

  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
    await page.locator(".track").first().waitFor();
    if (SHOTS) await page.locator(".player").screenshot({ path: path.join(SHOT_DIR, `player-${width}.png`) });

    const m = await page.evaluate(() => {
      const player = document.querySelector(".player");
      const pb = player.getBoundingClientRect();
      const vis = el => !!el && el.offsetParent !== null;
      const actions = document.querySelector(".player-actions");
      const icons = vis(actions)
        ? Array.from(actions.querySelectorAll("button")).filter(b => b.offsetParent !== null)
        : [];
      const transport = document.querySelector(".transport");
      const tb = vis(transport) ? transport.getBoundingClientRect() : null;
      const tButtons = Array.from(transport.querySelectorAll("button")).filter(b => b.offsetParent !== null);
      return {
        playerH: Math.round(pb.height),
        rows: getComputedStyle(player).gridTemplateRows,
        actionsVisible: vis(actions),
        iconCount: icons.length,
        lastIconRight: icons.length ? Math.round(icons[icons.length - 1].getBoundingClientRect().right) : null,
        iconGapToRight: icons.length ? Math.round(pb.right - icons[icons.length - 1].getBoundingClientRect().right) : null,
        transportCenterOffset: tb ? Math.round((tb.left + tb.right) / 2 - window.innerWidth / 2) : null,
        transportW: tb ? Math.round(tb.width) : null,
        transportButtons: tButtons.length,
      };
    });

    const band = EXPECT(width);
    const push = msg => failures.push(`${width}px (${band}): ${msg}`);

    if (band === "phone") {
      if (m.actionsVisible) push("the phone layout must hide the footer action row");
      if (m.iconCount !== 0) push(`the phone layout must show no footer icons, saw ${m.iconCount}`);
      if (m.transportButtons !== 5) push(`the phone transport must keep 5 buttons, saw ${m.transportButtons}`);
    } else {
      if (!m.actionsVisible) push("the icon cluster must stay visible");
      if (m.iconCount !== 7) push(`expected 7 footer icons, saw ${m.iconCount}`);
      if (m.iconGapToRight !== null && Math.abs(m.iconGapToRight - 20) > 3) {
        push(`last icon sits ${m.iconGapToRight}px from the right edge, expected ~20px`);
      }
      if (m.transportButtons !== 3) push(`expected 3 transport buttons, saw ${m.transportButtons}`);
    }
    if (m.transportCenterOffset !== null && Math.abs(m.transportCenterOffset) > 2) {
      push(`transport centre is ${m.transportCenterOffset}px off the viewport centre`);
    }
    rows.push({ width, band, ...m });
  }

  for (const r of rows) {
    console.log(
      `${String(r.width).padStart(4)} ${r.band.padEnd(7)} h=${String(r.playerH).padStart(3)} ` +
      `rows=${r.rows.padEnd(13)} icons=${r.iconCount} gap=${r.iconGapToRight === null ? "  -" : String(r.iconGapToRight).padStart(3)} ` +
      `transport=${r.transportButtons}x/${r.transportW === null ? "-" : r.transportW} centre=${r.transportCenterOffset}`
    );
  }
  await browser.close();
  fixture.kill();

  if (failures.length) {
    console.error("\nFAIL");
    for (const f of failures) console.error("  " + f);
    process.exit(1);
  }
  console.log("\nplayer narrow band: OK");
  process.exit(0);
})().catch(e => { console.error("ERR", e.message); process.exit(1); });
