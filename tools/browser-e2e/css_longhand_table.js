// Expand every (property, value) pair found in the stylesheets into the longhand
// names this engine actually sets.
//
// The table exists so the offline analysis in `tools/merge_duplicate_selectors.py`
// can compare declarations exactly instead of by name prefix: `border-radius`
// and `border-color` share a prefix but never compete, while `padding` and
// `padding-top` compete through the shorthand.
//
//   node css_longhand_table.js <pairs.json> <out.json>
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const PAIRS = process.argv[2];
const OUT = process.argv[3];

(async () => {
  const browser = await chromium.launch({
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  });
  const page = await browser.newPage();
  await page.setContent("<!doctype html><html><body></body></html>");

  const pairs = JSON.parse(fs.readFileSync(PAIRS, "utf8"));
  const table = await page.evaluate((list) => {
    const probe = document.createElement("div");
    const out = {};
    for (const [prop, value] of list) {
      probe.style.cssText = "";
      let names = [];
      try {
        probe.style.setProperty(prop, value);
        for (let i = 0; i < probe.style.length; i += 1) names.push(probe.style[i]);
      } catch (e) {
        names = [];
      }
      if (!names.length) names = [prop];
      out[prop + "\u0000" + value] = names;
    }
    return out;
  }, pairs);

  fs.writeFileSync(OUT, JSON.stringify(table));
  const distinctProps = new Set(pairs.map(p => p[0]));
  console.log(`pairs=${pairs.length} props=${distinctProps.size} -> ${path.basename(OUT)}`);
  await browser.close();
})();
