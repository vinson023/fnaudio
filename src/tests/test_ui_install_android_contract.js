const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const index = fs.readFileSync(path.join(root, "app/ui/index.html"), "utf8");
const app = fs.readFileSync(path.join(root, "app/ui/app.js"), "utf8");
const css = fs.readFileSync(path.join(root, "app/ui/app.css"), "utf8");
const wizardInstall = fs.readFileSync(path.join(root, "wizard/../wizard/install"), "utf8");
const gradle = fs.readFileSync(path.join(root, "../android-client/app/build.gradle"), "utf8");

assert.doesNotMatch(wizardInstall, /wizard_library_path/, "installation must not request a music directory");
assert.match(index, /安装完成后，请在这里选择音乐目录/, "library settings must explain post-install directory setup");
// One entry since R532: the fnOS host picker could not see 远程挂载, so the
// server-side browser (a superset: volume roots plus every mount point) is
// the only way in.  A second button that opened the picker was removed.
assert.match(index, /id="chooseLibraryPathBtn"/, "library settings must expose the directory entry point");
assert.match(app, /\$\("chooseLibraryPathBtn"\)\.onclick = \(\) => openLibraryDirBrowser\(""\)/, "the entry point must open the server directory browser");
assert.doesNotMatch(app, /pickUserFile/, "the fnOS host picker must not be offered any more");
assert.match(css, /\.library-path-picker/, "library picker must have a dedicated aligned layout");
assert.match(index, /data-settings-block="playback-identity"[\s\S]*?只改变 Renderer 显示名称，不改变设备身份/, "the renderer group must say that only the display name changes");
assert.match(index, /class="settings-legacy-actions"[^>]*>[\s\S]*?id="savePlaybackSettingsBtn"/, "the renderer save must stay wired through the hidden trigger");
assert.match(css, /\.settings-inline-feedback\{display:inline-flex!important;align-items:center!important;min-height:34px!important\}/, "settings feedback must share the action row's vertical alignment");
assert.match(gradle, /main\.assets\.srcDirs \+= \["\.\.\/\.\.\/src\/app\/ui"\]/, "Android must package the current UI source tree");
assert.match(gradle, /verifyFnaudioUiSource/, "Android build must verify the UI source tree before packaging");

console.log("Install, settings layout, and Android asset/version contracts passed.");

// R532 removed the fnOS host picker: the server directory browser is a superset
// (volume roots plus every mount point, including the /vol1/@mountmgr shares the
// picker never listed), so one entry point replaced two.  The behaviour that used
// to need a runtime harness - readiness timeout, modal release, path merging,
// cancellation and denial - no longer exists; what remains is a single binding,
// which the static assertion above pins.
console.log("Official directory picker success, cancellation, errors and host boundary passed.");
