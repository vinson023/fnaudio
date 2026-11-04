// Computed-style snapshot harness.
// Captures, for a fixed set of page states and viewports, every element's
// resolved style for the properties a CSS refactor can plausibly move. Running
// it before and after a stylesheet change and diffing the two JSON files proves
// whether the change is inert far more strictly than eyeballing screenshots.
//
//   node css_snapshot.js <out.json>
//
// Two practical notes:
//  * Take the baseline from a WARM run. The very first capture after a cold
//    fixture start lags the async settings panes (playback/metadata settle on
//    their own data fetch), which shows up as ~109 spurious record diffs in
//    three `w1440-light/settings-*` states. The second run is reproducible to
//    the byte.
//  * The output is ~41 MB per run, so keep only the pair you are diffing.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE = 'http://127.0.0.1:8745/';
const OUT = process.argv[2] || path.join(__dirname, '..', '..', 'artifacts', '_css_snapshot.json');

const PROPS = [
  'display', 'position', 'top', 'right', 'bottom', 'left', 'z-index', 'float',
  'width', 'height', 'min-width', 'min-height', 'max-width', 'max-height',
  'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
  'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
  'border-top-width', 'border-right-width', 'border-bottom-width', 'border-left-width',
  'border-top-style', 'border-right-style', 'border-bottom-style', 'border-left-style',
  'border-top-color', 'border-right-color', 'border-bottom-color', 'border-left-color',
  'border-top-left-radius', 'border-top-right-radius', 'border-bottom-left-radius', 'border-bottom-right-radius',
  'background-color', 'background-image', 'background-size', 'background-position',
  'color', 'font-size', 'font-weight', 'font-style', 'line-height', 'letter-spacing',
  'text-align', 'text-transform', 'text-decoration-line', 'white-space', 'word-break',
  'opacity', 'visibility', 'overflow-x', 'overflow-y', 'box-shadow', 'transform',
  'flex-direction', 'flex-wrap', 'flex-grow', 'flex-shrink', 'flex-basis',
  'align-items', 'align-self', 'justify-content', 'gap', 'row-gap', 'column-gap',
  'grid-template-columns', 'grid-template-rows', 'grid-column', 'grid-row', 'order',
  'object-fit', 'filter', 'cursor', 'pointer-events',
];

const VIEWPORTS = [
  { name: 'w1440', w: 1440, h: 900 },
  { name: 'w1024', w: 1024, h: 768 },
  { name: 'w390', w: 390, h: 844 },
  { name: 'w360', w: 360, h: 740 },
];

function collect(props) {
  const keyOf = (el) => {
    const parts = [];
    let n = el;
    while (n && n.nodeType === 1 && n !== document.documentElement) {
      const parent = n.parentElement;
      let i = 0;
      if (parent) {
        for (const sib of parent.children) {
          i += 1;
          if (sib === n) break;
        }
      }
      parts.unshift(n.tagName.toLowerCase() + ':' + i);
      n = parent;
    }
    return parts.join('>');
  };
  const out = {};
  for (const el of document.querySelectorAll('*')) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' && !el.getClientRects().length) {
      // Keep hidden nodes: their resolved display is itself part of the contract.
      const vals = props.map((p) => cs.getPropertyValue(p)).join('|');
      out[keyOf(el)] = vals;
      continue;
    }
    const r = el.getBoundingClientRect();
    const vals = props.map((p) => cs.getPropertyValue(p)).join('|');
    out[keyOf(el)] = vals + '|box:' + [r.x, r.y, r.width, r.height].map((v) => Math.round(v * 100) / 100).join(',');
  }
  return out;
}

async function settle(page) {
  await page.waitForTimeout(900);
}

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  });
  const report = {};
  for (const vp of VIEWPORTS) {
    for (const theme of ['light', 'dark']) {
      const page = await browser.newPage({ viewport: { width: vp.w, height: vp.h } });
      await page.goto(BASE, { waitUntil: 'networkidle' });
      await page.evaluate((t) => {
        document.documentElement.setAttribute('data-theme', t);
        try {
          localStorage.setItem('fnaudio-theme', t);
        } catch (e) {}
      }, theme);
      await page.waitForTimeout(1600);

      const tag = `${vp.name}-${theme}`;
      report[`${tag}/library`] = await page.evaluate(collect, PROPS);

      // 设置对话框：直接 showModal，避免不同断点的入口按钮差异影响快照。
      await page.evaluate(() => document.getElementById('folderDialog').showModal());
      await settle(page);
      for (const tab of ['library', 'playback', 'metadata', 'dlna', 'runtime']) {
        await page.click(`[data-settings-tab="${tab}"]`).catch(() => {});
        await settle(page);
        report[`${tag}/settings-${tab}`] = await page.evaluate(collect, PROPS);
        if (tab === 'metadata') {
          for (const sub of ['overview', 'providers', 'tasks', 'tags']) {
            await page.click(`[data-metadata-settings-tab="${sub}"]`).catch(() => {});
            await settle(page);
            report[`${tag}/settings-metadata-${sub}`] = await page.evaluate(collect, PROPS);
          }
        }
      }
      await page.evaluate(() => {
        try {
          document.getElementById('folderDialog').close();
        } catch (e) {}
      });
      await settle(page);

      await page.evaluate(() => {
        const d = document.getElementById('deviceDialog');
        if (d) d.showModal();
      });
      await settle(page);
      report[`${tag}/device`] = await page.evaluate(collect, PROPS);
      await page.evaluate(() => {
        try {
          document.getElementById('deviceDialog').close();
        } catch (e) {}
      });
      await settle(page);

      // 歌词面板
      await page.evaluate(() => {
        const btn = document.getElementById('lyricsBtn');
        if (btn) btn.click();
      });
      await settle(page);
      report[`${tag}/lyrics`] = await page.evaluate(collect, PROPS);

      await page.close();
    }
  }
  fs.writeFileSync(OUT, JSON.stringify(report));
  const states = Object.keys(report).length;
  const elements = Object.values(report).reduce((n, s) => n + Object.keys(s).length, 0);
  console.log(`wrote ${OUT} states=${states} element-records=${elements}`);
  await browser.close();
})();
