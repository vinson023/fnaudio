// Does a "blocker" rule ever match the same element as the duplicate-selector
// group it blocks?
//
// Merging a group's blocks into its last block moves declarations later in the
// cascade. That is only dangerous when a rule between them ties on specificity
// and importance for an overlapping longhand AND can land on the same element.
// The first two conditions are answered offline; this probe answers the third by
// intersecting the matched-element sets across every sampled state.
//
//   node css_selector_overlap.js <blocked.json> <out.json>
//
// blocked.json: { "<sheet>": [ { "ctx": "...", "selector": "...", "blockers": ["..."] } ] }
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const BASE = "http://127.0.0.1:8745/";
const INPUT = process.argv[2];
const OUT = process.argv[3];

const VIEWPORTS = [
  { name: "w1440", w: 1440, h: 900 },
  { name: "w1024", w: 1024, h: 768 },
  { name: "w390", w: 390, h: 844 },
  { name: "w360", w: 360, h: 740 },
];

const DYNAMIC = /:(hover|active|focus|focus-visible|focus-within|visited|target|checked|disabled|enabled|placeholder-shown|autofill|user-invalid|user-valid|open|popover-open|modal)\b/;

// Runs in the page. `wanted` is the set of selectors whose element sets we need.
function probe(wanted) {
  const sets = new Map();
  for (const selector of wanted) {
    try {
      sets.set(selector, new Set(document.querySelectorAll(selector)));
    } catch (e) {
      sets.set(selector, new Set());
    }
  }
  // Hand back, per selector, the ids of the elements it matched. Ids are assigned
  // in the page so the same element carries the same id across selectors, which
  // is what makes the intersection test in Node cheap.
  const members = {};
  let index = 0;
  const ids = new Map();
  for (const [selector, elements] of sets) {
    const list = [];
    for (const element of elements) {
      let id = ids.get(element);
      if (id === undefined) { id = index; ids.set(element, id); index += 1; }
      list.push(id);
    }
    members[selector] = list;
  }
  return { members };
}

async function settle(page) {
  await page.waitForTimeout(900);
}

(async () => {
  const blocked = JSON.parse(fs.readFileSync(INPUT, "utf8"));
  const wanted = new Set();
  const pairs = [];
  for (const sheet of Object.keys(blocked)) {
    for (const group of blocked[sheet]) {
      wanted.add(group.selector);
      for (const blocker of group.blockers) wanted.add(blocker);
      pairs.push({ sheet, group });
    }
  }

  const overlap = new Map();   // "sheet|ctx|selector" -> Set of blockers that co-occur
  for (const { sheet, group } of pairs) {
    overlap.set([sheet, group.ctx, group.selector].join("|"), new Set());
  }

  const browser = await chromium.launch({
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  });
  let states = 0;
  for (const vp of VIEWPORTS) {
    for (const theme of ["light", "dark"]) {
      const page = await browser.newPage({ viewport: { width: vp.w, height: vp.h } });
      await page.goto(BASE, { waitUntil: "networkidle" });
      await page.evaluate((t) => {
        document.documentElement.setAttribute("data-theme", t);
        try { localStorage.setItem("fnaudio-theme", t); } catch (e) {}
      }, theme);
      await page.waitForTimeout(1600);

      const collect = async () => {
        const result = await page.evaluate(probe, Array.from(wanted));
        states += 1;
        const sets = new Map();
        for (const selector of wanted) {
          sets.set(selector, new Set(result.members[selector] || []));
        }
        for (const { sheet, group } of pairs) {
          const key = [sheet, group.ctx, group.selector].join("|");
          const mine = sets.get(group.selector);
          for (const blocker of group.blockers) {
            const theirs = sets.get(blocker);
            for (const id of theirs) {
              if (mine.has(id)) { overlap.get(key).add(blocker); break; }
            }
          }
        }
      };

      await collect();
      await page.evaluate(() => document.getElementById("folderDialog").showModal());
      await settle(page);
      for (const tab of ["library", "playback", "metadata", "dlna", "runtime"]) {
        await page.click(`[data-settings-tab="${tab}"]`).catch(() => {});
        await settle(page);
        await collect();
        if (tab === "metadata") {
          for (const sub of ["overview", "providers", "tasks", "tags"]) {
            await page.click(`[data-metadata-settings-tab="${sub}"]`).catch(() => {});
            await settle(page);
            await collect();
          }
        }
      }
      await page.evaluate(() => {
        try { document.getElementById("folderDialog").close(); } catch (e) {}
      });
      await settle(page);
      await page.evaluate(() => {
        const d = document.getElementById("deviceDialog");
        if (d) d.showModal();
      });
      await settle(page);
      await collect();
      await page.evaluate(() => {
        try { document.getElementById("deviceDialog").close(); } catch (e) {}
      });
      await settle(page);
      await page.evaluate(() => {
        const btn = document.getElementById("lyricsBtn");
        if (btn) btn.click();
      });
      await settle(page);
      await collect();

      await page.close();
      console.log(`  ${vp.name}-${theme}: ${states} states`);
    }
  }

  const out = {};
  for (const [key, blockers] of overlap) out[key] = Array.from(blockers);
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify(out));
  const total = Object.keys(out).length;
  const clean = Object.values(out).filter(list => list.length === 0).length;
  const dynamic = Object.values(out).filter(list => list.some(b => DYNAMIC.test(b))).length;
  console.log(`states=${states} groups=${total} no-overlap=${clean} has-dynamic-blocker=${dynamic}`);
  await browser.close();
})();
