const path = require("path");
const { spawn } = require("child_process");
const { test, expect } = require("@playwright/test");

let fixture;
let baseUrl;

test.beforeAll(async () => {
  const script = path.resolve(__dirname, "..", "..", "ui_e2e_fixture.py");
  fixture = spawn(process.env.PYTHON || "python", ["-B", script, "--port", "0"], {
    cwd: path.resolve(__dirname, "..", "..", ".."),
    stdio: ["ignore", "pipe", "pipe"],
  });
  baseUrl = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("UI fixture did not start")), 8000);
    fixture.once("error", reject);
    fixture.stderr.on("data", data => process.stderr.write(data));
    fixture.stdout.once("data", data => {
      clearTimeout(timer);
      resolve(String(data).trim());
    });
  });
});

test.afterAll(() => {
  if (fixture && !fixture.killed) fixture.kill();
});

async function loadLibrary(page, viewport) {
  await page.setViewportSize(viewport);
  const consoleErrors = [];
  page.on("console", message => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
  await expect(page.locator(".track")).toHaveCount(3);
  await expect(page.locator("#viewTitle")).toHaveText("全部音乐");
  return consoleErrors;
}

test("desktop library, context menu, device picker and settings are functional", async ({ page }) => {
  const consoleErrors = await loadLibrary(page, { width: 1440, height: 900 });
  await expect(page.locator(".track-title").first()).toHaveText("晨光");
  await page.locator(".track").first().click({ button: "right" });
  await expect(page.locator("#trackContextMenu")).toBeVisible();
  await expect(page.locator("#trackContextMenu")).toContainText("从当前开始播放所有歌曲");
  await expect(page.locator("#trackContextMenu")).toContainText("打开包含的文件夹");

  await page.locator("#deviceBtn").click();
  await expect(page.locator("#deviceDialog")).toBeVisible();
  await expect(page.locator("#deviceCurrentTarget")).toContainText("当前设备");
  await page.locator("#closeDialog").click();

  await page.locator("#folderBtn").click();
  await expect(page.locator("#folderDialog")).toBeVisible();
  await expect(page.locator("[data-settings-tab='metadata']")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBeTruthy();
  expect(consoleErrors).toEqual([]);
});

test("mobile search, menu, scrolling surface and footer stay usable", async ({ page }) => {
  const consoleErrors = await loadLibrary(page, { width: 390, height: 844 });
  await expect(page.locator("#mobileDeviceBtn")).toBeVisible();
  await expect(page.locator("#mobileModeBtn")).toBeVisible();
  await expect(page.locator("#deviceBtn")).toBeHidden();
  await expect(page.locator("#mobileShuffleBtn")).toBeVisible();
  await expect(page.locator("#mobileRepeatBtn")).toBeVisible();
  const transport = await page.evaluate(() => {
    const rect = id => document.querySelector(id).getBoundingClientRect();
    const shuffle = rect("#mobileShuffleBtn");
    const previous = rect("#prevBtn");
    const next = rect("#nextBtn");
    const repeat = rect("#mobileRepeatBtn");
    return {
      shuffleBeforePrevious: shuffle.right <= previous.left + 1,
      repeatAfterNext: repeat.left >= next.right - 1,
    };
  });
  expect(transport).toEqual({ shuffleBeforePrevious: true, repeatAfterNext: true });
  const search = page.locator("#mobileSearchInput");
  await expect(search).toBeVisible();
  await search.fill("DSD");
  await expect(page.locator(".track")).toHaveCount(1);
  await expect(page.locator(".track-title")).toHaveText("DSD Reference");
  await expect(page.locator("#pager")).toBeHidden();

  await page.locator("#mobileNavBtn").click();
  await expect(page.locator(".sidebar")).toBeVisible();
  const layout = await page.evaluate(() => {
    const topbar = document.querySelector(".topbar").getBoundingClientRect();
    const searchBox = document.querySelector(".mobile-library-search").getBoundingClientRect();
    const footer = document.querySelector(".player").getBoundingClientRect();
    const list = document.querySelector("#trackList");
    return {
      searchBelowTopbar: searchBox.top >= topbar.bottom - 1,
      footerInsideViewport: footer.bottom <= window.innerHeight + 1 && footer.top >= 0,
      listScrollable: ["auto", "scroll"].includes(getComputedStyle(list).overflowY),
      noHorizontalOverflow: document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
    };
  });
  expect(layout).toEqual({
    searchBelowTopbar: true,
    footerInsideViewport: true,
    listScrollable: true,
    noHorizontalOverflow: true,
  });
  expect(consoleErrors).toEqual([]);
});

test("mobile album detail renders and scrolls its song list", async ({ page }) => {
  const consoleErrors = await loadLibrary(page, { width: 390, height: 844 });
  await page.locator("#mobileNavBtn").click();
  await page.locator("[data-view='albums']").click();
  await expect(page.locator(".album-group-row")).toHaveCount(3);
  await page.locator(".album-group-row").filter({ hasText: "离线专辑" }).click();
  const tracks = page.locator(".album-detail-track-list .track");
  await expect(tracks).toHaveCount(1);
  await expect(tracks.first()).toBeVisible();
  const layout = await page.evaluate(() => {
    const viewport = document.querySelector("#libraryScroll");
    const list = document.querySelector(".album-detail-track-list");
    return {
      listHeight: Math.round(list.getBoundingClientRect().height),
      viewportScrollable: ["auto", "scroll"].includes(getComputedStyle(viewport).overflowY),
      noHorizontalOverflow: document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
    };
  });
  expect(layout.listHeight).toBeGreaterThan(0);
  expect(layout.viewportScrollable).toBeTruthy();
  expect(layout.noHorizontalOverflow).toBeTruthy();
  expect(consoleErrors).toEqual([]);
});
