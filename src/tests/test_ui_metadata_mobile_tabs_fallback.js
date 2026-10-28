const assert = require("node:assert/strict");
const fs = require("node:fs");

const css = fs.readFileSync("app/ui/app.css", "utf8");

assert.match(css, /\.metadata-settings-tabs\{display:flex;flex-wrap:nowrap;gap:2px;overflow-x:auto;overflow-y:hidden;scrollbar-width:none;padding-bottom:4px\}/,
  "base stylesheet fallback must keep metadata subtabs in one horizontal strip");
assert.match(css, /\.metadata-settings-tabs button\{min-width:0;flex:0 0 auto;padding:0 6px;white-space:nowrap\}/,
  "base stylesheet fallback must keep each metadata subtab single-line");
assert.doesNotMatch(css, /\.metadata-settings-tabs\{display:grid;grid-template-columns:repeat\(2/,
  "base stylesheet must not retain the retired two-column metadata subtab grid");

console.log("metadata subtabs fallback: base and FNOS theme layers share one-line horizontal behavior");
