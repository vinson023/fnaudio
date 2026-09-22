const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const cssPath = "app/ui/app.css";
const indexPath = "app/ui/index.html";
const uiDir = "app/ui";

const css = fs.readFileSync(cssPath, "utf8");
const index = fs.readFileSync(indexPath, "utf8");

// Comments are not selectors, and a declaration value such as
// `border:1px solid #dfe5ee` looks exactly like an id selector to a naive
// regular expression (115 of the 117 `#word` tokens in this sheet are colors),
// so the scanner has to walk the sheet and keep only selector preludes.
function stripComments(text) {
  // Blank out comment content while keeping every newline, so the reported
  // prelude lines still match the file on disk.
  return text.replace(/\/\*[\s\S]*?\*\//g, (comment) => comment.replace(/[^\n]/g, " "));
}

// Return every prelude that actually selects elements. An at-rule prelude
// (`@media(max-width:760px)`) is a condition, and the `from`/`0%` preludes
// inside `@keyframes` are progress labels, so neither is reported.
function selectorPreludes(text) {
  const preludes = [];
  const stack = [];
  let pending = "";
  let pendingLine = 1;
  let line = 1;
  for (const ch of text) {
    if (ch === "\n") line += 1;
    if (ch === "{" || ch === "}" || ch === ";") {
      const head = pending.trim();
      if (ch === "{") {
        const isAtRule = head.startsWith("@");
        const name = isAtRule ? head.split(/[\s(]/)[0] : "";
        stack.push(isAtRule ? { kind: "group", name } : { kind: "rule" });
        const enclosing = stack.slice(0, -1);
        const insideConditionalOnly = enclosing.every(
          (frame) => frame.kind === "group" && frame.name === "@media"
        );
        if (!isAtRule && insideConditionalOnly) preludes.push({ text: head, line: pendingLine });
      } else if (ch === "}") {
        stack.pop();
      }
      pending = "";
      continue;
    }
    // pending accumulates whitespace since the last token boundary, so the emptiness
    // test has to ignore it or pendingLine keeps reporting the line of an
    // earlier token (250 instead of 251 on the first dead more-button rule).
    if (pending.trim() === "" && !/\s/.test(ch)) pendingLine = line;
    pending += ch;
  }
  assert.equal(stack.length, 0, "app.css braces must balance for this scanner to be meaningful");
  return preludes;
}

function idSelectors(preludes) {
  const found = new Map();
  for (const prelude of preludes) {
    const withoutAttributes = prelude.text.replace(/\[[^\]]*\]/g, " ");
    for (const match of withoutAttributes.matchAll(/#([A-Za-z][\w-]*)/g)) {
      if (!found.has(match[1])) found.set(match[1], []);
      found.get(match[1]).push(prelude.line);
    }
  }
  return found;
}

function markupIds(text) {
  const ids = new Set();
  for (const match of text.matchAll(/\bid\s*=\s*"([^"]+)"/g)) ids.add(match[1]);
  for (const match of text.matchAll(/\bid\s*=\s*'([^']+)'/g)) ids.add(match[1]);
  return ids;
}

// An element can only carry an id that some UI script can spell out, so every
// single-word string literal in the UI bundle counts as reachable. This is
// deliberately generous: it can under-report dead selectors, never over-report.
function scriptIdTokens(dir) {
  const tokens = new Set();
  for (const file of fs.readdirSync(dir).filter((name) => name.endsWith(".js"))) {
    const text = fs.readFileSync(path.join(dir, file), "utf8");
    for (const match of text.matchAll(/["'`]([A-Za-z][\w-]*)["'`]/g)) tokens.add(match[1]);
  }
  return tokens;
}

// Hostile fixture: prove the scanner reports a phantom id, ignores colors,
// comment text, at-rule preludes and keyframe labels. Without this, an
// extraction that silently returned nothing would keep this gate green.
const probe = [
  "/* #phantomInsideComment */",
  ".shell{color:#fff;border:1px solid #dfe5ee}",
  "#volumePanel,#trackActionDialog .dialog-head{padding:0}",
  "@media(max-width:760px){#phantomControl{display:grid}}",
  "@keyframes marquee{from{opacity:0}50%{transform:translateX(-10px)}}",
].join("\n");
assert.deepEqual(
  [...idSelectors(selectorPreludes(stripComments(probe))).keys()].sort(),
  ["phantomControl", "trackActionDialog", "volumePanel"],
  "The selector scanner must catch a phantom id while ignoring colors, comments, @media conditions and @keyframes labels"
);

const reachable = new Set([...markupIds(index), ...scriptIdTokens(uiDir)]);
const violations = [...idSelectors(selectorPreludes(stripComments(css))).entries()]
  .filter(([id]) => !reachable.has(id))
  .map(([id, lines]) => `#${id} @ app.css:${lines.join(",")}`)
  .sort();
assert.deepEqual(
  violations,
  [],
  "app.css must not keep rules for elements the UI can never produce: " + violations.join(" | ")
);

// The retired "more" menu (`#mobileMoreBtn`, `#mobileMoreDialog`,
// `.mobile-more-button`, dropped from index.html in commit 208d550) must not
// come back as style only: on <=760px the whole `.player-actions` row is
// hidden and its controls were re-homed instead.
for (const staleFile of [indexPath, "app/ui/app.js", cssPath, "tests/test_ui_mobile_layout.js"]) {
  assert.doesNotMatch(
    fs.readFileSync(staleFile, "utf8"),
    /mobileMore|mobile-more-button/,
    `${staleFile} must not reference the retired mobile more menu`
  );
}
assert.doesNotMatch(css, /\.player-actions #mobileMoreBtn/, "dead more-button rules must stay deleted");
assert.match(
  css,
  /\.player-actions\{display:none!important\}/,
  "the bottom action row stays hidden on phones; do not half-restore it"
);
assert.match(
  css,
  /\.transport \.mobile-transport-control\{display:grid!important/,
  "shuffle and repeat stay reachable from the transport row on phones"
);
for (const id of ["mobileShuffleBtn", "mobileRepeatBtn", "mobileNavBtn", "mobileDeviceBtn", "mobileModeBtn"]) {
  assert.ok(reachable.has(id) && markupIds(index).has(id), `${id} must exist for the mobile layout`);
}

// The serialized DOM snapshot under tests/ was the other home of those phantom
// ids: 27 ids it described no longer exist and 66 current ids it never mentions,
// and no test ever read it.
assert.ok(
  !fs.existsSync(path.join("tests", "dom.txt")),
  "src/tests/dom.txt is a stale DOM snapshot and must not be revived"
);

console.log("Unreachable CSS selector regression checks passed.");