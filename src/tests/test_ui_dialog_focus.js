const assert = require("node:assert/strict");
const fs = require("node:fs");

const html = fs.readFileSync("app/ui/index.html", "utf8");
const app = fs.readFileSync("app/ui/app.js", "utf8");

assert.match(app, /function installDialogFocusManagement\(\)/);
assert.match(app, /new MutationObserver\(/, "dialog open state is observed centrally");
assert.match(app, /addEventListener\("close", \(\) => restoreOwner\(dialog\)\)/, "closing restores the trigger focus");
assert.match(app, /data-dialog-initial-focus/);
assert.match(app, /Promise\.resolve\(\)\.then\(/, "focus is deferred until showModal has applied the open state");
assert.doesNotMatch(app, /CSS\.escape\(/, "focus management does not depend on an optional CSS.escape API");
assert.doesNotMatch(app, /instanceof HTMLDialogElement/, "focus management does not throw when an older WebView lacks HTMLDialogElement");
assert.match(
  app,
  /normalizeDialogCloseControls\(\);\s*normalizeButtonTypes\(\);\s*installDialogFocusManagement\(\);/,
  "dialog normalization, button normalization, and focus management keep their startup order",
);

const dialogIds = [...html.matchAll(/<dialog\b[^>]*\bid="([^"]+)"[^>]*>/g)].map(match => match[1]);
assert.equal(dialogIds.length, 9, "all 9 native dialogs are covered");
assert.match(html, /id="deleteTrackDialog"[^>]*data-dialog-initial-focus="cancelDeleteTrack"/);
assert.match(html, /id="cancelDeleteTrack"[^>]*type="button"/);

for (const id of dialogIds) {
  const start = html.indexOf(`<dialog id="${id}"`);
  const end = html.indexOf("</dialog>", start);
  const dialog = html.slice(start, end + 9);
  assert.match(dialog, /<button\b/, `#${id} has a keyboard focus target`);
}

console.log(`dialog focus management: ${dialogIds.length} dialogs share deferred entry focus and trigger restoration`);
