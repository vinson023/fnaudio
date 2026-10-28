const assert = require("node:assert/strict");
const fs = require("node:fs");

const css = fs.readFileSync("app/ui/app.css", "utf8");

assert.match(css, /@media\s*\(prefers-reduced-motion:\s*reduce\)/,
  "the UI must honor the user's reduced-motion preference");
assert.match(css, /animation-duration:\.01ms!important/,
  "reduced motion must stop long-running decorative animations");
assert.match(css, /transition-duration:\.01ms!important/,
  "reduced motion must minimize transition movement");
assert.match(css, /scroll-behavior:auto!important/,
  "reduced motion must avoid smooth scrolling effects");

console.log("reduced motion: animation, transition, and scroll behavior are covered");
