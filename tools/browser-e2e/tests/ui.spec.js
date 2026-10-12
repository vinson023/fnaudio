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
  await expect(page.locator(".track")).toHaveCount(4);
  await expect(page.locator("#viewTitle")).toHaveText("全部音乐");
  return consoleErrors;
}

test("first-screen metrics expose bounded list, cover and metadata evidence", async ({ page }) => {
  await loadLibrary(page, { width: 1440, height: 900 });
  const metrics = await page.evaluate(() => window.__fnAudioUiMetricsSnapshot?.());
  expect(metrics).toBeTruthy();
  expect(metrics).toEqual(expect.objectContaining({
    renders: expect.any(Number),
    listCommits: expect.any(Number),
    snapshotMarkupReuses: expect.any(Number),
    listMarkupNoops: expect.any(Number),
    coverHydrations: expect.any(Number),
    coverRequests: expect.any(Number),
    coverLoads: expect.any(Number),
    coverFailures: expect.any(Number),
    coverRetries: expect.any(Number),
    firstListCommitMs: expect.any(Number),
    firstCoverHydrationMs: expect.any(Number),
    metadataPrefetchFirstMs: expect.any(Number),
    metadataPrefetchRequests: expect.any(Number),
    metadataPrefetchSuccesses: expect.any(Number),
    metadataPrefetchFailures: expect.any(Number),
    metadataPrefetchNoMatches: expect.any(Number),
  }));
  for (const value of Object.values(metrics)) {
    expect(value).toBeGreaterThanOrEqual(0);
    expect(value).toBeLessThanOrEqual(3600000);
  }
});

test("warm library snapshot hands off to an equivalent authoritative page without replacing rows", async ({ page }) => {
  let releaseLibrary;
  const libraryHeld = new Promise(resolve => { releaseLibrary = resolve; });
  await page.route("**/api/library**", async route => {
    await libraryHeld;
    await route.continue();
  });
  await page.addInitScript(() => {
    const items = [
      { id: "fixture-1", title: "晨光", artist: "测试歌手", album: "离线专辑", track_no: 1, duration: 185, format: "flac", mime: "audio/flac", is_dsd: false, modified: 1, cover_url: "", url: "media/fixture-1" },
      { id: "fixture-2", title: "DSD Reference", artist: "Lab Artist", album: "Native DSD", track_no: 2, duration: 242, format: "dsf", mime: "audio/x-dsf", is_dsd: true, modified: 2, cover_url: "", url: "media/fixture-2" },
      { id: "fixture-3", title: "No Artwork", artist: "", album: "", track_no: 3, duration: 98, format: "mp3", mime: "audio/mpeg", is_dsd: false, modified: 3, cover_url: "", url: "media/fixture-3" },
      { id: "fixture-4", title: "Already Covered", artist: "Lab Artist", album: "Native DSD", track_no: 4, duration: 201, format: "flac", mime: "audio/flac", is_dsd: false, modified: 4, cover_url: "fixture-cover.svg", url: "media/fixture-4" },
    ];
    localStorage.setItem("fnaudio.libraryPageSnapshot.v1", JSON.stringify({
      key: JSON.stringify({ view: "all", page: 1, pageSize: 96, folderRoot: "", folderPath: "", folderPage: 1, folderPageSize: 100, groupName: "", creator: "", creatorAllTracks: false, sortKey: "title", sortDir: "asc", search: "" }),
      savedAt: Date.now(),
      total: items.length,
      items,
    }));
  });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
  await expect(page.locator(".track")).toHaveCount(4);
  const before = await page.evaluate(() => ({
    rows: (window.__warmSnapshotRows = [...document.querySelectorAll(".track")]).length,
    metrics: window.__fnAudioUiMetricsSnapshot?.() || {},
  }));
  expect(before.rows).toBe(4);
  expect(before.metrics.snapshotMarkupReuses || 0).toBe(0);
  expect(before.metrics.listCommits || 0).toBeGreaterThanOrEqual(1);

  releaseLibrary();
  await expect.poll(async () => page.evaluate(() => {
    const metrics = window.__fnAudioUiMetricsSnapshot?.() || {};
    const rows = [...document.querySelectorAll(".track")];
    return {
      snapshotMarkupReuses: metrics.snapshotMarkupReuses || 0,
      listCommits: metrics.listCommits || 0,
      listMarkupNoops: metrics.listMarkupNoops || 0,
      sameRows: rows.length === 4 && rows.every((row, index) => row === window.__warmSnapshotRows?.[index]),
    };
  }), { timeout: 9000 }).toEqual(expect.objectContaining({
    snapshotMarkupReuses: 1,
    sameRows: true,
  }));
  const after = await page.evaluate(() => {
    const metrics = window.__fnAudioUiMetricsSnapshot?.() || {};
    return { listCommits: metrics.listCommits || 0, listMarkupNoops: metrics.listMarkupNoops || 0 };
  });
  expect(after.listCommits).toBe(before.metrics.listCommits);
  expect(after.listMarkupNoops).toBeGreaterThan(0);
});

test("metadata completion patches the existing song row without a list flash", async ({ page }) => {
  await loadLibrary(page, { width: 1440, height: 900 });
  await page.evaluate(() => {
    window.__fixtureInitialTrackNode = document.querySelector('[data-track-id="fixture-4"]');
  });
  await expect.poll(async () => page.evaluate(() => {
    const metrics = window.__fnAudioUiMetricsSnapshot?.() || {};
    const row = document.querySelector('[data-track-id="fixture-3"]');
    const stableRow = document.querySelector('[data-track-id="fixture-4"]');
    return {
      sameNode: stableRow === window.__fixtureInitialTrackNode,
      text: row?.textContent || "",
      image: row?.querySelector("img")?.getAttribute("src") || "",
      successes: metrics.metadataPrefetchSuccesses || 0,
    };
  }), { timeout: 9000 }).toEqual(expect.objectContaining({
    sameNode: true,
    text: expect.stringContaining("Provider Album"),
    image: expect.stringContaining("fixture-artwork-3"),
    successes: expect.any(Number),
  }));
  const evidence = await page.evaluate(() => {
    const metrics = window.__fnAudioUiMetricsSnapshot?.() || {};
    return {
      listCommits: metrics.listCommits || 0,
      successes: metrics.metadataPrefetchSuccesses || 0,
      coverHydrations: metrics.coverHydrations || 0,
      rowStillConnected: window.__fixtureInitialTrackNode?.isConnected === true,
    };
  });
  expect(evidence.rowStillConnected).toBe(true);
  expect(evidence.successes).toBeGreaterThan(0);
  expect(evidence.coverHydrations).toBeLessThanOrEqual(2);
  // The initial page needs one commit. Metadata may cause one keyed patch,
  // but must not trigger a burst of full-list commits after each row settles.
  expect(evidence.listCommits).toBeLessThanOrEqual(3);
  const afterRender = await page.evaluate(() => {
    const before = window.__fnAudioUiMetricsSnapshot?.() || {};
    window.render?.();
    const after = window.__fnAudioUiMetricsSnapshot?.() || {};
    return {
      listCommits: [before.listCommits || 0, after.listCommits || 0],
      listMarkupNoops: [before.listMarkupNoops || 0, after.listMarkupNoops || 0],
    };
  });
  expect(afterRender.listCommits[1]).toBe(afterRender.listCommits[0]);
  expect(afterRender.listMarkupNoops[1]).toBeGreaterThan(afterRender.listMarkupNoops[0]);
});

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
  await expect(page.locator(".track")).toHaveCount(2);
  await expect(page.locator(".track-title").first()).toHaveText("DSD Reference");
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
