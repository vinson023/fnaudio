const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const app = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "app.js"), "utf8");

const binding = app.match(/document\.querySelectorAll\("\[data-group-row\]"\)\.forEach\(row => \{[\s\S]*?row\.oncontextmenu[\s\S]*?\n    \}\);/);
assert.ok(binding, "group-row event binding must remain discoverable");
const source = binding[0];

assert.match(source, /row\.ondblclick\s*=\s*event\s*=>[\s\S]*?openGroupRow\(row\)/,
  "folder rows must open on double click");
assert.match(source, /row\.dataset\.groupType\s*===\s*"folder"[\s\S]*?return;/,
  "folder row single click must stop before the shared openGroupRow path");

const setView = app.match(/function setView\(view\) \{[\s\S]*?\n\}/);
assert.ok(setView, "setView must remain an independently inspectable function");
assert.match(setView[0], /resetLibraryScrollPosition\(\)/,
  "switching categories must reset the library scroll position");
assert.match(setView[0], /requestLibraryLoad\(1, false\)[\s\S]*?resetLibraryScrollPosition/,
  "async category refresh must keep the library scroll at the top after repaint");

console.log("Folder double-click and category scroll regression checks passed.");
