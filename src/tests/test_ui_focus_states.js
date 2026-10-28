const assert = require("node:assert/strict");
const fs = require("node:fs");

const css = fs.readFileSync("app/ui/app.css", "utf8");
const app = fs.readFileSync("app/ui/app.js", "utf8");

assert.match(css, /:where\(button,a,input,select,textarea,\[role="button"\],\[role="tab"\],\[role="switch"\]\):focus-visible/,
  "shared controls must expose a visible keyboard focus ring");
assert.match(css, /\.track:focus-within\{[^}]*background:var\(--ui-selected\)/,
  "song rows must expose focus context when an inner control receives focus");
assert.match(css, /\.group-row:focus-visible\{[^}]*box-shadow:inset 3px 0 0 var\(--ui-accent\)/,
  "keyboard-operable group rows must expose a row-level focus state");
assert.match(css, /\.artist-all-tracks-breadcrumb button:focus-visible/,
  "breadcrumb links must expose a visible focus state");
assert.match(app, /role="button" tabindex="0" aria-label="打开文件夹/,
  "folder rows must remain keyboard-operable before receiving the focus style");

console.log("shared keyboard focus states: controls, song rows, group rows, and breadcrumbs covered");
