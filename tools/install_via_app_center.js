// 通过 fnOS 应用中心安装 FPK —— 飞牛侧安装的唯一入口。
//
//   NODE_PATH=tools/browser-e2e/node_modules node tools/install_via_app_center.js <fpk> [--out <dir>]
//
// 为什么必须走这个脚本（2026-11-19 负责人指令）：
// 飞牛上的安装只有应用中心这一条路可作数。SSH 解包、`cmd/main start`、只看
// 「登记版本变了没有」，都不能证明用户点得进去、加得了音乐目录 —— 0.2.165
// 就是这么被宣布「装好了」，而实际装完加不了音乐目录的。
//
// 为什么不能只点「同意」：
// 应用中心有两条分支。同包名已安装时是**升级**，弹一个「未经验证应用」的
// 安全提示，点同意就直接装。**全新安装**多一步安装向导：「运行设置 · 服务端口
// （默认 53199）→ 下一步」→「应用设置 · 普通用户文件授权 → 安装」。只点同意
// 然后轮询登记版本，升级能过、全新安装必然卡在向导第一步，于是「装不上」被
// 误读成「服务端拒绝了包」。0.2.164 的 install_fpk.js 就是这个缺陷。
//
// 成功判据有三条，缺一条都算没装上：
//   1. 应用中心登记版本 == 包版本，且 status == "running"
//   2. 浏览器经 /cgi/ThirdParty/fnaudio/index.cgi/api/health 拿到 200
//      （:53199 从 LAN 直连是 403，那是设计如此，不代表应用没起来）
//   3. 退出码为 0
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = process.env.FNAUDIO_HOST || "http://192.168.5.141:5666";
const USER = process.env.FNAUDIO_USER || "admin";
const PASSWORD = process.env.FNAUDIO_PASSWORD || "vinson520";
const PROXY = "/cgi/ThirdParty/fnaudio/index.cgi";
const CHROME = process.env.FNAUDIO_CHROME || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

const args = process.argv.slice(2);
const positional = [];
let OUT = "";
for (let index = 0; index < args.length; index += 1) {
  if (args[index] === "--out") {
    OUT = path.resolve(args[index + 1] || "");
    index += 1;
    continue;
  }
  positional.push(args[index]);
}
const FPK = path.resolve(positional[0] || "");
const VERSION = path.basename(FPK).split("-")[1];
const TRACE_DIR = OUT || path.join(path.dirname(FPK), "install-trace");

const trace = [];

async function registry(page) {
  return page.evaluate(async () => {
    const response = await fetch("/app-center/v1/app/installed?language=zh-CN", { credentials: "include" });
    const payload = await response.json();
    const list = (payload.data && payload.data.list) || [];
    const app = list.find(entry => entry.appName === "fnaudio");
    return app ? { version: app.version, status: app.status } : null;
  });
}

async function visibleText(page) {
  return page.evaluate(() => {
    const nodes = Array.from(document.querySelectorAll(
      ".semi-toast-content, .semi-modal-content, .semi-notification-content, [class*='toast'], [class*='error'], [class*='progress']"
    ));
    return nodes
      .map(node => (node.innerText || "").replace(/\s+/g, " ").trim())
      .filter(text => text && text.length < 400);
  });
}

async function healthThroughProxy(page) {
  return page.evaluate(async proxy => {
    const started = performance.now();
    try {
      const response = await fetch(proxy + "/api/health", { credentials: "include" });
      const body = await response.text();
      return { status: response.status, ms: Math.round(performance.now() - started), body: body.slice(0, 200) };
    } catch (error) {
      return { status: "ERR", ms: Math.round(performance.now() - started), body: error.message };
    }
  }, PROXY);
}

(async () => {
  if (!positional[0] || !fs.existsSync(FPK)) throw new Error(`missing fpk: ${FPK}`);
  fs.mkdirSync(TRACE_DIR, { recursive: true });
  console.log(`fpk     ${FPK}`);
  console.log(`version ${VERSION}`);
  console.log(`host    ${BASE}`);
  console.log(`trace   ${TRACE_DIR}`);

  const browser = await chromium.launch({ executablePath: CHROME });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  page.on("response", async response => {
    const url = response.url();
    if (!url.includes("/app-center/")) return;
    const status = response.status();
    let body = "";
    try {
      body = (await response.text()).slice(0, 400);
    } catch {
      body = "<unreadable>";
    }
    trace.push({ url: url.replace(BASE, ""), status, body });
  });

  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.fill("#username", USER);
  await page.fill("#password", PASSWORD);
  await page.click("button:has-text('登录')");
  await page.waitForTimeout(3500);

  await page.click("text=应用中心");
  await page.waitForTimeout(3500);
  const before = await registry(page);
  console.log("registry before:", JSON.stringify(before));

  await page.click("text=手动安装");
  await page.waitForTimeout(2000);

  const select = page.locator(".semi-modal .semi-select").first();
  if (await select.count()) {
    await select.click();
    await page.waitForTimeout(600);
    await page.locator(".semi-select-option").first().click();
    await page.waitForTimeout(400);
  }

  const [chooser] = await Promise.all([
    page.waitForEvent("filechooser", { timeout: 15000 }),
    page.click("button:has-text('从电脑上传')"),
  ]);
  await chooser.setFiles(FPK);
  await page.waitForTimeout(5000);
  await page.screenshot({ path: `${TRACE_DIR}/1-uploaded.png` });
  console.log("after upload:", JSON.stringify(await visibleText(page)));

  const agree = page.locator("button:has-text('同意')").first();
  if (await agree.count()) {
    await agree.click();
    console.log("clicked 同意");
  } else {
    console.log("no 同意 dialog (already trusted)");
  }

  // 全新安装会走安装向导（「运行设置 · 服务端口」→ 下一步 → 安装），升级才跳过。
  // 只点「同意」然后轮询登记版本，在升级时能过、在全新安装时必然卡在向导第一步。
  const WIZARD_BUTTONS = ["下一步", "安装", "确认安装", "开始安装", "完成"];
  let wizardStep = 0;
  let last = null;
  for (let attempt = 0; attempt < 90; attempt += 1) {
    await page.waitForTimeout(2000);
    const text = await visibleText(page);

    // 只在最上层的安装弹窗里找按钮，且按精确文字匹配：页面底层有同名的
    // 「安装」标签页，宽匹配会把点击落到被遮住的元素上，Playwright 于是
    // 一直报 "subtree intercepts pointer events"。
    const modal = page.locator(".semi-modal").last();
    if (await modal.count()) {
      const buttons = modal.locator("button");
      const total = await buttons.count();
      for (const label of WIZARD_BUTTONS) {
        let clicked = false;
        for (let index = 0; index < total; index += 1) {
          const button = buttons.nth(index);
          const caption = (await button.innerText().catch(() => "")).replace(/\s+/g, "").trim();
          if (caption !== label) continue;
          if (!(await button.isEnabled().catch(() => false))) continue;
          console.log(`wizard step ${wizardStep}: click 「${label}」  ui: ${JSON.stringify(text.slice(0, 2))}`);
          await page.screenshot({ path: `${TRACE_DIR}/wizard-${wizardStep}-${label}.png` });
          await button.click({ timeout: 15000 });
          wizardStep += 1;
          clicked = true;
          break;
        }
        if (clicked) break;
      }
    }
    await page.waitForTimeout(1500);

    const current = await registry(page);
    if (JSON.stringify(current) !== JSON.stringify(last)) {
      console.log(`t+${(attempt + 1) * 2}s registry:`, JSON.stringify(current), "ui:", JSON.stringify(text.slice(0, 3)));
      last = current;
    }
    if (current && current.version === VERSION && current.status === "running") break;
  }

  await page.screenshot({ path: `${TRACE_DIR}/2-final.png`, fullPage: true });
  const finalText = await visibleText(page);
  const finalRegistry = await registry(page);
  const health = await healthThroughProxy(page);
  await browser.close();

  fs.writeFileSync(
    path.join(TRACE_DIR, "trace.json"),
    JSON.stringify({ fpk: FPK, version: VERSION, trace, finalText, finalRegistry, health }, null, 2)
  );

  console.log("\n=== app-center 请求（非 200 或含 error） ===");
  for (const entry of trace) {
    if (entry.status !== 200 || /error|fail|code":\s*[1-9]/.test(entry.body)) {
      console.log(`${entry.status} ${entry.url}\n    ${entry.body.replace(/\s+/g, " ").slice(0, 300)}`);
    }
  }
  console.log("\n=== 界面残留文字 ===");
  console.log(JSON.stringify(finalText.slice(0, 6), null, 1));
  console.log("\nregistry after:", JSON.stringify(finalRegistry));
  console.log("health via proxy:", JSON.stringify(health));

  if (!finalRegistry || finalRegistry.version !== VERSION || finalRegistry.status !== "running") {
    console.error("INSTALL_FAILED: 应用中心没有登记这个版本，或状态不是 running");
    process.exit(1);
  }
  if (health.status !== 200) {
    console.error("INSTALL_FAILED: 应用中心说 running，但经代理打不开 /api/health");
    process.exit(1);
  }
  console.log("INSTALL_OK");
})().catch(error => {
  console.error("SCRIPT_ERROR", error.message);
  process.exit(2);
});
