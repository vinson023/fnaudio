const assert = require("node:assert/strict");
const fs = require("node:fs");

const index = fs.readFileSync("app/ui/index.html", "utf8");
const app = fs.readFileSync("app/ui/app.js", "utf8");
const css = fs.readFileSync("app/ui/app.css", "utf8");

// R532: the fnOS host picker is gone.  It could not see fnOS 远程挂载 (it only
// lists the sidebar groups it is asked for, and shares live under
// /vol1/@mountmgr/...), so adding a mounted folder needed the server browser
// anyway; keeping both left two buttons that did the same job.  The browser is a
// superset - volume roots plus every mount point - so it is now the only entry.
assert.doesNotMatch(app, /pickUserFile/, "the fnOS host picker must not be offered any more");
assert.doesNotMatch(app, /async function chooseLibraryPath\(\)/, "the picker entry point is gone");
assert.match(app, /function hostUnavailable\(message\)/, "other host actions still need the missing-host marker");
assert.match(app, /function openLibraryDirBrowser\(path = ""\)/, "the browser needs an entry point");
assert.match(app, /async function loadLibraryDir\(path = ""\)/, "the browser must load listings by path");
assert.match(app, /apiFetch\(`api\/library\/dirs\$\{query\}`\)/, "the browser must call the server listing route");
assert.match(app, /function renderLibraryDirListing\(data = \{\}\)/, "listings need a renderer");
assert.match(app, /function addCurrentLibraryDir\(\)/, "the browser must be able to add the current directory");
assert.match(
  app,
  /renderLibraryPathInputs\(\[\.\.\.current, path\]\)/,
  "adding a directory must append to the existing configured roots",
);
assert.match(app, /\$\("closeLibraryDirDialog"\)\.onclick/, "the browser dialog needs a close handler");
assert.match(app, /\$\("libraryDirUpBtn"\)\.onclick/, "the browser needs an up-one-level handler");
// A browse root has no parent (so the volume root with @appdata/docker/thumb can
// never appear), but "up" must still leave the button usable to return to the
// root list; only the root list itself disables it.
assert.match(
  app,
  /upButton\.disabled = !parent && !current;/,
  "the up button must return to the root list instead of being dead on a root",
);
assert.match(app, /\$\("libraryDirAddBtn"\)\.onclick = addCurrentLibraryDir;/, "the add button must be wired");

// The listing must refuse to render untrusted names as markup.
assert.match(app, /data-dir-path="\$\{escapeHtml\(value\)\}"/, "directory paths must be escaped into markup");

// The dialog itself, and the status node that used to be appended to the end of
// the pane (invisible on a 360x640 phone) now sits right under the picker row.
assert.match(index, /<dialog id="libraryDirDialog"/, "the browser dialog must exist");
assert.match(index, /id="libraryDirList"/, "the browser needs a listing container");
assert.match(index, /id="libraryDirPath"/, "the browser needs a current-path label");
assert.match(index, /id="libraryDirStatus"[^>]*aria-live="polite"/, "the browser needs a live status line");
const statusIndex = index.indexOf('id="librarySettingsStatus"');
const pickerIndex = index.indexOf('class="library-path-picker"');
const actionsIndex = index.indexOf('id="saveLibrarySettingsBtn"');
assert.ok(statusIndex > pickerIndex, "the library status must follow the picker row");
assert.ok(statusIndex < actionsIndex, "the library status must stay above the save action");
assert.doesNotMatch(index, /id="librarySettingsStatus"[^>]*hidden/, "the status line must not be hidden by markup");

// Styling: the list scrolls inside the dialog instead of pushing the buttons away.
assert.match(css, /\.library-dir-list\{[^}]*max-height:[^}]*overflow-y:auto/, "the directory list must scroll in place");
assert.match(css, /\.library-dir-row\{[^}]*min-height:4[0-9]px/, "directory rows need a touch-sized target");
assert.match(css, /@media\(max-width:760px\)\{[^}]*\.library-dir-list\{/, "the phone layout needs its own list height");

// Reported 2026-11-11: an SMB share could be added from the Android client but
// not from the NAS web UI.  The web UI was stuck on the fnOS host picker, which
// only lists the sidebar groups it is asked for - "remote" (fnOS 远程挂载, under
// /vol1/@mountmgr/...) was never requested - so the share was not in the sidebar
// at all.  R532 removes the picker instead of patching its sidebar: the server
// browser lists the volume roots and every mount point, so it is a superset and
// the pane now has exactly one entry point.
assert.doesNotMatch(app, /pickUserFile/, "the fnOS host picker must not be offered any more");
assert.doesNotMatch(index, /browseLibraryPathBtn/, "one entry point only: the second button is gone");
assert.match(
  app,
  /\$\("chooseLibraryPathBtn"\)\.onclick = \(\) => openLibraryDirBrowser\(""\)/,
  "the single entry point must open the server directory browser",
);
assert.match(index, /id="chooseLibraryPathBtn"[^>]*>\+ 添加目录</, "the remaining entry keeps its label");

console.log("Library directory browser regression checks passed.");
