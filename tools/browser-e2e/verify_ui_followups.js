// Verification probe for the second UI-audit batch (P1-6..P1-8 + P2 list).
// Run: node verify_ui_followups.js
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const BASE = 'http://127.0.0.1:8745/';
const OUT = path.join(__dirname, '..', '..', 'artifacts', '_ui_fix_verify2');
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME });
  const report = {};

  // ---------- desktop ----------
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(BASE, { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);

  report.desktop = await page.evaluate(() => {
    const sidebar = document.querySelector('.sidebar');
    const titles = [...sidebar.querySelectorAll('.nav-title')].map((t) => t.textContent.trim());
    const groups = [];
    let current = null;
    for (const child of sidebar.querySelector('.sidebar-scroll').children) {
      if (child.classList.contains('nav-title')) { current = child.textContent.trim(); groups.push({ title: current, items: [] }); continue; }
      if (child.classList.contains('nav-item') && groups.length) {
        groups[groups.length - 1].items.push(child.textContent.trim().replace(/\s+/g, ' '));
      }
    }
    return {
      folderBtn: Boolean(document.getElementById('folderBtn')),
      sidebarHead: (() => { const h = document.querySelector('.sidebar-head'); return h ? getComputedStyle(h).display : null; })(),
      titles,
      groups,
      lyricsBtn: {
        svg: document.querySelectorAll('#lyricsBtn svg').length,
        text: document.getElementById('lyricsBtn').textContent.trim(),
        stroke: getComputedStyle(document.querySelector('#lyricsBtn svg')).stroke,
      },
    };
  });

  // settings: save labels + library health + path rows
  await page.click('#mobileSettingsNavBtn');
  await page.waitForTimeout(900);
  report.settings = await page.evaluate(() => {
    const d = document.getElementById('folderDialog');
    const health = document.getElementById('libraryHealth');
    return {
      saveLabels: [...d.querySelectorAll('.settings-save')].map((b) => ({ id: b.id, text: b.textContent.trim(), data: b.dataset.saveLabel })),
      healthClass: health.className,
      healthBg: getComputedStyle(health).backgroundColor,
      healthBorder: getComputedStyle(health).borderColor,
      healthDetail: document.getElementById('libraryHealthDetail').textContent.trim(),
      pathRows: [...document.querySelectorAll('.library-path-row')].map((r) => ({
        value: r.querySelector('input')?.value,
        hasRemove: Boolean(r.querySelector('.library-path-remove')),
      })),
    };
  });
  await page.screenshot({ path: path.join(OUT, 'fixed-settings-library.png') });

  // metadata control widths
  await page.click('[data-settings-tab="metadata"]');
  await page.waitForTimeout(500);
  await page.click('[data-metadata-settings-tab="providers"]');
  await page.waitForTimeout(500);
  report.metadata = await page.evaluate(() => {
    const pane = document.querySelector('.metadata-settings-subpane:not([hidden])');
    return [...pane.querySelectorAll('.metadata-probe-query input')].map((el) => {
      const r = el.getBoundingClientRect();
      return { id: el.id, w: Math.round(r.width), h: Math.round(r.height) };
    });
  });
  await page.screenshot({ path: path.join(OUT, 'fixed-metadata-providers.png') });
  await page.keyboard.press('Escape');
  await page.waitForTimeout(400);

  // lyrics empty state
  await page.click('#lyricsBtn');
  await page.waitForTimeout(800);
  report.lyricsEmpty = await page.evaluate(() => {
    const box = document.getElementById('lyricsLines');
    const p = box.querySelector('p');
    const rb = box.getBoundingClientRect();
    const rp = p ? p.getBoundingClientRect() : null;
    return {
      cls: box.className,
      display: getComputedStyle(box).display,
      text: p ? p.textContent.trim() : null,
      centerOffset: rp ? Math.round((rp.left + rp.width / 2) - (rb.left + rb.width / 2)) : null,
    };
  });
  await page.screenshot({ path: path.join(OUT, 'fixed-lyrics-empty.png') });
  await page.evaluate(() => { document.getElementById('lyricsView').hidden = true; });
  report.desktopErrors = errors;
  await page.close();

  // ---------- mobile ----------
  const m = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
  const mErrors = [];
  m.on('pageerror', (e) => mErrors.push(String(e)));
  await m.goto(BASE, { waitUntil: 'networkidle' });
  await m.waitForTimeout(2000);

  await m.click('#mobileNavBtn');
  await m.waitForTimeout(600);
  report.drawer = await m.evaluate(() => {
    const head = document.querySelector('.sidebar-head');
    const close = document.getElementById('mobileNavCloseBtn');
    return {
      headDisplay: head ? getComputedStyle(head).display : null,
      headText: head ? head.textContent.trim() : null,
      closeVisible: close ? close.getBoundingClientRect().width > 0 : false,
      closeRect: close ? (() => { const r = close.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; })() : null,
    };
  });
  await m.screenshot({ path: path.join(OUT, 'fixed-mobile-drawer.png') });
  await m.click('#mobileNavCloseBtn');
  await m.waitForTimeout(500);
  report.drawerClosed = await m.evaluate(() => !document.querySelector('.sidebar').classList.contains('mobile-open'));

  await m.evaluate(() => document.getElementById('folderDialog').showModal());
  await m.waitForTimeout(700);
  report.mobileButtons = await m.evaluate(() => ['libraryScanNowBtn', 'chooseLibraryPathBtn', 'saveLibrarySettingsBtn'].map((id) => {
    const el = document.getElementById(id);
    const r = el.getBoundingClientRect();
    return { id, h: Math.round(r.height) };
  }));
  await m.screenshot({ path: path.join(OUT, 'fixed-mobile-settings.png') });
  report.mobileErrors = mErrors;
  await m.close();

  await browser.close();
  console.log(JSON.stringify(report, null, 1));
})();
