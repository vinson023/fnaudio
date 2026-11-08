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

  await page.locator("#mobileSettingsNavBtn").click();
  await expect(page.locator("#folderDialog")).toBeVisible();
  await expect(page.locator("[data-settings-tab='metadata']")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBeTruthy();
  expect(consoleErrors).toEqual([]);
});

test("group rows play everything under them from the right-click menu", async ({ page }) => {
  // R499: the group menu lost 播放 in 0.1.172 while `runGroupAction()` kept the
  // branch, so for two years the menu could not reach it.  This drives the real
  // menu on a real album and artist row and reads the queue the player reports.
  const unexpected = [];
  page.on("console", message => {
    if (message.type() !== "error") return;
    const location = message.location?.() || {};
    // Actually playing a track points <audio> at media/fixture-N, which this
    // fixture does not serve. That 404 belongs to the harness, not to the app,
    // so it is the one console error this test tolerates.
    if (/\/media\/fixture-/.test(String(location.url || ""))) return;
    unexpected.push(`${message.text()} @ ${location.url || "<inline>"}`);
  });
  await loadLibrary(page, { width: 1440, height: 900 });
  const menu = page.locator("#trackContextMenu");

  await page.locator("[data-view='albums']").click();
  await expect(page.locator(".album-group-row")).toHaveCount(3);
  await page.locator(".album-group-row").filter({ hasText: "Native DSD" }).click({ button: "right" });
  await expect(menu).toBeVisible();
  expect(await menu.locator("[data-group-action]").evaluateAll(nodes => nodes.map(node => node.dataset.groupAction)))
    .toEqual(["play", "queue", "playlist", "open"]);
  await menu.locator("[data-group-action='play']").click();
  await expect(menu).toBeHidden();
  await expect(page.locator("#queueCount")).toHaveText("2");
  await expect(page.locator("#nowTitle")).toHaveText("DSD Reference");

  await page.locator("[data-view='artists']").click();
  await expect(page.locator(".group-row").filter({ hasText: "Lab Artist" })).toHaveCount(1);
  await page.locator(".group-row").filter({ hasText: "Lab Artist" }).click({ button: "right" });
  await expect(menu).toBeVisible();
  await menu.locator("[data-group-action='play']").click();
  await expect(menu).toBeHidden();
  await expect(page.locator("#queueCount")).toHaveText("2");
  await expect(page.locator("#nowTitle")).toHaveText("DSD Reference");
  expect(unexpected).toEqual([]);
});

test("no view renders a 播放全部 button", async ({ page }) => {
  // R501 put one in the album and genre detail breadcrumbs so those pages could
  // start their whole set; R508 removed every list toolbar copy; R511 removed the
  // last three (album detail, genre detail, category detail header) after the
  // owner said 还是有些地方有「播放全部」按钮.  This walks the three places that
  // used to have it and asserts the button is nowhere.
  const unexpected = [];
  page.on("console", message => {
    if (message.type() !== "error") return;
    const location = message.location?.() || {};
    if (/\/media\/fixture-/.test(String(location.url || ""))) return;
    unexpected.push(`${message.text()} @ ${location.url || "<inline>"}`);
  });
  const noPlayAll = async label => {
    await expect(page.locator("[data-play-all]"), `${label} still carries data-play-all`).toHaveCount(0);
    await expect(page.locator("button", { hasText: /^播放全部$/ }), `${label} still shows 播放全部`).toHaveCount(0);
  };

  await loadLibrary(page, { width: 1440, height: 900 });
  await noPlayAll("the library views");

  await page.locator("[data-view='albums']").click();
  await expect(page.locator(".album-group-row")).toHaveCount(3);
  await page.locator(".album-group-row").filter({ hasText: "Native DSD" }).click();
  // The page itself still has to work: rows are listed, the way back is there.
  await expect(page.locator(".album-detail-track-list .track").first()).toBeVisible();
  await noPlayAll("the album detail page");
  await page.locator(".album-detail-breadcrumb [data-group-back]").click();
  await expect(page.locator(".album-group-row")).toHaveCount(3);

  await page.locator("[data-view='genres']").click();
  await expect(page.locator(".group-row")).toHaveCount(1);
  await page.locator(".group-row").filter({ hasText: "未分类" }).click();
  await expect(page.locator(".category-tracks-breadcrumb")).toBeVisible();
  await noPlayAll("the genre detail page");
  expect(unexpected).toEqual([]);
});

test("phone hold opens the group menu and list toolbars drop 播放全部", async ({ page }) => {
  // R504: on a phone the group rows had no entry point at all -- `contextmenu`
  // returned early below 761px and there was no hold timer -- so 播放 was only
  // reachable with a mouse.  R508 then removed 播放全部 from every list toolbar
  // (the owner: 取消掉所有列表里面的「播放全部」按钮).  R511 then removed the last
  // three detail-page copies as well, so this only has to prove the list side.
  const consoleErrors = await loadLibrary(page, { width: 390, height: 844 });
  const openView = async view => {
    if ((page.viewportSize()?.width ?? 1440) <= 760) await page.locator("#mobileNavBtn").click();
    await page.locator(`[data-view='${view}']`).click();
  };

  await openView("albums");
  await expect(page.locator(".album-group-row")).toHaveCount(3);
  // The fixture does not publish a per-album count, so the expected size and the
  // expected first track are read from the album's own detail page -- which is
  // also the order the hold's 播放 has to reproduce.
  const albumRow = page.locator(".album-group-row").filter({ hasText: "Native DSD" });
  await albumRow.click();
  const albumTracks = await page.locator(".album-detail-track-list .track .track-title").evaluateAll(nodes => nodes.map(node => node.textContent.trim()));
  expect(albumTracks.length).toBeGreaterThan(1);
  await page.locator(".album-detail-breadcrumb [data-group-back]").click();
  await expect(page.locator(".album-group-row")).toHaveCount(3);
  await albumRow.evaluate(async node => {
    const box = node.getBoundingClientRect();
    const base = {
      bubbles: true, cancelable: true, pointerId: 1, pointerType: "touch", isPrimary: true,
      button: 0, clientX: Math.round(box.left + 40), clientY: Math.round(box.top + box.height / 2),
    };
    node.dispatchEvent(new PointerEvent("pointerdown", base));
    await new Promise(resolve => setTimeout(resolve, 750));
    node.dispatchEvent(new PointerEvent("pointerup", base));
  });
  const menu = page.locator("#trackContextMenu");
  await expect(menu).toBeVisible();
  await expect(menu.locator("[data-group-action]").first()).toHaveAttribute("data-group-action", "play");
  // The release that ends the hold must not also open the album: the row would
  // then navigate away and take the menu with it.
  await expect(page.locator(".album-detail-breadcrumb")).toHaveCount(0);
  await menu.locator("[data-group-action='play']").click();
  await expect(page.locator("#queueCount")).toHaveText(String(albumTracks.length));
  await expect(page.locator("#nowTitle")).toHaveText(albumTracks[0]);

  // R508: 负责人要求取消所有列表里的「播放全部」。平铺列表（全部 / DSD / 最近 /
  // 随机 100）本来就只为这条按钮挂过 #listToolbar，现在整条撤掉。
  await openView("all");
  await expect(page.locator("#listToolbar")).toHaveCount(0);
  await expect(page.locator("[data-play-all]")).toHaveCount(0);

  await openView("random100");
  await expect(page.locator("#listToolbar")).toHaveCount(0);
  await expect(page.locator(".playlist-toolbar")).toHaveCount(0);

  // 播放列表 / 收藏 / 队列原来就有计数条，它还要承载 删除播放列表 与 清空队列，
  // 所以留着——但里面的按钮必须已经不在。
  await openView("queue");
  const queueBar = page.locator(".playlist-toolbar").first();
  await expect(queueBar).toBeVisible();
  await expect(queueBar).toContainText("首歌曲");
  await expect(queueBar.locator("[data-clear-queue]")).toHaveCount(1);
  await expect(queueBar.locator("[data-play-all]")).toHaveCount(0);

  await openView("favorites");
  const favoritesBar = page.locator(".playlist-toolbar").first();
  await expect(favoritesBar).toBeVisible();
  await expect(favoritesBar).toContainText("首收藏歌曲");
  await expect(favoritesBar.locator("[data-play-all]")).toHaveCount(0);
  // The fixture has no audio bytes, so asking the player to start a track leaves
  // generic "Failed to load resource" lines; anything else is a real error.
  expect(consoleErrors.filter(text => !/Failed to load resource/.test(text))).toEqual([]);
});

// R505: the owner asked for 打开包含的文件夹 / 分享外部链接 / 删除歌曲 to disappear on
// phones. All three are file-manager proxy actions (on a phone they either launch
// another app's panel or fall into showFileDetails), and 删除 is the only danger item
// sitting right next to the playback group. Pin both sides of the width line.
test("phone track menu drops the three file actions", async ({ page }) => {
  const consoleErrors = await loadLibrary(page, { width: 390, height: 844 });
  const menu = page.locator("#trackContextMenu");
  const actionsOf = async () => menu.locator("[data-track-action]")
    .evaluateAll(nodes => nodes.map(node => node.dataset.trackAction));

  await page.locator(".track").first().click({ button: "right" });
  await expect(menu).toBeVisible();
  const phoneActions = await actionsOf();
  expect(phoneActions).toEqual(expect.arrayContaining(["queue", "favorite", "playlist", "info"]));
  expect(phoneActions).not.toContain("open-folder");
  expect(phoneActions).not.toContain("share");
  expect(phoneActions).not.toContain("delete-file");

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.locator(".track").first().click({ button: "right" });
  await expect(menu).toBeVisible();
  const desktopActions = await actionsOf();
  expect(desktopActions).toEqual(expect.arrayContaining(["open-folder", "share", "delete-file"]));
  expect(consoleErrors).toEqual([]);
});

test("mobile search, menu, scrolling surface and footer stay usable", async ({ page }) => {
  const consoleErrors = await loadLibrary(page, { width: 390, height: 844 });
  // The top bar is retired below 761px: both phone controls are gone from the
  // markup and their functions live in the settings "播放输出" section, so
  // asserting them visible only ever proved the dead strip was still in the DOM.
  await expect(page.locator("#mobileDeviceBtn")).toHaveCount(0);
  await expect(page.locator("#mobileModeBtn")).toHaveCount(0);
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

// R460: the mobile library column used to be sized as "viewport minus header",
// which is taller than its body-grid row by exactly the player height.  The
// pagination strip therefore overflowed into the player's row, was painted over
// by the player, and could not be tapped in the Android client.  Pin the real
// geometry instead of the CSS text: the strip must sit above the player and its
// next-page button must be the element that receives the tap.
test("mobile pagination strip sits above the player and stays tappable", async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem("fnaudio.pageSize", "2"); } catch (_) {}
  });
  const consoleErrors = [];
  page.on("console", message => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  for (const viewport of [{ width: 360, height: 800 }, { width: 390, height: 844 }, { width: 412, height: 915 }]) {
    await page.setViewportSize(viewport);
    await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
    await expect(page.locator(".track")).toHaveCount(2);
    const geometry = await page.evaluate(() => {
      const pager = document.getElementById("pager");
      const player = document.querySelector(".player");
      const next = pager.querySelector('[data-page-step="1"]');
      const pagerRect = pager.getBoundingClientRect();
      const playerRect = player.getBoundingClientRect();
      const nextRect = next.getBoundingClientRect();
      const hit = document.elementFromPoint(
        Math.round(nextRect.left + nextRect.width / 2),
        Math.round(nextRect.top + nextRect.height / 2),
      );
      return {
        overlap: Math.max(0, Math.round(pagerRect.bottom - playerRect.top)),
        hitPageStep: hit ? (hit.closest("button")?.getAttribute("data-page-step") || null) : null,
        summary: pager.innerText.replace(/\s+/g, " ").trim(),
      };
    });
    expect(geometry.overlap, `pager must not slide under the player at ${viewport.width}x${viewport.height}`).toBe(0);
    expect(geometry.hitPageStep, `pager button must receive the tap at ${viewport.width}x${viewport.height}`).toBe("1");
    await page.click('#pager [data-page-step="1"]');
    await expect(page.locator("#pager")).toContainText("第 2 / 2 页");
  }
  expect(consoleErrors).toEqual([]);
});

// R461: the Android client and any plain browser have no fnOS host, so the
// "选择音乐目录" button used to fail silently (the message landed below the
// fold).  It must now fall back to the server directory browser and let the
// phone add a folder without the fnOS picker.
test("mobile settings can add a music folder through the server browser", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
  await expect(page.locator(".track")).toHaveCount(4);

  // Phones reach settings through the navigation drawer.
  await page.locator("#mobileNavBtn").click();
  await page.locator("#mobileSettingsNavBtn").click();
  await expect(page.locator("#folderDialog")).toHaveAttribute("open", "");
  // The phone frame opens on the group list, so the library pane is one tap in.
  await page.locator('[data-settings-tab="library"]').click();
  await expect(page.locator("#settings-pane-library")).toBeVisible();
  await page.locator("#chooseLibraryPathBtn").click();

  const browser = page.locator("#libraryDirDialog");
  await expect(browser).toHaveAttribute("open", "");
  // The first screen is the user's own storage ("我的文件"), exactly like the
  // fnOS picker; the volume root with @appdata/docker/thumb is never shown.
  await expect(browser.locator("#libraryDirList")).toContainText("我的文件");
  await expect(browser.locator("#libraryDirList")).not.toContainText("@appdata");
  const statusUnderButton = await page.evaluate(() => {
    const status = document.getElementById("librarySettingsStatus");
    const picker = document.getElementById("chooseLibraryPathBtn");
    if (!status || !picker) return null;
    return { text: status.textContent, belowButton: status.getBoundingClientRect().top >= picker.getBoundingClientRect().top };
  });
  expect(statusUnderButton?.belowButton, "the fallback hint must sit under the button the user just tapped").toBe(true);

  await browser.locator('#libraryDirList [data-dir-path="/vol1/1000"]').click();
  await expect(browser.locator("#libraryDirPath")).toHaveText("/vol1/1000");
  // "Up" from the home returns to the root list rather than walking up to /vol1,
  // which is where @appdata, docker and thumb live.
  await browser.locator("#libraryDirUpBtn").click();
  await expect(browser.locator("#libraryDirList")).toContainText("我的文件");
  await expect(browser.locator("#libraryDirPath")).toHaveText("选择一个磁盘或共享目录");
  await browser.locator('#libraryDirList [data-dir-path="/vol1/1000"]').click();
  await expect(browser.locator("#libraryDirPath")).toHaveText("/vol1/1000");
  await browser.locator('#libraryDirList [data-dir-path="/vol1/1000/Music"]').click();
  await expect(browser.locator("#libraryDirPath")).toHaveText("/vol1/1000/Music");

  await browser.locator("#libraryDirAddBtn").click();
  await expect(page.locator("#folderDialog")).toHaveAttribute("open", "");
  // The fixture already ships one configured root, so the newly added folder is
  // the last row rather than the only one.
  await expect(page.locator("#libraryPathList .library-path-input").last()).toHaveValue("/vol1/1000/Music");
  await expect(page.locator("#librarySettingsStatus")).toContainText("已添加目录");
  await expect(browser).not.toHaveAttribute("open", "");
});

test("a phone tap opens a folder row while a desktop click only selects it", async ({ page }) => {
  // R513（负责人「移动端文件夹改为单击进入」）。 Before this the folder branch of the
  // click handler swallowed the tap on a phone: the row highlighted nothing, opened
  // nothing, and the only way in was the hold menu's 打开 — which read as "the tap
  // did not work".  Desktop keeps the explorer idiom (single click selects, double
  // click enters), so both halves are asserted here against the same markup.
  await loadLibrary(page, { width: 390, height: 844 });
  await page.route("**/api/library/folders**", route => route.fulfill({
    json: { folders: [{ name: "Live", path: "/fixture/music/Live", root: "/fixture/music", track_count: 1 }], count: 1 },
  }));
  await page.locator("#mobileNavBtn").click();
  await page.locator("[data-view='folders']").click();
  const phoneRow = page.locator(".folder-group-row").first();
  await expect(phoneRow).toBeVisible();
  await phoneRow.click();
  // The breadcrumb only exists once the folder has been entered.
  await expect(page.locator(".folder-breadcrumb")).toBeVisible();
  await expect(page.locator(".folder-crumb.is-current")).toHaveText("Live");

  // A fresh load puts the view back on the library root, so the desktop half
  // starts from the same place the phone half did.
  await loadLibrary(page, { width: 1440, height: 900 });
  await page.locator("[data-view='folders']").click();
  const desktopRow = page.locator(".folder-group-row").first();
  await expect(desktopRow).toBeVisible();
  await desktopRow.click();
  // A desktop single click selects the row and must not leave the folder list: at
  // the library root there is no current-folder crumb, and only entering the folder
  // creates one.
  await expect(desktopRow).toHaveClass(/is-selected/);
  await expect(page.locator(".folder-crumb.is-current")).toHaveCount(0);
  await desktopRow.dblclick();
  await expect(page.locator(".folder-crumb.is-current")).toHaveText("Live");
});

test("completion log names the failed and unmatched tracks instead of only counting them", async ({ page }) => {
  // R519: the log used to print "失败 2 · 未匹配 155" and stop there, which is a
  // number nobody can act on.  The counters are the entry point now and the
  // dialog has to answer "which track, which job, what error".
  await loadLibrary(page, { width: 1440, height: 900 });
  await page.locator("#mobileSettingsNavBtn").click();
  await page.locator("[data-settings-tab='metadata']").click();

  const failedCounter = page.locator('[data-metadata-stat-issues="failed"]');
  await expect(failedCounter).toBeVisible();
  await expect(failedCounter).toContainText("6");
  await failedCounter.click();

  await expect(page.locator("#metadataLogDialog")).toBeVisible();
  await expect(page.locator("#metadataLogIssues")).toBeVisible();
  // The summary splits the counters by job type instead of repeating the total.
  await expect(page.locator("#metadataLogSummary")).toContainText("失败 6（Tag 写回 4、歌词 2）");
  await expect(page.locator("#metadataLogSummary")).toContainText("未匹配 8（歌词 6、封面 2）");

  const rows = page.locator("#metadataLogIssuesList .metadata-log-issue");
  await expect(rows).toHaveCount(4);
  await expect(rows.first()).toContainText("晨光");
  await expect(rows.first()).toContainText("Tag 写回");
  await expect(rows.first()).toContainText("permission denied");
  await expect(page.locator("#metadataLogIssuesNote")).toContainText("另有 10 条未展开");

  // A named track is actionable, but only when the loaded page can resolve it.
  await expect(rows.first()).toHaveAttribute("role", "button");
  await expect(rows.first()).toHaveAttribute("data-metadata-issue-track", "fixture-1");
  await expect(rows.last()).toHaveAttribute("role", "button");

  await page.locator("#closeMetadataLogBtn").click();
  await expect(page.locator("#metadataLogDialog")).toBeHidden();
});

test("the issue detail still fits a phone screen", async ({ page }) => {
  // The detail block adds height to a dialog that already had a fixed window on
  // a phone; the flex column has to keep both the rows and the footer reachable.
  await loadLibrary(page, { width: 390, height: 844 });
  await page.locator("#mobileNavBtn").click();
  await page.locator("#mobileSettingsNavBtn").click();
  await page.locator("[data-settings-tab='metadata']").click();

  const failedCounter = page.locator('[data-metadata-stat-issues="failed"]');
  await failedCounter.scrollIntoViewIfNeeded();
  await failedCounter.click();

  await expect(page.locator("#metadataLogDialog")).toBeVisible();
  await expect(page.locator("#metadataLogIssuesList .metadata-log-issue").first()).toBeVisible();
  const box = await page.locator("#metadataLogDialog").boundingBox();
  expect(box.y).toBeGreaterThanOrEqual(0);
  expect(box.y + box.height).toBeLessThanOrEqual(845);
  await expect(page.locator("#closeMetadataLogBtn")).toBeVisible();
  await page.locator("#closeMetadataLogBtn").click();
  await expect(page.locator("#metadataLogDialog")).toBeHidden();
});
