const path = require('path');
const {spawn} = require('child_process');
const {test, expect} = require('@playwright/test');

let fixture;
let baseUrl;
test.beforeAll(async () => {
  fixture = spawn(process.env.PYTHON || 'python', ['-B', path.resolve(__dirname, '../../ui_e2e_fixture.py'), '--port', '0'], {stdio:['ignore','pipe','pipe']});
  baseUrl = await new Promise((resolve,reject) => {
    const timer = setTimeout(() => reject(new Error('fixture startup timeout')),8000);
    fixture.once('error',reject);
    fixture.stdout.once('data',data => {clearTimeout(timer); resolve(String(data).trim());});
  });
});
test.afterAll(() => fixture?.kill());

async function load(page, width=1440, height=900) {
  await page.setViewportSize({width,height});
  await page.goto(baseUrl,{waitUntil:'networkidle'});
  await expect(page.locator('.track')).toHaveCount(4);
}
async function openSettings(page) {
  if ((page.viewportSize()?.width ?? 1440) <= 760) await page.locator('#mobileNavBtn').click();
  await page.locator('#mobileSettingsNavBtn').click();
}
// Phones open settings on the rail; picking a group is what reveals its pane.
async function openSettingsGroup(page, name) {
  await openSettings(page);
  await page.locator(`[data-settings-tab="${name}"]`).click();
  await expect(page.locator(`#settings-pane-${name}`)).toBeVisible();
}
async function insideViewport(page, selector) {
  const element = page.locator(selector);
  await expect(element,selector).toBeVisible();
  const bounds = await element.boundingBox();
  const viewport = page.viewportSize();
  expect(bounds.x,selector).toBeGreaterThanOrEqual(-1);
  expect(bounds.y,selector).toBeGreaterThanOrEqual(-1);
  expect(bounds.x+bounds.width,selector).toBeLessThanOrEqual(viewport.width+1);
  expect(bounds.y+bounds.height,selector).toBeLessThanOrEqual(viewport.height+1);
}
async function screenshot(page, info, name) {
  await page.screenshot({path:info.outputPath(name+'.png')});
}

test('FNOS search field syncs input and clears from either viewport', async ({page}, info) => {
  await load(page, 1440, 900);
  await expect(page.locator('.mobile-library-search')).toBeHidden();
  await expect(page.locator('#pager')).toBeHidden();
  const desktopInput = page.locator('#searchInput');
  const mobileInput = page.locator('#mobileSearchInput');
  const desktopClear = page.locator('#searchClearBtn');
  const mobileClear = page.locator('#mobileSearchClearBtn');
  await expect(desktopClear).toBeHidden();
  await expect(mobileClear).toBeHidden();
  await page.screenshot({path: info.outputPath('search-field-desktop.png')});
  await desktopInput.fill('测试搜索');
  await expect(mobileInput).toHaveValue('测试搜索');
  await expect(desktopClear).toBeVisible();
  await expect(mobileClear).toBeHidden();
  expect(await desktopInput.evaluate(element => getComputedStyle(element).outlineStyle)).toBe('none');
  expect(await desktopInput.evaluate(element => getComputedStyle(element).boxShadow)).toBe('none');
  await desktopClear.click();
  await expect(desktopInput).toHaveValue('');
  await expect(mobileInput).toHaveValue('');
  await expect(desktopClear).toBeHidden();
  await page.setViewportSize({width: 375, height: 812});
  await expect(mobileInput).toBeVisible();
  await mobileInput.fill('移动搜索');
  await expect(desktopInput).toHaveValue('移动搜索');
  await expect(mobileClear).toBeVisible();
  await mobileClear.click();
  await expect(mobileInput).toHaveValue('');
  await expect(desktopInput).toHaveValue('');
  await expect(mobileClear).toBeHidden();
  await page.screenshot({path: info.outputPath('search-field-mobile.png')});
});

test('Requested UI: toolbar column shortcut removed, table column selector retained', async ({page}) => {
  await load(page);
  await expect(page.locator('#mobileColumnsBtn')).toHaveCount(0);
  await page.locator('.table-head-more:visible').click();
  await expect(page.locator('#columnsDialog')).toBeVisible();
  const selectedCount = await page.locator('#selectedColumnChoiceList .column-choice').count();
  await expect(page.locator('#selectedColumnChoiceList .column-move-button svg')).toHaveCount(selectedCount * 2);
  await expect(page.locator('#selectedColumnChoiceList .column-move-button[aria-label="上移"]')).toHaveCount(selectedCount);
  await expect(page.locator('#selectedColumnChoiceList .column-move-button[aria-label="下移"]')).toHaveCount(selectedCount);
});

test('FNOS: every button has an accessible name',async({page})=>{
  await load(page);
  const unnamed=await page.locator('button').evaluateAll(buttons=>buttons
    .filter(button=>!button.disabled && !button.getAttribute('aria-hidden'))
    .filter(button=>!button.getAttribute('aria-label') && !button.getAttribute('aria-labelledby')
      && !button.title && !button.innerText.trim())
    .map(button=>({id:button.id,className:button.className,html:button.outerHTML.slice(0,180)})));
  expect(unnamed).toEqual([]);
});

for (const [width, height] of [[1440, 900], [375, 812]]) {
  test(`FNOS ${width}: visible button icons fit their hit targets`, async ({page}) => {
    await load(page, width, height);
    const overflow = await page.locator('button:visible svg:visible, button:visible .mode-mp3-icon:visible').evaluateAll(elements => elements
      .map(icon => {
        const iconBox = icon.getBoundingClientRect();
        const buttonBox = icon.closest('button').getBoundingClientRect();
        return {
          button: icon.closest('button').id || icon.closest('button').getAttribute('aria-label') || icon.closest('button').textContent.trim(),
          width: iconBox.width,
          height: iconBox.height,
          left: iconBox.left - buttonBox.left,
          right: buttonBox.right - iconBox.right,
          top: iconBox.top - buttonBox.top,
          bottom: buttonBox.bottom - iconBox.bottom,
        };
      })
      .filter(icon => icon.width <= 0 || icon.height <= 0 || icon.left < -1 || icon.right < -1 || icon.top < -1 || icon.bottom < -1));
    expect(overflow).toEqual([]);
  });
}

test('FNOS: touch WebViews with a wide CSS viewport retain mobile geometry', async ({browser}) => {
  const context = await browser.newContext({viewport:{width:980,height:2000},isMobile:true,hasTouch:true,deviceScaleFactor:3});
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  await cdp.send('Emulation.setEmulatedMedia',{features:[{name:'pointer',value:'coarse'},{name:'hover',value:'none'}]});
  await page.goto(baseUrl,{waitUntil:'networkidle'});
  await expect(page.locator('.track')).toHaveCount(4);
  const geometry = await page.evaluate(() => {
    const rect = selector => {
      const value = document.querySelector(selector).getBoundingClientRect();
      return {left:value.left,right:value.right,width:value.width,center:(value.left+value.right)/2};
    };
    return {
      viewport:innerWidth,
      pointerCoarse:matchMedia('(pointer: coarse)').matches,
      documentWidth:document.documentElement.scrollWidth,
      headerHeight:getComputedStyle(document.querySelector('.topbar')).height,
      pagebarJustify:getComputedStyle(document.querySelector('.mobile-pagebar')).justifyContent,
      pagebarTitleLeft:document.querySelector('.mobile-page-title').getBoundingClientRect().left,
      pagebarButtonRight:document.querySelector('#mobileNavBtn').getBoundingClientRect().right,
      player:rect('.player'),
      transport:rect('.transport'),
      elapsed:rect('#elapsed'),
      duration:rect('#duration'),
    };
  });
    expect(geometry.headerHeight, JSON.stringify(geometry)).toBe('56px');
  expect(geometry.pagebarJustify, JSON.stringify(geometry)).toBe('flex-start');
  expect(geometry.pagebarTitleLeft).toBeGreaterThan(geometry.pagebarButtonRight);
    await expect(page.locator('.top-actions')).toHaveCount(0);
    await expect(page.locator('.mobile-pagebar')).toBeVisible();
  expect(Math.abs(geometry.transport.center-geometry.viewport/2)).toBeLessThanOrEqual(1);
  expect(geometry.elapsed.left).toBeGreaterThanOrEqual(0);
  expect(geometry.duration.right).toBeLessThanOrEqual(geometry.viewport);
  expect(geometry.documentWidth).toBeLessThanOrEqual(geometry.viewport);
  expect(geometry.player.right).toBeLessThanOrEqual(geometry.viewport);
  await context.close();
});

test('Android WebView class keeps the header left-aligned outside media-query width', async ({page}) => {
  await load(page, 1440, 900);
  const layout = await page.evaluate(() => {
    document.documentElement.classList.add('fnaudio-android-client');
    const pagebar = document.querySelector('.mobile-pagebar');
    const title = document.querySelector('.mobile-page-title');
    const menu = document.querySelector('#mobileNavBtn');
    return {
      pagebarDisplay: getComputedStyle(pagebar).display,
      pagebarJustify: getComputedStyle(pagebar).justifyContent,
      titleTextAlign: getComputedStyle(title).textAlign,
      titleLeft: title.getBoundingClientRect().left,
      menuRight: menu.getBoundingClientRect().right,
      topActionsCount: document.querySelectorAll('.top-actions').length,
    };
  });
  expect(layout.pagebarDisplay).toBe('flex');
  expect(layout.pagebarJustify).toBe('flex-start');
  expect(layout.titleTextAlign).toBe('left');
  expect(layout.titleLeft).toBeGreaterThanOrEqual(layout.menuRight);
  expect(layout.topActionsCount).toBe(0);
});

test('Desktop actions are hidden and sidebar settings stay fixed while library nav scrolls', async ({page}) => {
  await load(page, 1440, 900);
  await expect(page.locator('.top-actions')).toHaveCount(0);
  await expect(page.locator('.sidebar-footer')).toHaveCount(0);
  await expect(page.locator('.sidebar')).toHaveCSS('width', '188px');
  await page.locator('#pager').evaluate(element => {
    element.innerHTML = '<div class="pager-inner"><div class="pager-nav"><button class="pager-nav-button" type="button" aria-label="首页"><svg viewBox="0 0 24 24"><path d="M18 6 12 12l6 6"/><path d="m11 6-5 6 6 6"/></svg></button><button class="pager-nav-button" type="button" aria-label="上一页"><svg viewBox="0 0 24 24"><path d="m15 6-6 6 6 6"/></svg></button><span class="pager-page-summary" aria-label="当前页">第 1 / 2 页</span><button class="pager-nav-button" type="button" aria-label="下一页"><svg viewBox="0 0 24 24"><path d="m9 6 6 6-6 6"/></svg></button><button class="pager-nav-button" type="button" aria-label="尾页"><svg viewBox="0 0 24 24"><path d="m6 6 6 6-6 6"/><path d="m13 6 6 6-6 6"/></svg></button></div><div class="pager-status"><span>共 2 首</span><button class="pager-refresh-button" type="button" aria-label="刷新音乐库"></button></div></div>';
  });
  const settingsRow = await page.locator('.sidebar-settings').boundingBox();
  const pagerRow = await page.locator('#pager').boundingBox();
  const settingsButton = await page.locator('#mobileSettingsNavBtn').boundingBox();
  expect(settingsRow.height).toBe(44);
  expect(pagerRow.height).toBe(settingsRow.height);
  const pagerChildren = await page.locator('.pager-nav > *').evaluateAll(elements => elements.map(element => {
    const rect = element.getBoundingClientRect();
    return {left: rect.left, right: rect.right};
  }));
  for (let index = 1; index < pagerChildren.length; index++) {
    expect(pagerChildren[index].left).toBeGreaterThanOrEqual(pagerChildren[index - 1].right - 1);
  }
  expect(Math.abs((settingsButton.y - settingsRow.y) - (settingsRow.y + settingsRow.height - (settingsButton.y + settingsButton.height)))).toBeLessThanOrEqual(1);
  const before = await page.locator('#mobileSettingsNavBtn').boundingBox();
  const scroll = page.locator('.sidebar-scroll');
  await scroll.evaluate(element => {
    for (let i = 0; i < 20; i++) {
      const item = document.createElement('button');
      item.className = 'nav-item';
      item.textContent = `额外分类 ${i}`;
      element.append(item);
    }
    element.scrollTop = element.scrollHeight;
  });
  const after = await page.locator('#mobileSettingsNavBtn').boundingBox();
  expect(await scroll.evaluate(element => element.scrollTop)).toBeGreaterThan(0);
  expect(Math.abs(after.y - before.y)).toBeLessThanOrEqual(1);
  await expect(page.locator('#mobileSettingsNavBtn')).toBeVisible();
  await page.screenshot({path:path.resolve(__dirname, '../test-results/sidebar-settings-fixed-desktop.png')});
  await page.locator('#mobileSettingsNavBtn').click();
  await expect(page.locator('#folderDialog')).toBeVisible();
});

test('Mobile sidebar settings stay docked below the scrolling library navigation', async ({page}, info) => {
  await load(page, 375, 812);
  await page.locator('#mobileNavBtn').click();
  await expect(page.locator('.sidebar-footer')).toHaveCount(0);
  const drawer = await page.locator('.sidebar').boundingBox();
  expect(drawer.width).toBeCloseTo(260, 0);
  const scrollBox = await page.locator('.sidebar-scroll').boundingBox();
  expect(Math.abs((scrollBox.x + scrollBox.width) - (drawer.x + drawer.width))).toBeLessThanOrEqual(1);
  const settingsBox = await page.locator('.sidebar-settings').boundingBox();
  const settingsButtonBox = await page.locator('#mobileSettingsNavBtn').boundingBox();
  expect(Math.abs((settingsButtonBox.y - settingsBox.y) - (settingsBox.y + settingsBox.height - (settingsButtonBox.y + settingsButtonBox.height)))).toBeLessThanOrEqual(1);
  const settings = page.locator('#mobileSettingsNavBtn');
  const before = await settings.boundingBox();
  const scroll = page.locator('.sidebar-scroll');
  await scroll.evaluate(element => {
    for (let i = 0; i < 20; i++) {
      const item = document.createElement('button');
      item.className = 'nav-item';
      item.textContent = `额外分类 ${i}`;
      element.append(item);
    }
    element.scrollTop = element.scrollHeight;
  });
  const after = await settings.boundingBox();
  expect(await scroll.evaluate(element => element.scrollTop)).toBeGreaterThan(0);
  expect(Math.abs(after.y - before.y)).toBeLessThanOrEqual(1);
  await expect(settings).toBeVisible();
  await page.screenshot({path:info.outputPath('sidebar-settings-fixed-mobile.png')});
});

test('Desktop player uses a full-width progress rail and puts time under track details', async ({page}, info) => {
  await load(page, 1440, 900);
  const layout = await page.evaluate(() => {
    const box = selector => {
      const rect = document.querySelector(selector).getBoundingClientRect();
      return {left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom, width: rect.width, height: rect.height};
    };
    return {
      player: box('.player'),
      progress: box('.player .progress'),
      elapsed: box('.player #elapsed'),
      seek: box('.player #seek'),
      duration: box('.player #duration'),
      nowTime: box('.player #nowTime'),
      transport: box('.player .transport'),
      track: box('.player .now-playing'),
      actions: box('.player .player-actions'),
    };
  });
  expect(Math.abs(layout.progress.bottom - layout.player.top)).toBeLessThanOrEqual(1);
  expect(layout.progress.left - layout.player.left).toBeGreaterThanOrEqual(0);
  expect(layout.player.right - layout.progress.right).toBeGreaterThanOrEqual(0);
  expect(layout.progress.width).toBeGreaterThan(layout.player.width - 48);
  expect(layout.elapsed.width).toBe(0);
  expect(layout.duration.width).toBe(0);
  expect(layout.nowTime.top).toBeGreaterThan(layout.track.top);
  expect(layout.nowTime.left).toBeGreaterThanOrEqual(layout.track.left);
  await expect(page.locator('#transportStateUnknown')).toBeHidden();
  expect(layout.seek.left).toBeGreaterThanOrEqual(layout.progress.left);
  expect(layout.seek.right).toBeLessThanOrEqual(layout.progress.right);
  // R485: the track information owns the left edge, the transport owns the
  // middle of the bar, and the action row keeps the right edge.
  expect(layout.track.left).toBeLessThan(layout.transport.left);
  expect(layout.transport.right).toBeLessThanOrEqual(layout.actions.left);
  expect(layout.player.right - layout.actions.right).toBeLessThanOrEqual(24);
  expect(Math.abs((layout.transport.left + layout.transport.right) / 2 - (layout.player.left + layout.player.right) / 2)).toBeLessThanOrEqual(1);
  for (const child of [layout.transport, layout.track, layout.actions]) {
    expect(Math.abs((child.top + child.bottom) / 2 - (layout.player.top + layout.player.bottom) / 2)).toBeLessThanOrEqual(1);
  }
  await page.screenshot({path:info.outputPath('desktop-player-centered-controls.png')});
});

test('Desktop player keeps the transport on the centre line when the window narrows', async ({page}, info) => {
  // The outer columns are equal shares of the leftover width, so the transport
  // is centred by construction.  A narrow window is where a long title or a wide
  // action row could quietly push it off that line again.
  await load(page, 800, 900);
  const layout = await page.evaluate(() => {
    document.querySelector('.now-meta strong').textContent =
      '这是一个非常长的歌曲标题用来确认截断而不是把中间的控制区推走';
    const box = selector => {
      const rect = document.querySelector(selector).getBoundingClientRect();
      return {left: rect.left, right: rect.right, width: rect.width};
    };
    const player = box('.player');
    const title = document.querySelector('.now-meta strong');
    return {
      player,
      transport: box('.player .transport'),
      track: box('.player .now-playing'),
      actions: box('.player .player-actions'),
      overflow: getComputedStyle(title).textOverflow,
      actionsOverflow: document.querySelector('.player-actions').scrollWidth
        - document.querySelector('.player-actions').clientWidth,
    };
  });
  expect(Math.abs((layout.transport.left + layout.transport.right) / 2 - (layout.player.left + layout.player.right) / 2)).toBeLessThanOrEqual(1);
  expect(layout.track.right).toBeLessThanOrEqual(layout.transport.left);
  expect(layout.transport.right).toBeLessThanOrEqual(layout.actions.left);
  expect(layout.overflow).toBe('ellipsis');
  // One pixel of slack: at 761px the action row is exactly as wide as its column.
  expect(layout.actionsOverflow).toBeLessThanOrEqual(1);
  await page.screenshot({path:info.outputPath('desktop-player-centered-narrow.png')});
});

test('Desktop player action row keeps one pitch on both sides of the 1180px breakpoint', async ({page}) => {
  // The volume control is a wrapper around a button.  When the wrapper and the
  // button disagree on width the row's last gap grows by the difference, so
  // resizing the window silently changes the spacing: below 1180px both were
  // 34px and the row looked even, above it the wrapper was 40px against a 36px
  // button and the gap before the speaker read 2px wider than the rest.
  const measure = () => page.evaluate(() => {
    const ids = ['deviceBtn', 'lyricsBtn', 'favoriteCurrentBtn', 'repeatBtn', 'shuffleBtn', 'queueBtn', 'volumeBtn'];
    const boxes = ids.map(id => document.getElementById(id).getBoundingClientRect());
    const gaps = [];
    for (let k = 1; k < boxes.length; k += 1) gaps.push(+(boxes[k].left - boxes[k - 1].right).toFixed(1));
    return {gaps, widths: boxes.map(box => +box.width.toFixed(1))};
  });

  const rows = [];
  for (const width of [1111, 1192, 1440]) {
    await load(page, width, 900);
    rows.push({width, ...(await measure())});
  }
  for (const row of rows) {
    expect(new Set(row.widths).size, `action buttons differ in size at ${row.width}: ${row.widths.join(',')}`).toBe(1);
    expect(new Set(row.gaps).size, `action gaps are uneven at ${row.width}: ${row.gaps.join(',')}`).toBe(1);
  }
  // The pitch must not change when the window crosses the breakpoint.
  expect(rows[1].gaps, 'the row re-spaced itself across 1180px').toEqual(rows[0].gaps);
  expect(rows[2].gaps).toEqual(rows[0].gaps);
});

test('Mobile player keeps previous, play and next controls centered', async ({page}, info) => {
  await load(page, 375, 812);
  const geometry = await page.evaluate(() => {
    const player = document.querySelector('.player').getBoundingClientRect();
    const progress = document.querySelector('.player .progress').getBoundingClientRect();
    const transport = document.querySelector('.player .transport').getBoundingClientRect();
    const nowTime = document.querySelector('#nowTime').getBoundingClientRect();
    const previous = document.querySelector('#prevBtn').getBoundingClientRect();
    const play = document.querySelector('#playBtn').getBoundingClientRect();
    const next = document.querySelector('#nextBtn').getBoundingClientRect();
    return {
      playerCenter: (player.left + player.right) / 2,
      progressLeft: progress.left,
      progressRight: progress.right,
      progressCenter: (progress.left + progress.right) / 2,
      progressBottom: progress.bottom,
      playerTop: player.top,
      playerBottom: player.bottom,
      transportBottom: transport.bottom,
      transportTop: transport.top,
      transportCenter: (transport.left + transport.right) / 2,
      previousCenter: (previous.left + previous.right) / 2,
      playCenter: (play.left + play.right) / 2,
      nextCenter: (next.left + next.right) / 2,
    };
  });
  expect(Math.abs(geometry.transportCenter - geometry.playerCenter)).toBeLessThanOrEqual(2);
  expect(geometry.playerBottom - geometry.transportBottom).toBeGreaterThanOrEqual(12);
  expect(Math.abs(geometry.progressCenter - geometry.playerCenter)).toBeLessThanOrEqual(1);
  expect(Math.abs(geometry.progressBottom - geometry.playerTop)).toBeLessThanOrEqual(1);
  expect(geometry.progressLeft).toBe(0);
  expect(geometry.progressRight).toBe(375);
  expect(geometry.previousCenter).toBeLessThan(geometry.playCenter);
  expect(geometry.playCenter).toBeLessThan(geometry.nextCenter);
  await page.screenshot({path:info.outputPath('mobile-player-centered-controls.png')});
});

test('Player progress uses a full-width thin rail with time under song details', async ({page}, info) => {
  await load(page, 375, 812);
  const geometry = await page.evaluate(() => {
    const player = document.querySelector('.player').getBoundingClientRect();
    const seek = document.querySelector('#seek');
    seek.value = '50';
    updateSeekRail(50);
    const box = selector => {
      const rect = document.querySelector(selector).getBoundingClientRect();
      return {left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom, width: rect.width, height: rect.height};
    };
    const track = getComputedStyle(seek, '::-webkit-slider-runnable-track');
    const thumb = getComputedStyle(seek, '::-webkit-slider-thumb');
    return {
      rail: box('#seek'),
      player,
      elapsed: box('#elapsed'),
      duration: box('#duration'),
      nowTime: box('#nowTime'),
      trackHeight: track.height,
      thumbWidth: thumb.width,
      fill: seek.style.getPropertyValue('--seek-fill'),
      overflow: getComputedStyle(document.querySelector('.progress')).overflow,
    };
  });
  expect(geometry.rail.height).toBe(4);
  expect(geometry.elapsed.width).toBe(0);
  expect(geometry.duration.width).toBe(0);
  expect(geometry.nowTime.top).toBeGreaterThanOrEqual(geometry.player.top);
  expect(geometry.nowTime.bottom).toBeLessThanOrEqual(geometry.player.bottom);
  expect(Math.abs(geometry.rail.bottom - geometry.player.top)).toBeLessThanOrEqual(1);
  await expect(page.locator('#transportStateUnknown')).toBeHidden();
  expect(geometry.rail.left).toBe(0);
  expect(geometry.rail.right).toBe(375);
  expect(geometry.fill).toBe('50%');
  // The 10px handle is taller than the rail, so the phone rail may not clip it.
  expect(geometry.overflow).toBe('visible');

  // The buffered band: 30s played of 120s, buffered to 90s, arrives through the
  // same `progress` event the browser fires.
  const buffer = await page.evaluate(() => {
    const audio = document.querySelector('#audio');
    const ranges = {length: 1, start: () => 0, end: () => 90};
    Object.defineProperty(audio, 'buffered', {configurable: true, get: () => ranges});
    Object.defineProperty(audio, 'currentTime', {configurable: true, get: () => 30, set: () => {}});
    Object.defineProperty(audio, 'duration', {configurable: true, get: () => 120});
    audio.dispatchEvent(new Event('progress'));
    const seek = document.querySelector('#seek');
    return {fill: seek.style.getPropertyValue('--seek-fill'), buffer: seek.style.getPropertyValue('--seek-buffer')};
  });
  expect(buffer.fill).toBe('50%');
  expect(buffer.buffer).toBe('75%');
  await screenshot(page, info, 'player-progress-reference-style');
});

test('Player keeps readable transport glyphs when the theme layer is unavailable', async ({page}) => {
  // The theme layer is the last sheet and restyles the player, but the page has
  // to stay readable without it: a stale cache, a blocked request or an older
  // WebView can all leave app.css as the only sheet that applies.  In that
  // state the transport glyphs used to fall back to the SVG default black fill,
  // which painted a black triangle inside the blue play button, and the phone
  // seek rail fell back to the native #efefef control.
  await page.emulateMedia({colorScheme: 'dark'});
  await load(page, 375, 812);
  await page.evaluate(() => {
    for (const link of document.querySelectorAll('link[rel=stylesheet]')) {
      if (link.href.includes('fnos-theme.css')) link.disabled = true;
    }
  });
  const bare = await page.evaluate(() => {
    const fillOf = id => getComputedStyle(document.getElementById(id).querySelector('svg')).fill;
    const seek = document.getElementById('seek');
    return {
      play: fillOf('playBtn'),
      prev: fillOf('prevBtn'),
      next: fillOf('nextBtn'),
      seekAppearance: getComputedStyle(seek).appearance,
      seekHeight: seek.getBoundingClientRect().height,
    };
  });
  expect(bare.play, 'the play triangle must stay white on the accent disc').toBe('rgb(255, 255, 255)');
  for (const [name, fill] of [['prev', bare.prev], ['next', bare.next]]) {
    expect(fill, `${name} must not fall back to the black SVG default`).not.toBe('rgb(0, 0, 0)');
    expect(fill, `${name} must take the button colour`).toBe('rgba(255, 255, 255, 0.75)');
  }
  expect(bare.seekAppearance, 'the phone seek must not fall back to the native control').toBe('none');
  expect(bare.seekHeight).toBe(8);
});

test('A dropped stylesheet request is retried instead of leaving the player half-styled', async ({page}) => {
  // Regression for the intermittent report: the same build painted white
  // transport glyphs on one launch and black ones on the next.  A single failed
  // request for fnos-theme.css is enough to cause it -- app.css and
  // design-tokens.css still carry the layout and the palette, so the only
  // symptoms are the black SVG default on the transport glyphs and the native
  // seek rail.  The browser never re-requests a sheet that failed, so the page
  // has to do it.
  let attempts = 0;
  await page.route('**/fnos-theme.css*', async route => {
    attempts += 1;
    if (attempts === 1) return route.abort('failed');
    return route.continue();
  });
  await page.setViewportSize({width: 375, height: 812});
  await page.goto(baseUrl, {waitUntil: 'load'});
  await expect.poll(() => attempts, {
    message: 'the sheet that failed must be requested again',
    timeout: 5000,
  }).toBeGreaterThan(1);
  await expect.poll(() => page.evaluate(() => {
    const links = [...document.querySelectorAll('link[href*="fnos-theme.css"]')];
    return {count: links.length, applied: links.filter(link => !!link.sheet).length};
  }), {message: 'the retried sheet must end up applied', timeout: 5000}).toEqual({count: 1, applied: 1});
  // Exactly one retry: a sheet that is genuinely gone must not turn into a loop.
  expect(attempts, 'the retry must not repeat').toBe(2);
});

test('FNOS: every dialog close control uses the shared line icon', async ({page}) => {
  await load(page);
  const ids = [
    'closeDialog', 'closeFolderDialog', 'closeDlnaDiagnosticsDialog', 'closePlaylistDialog',
    'closeTrackActionDialog', 'closeMetadataCandidateDialog', 'closeExternalShareDialog',
    'closeColumnsDialog',
  ];
  for (const id of ids) {
    const button = page.locator(`#${id}`);
    await expect(button).toHaveClass(/dialog-close-button/);
    await expect(button).toHaveAttribute('type', 'button');
    await expect(button).toHaveAttribute('aria-label', '关闭');
    await expect(button.locator('svg')).toHaveCount(1);
    await expect(button.locator('svg path')).toHaveCount(1);
    await expect(button.locator('svg path')).toHaveAttribute('d', /M18 6/);
    await expect(button).not.toContainText('×');
  }
});

test('FNOS: dynamic playlist navigation uses the shared line icon system', async ({page}) => {
  await load(page);
  const createPlaylist = page.locator('#newPlaylistBtn');
  await expect(createPlaylist.locator('svg')).toBeVisible();
  await expect(createPlaylist.locator('svg')).toHaveAttribute('aria-hidden', 'true');
  await expect(createPlaylist).toContainText('新建播放列表');
  await createPlaylist.click();
  await page.locator('#playlistNameInput').fill('图标验收播放列表');
  await page.locator('#savePlaylistBtn').click();
  const entry = page.locator('#playlistNav .playlist-nav-item').first();
  await expect(entry.locator('svg')).toBeVisible();
  await expect(entry.locator('svg path')).toHaveCount(1);
  await expect(entry).not.toContainText('♪');
});

test('FNOS: transport controls use SVG without invoking audio during visual state checks', async ({page}, info) => {
  await load(page);
  for (const [id, icon] of [['prevBtn', 'prev-icon'], ['playBtn', 'play-icon'], ['nextBtn', 'next-icon']]) {
    const control = page.locator(`#${id}`);
    await expect(control.locator(`svg.transport-icon.${icon}`)).toBeVisible();
    await expect(control.locator('svg')).toHaveAttribute('aria-hidden', 'true');
  }
  const play = page.locator('#playBtn');
  await play.evaluate(button => window.setPlayButton(true));
  await expect(play.locator('svg.transport-icon.pause-icon')).toBeVisible();
  await play.evaluate(button => window.setPlayButton(false));
  await expect(play.locator('svg.transport-icon.play-icon')).toBeVisible();
  await screenshot(page, info, 'transport-svg-icons');
});

test('FNOS: empty library state uses the shared line icon system', async ({page}, info) => {
  await load(page);
  await page.locator('#empty').evaluate(element => { element.hidden = false; });
  await expect(page.locator('#empty .empty-icon svg.record-placeholder')).toBeVisible();
  await expect(page.locator('#empty .empty-icon svg circle')).toHaveCount(2);
  await expect(page.locator('#empty .empty-icon')).not.toContainText('♪');
  await screenshot(page, info, 'empty-library');
});

test('FNOS: missing artwork uses the record fallback across player surfaces', async ({page}, info) => {
  await load(page);
  await page.locator('#lyricsView').evaluate(element => { element.hidden = false; });
  for (const selector of ['.track-cover:has(.track-cover-fallback:not([hidden]))', '#nowCover', '#lyricsCover']) {
    const fallback = page.locator(selector).first();
    await expect(fallback).toBeVisible();
    await expect(fallback.locator('svg.record-placeholder')).toHaveCount(1);
    await expect(fallback.locator('svg.record-placeholder')).toHaveAttribute('aria-hidden', 'true');
    const svg = await fallback.locator('svg.record-placeholder').evaluate(element => ({
      width: getComputedStyle(element).width,
      height: getComputedStyle(element).height,
    }));
    expect(svg.width, `${selector} must render a visible record placeholder`).not.toBe('0px');
    expect(svg.height, `${selector} must render a visible record placeholder`).not.toBe('0px');
  }
  await screenshot(page, info, 'cover-fallbacks');
});

test('FNOS: current track indicator uses the shared blue state token', async ({page}) => {
  await load(page);
  const row = page.locator('.track').first();
  await row.evaluate(element => element.classList.add('is-current'));
  const style = await row.evaluate(element => {
    const computed = getComputedStyle(element);
    return {
      backgroundColor: computed.backgroundColor,
      boxShadow: computed.boxShadow,
      titleColor: getComputedStyle(element.querySelector('.track-title')).color,
    };
  });
  expect(style.backgroundColor).toBe('rgba(0, 0, 0, 0)');
  expect(style.boxShadow).toBe('none');
  expect(style.titleColor).toBe('rgb(0, 102, 255)');
});

test('FNOS: player control states use the shared blue tokens', async ({page}) => {
  await load(page);
  await page.evaluate(() => { document.documentElement.dataset.theme = 'light'; });
  await page.evaluate(() => {
    ['shuffleBtn', 'repeatBtn', 'favoriteCurrentBtn'].forEach(id => $(id).classList.add('active-control'));
  });
  const colors = await page.evaluate(() => ['shuffleBtn', 'repeatBtn', 'favoriteCurrentBtn'].map(id => {
    const style = getComputedStyle($(id));
    return { id, color: style.color, background: style.backgroundColor };
  }));
  expect(colors).toEqual([
    { id: 'shuffleBtn', color: 'rgb(0, 102, 255)', background: 'rgba(0, 102, 255, 0.15)' },
    { id: 'repeatBtn', color: 'rgb(0, 102, 255)', background: 'rgba(0, 102, 255, 0.15)' },
    { id: 'favoriteCurrentBtn', color: 'rgb(0, 102, 255)', background: 'rgba(0, 102, 255, 0.15)' },
  ]);
  await page.locator('#deviceBtn').hover();
  const hover = await page.locator('#deviceBtn').evaluate(button => {
    const style = getComputedStyle(button);
    return { color: style.color, background: style.backgroundColor };
  });
  expect(hover).toEqual({ color: 'rgb(11, 11, 12)', background: 'rgba(0, 0, 0, 0.08)' });
});

test('FNOS: settings save feedback distinguishes success from failure', async ({page}) => {
  await load(page);
  const feedback = await page.evaluate(async () => {
    const button = document.createElement('button');
    const status = document.createElement('p');
    status.className = 'settings-pane-status';
    document.body.append(button, status);
    await saveSettingsPane(button, status, async () => true, '设置已保存。');
    const success = { className: status.className, color: getComputedStyle(status).color };
    await saveSettingsPane(button, status, async () => { throw new Error('服务不可用'); });
    const failure = { className: status.className, color: getComputedStyle(status).color };
    button.remove();
    status.remove();
    return { success, failure };
  });
  expect(feedback).toEqual({
    success: { className: 'settings-pane-status is-success', color: 'rgb(0, 158, 97)' },
    failure: { className: 'settings-pane-status is-error', color: 'rgb(219, 56, 44)' },
  });
});

test('FNOS: Tag write jobs keep distinct success, warning and error states', async ({page}) => {
  await load(page);
  const states = await page.evaluate(() => {
    const list = document.createElement('div');
    list.className = 'metadata-tag-jobs';
    for (const state of ['done', 'running', 'retry', 'failed', 'no_match']) {
      const row = document.createElement('div');
      row.className = `metadata-tag-job is-${state}`;
      row.textContent = state;
      list.append(row);
    }
    document.body.append(list);
    return [...list.children].map(element => {
      const style = getComputedStyle(element);
      return { state: element.textContent, color: style.color, background: style.backgroundColor, border: style.borderLeftColor };
    });
  });
  expect(states).toEqual([
    { state: 'done', color: 'rgb(0, 158, 97)', background: 'rgba(0, 158, 97, 0.12)', border: 'rgb(0, 158, 97)' },
    { state: 'running', color: 'rgb(0, 102, 255)', background: 'rgba(0, 102, 255, 0.15)', border: 'rgb(0, 102, 255)' },
    { state: 'retry', color: 'rgb(139, 90, 0)', background: 'rgb(255, 248, 230)', border: 'rgb(139, 90, 0)' },
    { state: 'failed', color: 'rgb(219, 56, 44)', background: 'rgba(219, 56, 44, 0.12)', border: 'rgb(219, 56, 44)' },
    { state: 'no_match', color: 'rgb(139, 90, 0)', background: 'rgb(255, 248, 230)', border: 'rgb(139, 90, 0)' },
  ]);
});

test('FNOS: creator all-songs entry uses the shared blue focus token', async ({page}) => {
  await load(page);
  await page.evaluate(() => {
    document.querySelector('#trackList').insertAdjacentHTML('beforeend', renderCreatorAllSongsEntry([]));
    const entry = document.querySelector('.artist-all-songs-entry');
    entry.focus();
  });
  const focus = await page.locator('.artist-all-songs-entry').evaluate(element => {
    const style = getComputedStyle(element);
    return { outline: style.outlineColor, width: style.outlineWidth, offset: style.outlineOffset };
  });
  expect(focus).toEqual({ outline: 'rgb(0, 102, 255)', width: '2px', offset: '2px' });
  await page.locator('.artist-all-songs-entry').hover();
  const hover = await page.locator('.artist-all-songs-entry').evaluate(element => {
    const style = getComputedStyle(element);
    return { color: style.color, background: style.backgroundColor, border: style.borderTopColor };
  });
  expect(hover).toEqual({ color: 'rgb(11, 11, 12)', background: 'rgba(0, 0, 0, 0.08)', border: 'rgba(0, 0, 0, 0.1)' });
});

test('FNOS: mobile repeat modes use one state glyph without duplicate badges', async ({page}, info) => {
  await load(page, 375, 812);
  const button = page.locator('#mobileRepeatBtn');
  for (const [mode, expectedPaths] of [['off', 4], ['all', 4], ['one', 5]]) {
    await page.evaluate(value => {
      state.repeat = value;
      updateRepeatShuffleButtons();
    }, mode);
    await expect(button).toHaveAttribute('data-repeat', mode);
    await expect(button.locator('svg path')).toHaveCount(expectedPaths);
    const badge = await button.evaluate(element => getComputedStyle(element, '::after').content);
    expect(badge).toBe('none');
  }
  await screenshot(page, info, 'mobile-repeat-modes');
});

test('FNOS: settings rail supports keyboard navigation with synchronized ARIA state', async ({page}) => {
  await load(page);
  await openSettings(page);

  const lastTab = page.locator('[data-settings-tab="advanced"]');
  await page.locator('[data-settings-tab="library"]').focus();
  await page.keyboard.press('End');
  await expect(lastTab).toBeFocused();
  await expect(lastTab).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('#settings-pane-advanced')).toBeVisible();
  await expect(page.locator('[data-settings-tab="library"]')).toHaveAttribute('tabindex', '-1');
  await page.keyboard.press('ArrowLeft');
  await expect(page.locator('[data-settings-tab="appearance"]')).toBeFocused();
  await expect(page.locator('#settings-pane-appearance')).toBeVisible();
  await expect(page.locator('#settings-pane-appearance .dialog-help')).toContainText('浅色与深色由 fnAudio 单独显示');

  await page.locator('[data-settings-tab="metadata"]').click();
  // Metadata is one scrolling column now. A second tablist inside the rail is
  // exactly the nesting this rewrite removed, so its absence is the contract.
  await expect(page.locator('#settings-pane-metadata [role="tablist"]')).toHaveCount(0);
  for (const block of ['metadata-overview', 'metadata-providers', 'metadata-tasks', 'metadata-tags']) {
    await expect(page.locator(`[data-settings-block="${block}"]`)).toHaveCount(1);
  }
  await expect(page.locator('[data-settings-block="metadata-tags"]')).toHaveClass(/settings-danger-zone/);
});

test('FNOS: settings controls use the shared state palette', async ({page}) => {
  await load(page);
  await page.evaluate(() => { document.documentElement.dataset.theme = 'light'; });
  await openSettings(page);
  const settingsTab = page.locator('[data-settings-tab="metadata"]');
  const activeSettingsTab = page.locator('[data-settings-tab="library"]');
  const tabStyle = await activeSettingsTab.evaluate(button => {
    const style = getComputedStyle(button);
    return { color: style.color, background: style.backgroundColor };
  });
  expect(tabStyle).toEqual({ color: 'rgb(0, 102, 255)', background: 'rgba(0, 102, 255, 0.15)' });
  // The footer is the only save surface, so it can only be sampled once a change
  // has queued something for it to write.
  await page.locator('[data-settings-tab="network"]').click();
  await page.locator('#libraryConnectionPoolInput').click();
  await expect(page.locator('#settingsSaveBtn')).toBeVisible();
  const saveStyle = await page.locator('#settingsSaveBtn').evaluate(button => {
    const style = getComputedStyle(button);
    return { color: style.color, background: style.backgroundColor };
  });
  expect(saveStyle).toEqual({ color: 'rgb(255, 255, 255)', background: 'rgb(0, 102, 255)' });
  await settingsTab.click();
  const providerTest = page.locator('.metadata-provider-test').first();
  await providerTest.hover();
  const providerHover = await providerTest.evaluate(button => {
    const style = getComputedStyle(button);
    return { color: style.color, background: style.backgroundColor };
  });
  expect(providerHover).toEqual({ color: 'rgb(11, 11, 12)', background: 'rgba(0, 0, 0, 0.08)' });
});

test('FNOS: metadata groups draw one divider each, not two', async ({page}) => {
  await load(page);
  await openSettingsGroup(page, 'metadata');
  const providerGroup = page.locator('[data-settings-block="metadata-providers"]');
  await expect(providerGroup).toBeVisible();
  // The group separator is the only rule above the provider list; the inner
  // heading block used to add a second one when the sub-tabs were still there.
  await expect.poll(() => providerGroup.evaluate(element => getComputedStyle(element).borderTopWidth)).toBe('1px');
  const heading = page.locator('[data-settings-block="metadata-providers"] .metadata-provider-heading');
  await expect.poll(() => heading.evaluate(element => getComputedStyle(element).borderTopWidth)).toBe('0px');
});

test('FNOS: service pane keeps one heading per group', async ({page}) => {
  await load(page);
  await openSettingsGroup(page, 'network');
  const heads = page.locator('#settings-pane-network > .settings-group > .settings-group-head');
  await expect(heads).toHaveCount(3);
  const texts = await heads.locator('h3').allTextContents();
  expect(texts).toEqual(['DLNA 设备', '运行端口', '曲库连接池']);
  // The DLNA diagnostics button is an action, not a second heading.
  const actions = page.locator('#settings-pane-network .settings-inline-actions');
  await expect.poll(() => actions.evaluate(element => getComputedStyle(element).borderTopWidth)).toBe('0px');
});

for (const [width, height] of [[320, 568], [375, 667], [320, 900], [1440, 900]]) {
  test(`FNOS ${width}x${height}: the shared save bar stays reachable`, async ({page}, info) => {
    await load(page, width, height);
    await openSettingsGroup(page, 'metadata');

    const list = page.locator('#metadataProviderList');
    await expect(list).toBeVisible();
    const toggle = list.locator('[data-metadata-provider-toggle]').first();
    await toggle.scrollIntoViewIfNeeded();
    await toggle.click();

    const save = page.locator('#settingsSaveBtn');
    await expect(save).toBeVisible();
    await expect(save).toContainText('保存更改');
    const box = await save.boundingBox();
    const viewport = page.viewportSize();
    expect(box.y + box.height, 'the shared save action must remain in the dialog viewport').toBeLessThanOrEqual(viewport.height + 1);
    expect(box.y, 'the shared save action must not scroll off the top').toBeGreaterThanOrEqual(0);

    if (width <= 760) {
      await expect(page.locator('#folderDialog')).toHaveCSS('height', `${viewport.height}px`);
      const lastRow = list.locator('.metadata-provider-row').last();
      await lastRow.scrollIntoViewIfNeeded();
      const geometry = await page.evaluate(() => {
        const pane = document.querySelector('#settings-pane-metadata');
        const row = document.querySelector('#metadataProviderList .metadata-provider-row:last-child');
        const actions = row.querySelector('.metadata-provider-actions');
        const control = actions.querySelector('button:last-child');
        const controlBox = control.getBoundingClientRect();
        const hit = document.elementFromPoint(controlBox.left + controlBox.width / 2, controlBox.top + controlBox.height / 2);
        return {
          paneOverflowY: getComputedStyle(pane).overflowY,
          paneScrolls: pane.scrollHeight > pane.clientHeight,
          rowRight: row.getBoundingClientRect().right,
          actionsRight: actions.getBoundingClientRect().right,
          hitIsControl: hit === control || control.contains(hit),
        };
      });
      expect(geometry.paneOverflowY, 'the active settings pane must own mobile content scrolling').toBe('auto');
      expect(geometry.paneScrolls, 'settings content must overflow its fixed mobile pane').toBeTruthy();
      expect(geometry.rowRight - geometry.actionsRight, 'mobile provider actions must align to the card content edge').toBeLessThanOrEqual(16);
      expect(geometry.hitIsControl, 'the save bar must not cover the last provider control').toBeTruthy();
    }
    await screenshot(page, info, `settings-save-bar-${width}x${height}`);
  });
}

test('FNOS: mobile library settings keep directory selection above the save bar', async ({page}, info) => {
  await load(page, 320, 812);
  await openSettingsGroup(page, 'library');
  const picker = page.locator('#chooseLibraryPathBtn');
  await expect(picker).toBeVisible();
  const pickerBox = await picker.boundingBox();
  expect(pickerBox.y + pickerBox.height, 'directory picker must remain inside the mobile dialog viewport').toBeLessThanOrEqual(812);
  const pickerIsTopmost = await page.evaluate(() => {
    const button = document.querySelector('#chooseLibraryPathBtn');
    const box = button.getBoundingClientRect();
    const top = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
    return top === button || button.contains(top);
  });
  expect(pickerIsTopmost, 'directory picker must not be covered by the save bar').toBeTruthy();
  await screenshot(page, info, 'mobile-library-path-picker');
  // Removing a directory is the only edit on this pane that can be staged, so it
  // is what has to summon the footer on a phone.
  await page.locator('.library-path-remove').first().click();
  const save = page.locator('#settingsSaveBtn');
  await expect(save).toBeVisible();
  await expect(save).toContainText('保存更改');
  const saveBox = await save.boundingBox();
  expect(saveBox.y + saveBox.height).toBeLessThanOrEqual(812 + 1);
});

test('FNOS: mobile detail level keeps the save bar inside the frame', async ({page}) => {
  await load(page, 320, 812);
  await openSettingsGroup(page, 'advanced');
  await page.locator('#lyricsCacheBudgetInput').selectOption('262144');
  const save = page.locator('#settingsSaveBtn');
  await expect(save).toBeVisible();
  await expect(save).toHaveText('保存更改（1）');
  const geometry = await page.evaluate(() => {
    const dialog = document.querySelector('#folderDialog');
    const footer = document.querySelector('.settings-foot');
    const button = document.querySelector('#settingsSaveBtn');
    const box = button.getBoundingClientRect();
    const top = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
    return {
      dialog: dialog.getBoundingClientRect().toJSON(),
      footer: footer.getBoundingClientRect().toJSON(),
      button: box.toJSON(),
      buttonIsTopmost: top === button || button.contains(top),
    };
  });
  expect(geometry.footer.bottom).toBeLessThanOrEqual(geometry.dialog.bottom + 1);
  expect(geometry.button.top).toBeGreaterThanOrEqual(geometry.dialog.top);
  expect(geometry.button.bottom).toBeLessThanOrEqual(geometry.dialog.bottom);
  expect(geometry.buttonIsTopmost).toBeTruthy();
});

test('FNOS: selected library paths remain readable in dark settings', async ({page}) => {
  await page.emulateMedia({colorScheme: 'dark'});
  await load(page, 1440, 900);
  await openSettings(page);
  await page.evaluate(() => renderLibraryPathInputs(['/fixture/music']));
  const colors = await page.locator('.library-path-input').evaluate(element => {
    const style = getComputedStyle(element);
    return {background: style.backgroundColor, color: style.color};
  });
  expect(colors).toEqual({
    background: 'rgb(35, 35, 38)',
    color: 'rgb(255, 255, 255)',
  });
});

for (const width of [320, 1440]) {
  test(`FNOS ${width}: save bar actions share one edge`, async ({page}, info) => {
    await load(page, width, 900);
    await openSettingsGroup(page, 'network');
    await page.locator('#libraryConnectionPoolInput').click();
    await expect(page.locator('#settingsSaveBtn')).toBeVisible();

    const actions = page.locator('.settings-foot-actions');
    const layout = await actions.evaluate(element => ({
      box: element.getBoundingClientRect().toJSON(),
      footer: element.parentElement.getBoundingClientRect().toJSON(),
      buttons: [...element.querySelectorAll('button')].map(button => button.getBoundingClientRect().toJSON()),
      scrollWidth: element.scrollWidth,
      clientWidth: element.clientWidth,
    }));
    expect(layout.buttons).toHaveLength(2);
    expect(layout.scrollWidth).toBeLessThanOrEqual(layout.clientWidth);
    for (const button of layout.buttons) {
      expect(button.right).toBeLessThanOrEqual(layout.footer.right + 1);
      expect(button.left).toBeGreaterThanOrEqual(layout.footer.left - 1);
    }
    if (width < 761) {
      // Phones stack the count above two equal-width buttons.
      expect(Math.abs(layout.buttons[0].top - layout.buttons[1].top)).toBeLessThanOrEqual(1);
      expect(Math.abs(layout.buttons[0].width - layout.buttons[1].width)).toBeLessThanOrEqual(1);
    } else {
      expect(layout.footer.right - layout.buttons[1].right, 'desktop save actions must sit on the frame edge').toBeLessThanOrEqual(24);
    }
    await screenshot(page, info, `save-bar-actions-${width}`);
  });
}

test('FNOS: folder rows expose keyboard entry and a visible affordance', async ({page}) => {
  await load(page);
  await page.route('**/api/library/folders**', route => route.fulfill({json:{folders:[{name:'Live',path:'/fixture/music/Live',root:'/fixture/music',track_count:1}],count:1}}));
  await page.locator('[data-view="folders"]').click();
  const row = page.locator('.folder-group-row').first();
  await expect(row).toHaveAttribute('role', 'button');
  await expect(row).toHaveAttribute('tabindex', '0');
  await expect(row.locator('.folder-group-chevron')).toBeVisible();
  await expect(row.locator('.folder-group-chevron svg')).toBeVisible();
  await expect(row.locator('.folder-group-chevron svg path')).toHaveCount(1);
  expect(await row.evaluate(element => typeof element.onkeydown)).toBe('function');
  await row.focus();
  await row.press('Enter');
  await expect(page.locator('.folder-breadcrumb')).toBeVisible();
});

test('FNOS: opening folder rows use the selected-state token in dark mode', async ({page}) => {
  await page.emulateMedia({ colorScheme: 'dark' });
  await load(page);
  await page.route('**/api/library/folders**', route => route.fulfill({json:{folders:[{name:'Live',path:'/fixture/music/Live',root:'/fixture/music',track_count:1}],count:1}}));
  await page.locator('[data-view="folders"]').click();
  const row = page.locator('.group-row').first();
  expect(await row.evaluate(element => getComputedStyle(element).backgroundColor)).toBe('rgb(35, 35, 38)');
  await row.hover();
  expect(await row.evaluate(element => getComputedStyle(element).backgroundColor)).toBe('rgba(255, 255, 255, 0.1)');
  await page.mouse.move(0, 0);
  await row.evaluate(element => element.classList.add('is-opening'));
  expect(await row.evaluate(element => getComputedStyle(element).backgroundColor)).toBe('rgba(0, 102, 255, 0.25)');
});

test('FNOS: dark folder breadcrumbs use readable semantic colors', async ({page}) => {
  await page.emulateMedia({ colorScheme: 'dark' });
  await load(page);
  await page.route('**/api/library/folders**', route => route.fulfill({json:{folders:[{name:'Live',path:'/fixture/music/Live',root:'/fixture/music',track_count:1}],count:1}}));
  await page.locator('[data-view="folders"]').click();
  const row = page.locator('.folder-group-row').first();
  await row.press('Enter');
  await expect(page.locator('.folder-breadcrumb')).toBeVisible();
  await expect(page.locator('.folder-breadcrumb .folder-crumb').first()).toBeVisible();
  const colors = await page.locator('.folder-breadcrumb').evaluate(element => ({
    background: getComputedStyle(element).backgroundColor,
    current: getComputedStyle(element.querySelector('.folder-crumb.is-current') || element.querySelector('.folder-crumb:last-of-type')).color,
    link: getComputedStyle(element.querySelector('.folder-crumb:not(.is-current)') || element.querySelector('.folder-crumb')).color,
    separator: getComputedStyle(element.querySelector('.folder-crumb-separator') || element).color,
  }));
  expect(colors).toEqual({
    background: 'rgb(35, 35, 38)',
    current: 'rgb(255, 255, 255)',
    link: 'rgb(0, 102, 255)',
    separator: 'rgba(255, 255, 255, 0.5)',
  });
});

test('FNOS: dark DLNA diagnostics use readable semantic colors', async ({page}) => {
  await page.emulateMedia({ colorScheme: 'dark' });
  await load(page);
  const colors = await page.evaluate(() => {
    const entry = document.createElement('article');
    entry.className = 'diagnostic-entry';
    entry.innerHTML = '<div><strong>设备</strong><span>时间</span></div><small>格式</small><p>记录详情</p>';
    document.body.appendChild(entry);
    const result = {
      border: getComputedStyle(entry).borderBottomColor,
      strong: getComputedStyle(entry.querySelector('strong')).color,
      muted: getComputedStyle(entry.querySelector('span')).color,
      detail: getComputedStyle(entry.querySelector('p')).color,
    };
    entry.remove();
    return result;
  });
  expect(colors).toEqual({
    border: 'rgba(255, 255, 255, 0.08)',
    strong: 'rgb(255, 255, 255)',
    muted: 'rgba(255, 255, 255, 0.5)',
    detail: 'rgba(255, 255, 255, 0.75)',
  });
});

test('FNOS: folder pagination uses semantic surface and divider colors', async ({page}) => {
  await page.emulateMedia({colorScheme: 'dark'});
  await load(page);
  await page.evaluate(() => {
    const pager = document.createElement('div');
    pager.className = 'folder-pager';
    pager.innerHTML = '<button class="secondary-button" type="button">上一组</button><span>文件夹 1 / 2</span>';
    document.body.appendChild(pager);
  });
  const colors = await page.locator('.folder-pager').evaluate(element => {
    const style = getComputedStyle(element);
    return {background: style.backgroundColor, border: style.borderTopColor, color: style.color};
  });
  expect(colors).toEqual({
    background: 'rgb(35, 35, 38)',
    border: 'rgba(255, 255, 255, 0.08)',
    color: 'rgba(255, 255, 255, 0.5)',
  });
});

for (const [width, height] of [
  [1440, 900],
  [375, 812],
]) {
test(`FNOS ${width}: the MP3 transcode control lives in settings, not the retired top bar`, async ({page}) => {
  await load(page, width, height);
  // The .top-actions strip and its five buttons are gone from the markup, so
  // these nodes must stay absent.  The transcode switch moved into the
  // "播放输出" section, which is where this test now looks for it.
  await expect(page.locator('.top-actions')).toHaveCount(0);
  await expect(page.locator('#modeBtn')).toHaveCount(0);
  await expect(page.locator('#mobileModeBtn')).toHaveCount(0);
  await openSettings(page);
  await page.locator("[data-settings-tab='playback']").click();
  const settingsButton = page.locator('#settingsModeBtn');
  await expect(settingsButton).toBeVisible();
  await expect(settingsButton).toHaveText(/MP3 转码：(开|关)/);
  const box = await settingsButton.boundingBox();
  expect(box.height).toBeGreaterThanOrEqual(38);
});
}

test('FNOS: lyrics control renders the 词 glyph in its icon slot', async ({page}) => {
  await load(page);
  await expect(page.locator('#lyricsBtn svg.lyric-symbol')).toBeVisible();
  await expect(page.locator('#lyricsBtn svg.lyric-symbol')).toHaveCount(1);
  await expect(page.locator('#lyricsBtn')).toHaveText('词');
});

for (const [width, height] of [[1440, 900], [768, 900], [375, 812]]) {
  test(`FNOS ${width}: lyrics page keeps artwork, metadata and lines in view`, async ({page}, info) => {
    await load(page, width, height);
    await page.route('**/api/lyrics**', route => route.fulfill({json: {
      lyrics: '[00:00.00]E2E lyric one\n[00:04.00]E2E lyric two\n[00:08.00]E2E lyric three\n[00:12.00]E2E lyric four\n[00:16.00]E2E lyric five\n[00:20.00]E2E lyric six',
      source: 'fixture',
      pending: false,
    }}));
    await page.evaluate(async () => {
      state.queue = [...state.items];
      state.index = 0;
      await openLyrics();
    });
    await expect(page.locator('#lyricsView')).toBeVisible();
    await expect(page.locator('#lyricsTitle')).toHaveText('晨光');
    await expect(page.locator('#lyricsLines')).toContainText('E2E lyric six');
    for (const selector of ['#lyricsCover', '#lyricsLines']) {
      await insideViewport(page, selector);
    }
    // No header bar: it printed the same title and artist the artwork caption
    // prints below it, and the player bar names the track again (R489).
    await expect(page.locator('.lyrics-header')).toHaveCount(0);
    await expect(page.locator('#lyricsClose')).toHaveCount(0);
    await expect(page.locator('#lyricsFavoriteBtn')).toHaveCount(0);
    await expect(page.locator('#lyricsCover .record-placeholder')).toBeVisible();
    await screenshot(page, info, `lyrics-${width}`);
  });
}

for (const [width,height] of [[375,812],[667,375],[900,600]]) {
  test(`Requested UI: Android ${width} hides footer actions and preserves transport`, async ({page},info) => {
    await page.addInitScript(() => { window.FnAudioNative = {isAvailable: () => true}; });
    await load(page,width,height);
    await expect(page.locator('.player-actions')).toBeHidden();
    await expect(page.locator('#stopBtn')).toHaveCount(0);
    for (const selector of ['#prevBtn','#playBtn','#nextBtn','#seek']) await insideViewport(page,selector);
    if (width===375) {
      // The progress strip sits directly above the player, so "player.bottom minus
      // strip.bottom" is simply the player's own height -- asserting it stays under
      // 20px never described spacing and could never pass while the bar exists.
      // The real contract is that the strip touches the bar and the bar stays compact.
      const geo = await page.evaluate(() => {
        const player = document.querySelector('.player').getBoundingClientRect();
        const progress = document.querySelector('.progress').getBoundingClientRect();
        return {playerHeight: player.height, seam: Math.abs(player.top - progress.bottom)};
      });
      expect(geo.seam, 'the progress strip must touch the player').toBeLessThan(2);
      expect(geo.playerHeight, 'the phone player stays a compact bar').toBeLessThanOrEqual(150);
    }
    await screenshot(page,info,'android-compact-player');
  });
}

test('Requested UI: track numbers align with headers in library and album details', async ({page},info) => {
  await page.addInitScript(() => localStorage.setItem('fnaudio.trackColumns.v3',JSON.stringify({all:['track_no','title','artist','album','format','quality']})));
  await load(page);
  async function aligned() {
    const offsets = await page.evaluate(() => {
      const head = [...document.querySelectorAll('.album-detail-table-head, .table-head')]
        .find(element => !element.hidden && getComputedStyle(element).display !== 'none');
      const row = document.querySelector('.album-detail-track-list .track, .track-list .track');
      if (!head || !row) return {missing: true};
      const headColumns = getComputedStyle(head).gridTemplateColumns.split(' ').filter(Boolean);
      const rowColumns = getComputedStyle(row).gridTemplateColumns.split(' ').filter(Boolean);
      return {headColumns, rowColumns, headStyle: head.getAttribute('style'), rowStyle: row.getAttribute('style'), shared: getComputedStyle(document.body).getPropertyValue('--fnaudio-track-columns'), columns: [...head.querySelectorAll('[data-track-column]')].map(header => {
        const key = header.dataset.trackColumn;
        const cell = key === 'title' ? row.querySelector('.track-main') : row.querySelector(`.track-cell-${key}`);
        return {key, present: Boolean(cell)};
      })};
    });
    expect(offsets).not.toEqual({missing: true});
    console.log('TRACK_LAYOUT', JSON.stringify(offsets));
    expect(offsets.headColumns).toEqual(offsets.rowColumns);
    expect(offsets.columns.every(column => column.present)).toBeTruthy();
  }
  await aligned();
  await page.locator('[data-track-column="track_no"] .track-head-button').click();
  await aligned();
  await screenshot(page,info,'aligned-library');
  await page.locator('[data-view="albums"]').click();
  await page.locator('.album-group-row').filter({hasText:'离线专辑'}).click();
  await expect(page.locator('.album-detail-track-list .track')).toHaveCount(1);
  await aligned();
  await screenshot(page,info,'aligned-album');
});

for (const width of [320,375,414,768,1280,1440]) {
  test(`FNOS ${width}: complete controls, usable navigation and contained layout`,async ({page},info) => {
    const errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    const viewportHeight=width<761?812:900;
    await load(page,width,viewportHeight);
    const mobile=width<=760;
    const controls=['#prevBtn','#playBtn','#nextBtn','#seek'];
    controls.push(...(mobile?['#mobileNavBtn','#mobileShuffleBtn','#mobileRepeatBtn']:['#shuffleBtn','#repeatBtn']));
    for (const selector of controls) await insideViewport(page,selector);
    if (mobile) {
      await page.locator('#mobileNavBtn').click();
      await insideViewport(page,'#mobileSettingsNavBtn');
      await page.locator('#mobileSettingsNavBtn').click();
      await expect(page.locator('#folderDialog')).toBeVisible();
      await page.locator('#closeFolderDialog').click();
      await expect(page.locator('.player-actions')).toBeHidden();
    } else {
      await insideViewport(page,'#mobileSettingsNavBtn');
      await expect(page.locator('.top-actions')).toHaveCount(0);
      for (const selector of ['#lyricsBtn','#favoriteCurrentBtn','#queueBtn','#volumeBtn']) await insideViewport(page,selector);
    }
    if (width < 560 && viewportHeight > 540) {
      for (const selector of ['#mobileShuffleBtn','#prevBtn','#playBtn','#nextBtn','#mobileRepeatBtn']) {
        const bounds = await page.locator(selector).boundingBox();
        expect(bounds.width, `${selector} touch width`).toBeGreaterThanOrEqual(44);
        expect(bounds.height, `${selector} touch height`).toBeGreaterThanOrEqual(44);
      }
    }
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
    expect(await page.evaluate(()=>{
      const a=document.querySelector('.content').getBoundingClientRect();
      const b=document.querySelector('.player').getBoundingClientRect();
      return a.height>100 && a.bottom<=b.top+1;
    })).toBeTruthy();
    await screenshot(page,info,'player');
    if (!mobile) {
      await page.locator('#volumeBtn').click();
      await insideViewport(page,'#volume');
      // R488: the popover rail is a rebuilt range, not the UA vertical slider.
      // getComputedStyle cannot see the -webkit- pseudo-elements (Chromium hands
      // back the host element's own style), so this asserts what is observable:
      // the rebuild, the geometry it must not move, and the fill the JS pushes
      // into CSS for the gradient.
      const rail = await page.evaluate(() => {
        const slider = document.querySelector('#volume');
        const panel = document.querySelector('#volumePanel');
        slider.value = '0.62';
        slider.dispatchEvent(new Event('input', {bubbles: true}));
        const cs = getComputedStyle(slider);
        const s = slider.getBoundingClientRect();
        const p = panel.getBoundingClientRect();
        const state = {
          appearance: cs.appearance,
          writingMode: cs.writingMode,
          fill: slider.style.getPropertyValue('--volume-fill'),
          rail: getComputedStyle(panel).getPropertyValue('--volume-rail').trim(),
          slider: [Math.round(s.width), Math.round(s.height)],
          panel: [Math.round(p.width), Math.round(p.height)],
        };
        slider.value = '1';
        slider.dispatchEvent(new Event('input', {bubbles: true}));
        return state;
      });
      expect(rail.appearance, 'the UA vertical slider paints its own track').toBe('none');
      expect(rail.writingMode).toBe('vertical-rl');
      expect(rail.slider, 'the rebuild changes what is painted, not where').toEqual([24, 112]);
      expect(rail.panel).toEqual([48, 144]);
      expect(rail.fill).toBe('62%');
      expect(rail.rail).toContain('color-mix');
      await page.locator('#volumeBtn').click();
    }
    if(mobile) {
      await expect(page.locator('.sidebar')).toBeHidden();
      await page.locator('#mobileNavBtn').click();
      await expect(page.locator('.sidebar')).toBeVisible();
    }
    for(const view of ['all','dsd','folders','albums','artists','composers','genres','random100','recent','favorites','queue']) {
      expect(await page.locator(`.nav-item[data-view="${view}"]`).count()).toBe(1);
    }
    if(mobile) {
      await screenshot(page,info,'navigation');
      await page.keyboard.press('Escape');
      await expect(page.locator('.sidebar')).toBeHidden();
      await expect(page.locator('#mobileNavBtn')).toBeFocused();
    }
    if (mobile) {
      // The top bar is retired on phones, so the device dialog opens from the
      // settings "播放输出" section.  #mobileDeviceBtn no longer exists; keeping
      // it in the click path only ever tested the timeout.
      await expect(page.locator('#mobileDeviceBtn')).toHaveCount(0);
      await page.locator('#mobileNavBtn').click();
      await page.locator('#mobileSettingsNavBtn').click();
      await page.locator("[data-settings-tab='playback']").click();
      await page.locator('#settingsDeviceBtn').click();
    } else {
      await page.locator('#deviceBtn').click();
    }
    await expect(page.locator('#deviceDialog')).toBeVisible();
    // Nine dialogs now carry a close control: the eight settings/device dialogs
    // plus the server-side music directory browser that clients without the
    // fnOS host picker fall back to.
    await expect(page.locator('.dialog-close-button')).toHaveCount(9);
    await expect(page.locator('#closeDialog svg')).toBeVisible();
    await expect(page.locator('#closeDialog')).toHaveAttribute('aria-label','关闭');
    await insideViewport(page,'#scanDevices');
    await screenshot(page,info,'devices');
    await page.locator('#closeDialog').click();
    await expect(page.locator('#mobileColumnsBtn')).toHaveCount(0);
    if (!mobile) {
      await page.locator('.table-head-more:visible').click();
      await expect(page.locator('#columnsDialog')).toBeVisible();
      await page.locator('#saveColumnsBtn').scrollIntoViewIfNeeded();
      await insideViewport(page,'#saveColumnsBtn');
      await page.locator('#closeColumnsDialog').click();
    }
    if (!mobile) {
      await page.locator('#lyricsBtn').click();
      await expect(page.locator('#lyricsView')).toBeVisible();
      // The header has no back button any more, so the two remaining exits have
      // to work: Escape, and the 词 toggle in the player bar (R489).
      await page.keyboard.press('Escape');
      await expect(page.locator('#lyricsView')).toBeHidden();
      await page.locator('#lyricsBtn').click();
      await expect(page.locator('#lyricsView')).toBeVisible();
      await page.locator('#lyricsBtn').click();
      await expect(page.locator('#lyricsView')).toBeHidden();
    }
    expect(errors).toEqual([]);
  });
}

test('FNOS 768: wide track columns scroll inside the library viewport', async ({page}, info) => {
  await load(page, 768, 900);
  const metrics = await page.evaluate(() => {
    const viewport = document.querySelector('.library-scroll');
    const before = viewport.scrollLeft;
    viewport.scrollLeft = Math.min(160, viewport.scrollWidth - viewport.clientWidth);
    return {
      before,
      after: viewport.scrollLeft,
      overflow: viewport.scrollWidth > viewport.clientWidth,
      pageFits: document.documentElement.scrollWidth <= innerWidth,
      headerWidth: document.querySelector('.table-head').scrollWidth,
      rowsWidth: document.querySelector('.track-list').scrollWidth,
      viewportWidth: viewport.clientWidth,
    };
  });
  expect(metrics.overflow, 'the medium-width list must expose a horizontal scroll surface when columns do not fit').toBeTruthy();
  expect(metrics.after, 'horizontal scrolling must move the library viewport').toBeGreaterThan(metrics.before);
  expect(Math.abs(metrics.headerWidth - metrics.rowsWidth), 'header and rows must share the same wide content track, allowing header inline padding').toBeLessThanOrEqual(24);
  expect(metrics.pageFits, 'the horizontal table must not widen the document').toBeTruthy();
  await screenshot(page, info, 'tablet-wide-library');
});

for(const width of [320,768,1440]) {
  test(`FNOS ${width}: six settings groups stay operable`,async ({page},info) => {
    await load(page,width,width<761?812:900);
    await openSettings(page);
    const dialog=page.locator('#folderDialog');
    const closeSize=await page.locator('#closeFolderDialog').evaluate(el=>{
      const box=el.getBoundingClientRect();
      return {width:box.width,height:box.height};
    });
    expect(closeSize.width).toBeGreaterThanOrEqual(width<761?44:36);
    expect(closeSize.height).toBeGreaterThanOrEqual(width<761?44:36);

    const groups=['library','playback','metadata','network','appearance','advanced'];
    if (width < 761) {
      // The phone frame opens on the rail: six full-width rows, no pane yet.
      await expect(page.locator('.settings-panes')).toBeHidden();
      await expect(page.locator('.settings-foot')).toBeHidden();
      await expect(page.locator('.settings-nav button')).toHaveCount(groups.length);
      const rail = await page.locator('.settings-nav').evaluate(el => ({
        tops: [...el.querySelectorAll('button')].map(b => Math.round(b.getBoundingClientRect().top)),
        heights: [...el.querySelectorAll('button')].map(b => Math.round(b.getBoundingClientRect().height)),
      }));
      expect([...new Set(rail.heights)], 'every rail row must be the same height').toEqual([60]);
      expect(new Set(rail.tops).size, 'rail rows must not share a baseline').toBe(groups.length);
      await screenshot(page, info, 'settings-rail');
    }

    for(const tab of groups) {
      await page.locator(`[data-settings-tab="${tab}"]`).click();
      await expect(page.locator(`#settings-pane-${tab}`)).toBeVisible();
      expect(await dialog.evaluate(el=>el.scrollWidth<=el.clientWidth+1)).toBeTruthy();
      if (width < 761) {
        // Picking a group replaces the rail with its pane; the back arrow is the
        // only way up, so the header close button steps aside.
        await expect(page.locator('.settings-nav')).toBeHidden();
        await expect(page.locator('#settingsBackBtn')).toBeVisible();
        await expect(page.locator('#closeFolderDialog')).toBeHidden();
        const paneBox = await page.locator(`#settings-pane-${tab}`).evaluate(el => el.getBoundingClientRect().toJSON());
        expect(paneBox.left).toBeGreaterThanOrEqual(-1);
        expect(paneBox.right).toBeLessThanOrEqual(width + 1);
      }
      await screenshot(page,info,'settings-'+tab);
      if (width < 761) {
        await page.locator('#settingsBackBtn').click();
        await expect(page.locator('.settings-nav')).toBeVisible();
        await expect(page.locator('.settings-panes')).toBeHidden();
      }
    }

    await page.locator('[data-settings-tab="metadata"]').click();
    // Metadata is one column of four blocks: all of them render, none hides
    // behind a second tab strip.
    for (const block of ['metadata-overview','metadata-providers','metadata-tasks','metadata-tags']) {
      const group = page.locator(`[data-settings-block="${block}"]`);
      await expect(group).toHaveCount(1);
      await expect(group).toBeVisible();
    }
    if (width < 761) {
      const providerTop = await page.locator('#metadataProviderList').evaluate(el=>el.getBoundingClientRect().top);
      const probeTop = await page.locator('.metadata-probe-query').evaluate(el=>el.getBoundingClientRect().top);
      expect(providerTop, 'mobile source management must precede optional provider test inputs').toBeLessThan(probeTop);
    }
    const testButton=page.locator('[data-metadata-provider-test]').first();
    await testButton.scrollIntoViewIfNeeded();
    await expect(testButton).toBeVisible();
    await page.locator('#metadataProbeTitleInput').fill('晨光');
    // Browser fixtures supply probe results; no provider credentials/network.
    await page.route('**/api/metadata/provider-test',route=>route.fulfill({json:{ok:true,result:{ok:true,provider_id:'netease',response_ms:125,search:{available:true,supported:true,title:'晨光'},cover:{available:true,supported:true},lyrics:{available:true,supported:true}}}}));
    await testButton.click();
    const result=page.locator('[data-metadata-provider-result]:visible').first();
    await expect(result).toBeVisible();
    await expect(result).toContainText('125 ms');
    expect(await result.evaluate(el=>el.scrollWidth<=el.clientWidth+1)).toBeTruthy();
    await screenshot(page,info,'provider-result');

    // Probing is read-only, so nothing may be queued for the footer yet.
    await expect(page.locator('#settingsSaveBtn')).toBeHidden();
    // Toggling a source is the metadata edit that has to summon it.
    await page.locator('[data-metadata-provider-toggle]').first().click();
    const save = page.locator('#settingsSaveBtn');
    await expect(save).toBeVisible();
    const saveBounds = await save.evaluate(el => {
      const rect = el.getBoundingClientRect();
      return {top: rect.top, bottom: rect.bottom, viewport: window.innerHeight};
    });
    expect(saveBounds.bottom).toBeLessThanOrEqual(saveBounds.viewport + 1);
    expect(saveBounds.top).toBeGreaterThanOrEqual(0);
    expect(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBeTruthy();
    await insideViewport(page,'#settingsSaveBtn');
    // Read all settings and scroll to saves; do not write fixture or NAS settings.
  });
}

test('FNOS: every library view, dynamic playlist and folder/album details retain their actions',async ({page},info)=>{
  const errors=[]; page.on('pageerror',e=>errors.push(e.message));
  await load(page);
  for(const view of ['dsd','folders','albums','artists','composers','genres','random100','recent','favorites','queue','all']) {
    await page.locator(`[data-view="${view}"]`).click();
    await expect(page.locator(`[data-view="${view}"]`)).toHaveClass(/active/);
    await screenshot(page,info,'view-'+view);
  }
  await page.locator('[data-view="albums"]').click();
  await page.locator('.album-group-row').filter({hasText:'离线专辑'}).click();
  await expect(page.locator('.album-detail-track-list .track')).toHaveCount(1);
  await screenshot(page,info,'album-detail');
  await page.locator('[data-view="all"]').click();
  await page.locator('#newPlaylistBtn').click();
  await expect(page.locator('#playlistDialog')).toBeVisible();
  await screenshot(page,info,'playlist');
  await page.locator('#playlistNameInput').fill('界面验收播放列表');
  await page.locator('#savePlaylistBtn').click();
  await expect(page.locator('#playlistNav .nav-item')).toHaveCount(1);
  await page.locator('#playlistNav .nav-item').click();
  await expect(page.locator('#empty')).toBeVisible();
  await expect(page.locator('#emptyTitle')).toHaveText('播放列表为空');
  await expect(page.locator('#emptyText')).not.toHaveText('音乐库已就绪');
  await expect(page.locator('#emptyText')).toContainText('播放列表');
  await screenshot(page,info,'playlist-view');
  await page.locator('[data-view="favorites"]').click();
  await expect(page.locator('#emptyTitle')).toHaveText('还没有收藏歌曲');
  await expect(page.locator('#emptyText')).toContainText('收藏歌曲');
  await page.locator('[data-view="queue"]').click();
  await expect(page.locator('#emptyTitle')).toHaveText('当前队列为空');
  await expect(page.locator('#emptyText')).toContainText('当前队列');
  expect(errors).toEqual([]);
});

for(const width of [320,1440]) {
  test(`FNOS ${width}: metadata candidates, context menu and functional dialogs`,async({page},info)=>{
    await load(page,width,width<761?812:900);
    await page.route('**/api/metadata/track/search',route=>route.fulfill({json:{ok:true,search_id:'ui-fixture-search',candidates:[{title:'晨光',artist:'测试歌手',album:'离线专辑',provider_id:'netease',confidence:.96},{title:'晨光（现场）',artist:'测试歌手',album:'演唱会',provider_id:'qqmusic',confidence:.78}]}}));
    // Call the real entry point, with deterministic API candidates.
    await page.evaluate(()=>openMetadataCandidateDialog('fixture-1'));
    await expect(page.locator('.metadata-candidate-choice')).toHaveCount(2);
    await page.locator('.metadata-candidate-choice').last().click();
    await expect(page.locator('input[name="metadataCandidate"]').last()).toBeChecked();
    expect(await page.locator('input[name="metadataCandidate"]').last().evaluate(element => getComputedStyle(element).accentColor)).toBe('rgb(0, 102, 255)');
    const confirmStyle = await page.locator('.metadata-candidate-dialog .track-action-choice').evaluate(button => {
      const style = getComputedStyle(button);
      return { color: style.color, background: style.backgroundColor, borderColor: style.borderColor };
    });
    expect(confirmStyle).toEqual({ color: 'rgb(255, 255, 255)', background: 'rgb(0, 102, 255)', borderColor: 'rgb(0, 102, 255)' });
    const selectedCandidateStyle = await page.locator('.metadata-candidate-choice').last().evaluate(element => {
      const style = getComputedStyle(element);
      return { background: style.backgroundColor, borderColor: style.borderColor };
    });
    expect(selectedCandidateStyle).toEqual({ background: 'rgba(0, 102, 255, 0.15)', borderColor: 'rgb(0, 102, 255)' });
    await page.locator('#metadataCandidateSearchInput').fill('另一首歌曲');
    await page.locator('#metadataCandidateSearchForm button').click();
    await expect(page.locator('.metadata-candidate-choice')).toHaveCount(2);
    await screenshot(page,info,'metadata-candidates');
    const candidateDialog=page.locator('#metadataCandidateDialog');
    expect(await candidateDialog.evaluate(el=>el.scrollWidth<=el.clientWidth+1)).toBeTruthy();
    await page.locator('#closeMetadataCandidateDialog').click();
    await page.evaluate(()=>openTrackContextMenu('fixture-1',innerWidth-20,innerHeight-20,false));
    await insideViewport(page,'#trackContextMenu');
    const menuIcons = page.locator('#trackContextMenu .track-context-actions .track-action-choice > svg');
    await expect(menuIcons).toHaveCount(await page.locator('#trackContextMenu .track-context-actions .track-action-choice').count());
    await expect(menuIcons.first()).toHaveAttribute('aria-hidden', 'true');
    await expect(menuIcons.first()).toBeVisible();
    await screenshot(page,info,'context-menu');
    await page.keyboard.press('Escape');
    await page.evaluate(()=>openDeleteTrackDialog(['fixture-1']));
    await expect(page.locator('#deleteTrackDialog')).toBeVisible();
    await page.locator('#cancelDeleteTrack').scrollIntoViewIfNeeded();
    await insideViewport(page,'#cancelDeleteTrack');
    await screenshot(page,info,'delete-confirmation');
    await page.locator('#cancelDeleteTrack').click();
    await page.evaluate(()=>{resetExternalShareDialog({path:'/fixture/music/晨光.flac'});document.getElementById('externalShareDialog').showModal();});
    await expect(page.locator('#externalShareDialog')).toBeVisible();
    await expect(page.locator('.external-share-file-icon svg')).toBeVisible();
    await expect(page.locator('.external-share-file-icon svg path')).toHaveCount(2);
    await page.locator('#sharePasswordDetail').evaluate(element => { element.hidden = false; });
    await page.locator('#sharePasswordInput').focus();
    expect(await page.locator('#sharePasswordInput').evaluate(element => getComputedStyle(element).borderTopColor))
      .toBe('rgb(0, 102, 255)');
    const shareFooter = page.locator('#externalShareForm > .external-share-footer');
    await expect(shareFooter.locator('button')).toHaveCount(2);
    const shareGeometry = await shareFooter.locator('button').evaluateAll(buttons => buttons.map(button => {
      const box = button.getBoundingClientRect();
      return {top: box.top, bottom: box.bottom, width: box.width, right: box.right};
    }));
    expect(Math.abs(shareGeometry[0].top - shareGeometry[1].top), 'external-share actions must share one row').toBeLessThanOrEqual(1);
    expect(shareGeometry[0].width, 'external-share cancel action must remain wide enough').toBeGreaterThanOrEqual(80);
    expect(shareGeometry[1].width, 'external-share confirm action must remain wide enough').toBeGreaterThanOrEqual(80);
    expect(shareGeometry[1].right, 'external-share actions must stay inside the dialog').toBeLessThanOrEqual(width - 8);
    await screenshot(page,info,'external-share');
    await page.locator('#cancelExternalShare').click();
  });
}

test('FNOS dark palette applies across library, player and settings without white legacy surfaces',async({page},info)=>{
  await page.emulateMedia({colorScheme:'dark'});
  await load(page);
  const expected='rgb(35, 35, 38)';
  for(const selector of ['.content','.player']) {
    expect(await page.locator(selector).evaluate(el=>getComputedStyle(el).backgroundColor)).toBe(expected);
  }
  expect(await page.locator('.track-cell-format').first().evaluate(el=>getComputedStyle(el).backgroundColor)).toBe(expected);
  expect(await page.locator('.track-cell-format.dsd').evaluate(el=>getComputedStyle(el).backgroundColor)).toBe('rgba(234, 191, 117, 0.12)');
  await screenshot(page,info,'dark-player');
  await page.locator('[data-view="albums"]').click();
  await page.locator('.album-group-row').filter({hasText:'离线专辑'}).click();
  expect(await page.locator('.album-detail-layout').evaluate(el=>getComputedStyle(el).backgroundColor)).toBe(expected);
  expect(await page.locator('.album-detail-sidebar h2').evaluate(el=>getComputedStyle(el).color)).toBe('rgb(255, 255, 255)');
  const albumActions = await page.evaluate(() => {
    const element = document.createElement('div');
    element.className = 'album-detail-actions';
    element.textContent = '1 首歌曲';
    document.body.appendChild(element);
    const result = {
      background: getComputedStyle(element).backgroundColor,
      border: getComputedStyle(element).borderBottomColor,
      color: getComputedStyle(element).color,
    };
    element.remove();
    return result;
  });
  expect(albumActions.background).toBe(expected);
  expect(albumActions.color).toBe('rgba(255, 255, 255, 0.5)');
  expect(albumActions.border).not.toBe('rgb(255, 255, 255)');
  await screenshot(page,info,'dark-album');

  const categoryDetail = await page.evaluate(() => {
    const element = document.createElement('div');
    element.className = 'category-detail';
    element.innerHTML = '<div class="category-detail-main"><strong>分类</strong><span>1 首歌曲</span></div>';
    document.body.appendChild(element);
    const result = {
      background: getComputedStyle(element).backgroundColor,
      border: getComputedStyle(element).borderBottomColor,
      title: getComputedStyle(element.querySelector('strong')).color,
      subtitle: getComputedStyle(element.querySelector('span')).color,
    };
    element.remove();
    return result;
  });
  expect(categoryDetail.background).toBe(expected);
  expect(categoryDetail.title).toBe('rgb(255, 255, 255)');
  expect(categoryDetail.subtitle).toBe('rgba(255, 255, 255, 0.5)');
  expect(categoryDetail.border).not.toBe('rgb(255, 255, 255)');
  await screenshot(page,info,'dark-category-detail');

  const dangerButton = await page.evaluate(() => {
    const element = document.createElement('button');
    element.className = 'danger-button';
    element.textContent = '清空队列';
    document.body.appendChild(element);
    const result = {
      background: getComputedStyle(element).backgroundColor,
      border: getComputedStyle(element).borderColor,
      color: getComputedStyle(element).color,
    };
    element.remove();
    return result;
  });
  expect(dangerButton.background).toBe('rgba(219, 56, 44, 0.12)');
  expect(dangerButton.border).toBe('rgb(219, 56, 44)');
  expect(dangerButton.color).toBe('rgb(219, 56, 44)');

  const trackActionInfo = await page.evaluate(() => {
    const element = document.createElement('div');
    element.className = 'track-action-info';
    element.textContent = '操作说明';
    document.body.appendChild(element);
    const result = {
      background: getComputedStyle(element).backgroundColor,
      border: getComputedStyle(element).borderColor,
      color: getComputedStyle(element).color,
    };
    element.remove();
    return result;
  });
  expect(trackActionInfo.background).toBe(expected);
  expect(trackActionInfo.border).not.toBe('rgb(255, 255, 255)');
  expect(trackActionInfo.color).toBe('rgba(255, 255, 255, 0.75)');
  await page.locator('[data-view="all"]').click();
  await page.locator('.table-head-more:visible').click();
  expect(await page.locator('.column-choice').first().evaluate(el=>getComputedStyle(el).backgroundColor)).toBe('rgba(0, 102, 255, 0.25)');
  await screenshot(page,info,'dark-columns');
  await page.locator('#closeColumnsDialog').click();
  await page.locator('#deviceBtn').click();
  expect(await page.locator('#deviceDialog h2').evaluate(el=>getComputedStyle(el).color)).toBe('rgb(255, 255, 255)');
  await expect(page.locator('.device-row.is-current')).toHaveCount(1);
  expect(await page.locator('.device-row.is-current').evaluate(el=>getComputedStyle(el).backgroundColor)).toBe('rgba(0, 102, 255, 0.25)');
  expect(await page.locator('.device-dialog-footer').evaluate(el => ({
    background: getComputedStyle(el).backgroundColor,
    border: getComputedStyle(el).borderTopColor,
  }))).toEqual({
    background: 'rgb(35, 35, 38)',
    border: 'rgba(255, 255, 255, 0.08)',
  });
  await screenshot(page,info,'dark-devices');
  await page.locator('#closeDialog').click();
  await openSettings(page);
  expect(await page.locator('#folderDialog h2').evaluate(el=>getComputedStyle(el).color)).toBe('rgb(255, 255, 255)');
  // The fixture library is healthy, so the danger tint is forced here: the point
  // of the check is that the error surface is dark, not that the card is in error.
  await page.evaluate(() => document.getElementById('libraryHealth').classList.add('is-error'));
  expect(await page.locator('.library-health').evaluate(el=>getComputedStyle(el).backgroundColor)).toBe('rgba(219, 56, 44, 0.12)');
  await page.evaluate(() => document.getElementById('libraryHealth').classList.remove('is-error'));
  await screenshot(page,info,'dark-library-health');
  await page.locator('#settings-tab-metadata').click();
  await screenshot(page,info,'dark-providers');
  expect(await page.locator('#folderDialog').evaluate(el=>getComputedStyle(el).colorScheme)).toBe('dark');
  await page.locator('#closeFolderDialog').click();
  await page.evaluate(()=>{resetExternalShareDialog({path:'/fixture/music/晨光.flac'});document.getElementById('externalShareDialog').showModal();});
  expect(await page.locator('#externalShareDialog').evaluate(el=>getComputedStyle(el).backgroundColor)).toBe('rgb(35, 35, 38)');
  expect(await page.locator('.external-share-file strong').evaluate(el=>getComputedStyle(el).color)).toBe('rgb(255, 255, 255)');
  await screenshot(page,info,'dark-sharing');
  await page.locator('#cancelExternalShare').click();
  await page.locator('#lyricsBtn').click();
  await page.evaluate(()=>document.getElementById('lyricsLines').innerHTML='<p class="active">当前歌词可读性</p>');
  expect(await page.locator('.lyrics-lines p.active').evaluate(el=>getComputedStyle(el).color)).toBe('rgb(0, 102, 255)');
  await page.keyboard.press('Escape');
  await expect(page.locator('#lyricsView')).toBeHidden();
  await page.evaluate(()=>document.documentElement.dataset.theme='light');
  expect(await page.locator('.content').evaluate(el=>getComputedStyle(el).backgroundColor)).toBe('rgb(255, 255, 255)');
});

test('FNOS dark active navigation keeps readable foreground contrast', async ({page}) => {
  await page.emulateMedia({colorScheme: 'dark'});
  await load(page, 320, 812);
  const colors = await page.locator('.nav-item.active').evaluate(element => {
    const style = getComputedStyle(element);
    const count = element.querySelector('b');
    return {
      color: style.color,
      background: style.backgroundColor,
      countColor: count ? getComputedStyle(count).color : '',
    };
  });
  expect(colors).toEqual({
    color: 'rgb(255, 255, 255)',
    background: 'rgb(0, 102, 255)',
    countColor: 'rgb(255, 255, 255)',
  });
});

test('FNOS light active navigation keeps normal text contrast', async ({page}) => {
  await page.emulateMedia({colorScheme: 'light'});
  await load(page, 320, 812);
  const ratio = await page.locator('.nav-item.active').evaluate(element => {
    const parse = value => {
      const match = value.match(/rgba?\(([^)]+)\)/);
      const srgb = value.match(/color\(srgb\s+([^\s]+)\s+([^\s]+)\s+([^\s)]+)/);
      const channels = match
        ? match[1].split(',').map(channel => Number.parseFloat(channel.trim())).slice(0, 3).map(channel => channel / 255)
        : srgb
          ? srgb.slice(1, 4).map(channel => Number.parseFloat(channel))
          : null;
      if (!channels) return null;
      return channels.map(channel => {
        return channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
      });
    };
    const luminance = rgb => 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2];
    const style = getComputedStyle(element);
    const foreground = luminance(parse(style.color));
    const background = luminance(parse(style.backgroundColor));
    return (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05);
  });
  expect(ratio).toBeGreaterThanOrEqual(4.5);
});

test('FNOS light palette keeps format cells on the shared semantic tokens', async ({page}) => {
  await page.emulateMedia({colorScheme: 'light'});
  await load(page, 1440, 900);
  const state = await page.evaluate(() => {
    const normal = document.querySelector('.track-cell-format:not(.dsd)');
    const dsd = document.querySelector('.track-cell-format.dsd');
    return {
      normal: {
        color: getComputedStyle(normal).color,
        background: getComputedStyle(normal).backgroundColor,
      },
      dsd: {
        color: getComputedStyle(dsd).color,
        background: getComputedStyle(dsd).backgroundColor,
      },
    };
  });
  expect(state).toEqual({
    normal: {color: 'rgba(0, 0, 0, 0.75)', background: 'rgb(255, 255, 255)'},
    dsd: {color: 'rgb(139, 90, 0)', background: 'rgb(255, 248, 230)'},
  });
});

test('FNOS light DSD format labels keep normal text contrast', async ({page}) => {
  await page.emulateMedia({colorScheme: 'light'});
  await load(page, 1440, 900);
  const ratio = await page.locator('.track-cell-format.dsd').evaluate(element => {
    const parse = value => {
      const match = value.match(/rgba?\(([^)]+)\)/);
      const channels = match[1].split(',').map(channel => Number.parseFloat(channel.trim())).slice(0, 3).map(channel => channel / 255);
      return channels.map(channel => channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4);
    };
    const luminance = rgb => 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2];
    const style = getComputedStyle(element);
    const foreground = luminance(parse(style.color));
    const background = luminance(parse(style.backgroundColor));
    return (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05);
  });
  expect(ratio).toBeGreaterThanOrEqual(4.5);
});

test('FNOS system dark palette keeps DSD warning tokens after generic aliases', async ({page}) => {
  await page.emulateMedia({colorScheme: 'dark'});
  await load(page, 1440, 900);
  await page.evaluate(() => document.documentElement.removeAttribute('data-theme'));
  const style = await page.locator('.track-cell-format.dsd').evaluate(element => {
    const computed = getComputedStyle(element);
    return {color: computed.color, background: computed.backgroundColor};
  });
  expect(style).toEqual({
    color: 'rgb(234, 191, 117)',
    background: 'rgba(234, 191, 117, 0.12)',
  });
});

test('FNOS light palette keeps inactive player controls on the secondary token', async ({page}) => {
  await page.emulateMedia({colorScheme: 'light'});
  await load(page, 1440, 900);
  const colors = await page.evaluate(() => [
    '#deviceBtn', '#lyricsBtn', '#favoriteCurrentBtn', '#repeatBtn', '#shuffleBtn', '#queueBtn',
  ].map(selector => getComputedStyle(document.querySelector(selector)).color));
  expect(colors).toEqual(Array(6).fill('rgba(0, 0, 0, 0.75)'));
});

test('FNOS short landscape preserves browsing space and compact transport controls',async({page},info)=>{
  await load(page,667,375);
  const list=await page.locator('#trackList').boundingBox();
  expect(list.height).toBeGreaterThan(100);
  await expect(page.locator('#stopBtn')).toHaveCount(0);
  for(const selector of ['#prevBtn','#playBtn','#nextBtn','#mobileShuffleBtn','#mobileRepeatBtn']) await insideViewport(page,selector);
  // #refreshBtn was removed together with the .top-actions strip; refreshing
  // the library now happens through the settings scan action.
  await expect(page.locator('.top-actions')).toHaveCount(0);
  await expect(page.locator('#refreshBtn')).toHaveCount(0);
  await expect(page.locator('.player-actions')).toBeHidden();
  await screenshot(page,info,'landscape');
});

test('FNOS audit: visible light UI has no retired teal tokens across breakpoints', async ({page}) => {
  for (const [width, height] of [[320, 812], [375, 812], [768, 900], [1440, 900]]) {
    await load(page, width, height);
    await page.evaluate(() => { document.documentElement.dataset.theme = 'light'; });
    const retired = await page.evaluate(() => {
      const values = new Set([
        'rgb(18, 184, 168)', 'rgb(7, 157, 145)', 'rgb(10, 168, 157)',
        'rgb(8, 167, 158)', 'rgb(8, 127, 118)', 'rgb(18, 165, 155)',
      ]);
      return [...document.querySelectorAll('body *')].filter(element => {
        const style = getComputedStyle(element);
        if (style.display === 'none' || style.visibility === 'hidden') return false;
        return [style.color, style.backgroundColor, style.borderTopColor, style.borderRightColor,
          style.borderBottomColor, style.borderLeftColor].some(value => values.has(value));
      }).slice(0, 30).map(element => ({
        tag: element.tagName, id: element.id, className: String(element.className),
        color: getComputedStyle(element).color,
        background: getComputedStyle(element).backgroundColor,
      }));
    });
    expect(retired, `retired teal tokens at ${width}px`).toEqual([]);
  }
});

test('FNOS audit: open dialogs have no retired teal tokens', async ({page}) => {
  await load(page, 1440, 900);
  await page.evaluate(() => { document.documentElement.dataset.theme = 'light'; });
  const scan = async label => {
    const retired = await page.evaluate(() => {
      const values = new Set([
        'rgb(18, 184, 168)', 'rgb(7, 157, 145)', 'rgb(10, 168, 157)',
        'rgb(8, 167, 158)', 'rgb(8, 127, 118)', 'rgb(18, 165, 155)',
      ]);
      return [...document.querySelectorAll('body *')].filter(element => {
        const style = getComputedStyle(element);
        if (style.display === 'none' || style.visibility === 'hidden') return false;
        return [style.color, style.backgroundColor, style.borderTopColor, style.borderRightColor,
          style.borderBottomColor, style.borderLeftColor].some(value => values.has(value));
      }).map(element => ({ tag: element.tagName, id: element.id, className: String(element.className) }));
    });
    expect(retired, `retired teal tokens in ${label}`).toEqual([]);
  };
  await scan('library');
  await page.locator('#deviceBtn').click();
  await scan('device dialog');
  await page.locator('#closeDialog').click();
  await openSettings(page);
  await scan('library settings');
  await page.locator('[data-settings-tab="metadata"]').click();
  await scan('metadata providers');
});

test('FNOS audit: dark playback and format states preserve contrast tokens', async ({page}) => {
  await page.emulateMedia({ colorScheme: 'dark' });
  await load(page, 1440, 900);
  await page.locator('.track').first().evaluate(element => element.classList.add('is-current'));
  await page.locator('.track.is-current .track-title-line').evaluate(element => {
    const indicator = document.createElement('span');
    indicator.className = 'track-playing-indicator';
    indicator.textContent = '正在播放';
    element.appendChild(indicator);
  });
  const state = await page.evaluate(() => {
    const current = document.querySelector('.track.is-current');
    const title = current.querySelector('.track-title');
    const normalFormat = document.querySelector('.track-cell-format:not(.dsd)');
    const dsdFormat = document.querySelector('.track-cell-format.dsd');
    const sorted = document.querySelector('.track-sort-indicator');
    const indicator = document.querySelector('.track-playing-indicator');
    return {
      currentRow: getComputedStyle(current).backgroundColor,
      currentTitle: getComputedStyle(title).color,
      currentSubtitle: getComputedStyle(current.querySelector('.mobile-track-subtitle')).color,
      normalFormat: {
        color: getComputedStyle(normalFormat).color,
        background: getComputedStyle(normalFormat).backgroundColor,
      },
      dsdFormat: {
        color: getComputedStyle(dsdFormat).color,
        background: getComputedStyle(dsdFormat).backgroundColor,
      },
      sortIndicator: getComputedStyle(sorted).color,
      playingIndicator: {
        color: getComputedStyle(indicator).color,
        background: getComputedStyle(indicator).backgroundColor,
      },
    };
  });
  expect(state).toEqual({
    currentRow: 'rgba(0, 0, 0, 0)',
    currentTitle: 'rgb(0, 102, 255)',
    currentSubtitle: 'rgb(0, 102, 255)',
    normalFormat: { color: 'rgba(255, 255, 255, 0.75)', background: 'rgb(35, 35, 38)' },
    dsdFormat: { color: 'rgb(234, 191, 117)', background: 'rgba(234, 191, 117, 0.12)' },
    sortIndicator: 'rgb(0, 102, 255)',
    playingIndicator: { color: 'rgb(0, 102, 255)', background: 'rgba(0, 102, 255, 0.25)' },
  });
});

test('FNOS audit: dark inactive player controls keep readable secondary contrast', async ({page}) => {
  await page.emulateMedia({colorScheme: 'dark'});
  await load(page, 1440, 900);
  const colors = await page.evaluate(() => [
    '#deviceBtn', '#lyricsBtn', '#favoriteCurrentBtn', '#repeatBtn', '#shuffleBtn', '#queueBtn',
  ].map(selector => getComputedStyle(document.querySelector(selector)).color));
  expect(colors).toEqual(Array(6).fill('rgba(255, 255, 255, 0.75)'));
});

test('FNOS 375 dark mobile settings keep surfaces tokenized', async ({page}) => {
  await page.emulateMedia({colorScheme: 'dark'});
  await load(page, 375, 812);
  await openSettings(page);
  await page.locator('[data-settings-tab="metadata"]').click();
  await page.locator('#deviceDialog').evaluate(dialog => dialog.showModal());
  const whiteSurfaces = await page.evaluate(() => [...document.querySelectorAll('body *')]
    .filter(element => {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0
        && style.backgroundColor === 'rgb(255, 255, 255)';
    })
    .slice(0, 30)
    .map(element => ({tag: element.tagName, id: element.id, className: String(element.className)})));
  expect(whiteSurfaces).toEqual([]);
});

test('FNOS 375 dark mobile has no retired teal state colors', async ({page}) => {
  await page.emulateMedia({colorScheme: 'dark'});
  await load(page, 375, 812);
  await openSettings(page);
  await page.locator('[data-settings-tab="metadata"]').click();
  const retired = await page.evaluate(() => {
    const values = new Set([
      'rgb(18, 184, 168)', 'rgb(7, 157, 145)', 'rgb(10, 168, 157)',
      'rgb(8, 167, 158)', 'rgb(8, 127, 118)', 'rgb(18, 165, 155)',
    ]);
    return [...document.querySelectorAll('body *')].filter(element => {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      if (style.display === 'none' || style.visibility === 'hidden' || rect.width <= 0 || rect.height <= 0) return false;
      return [style.color, style.backgroundColor, style.borderTopColor, style.borderRightColor,
        style.borderBottomColor, style.borderLeftColor].some(value => values.has(value));
    }).slice(0, 30).map(element => ({tag: element.tagName, id: element.id, className: String(element.className)}));
  });
  expect(retired).toEqual([]);
});



