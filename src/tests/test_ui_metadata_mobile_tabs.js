const assert = require("node:assert/strict");
const fs = require("node:fs");

const css = fs.readFileSync("app/ui/app.css", "utf8");

assert.match(css, /\.metadata-settings-tabs button\{min-width:0;flex:0 0 auto;padding:0 6px;white-space:nowrap\}/,
  "mobile metadata subtabs must keep labels on one line");
assert.doesNotMatch(css, /\.metadata-settings-tabs button\{[^}]*white-space:normal/,
  "mobile metadata subtabs must not use wrapping labels");

const theme = fs.readFileSync("app/ui/fnos-theme.css", "utf8");
assert.match(theme, /\.metadata-settings-tabs \{ display: flex !important; flex-wrap: nowrap !important;[\s\S]*?overflow-x: auto !important;/,
  "FNOS mobile metadata subtabs must stay in one horizontal strip");
assert.match(theme, /\.metadata-settings-tabs button \{ flex: 0 0 auto !important; white-space: nowrap !important; \}/,
  "FNOS mobile metadata subtabs must keep each tab single-line");

console.log("mobile metadata subtabs: labels remain single-line and bounded");
