// 列应用中心里已安装应用的状态，或点指定应用卡片上的操作按钮。
//
//   NODE_PATH=tools/browser-e2e/node_modules node tools/app_center_apps.js --list
//   NODE_PATH=tools/browser-e2e/node_modules node tools/app_center_apps.js --inspect fnAudio
//   NODE_PATH=tools/browser-e2e/node_modules node tools/app_center_apps.js --click fnAudio
//   NODE_PATH=tools/browser-e2e/node_modules node tools/app_center_apps.js --stop fnAudio
//
// 为什么需要它：
// 0.2.170 升级一直失败在 install_callback 的端口校验上 —— 它 bind 0.0.0.0:53199，
// 而旧实例还活着，于是 exit 1，应用中心只显示「执行脚本出错且原因未知」。
// 旧实例由 trim_http_cgi.service 保活（cgroup 里能看到 server.py 和 mpd），
// 杀掉会立刻被拉起，所以必须让应用中心把它停掉，端口才会真的松。
//
// 定位按钮的两个坑（都踩过）：
// ① 按「按钮文字 == 停用」直接找 —— 已安装列表里每张卡片都有一个「停用」，
//    点到了隔壁应用；从按钮往上找祖先会走到包住整页的网格，容器文字里当然
//    也有 fnAudio，于是「属于 fnAudio」对每个按钮都成立。
// ② 改成「同一行、右侧最近的按钮」—— 卡片其实是竖排（名字在上、按钮在下），
//    label 宽 179px 时按钮在它左下方，dx 为负被过滤掉，于是又选中了下一列。
// 现在按实测的祖先链走：从应用名往上收，第一个「含操作按钮」的祖先就是卡片
// （实测 depth 1 就有按钮，卡片本体在 depth 3，`rounded-lg border`，269×78）。
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = process.env.FNAUDIO_HOST || "http://192.168.5.141:5666";
const USER = process.env.FNAUDIO_USER || "admin";
const PASSWORD = process.env.FNAUDIO_PASSWORD || "vinson520";
const CHROME = process.env.FNAUDIO_CHROME || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

const args = process.argv.slice(2);
const LIST_ONLY = args.includes("--list");
const INSPECT = args.includes("--inspect");
const CLICK_ONLY = args.includes("--click");
const stopIndex = args.indexOf("--stop");
const TARGET = stopIndex >= 0
  ? args[stopIndex + 1]
  : (args.filter(entry => !entry.startsWith("--")).pop() || "");

const TRACE_DIR = path.join(process.cwd(), "artifacts", "app-center-apps");
const trace = [];

async function registryAll(page) {
  return page.evaluate(async () => {
    const response = await fetch("/app-center/v1/app/installed?language=zh-CN", { credentials: "include" });
    const payload = await response.json();
    const list = (payload.data && payload.data.list) || [];
    return list.map(entry => ({ appName: entry.appName, version: entry.version, status: entry.status }));
  });
}

// 登记名是小写 fnaudio，卡片上写的是 fnAudio，比较时不能区分大小写。
function pickApp(list, target) {
  const needle = String(target).toLowerCase();
  return list.find(entry => String(entry.appName).toLowerCase() === needle) || null;
}

// fnOS 桌面会把打开过的应用留成窗口，窗口是 iframe，盖在应用中心上面时
// Playwright 的点击会一直报 "subtree intercepts pointer events"。用 JS 直接
// 点窗口自己的关闭按钮，绕开命中测试。
async function closeAppWindows(page) {
  return page.evaluate(() => {
    const windows = Array.from(document.querySelectorAll(".trim-ui__app-layout--window"));
    let closed = 0;
    for (const win of windows) {
      const close = Array.from(win.querySelectorAll("button, [role='button'], i, span, div"))
        .find(el => /close/i.test((el.className || "").toString()) || /关闭/.test(el.getAttribute("aria-label") || ""));
      if (close) {
        close.click();
        closed += 1;
      }
    }
    return { total: windows.length, closed };
  });
}

async function findActionButton(page, appName) {
  return page.evaluate(name => {
    const ACTIONS = /^(打开|停用|启用|停止|卸载|更新)$/;
    const label = Array.from(document.querySelectorAll("div, span, a, p"))
      .find(node => (node.innerText || "").trim() === name && node.getBoundingClientRect().width > 0);
    if (!label) return { hit: null, reason: "app name node not found" };

    let card = label;
    for (let depth = 0; depth < 6 && card.parentElement; depth += 1) {
      card = card.parentElement;
      const text = (card.innerText || "").replace(/\s+/g, " ").trim();
      if (text.length > 200) break; // 走到网格了，单张卡片不会这么长
      const button = Array.from(card.querySelectorAll("button"))
        .find(node => ACTIONS.test((node.innerText || "").replace(/\s+/g, "").trim()));
      if (button) {
        const rect = button.getBoundingClientRect();
        return {
          hit: {
            caption: (button.innerText || "").replace(/\s+/g, "").trim(),
            cardText: text.slice(0, 100),
            depth,
            rect: [Math.round(rect.x), Math.round(rect.y), Math.round(rect.width), Math.round(rect.height)],
          },
        };
      }
    }
    return { hit: null, reason: "no action button in the card" };
  }, appName);
}

// 确认弹窗只认模态框里的按钮。在全页按文字找「停用」，会点到别的卡片的停用。
async function confirmModal(page) {
  for (const text of ["确定", "确认", "停用", "停止"]) {
    const modal = page.locator(".semi-modal, .semi-portal").last();
    if (!(await modal.count())) return false;
    const buttons = modal.locator("button");
    const total = await buttons.count();
    for (let index = 0; index < total; index += 1) {
      const button = buttons.nth(index);
      const caption = (await button.innerText().catch(() => "")).replace(/\s+/g, "").trim();
      if (caption !== text) continue;
      if (!(await button.isVisible().catch(() => false))) continue;
      if (!(await button.isEnabled().catch(() => false))) continue;
      console.log(`confirm 「${text}」`);
      await button.click({ timeout: 10000 }).catch(error => console.log("confirm failed:", error.message));
      return true;
    }
  }
  return false;
}

function dumpRequests() {
  console.log("\n=== app-center 请求（非 GET 或异常） ===");
  for (const entry of trace) {
    if (entry.method === "GET" && entry.status === 200 && !/error|fail|code":\s*[1-9]/.test(entry.body)) continue;
    console.log(`${entry.method} ${entry.status} ${entry.url}`);
    if (entry.post) console.log(`    post: ${entry.post.replace(/\s+/g, " ").slice(0, 200)}`);
    console.log(`    body: ${entry.body.replace(/\s+/g, " ").slice(0, 200)}`);
  }
}

(async () => {
  fs.mkdirSync(TRACE_DIR, { recursive: true });
  const browser = await chromium.launch({ executablePath: CHROME });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  page.on("response", async response => {
    const url = response.url();
    if (!url.includes("/app-center/")) return;
    let body = "";
    try {
      body = (await response.text()).slice(0, 300);
    } catch {
      body = "<unreadable>";
    }
    const request = response.request();
    trace.push({
      method: request.method(),
      url: url.replace(BASE, ""),
      status: response.status(),
      post: (request.postData() || "").slice(0, 300),
      body,
    });
  });

  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.fill("#username", USER);
  await page.fill("#password", PASSWORD);
  await page.click("button:has-text('登录')");
  await page.waitForTimeout(3500);

  for (let attempt = 0; attempt < 3; attempt += 1) {
    const result = await closeAppWindows(page);
    console.log("close windows:", JSON.stringify(result));
    if (!result.total) break;
    await page.waitForTimeout(800);
  }

  await page.click("text=应用中心");
  await page.waitForTimeout(3000);
  const installed = page.locator("text=已安装").first();
  if (await installed.count()) {
    await installed.click();
    await page.waitForTimeout(2500);
  }

  if (LIST_ONLY || !TARGET) {
    const all = await registryAll(page);
    console.log("=== 已安装应用 ===");
    for (const entry of all) {
      console.log(`  ${String(entry.appName).padEnd(26)} ${String(entry.version).padEnd(12)} ${entry.status}`);
    }
    await page.screenshot({ path: `${TRACE_DIR}/list.png`, fullPage: true });
    await browser.close();
    return;
  }

  if (INSPECT) {
    const chain = await page.evaluate(name => {
      const label = Array.from(document.querySelectorAll("div, span, a, p"))
        .find(node => (node.innerText || "").trim() === name && node.getBoundingClientRect().width > 0);
      if (!label) return { error: "label not found" };
      const out = [];
      let node = label;
      for (let depth = 0; depth < 6 && node; depth += 1) {
        const rect = node.getBoundingClientRect();
        out.push({
          depth,
          tag: node.tagName,
          cls: (node.className || "").toString().slice(0, 70),
          text: (node.innerText || "").replace(/\s+/g, " ").trim().slice(0, 50),
          rect: [Math.round(rect.x), Math.round(rect.y), Math.round(rect.width), Math.round(rect.height)],
          buttons: Array.from(node.querySelectorAll("button")).map(b => (b.innerText || "").replace(/\s+/g, "").trim()),
        });
        node = node.parentElement;
      }
      return { chain: out };
    }, TARGET);
    console.log(JSON.stringify(chain, null, 1));
    await page.screenshot({ path: `${TRACE_DIR}/inspect.png`, fullPage: true });
    await browser.close();
    return;
  }

  const before = pickApp(await registryAll(page), TARGET);
  console.log(`${TARGET} before:`, JSON.stringify(before));

  const found = await findActionButton(page, TARGET);
  console.log("action button:", JSON.stringify(found));
  if (!found.hit) {
    console.log("ACTION_BUTTON_NOT_FOUND", found.reason || "");
    await browser.close();
    process.exit(3);
  }

  await page.mouse.click(found.hit.rect[0] + found.hit.rect[2] / 2, found.hit.rect[1] + found.hit.rect[3] / 2);
  await page.waitForTimeout(2000);
  await confirmModal(page);

  if (CLICK_ONLY) {
    await page.waitForTimeout(8000);
    const after = await findActionButton(page, TARGET);
    console.log("card caption after:", JSON.stringify(after.hit));
    console.log("registry after:", JSON.stringify(pickApp(await registryAll(page), TARGET)));
    await page.screenshot({ path: `${TRACE_DIR}/after-click.png`, fullPage: true });
    dumpRequests();
    await browser.close();
    return;
  }

  let last = null;
  for (let attempt = 0; attempt < 25; attempt += 1) {
    await page.waitForTimeout(2000);
    const current = pickApp(await registryAll(page), TARGET);
    const line = JSON.stringify(current);
    if (line !== last) {
      console.log(`t+${(attempt + 1) * 2}s`, line);
      last = line;
    }
    if (current && current.status !== "start" && current.status !== "running") break;
  }

  await page.screenshot({ path: `${TRACE_DIR}/after-stop.png`, fullPage: true });
  const finalAll = await registryAll(page);
  await browser.close();

  fs.writeFileSync(path.join(TRACE_DIR, "trace.json"), JSON.stringify({ trace, finalAll }, null, 2));
  dumpRequests();
  console.log("\n=== 全部状态 ===");
  for (const entry of finalAll) {
    console.log(`  ${String(entry.appName).padEnd(26)} ${String(entry.version).padEnd(12)} ${entry.status}`);
  }
})().catch(error => {
  console.error("SCRIPT_ERROR", error.message);
  process.exit(2);
});
