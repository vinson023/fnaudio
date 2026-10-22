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
assert.match(index, /id="chooseLibraryPathBtn"/, "library settings must expose the official directory picker action");
assert.match(app, /response\?\.data|Array\.isArray\(response\)/, "library picker must consume returned directory paths");
assert.match(css, /\.library-path-picker/, "library picker must have a dedicated aligned layout");
assert.match(index, /class="settings-pane-actions"><span class="settings-inline-feedback">保存后立即生效<\/span><button[^>]*id="savePlaybackSettingsBtn"/, "Renderer save hint must align with its actual save action");
assert.match(css, /\.settings-inline-feedback\{display:inline-flex!important;align-items:center!important;min-height:34px!important\}/, "settings feedback must share the action row's vertical alignment");
assert.match(gradle, /main\.assets\.srcDirs \+= \["\.\.\/\.\.\/src\/app\/ui"\]/, "Android must package the current UI source tree");
assert.match(gradle, /verifyFnaudioUiSource/, "Android build must verify the UI source tree before packaging");

console.log("Install, settings layout, and Android asset/version contracts passed.");

(async () => {
  const source = app.match(/^async function chooseLibraryPath\([^]*?^}/m)?.[0];
  const helper = app.match(/^async function runTrimHostAction\([^]*?^}/m)?.[0];
  assert.ok(source, "test must execute the real directory picker function");
  assert.ok(helper, "test must execute the real host readiness and timeout helper");
  let paths = ["/vol1/music"];
  let selection = {code: 0, data: [" /vol2/music ", "/vol1/music", "", null]};
  let ready = false;
  let calls = 0;
  const status = {textContent: ""};
  const button = {disabled: false};
  const dialog = {open: true, close() { this.open = false; }, showModal() { this.open = true; }};
  const nodes = {librarySettingsStatus: status, chooseLibraryPathBtn: button, folderDialog: dialog};
  const sdk = {
    isStandaloneWeb: false,
    async ready() { ready = true; },
    async pickUserFile(options) {
      assert.equal(ready, true, "SDK must be ready before opening the native picker");
      assert.equal(options.directory, true);
      assert.equal(dialog.open, false, "native modal must not make the host picker inert");
      assert.equal(button.disabled, true, "pending picker must reject duplicate clicks");
      calls++;
      if (selection instanceof Error) throw selection;
      return selection;
    },
  };
  const context = {getTrimSdk: async () => sdk, $: id => nodes[id], setTimeout, clearTimeout,
    collectLibraryPaths: () => paths, renderLibraryPathInputs: values => {paths = [...values];}};
  vm.createContext(context);
  vm.runInContext(`${helper}\n${source}`, context);
  assert.equal(await context.chooseLibraryPath(), true);
  assert.deepEqual(paths, ["/vol1/music", "/vol2/music"], "returned paths are merged and deduplicated");
  assert.match(status.textContent, /保存音乐库设置/, "selection must not silently save configuration");
  assert.equal(dialog.open, true, "settings must return after directory selection");
  assert.equal(button.disabled, false);
  for (const cancelled of [undefined, {code: 0, data: []}]) {
    selection = cancelled;
    assert.equal(await context.chooseLibraryPath(), false);
    assert.deepEqual(paths, ["/vol1/music", "/vol2/music"], "cancel must preserve configured roots");
    assert.equal(dialog.open, true, "cancelling must restore settings");
    assert.equal(button.disabled, false);
  }
  for (const failure of [{code: 5, msg: "授权被拒绝"}, new Error("选择窗口不可用")]) {
    selection = failure;
    assert.equal(await context.chooseLibraryPath(), false);
    assert.match(status.textContent, /授权被拒绝|选择窗口不可用/);
    assert.equal(paths.length, 2);
    assert.equal(dialog.open, true, "errors must restore settings");
    assert.equal(button.disabled, false);
  }
  const before = calls;
  sdk.isStandaloneWeb = true;
  assert.equal(await context.chooseLibraryPath(), false);
  assert.equal(calls, before, "unsupported standalone browser must not call the host-only picker");
  assert.match(status.textContent, /飞牛桌面或飞牛 App/);
  console.log("Official directory picker success, cancellation, errors and host boundary passed.");
})().catch(error => {console.error(error); process.exitCode = 1;});
