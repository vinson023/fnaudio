const assert = require("node:assert/strict");
const fs = require("node:fs");

const index = fs.readFileSync("app/ui/index.html", "utf8");
const app = fs.readFileSync("app/ui/app.js", "utf8");
const css = fs.readFileSync("app/ui/app.css", "utf8");

// R461: the fnOS host picker (pickUserFile) only exists inside the fnOS App or
// desktop WebView.  The Android client and any standalone browser have no host,
// so tapping "选择音乐目录" must fall back to the server-side directory browser
// instead of silently doing nothing.
assert.match(app, /async function chooseLibraryPath\(\)/, "the picker entry point must stay named");
assert.match(app, /function hostUnavailable\(message\)/, "the missing-host case needs its own marker");
assert.match(
  app,
  /catch \(error\) \{[\s\S]*?if \(error && error\.hostUnavailable\) \{[\s\S]*?当前环境没有飞牛目录选择器，已切换为服务器目录浏览。[\s\S]*?openLibraryDirBrowser\(""\);[\s\S]*?return false;/,
  "a host-less environment must fall back to the server directory browser",
);
// A denial or a timeout reached the host, so it must keep reporting itself
// instead of being papered over by another dialog.
assert.match(
  app,
  /status\.textContent = error\.message \|\| "打开目录选择窗口失败";[\s\S]*?return false;/,
  "host failures that are not 'no host' must still report their own message",
);
assert.doesNotMatch(
  app,
  /if \(!host\) throw new Error\("无法连接飞牛宿主/,
  "the missing-host errors must carry the hostUnavailable marker",
);
assert.match(app, /function openLibraryDirBrowser\(path = ""\)/, "the fallback browser needs an entry point");
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
// not from the NAS web UI.  The web UI only ever uses the fnOS picker, and the
// picker lists nothing but the groups it is asked for - "remote" (fnOS 远程挂载,
// mounted under /vol1/@mountmgr/...) was never requested, so the share was
// simply not in the sidebar.  The browser route stays available as a fallback
// because a share mounted by hand may appear under no group at all.
assert.match(
  app,
  /sidebarGroup: \["myFiles", "otherShare", "external", "remote", "favorites"\]/,
  "the fnOS picker must ask for remote mounts and external storage, not just 我的文件",
);
assert.match(index, /id="browseLibraryPathBtn"/, "the server browser needs its own always-visible button");
assert.match(
  app,
  /\$\("browseLibraryPathBtn"\)\.onclick = \(\) => openLibraryDirBrowser\(""\)/,
  "the browser button must open the server directory browser",
);

console.log("Library directory browser regression checks passed.");
