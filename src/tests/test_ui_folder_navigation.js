const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const app = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "app.js"), "utf8");

const binding = app.match(/document\.querySelectorAll\("\[data-group-row\]"\)\.forEach\(row => \{[\s\S]*?row\.oncontextmenu[\s\S]*?\n    \}\);/);
assert.ok(binding, "group-row event binding must remain discoverable");
const source = binding[0];

assert.match(source, /row\.ondblclick\s*=\s*event\s*=>[\s\S]*?openGroupRow\(row\)/,
  "folder rows must open on double click");
// R513（负责人「移动端文件夹改为单击进入」）: 单击分支现在是两条路——手机直接进入，
// 桌面只选中（双击才进）。断言写成「手机这一支先于桌面那一支出现」，否则把两句话
// 调换顺序也能通过，而调换就是回归。
assert.match(
  source,
  /row\.dataset\.groupType\s*===\s*"folder"[\s\S]*?matchMedia\("\(max-width: 760px\)"\)\.matches\)\s*openGroupRow\(row\);[\s\S]*?else\s*setGroupSelection\(\[row\.dataset\.groupKey\]\);[\s\S]*?return;/,
  "a phone tap must enter the folder while a desktop click only selects it",
);

const setView = app.match(/function setView\(view\) \{[\s\S]*?\n\}/);
assert.ok(setView, "setView must remain an independently inspectable function");
assert.match(setView[0], /resetLibraryScrollPosition\(\)/,
  "switching categories must reset the library scroll position");
assert.match(setView[0], /requestLibraryLoad\(1, false\)[\s\S]*?resetLibraryScrollPosition/,
  "async category refresh must keep the library scroll at the top after repaint");

console.log("Folder double-click and category scroll regression checks passed.");
