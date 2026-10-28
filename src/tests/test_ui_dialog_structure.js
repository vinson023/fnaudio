const assert = require("node:assert/strict");
const fs = require("node:fs");

const html = fs.readFileSync("app/ui/index.html", "utf8");

const dialogIds = [
  ["deviceDialog", "deviceDialogTitle"],
  ["folderDialog", "folderDialogTitle"],
  ["dlnaDiagnosticsDialog", "dlnaDiagnosticsDialogTitle"],
  ["playlistDialog", "playlistDialogTitle"],
  ["trackActionDialog", "trackActionTitle"],
  ["metadataCandidateDialog", "metadataCandidateTitle"],
  ["externalShareDialog", "externalShareDialogTitle"],
  ["deleteTrackDialog", "deleteTrackTitle"],
  ["columnsDialog", "columnsDialogTitle"],
];

function dialogMarkup(id) {
  const start = html.indexOf(`<dialog id="${id}"`);
  assert.ok(start >= 0, `#${id} exists`);
  const end = html.indexOf("</dialog>", start);
  assert.ok(end > start, `#${id} is closed`);
  return html.slice(start, end + "</dialog>".length);
}

for (const [dialogId, titleId] of dialogIds) {
  const dialog = dialogMarkup(dialogId);
  assert.match(dialog, new RegExp(`aria-labelledby="${titleId}"`), `#${dialogId} has a stable accessible title reference`);
  assert.match(dialog, new RegExp(`<h2[^>]*id="${titleId}"`), `#${dialogId} title element exists`);
  for (const close of dialog.matchAll(/<button\b[^>]*class="[^"]*dialog-close-button[^"]*"[^>]*>/g)) {
    assert.match(close[0], /\btype="button"/, `${dialogId} close button is not an implicit submit button`);
    assert.match(close[0], /aria-label="关闭"/, `${dialogId} close button is named`);
  }
  for (const svg of dialog.matchAll(/<svg\b[^>]*>/g)) {
    assert.match(svg[0], /aria-hidden="true"/, `${dialogId} SVG chrome is decorative`);
  }
}

// The external share form must not be swallowed by the title bar. This catches the
// exact regression where a missing </div> made the form inherit header layout.
assert.match(
  dialogMarkup("externalShareDialog"),
  /id="closeExternalShareDialog"[^>]*>[\s\S]*?<\/button>\s*<\/div>\s*<div id="externalShareForm">/,
  "externalShareDialog closes its title bar before the form",
);

assert.match(
  dialogMarkup("deleteTrackDialog"),
  /aria-describedby="deleteTrackDescription"/,
  "deleteTrackDialog exposes its confirmation description",
);

console.log(`dialog structure: ${dialogIds.length} dialogs, stable titles, typed close buttons, and decorative SVG chrome verified`);
