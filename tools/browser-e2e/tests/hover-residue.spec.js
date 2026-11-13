// 触摸端不留悬停痕迹（R553）
//
// Android WebView 与 iOS Safari 会把 :hover 留在最后点过的控件上。任何"悬停才
// 出现"的底色/边框/图标颜色都会跟着留在那里——用户报的就是传输栏：点一下下一首，
// #nextBtn 挂着一块 #EBEBEB 圆角方块直到下一次点击。
//
// 这条用例对触摸视口下每一个可见按钮做同一件事：记录静止态 → 点一下 → 再记录，
// 两者必须一致。真正会持久切换状态的控件（active-control / aria-pressed 变化）
// 跳过，因为那里的差异是功能本身。桌面视口反向验证：指针悬停仍然要画出反馈，
// 否则就是把这个功能改没了。
const path = require("path");
const { spawn } = require("child_process");
const { test, expect } = require("@playwright/test");

// 边框颜色只在边框真的有宽度时才算视觉的一部分：0 宽度的边框色是浏览器为
// currentColor 保留的计算值，改了也看不见，比它只会制造假失败。
const PAINT_PROPERTIES = ["backgroundColor", "borderTopColor", "borderBottomColor", "boxShadow", "color", "borderTopWidth"];

let fixture;
let baseUrl;

test.beforeAll(async () => {
  const script = path.resolve(__dirname, "..", "..", "ui_e2e_fixture.py");
  fixture = spawn(process.env.PYTHON || "python", ["-B", script, "--port", "0"], {
    cwd: path.resolve(__dirname, "..", "..", ".."),
    stdio: ["ignore", "pipe", "pipe"],
  });
  baseUrl = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("UI fixture did not start")), 10000);
    fixture.once("error", reject);
    fixture.stderr.on("data", data => process.stderr.write(data));
    fixture.stdout.once("data", data => { clearTimeout(timer); resolve(String(data).trim()); });
  });
});

test.afterAll(() => {
  if (fixture && !fixture.killed) fixture.kill();
});

const readPaint = (handle) => handle.evaluate((node, properties) => {
  const style = getComputedStyle(node);
  const paint = {};
  properties.forEach(property => { paint[property] = style[property]; });
  const borderVisible = parseFloat(style.borderTopWidth) > 0;
  return {
    borderVisible,
    paint,
    state: `${node.className}|${node.getAttribute("aria-pressed") || ""}`,
  };
}, PAINT_PROPERTIES);

async function loadTouch(page) {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
  await expect(page.locator(".track")).toHaveCount(4);
}

test("触摸端点击按钮后不留悬停底色", async ({ browser }) => {
  // 每个控件都换一张干净页面，几十轮加载比默认预算慢。
  test.setTimeout(180000);
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 3,
    isMobile: true,
    hasTouch: true,
  });
  const page = await context.newPage();

  const residue = [];
  let checked = 0;

  // 每个控件都从干净页面开始：上一轮留下的 :hover 会污染下一轮的基线。
  for (let index = 0; index < 40; index += 1) {
    await loadTouch(page);
    const controls = page.locator("button, [role='button']");
    const total = await controls.count();
    if (index >= total) break;
    const node = controls.nth(index);
    const box = await node.boundingBox().catch(() => null);
    if (!box || box.width < 6 || box.height < 6) continue;
    const label = await node.evaluate(el => String(el.id || el.getAttribute("aria-label") || el.className || el.tagName).slice(0, 48));
    const before = await readPaint(node);
    await node.tap({ force: true }).catch(() => {});
    await page.waitForTimeout(140);
    const after = await readPaint(node).catch(() => null);
    if (!after) continue;
    checked += 1;
    if (before.state !== after.state) continue; // 真的切换了状态，不是残留
    const changed = Object.keys(before.paint).filter(key => {
      if (!before.borderVisible && key.startsWith("border")) return false;
      return before.paint[key] !== after.paint[key];
    });
    if (changed.length) {
      residue.push(`${label}: ${changed.map(key => `${key} ${before.paint[key]} -> ${after.paint[key]}`).join("; ")}`);
    }
  }

  expect(checked, "至少要真的点过一批控件").toBeGreaterThan(10);
  expect(residue, `触摸端留下悬停痕迹：\n${residue.join("\n")}`).toEqual([]);
  await context.close();
});

test("桌面端指针悬停仍然有反馈", async ({ browser }) => {
  // 反向守卫：把触摸端修好不能顺手把鼠标用户的悬停反馈一起关掉。
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
  await expect(page.locator(".track")).toHaveCount(4);

  const next = page.locator("#nextBtn");
  const before = (await readPaint(next)).paint;
  await next.hover();
  await page.waitForTimeout(80);
  const hovered = (await readPaint(next)).paint;
  expect(before.backgroundColor).not.toBe(hovered.backgroundColor);
  expect(hovered.backgroundColor).not.toBe("rgba(0, 0, 0, 0)");

  const row = page.locator(".track").first();
  const rowBefore = (await readPaint(row)).paint;
  await row.hover();
  await page.waitForTimeout(80);
  expect((await readPaint(row)).paint.backgroundColor).not.toBe(rowBefore.backgroundColor);
  await context.close();
});
