// D9 的判别测试：曲库连接池开关必须真的接在设置页「高级与诊断」pane 上，读写都只带
// 它自己那一个键，并且任何一步都不能把失败说成成功。方向各断一面：控件放错
// pane、保存走成音乐库分支、请求体多带键、服务端回落布尔后仍回显旧值、失败
// 时静默关闭对话框，这五类都会红。
// R139（裁定 Q6=A）在同一 pane 上加入歌词缓存预算：本文件同时判别预算控件的
// pane 归属、键名与服务端常量一致、回显非预设值时不静默丢弃、以及保存请求体恰
// 带两键且互不覆写。
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const UI_DIR = "app/ui";
const app = fs.readFileSync(path.join(UI_DIR, "app.js"), "utf8");
const index = fs.readFileSync(path.join(UI_DIR, "index.html"), "utf8");
const serverPy = fs.readFileSync(path.join("app", "server", "server.py"), "utf8");
const libraryPy = fs.readFileSync(path.join("app", "server", "library.py"), "utf8");
const cachePy = fs.readFileSync(path.join("app", "server", "metadata_local_lyrics_cache.py"), "utf8");
const configPy = fs.readFileSync(path.join("app", "server", "config.py"), "utf8");
const dlnaServicePy = fs.readFileSync(path.join("app", "server", "dlna", "service.py"), "utf8");

function functionSource(name) {
  const match = app.match(new RegExp("^(?:async )?function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable`);
  return match[0];
}

// 1) 高级性能控件留在高级 pane；Renderer 显示名归「播放与设备」pane。
const paneMatch = index.match(/<section\b[^>]*class="settings-pane"[^>]*data-settings-pane="runtime"[^>]*>([\s\S]*?)<\/section>/);
assert.ok(paneMatch, "the runtime settings pane must exist");
assert.match(paneMatch[1], /<input id="libraryConnectionPoolInput" type="checkbox">/, "the pool toggle belongs to the runtime pane");
assert.match(paneMatch[1], /<label class="metadata-toggle">/, "the toggle must reuse the established settings-toggle shape");
assert.doesNotMatch(index.match(/data-settings-pane="metadata"[^>]*>([\s\S]*?)<\/section>/)[1], /libraryConnectionPoolInput/, "the metadata pane must not claim the pool switch");
assert.match(paneMatch[1], /<select id="lyricsCacheBudgetInput">/, "the budget select belongs to the runtime pane");
const dlnaPaneMatch = index.match(/<section\b[^>]*class="settings-pane"[^>]*data-settings-pane="dlna"[^>]*>([\s\S]*?)<\/section>/);
assert.ok(dlnaPaneMatch, "the DLNA settings pane must exist");
const playbackPaneMatch = index.match(/<section\b[^>]*class="settings-pane"[^>]*data-settings-pane="playback"[^>]*>([\s\S]*?)<\/section>/);
assert.ok(playbackPaneMatch, "the playback and devices settings pane must exist");
assert.match(playbackPaneMatch[1], /<input id="rendererNameInput" type="text" maxlength="128"/, "the renderer name editor belongs to playback and devices and is bounded");
assert.doesNotMatch(dlnaPaneMatch[1], /rendererNameInput/, "DLNA diagnostics must not own the general renderer identity field");
assert.match(paneMatch[1], /<option value="8388608" selected>/, "the select must offer the shipped default");
const budgetSelectMarkup = paneMatch[1].match(/<select id="lyricsCacheBudgetInput">([\s\S]*?)<\/select>/);
assert.ok(budgetSelectMarkup, "the budget control must be a select, not a free-text box");
const PRESET_BUDGETS = [...budgetSelectMarkup[1].matchAll(/<option value="(\d+)"/g)].map(found => found[1]);
assert.equal(PRESET_BUDGETS.length, 6, "the select must offer exactly six budgets");
assert.ok(PRESET_BUDGETS.includes("65536"), "the select must offer the floor the cache enforces");
assert.ok(PRESET_BUDGETS.includes("67108864"), "the select must offer the ceiling the cache enforces");
assert.doesNotMatch(index.match(/data-settings-pane="metadata"[^>]*>([\s\S]*?)<\/section>/)[1], /lyricsCacheBudgetInput/, "the metadata pane must not claim the budget");
// 端口那两句话不能被挤掉：它仍是「改端口要重启」的唯一说明。
assert.match(paneMatch[1], /修改端口后，请停止并重新启动 fnAudio/, "the port restart notice must survive in the same pane");
assert.match(paneMatch[1], /修改后点击“保存高级设置”生效/, "advanced settings must explain their page-local save action");
assert.doesNotMatch(paneMatch[1], /这个开关即时生效/, "advanced controls must not claim immediate effect when they use a save button");

// 2) 常量口径必须与服务端配置键逐字相同，两侧任一改名都会在这里断掉。
const constLine = app.match(/^const LIBRARY_CONNECTION_POOL_SETTING_KEY = "([^"]+)";$/m);
assert.ok(constLine, "the setting key must be a single top-level constant");
assert.equal(constLine[1], "library_connection_pool");
assert.ok(libraryPy.includes("LIBRARY_CONNECTION_POOL_CONFIG_KEY = \"library_connection_pool\""), "the reader path must key off the same name");
assert.ok(/_library_connection_pool_enabled as library_connection_pool_enabled/.test(serverPy), "the handler must reuse the reader predicate, not invent a default");
const budgetConst = app.match(/^const LYRICS_CACHE_BUDGET_SETTING_KEY = "([^"]+)";$/m);
assert.ok(budgetConst, "the lyric cache budget key must be a single top-level constant");
const pyBudgetKey = cachePy.match(/^CONFIG_BYTES_KEY = "([^"]+)"$/m);
assert.ok(pyBudgetKey, "the cache module must keep naming the key");
assert.equal(budgetConst[1], pyBudgetKey[1], "the UI must address the same key the cache reads");
assert.equal(budgetConst[1], "metadata_lyrics_cache_max_bytes");
const rendererNameKey = app.match(/^const RENDERER_NAME_SETTING_KEY = "([^\"]+)";$/m);
assert.ok(rendererNameKey, "the renderer name setting key must be a single top-level constant");
assert.equal(rendererNameKey[1], "renderer_name");
assert.match(configPy, /DEFAULT_RENDERER_NAME = "fnAudio Renderer"/, "configuration must preserve the renderer default");
assert.match(dlnaServicePy, /friendly = html\.escape\(self\.renderer_name if is_renderer else "fnAudio Music Library"\)/, "only the renderer friendly name is configurable and XML-escaped");

// 3) 接线：切到运行 pane 要读回；运行页必须拥有自己的保存按钮，不再依赖全局保存。
assert.match(functionSource("setSettingsTab"), /if \(name === "runtime"\) loadRuntimeSettings\(\);/, "opening the runtime pane must read the setting back");
assert.match(app, /function ensureSettingsStatusNodes\(\)/, "settings panes must create page-local live statuses");
assert.match(functionSource("ensureSettingsStatusNodes"), /librarySettingsStatus[\s\S]*runtimeSettingsStatus[\s\S]*metadataOverviewSettingsStatus[\s\S]*metadataTagSettingsStatus/, "each save pane must own a status node");
assert.match(functionSource("openFolderBrowser"), /ensureSettingsStatusNodes\(\)/, "opening settings must materialize local status nodes");
assert.match(functionSource("ensureSettingsStatusNodes"), /playbackSettingsStatus/, "the playback pane needs a local read and save status");
assert.doesNotMatch(app, /folderSaveStatus/, "settings saves must not depend on the old global status node");
assert.match(app, /function saveSettingsPane\(button, statusNode, saveAction/, "page saves must receive their own status node");
assert.doesNotMatch(functionSource("saveSettingsPane"), /folderDialog"\)\.close\(\)/, "saving a pane must not close the whole settings dialog");
assert.match(functionSource("setSettingsTab"), /if \(name === "playback"\) loadPlaybackSettings\(\);/, "opening the playback and devices pane must read the renderer name back");
assert.match(app, /function settingsTabIndexForKey\(/, "top-level tabs must support keyboard navigation");
assert.match(functionSource("bindSettingsTabs"), /onkeydown/, "top-level tabs must bind keyboard navigation");
assert.match(functionSource("bindSettingsTabs"), /setSettingsTab\(state\.settingsTab \|\| "library"\)/, "top-level tab semantics must be initialized when bindings are installed");
assert.match(index, /data-settings-tab="playback"[^>]*>播放与设备/, "the top-level settings taxonomy must expose playback and devices");
assert.match(index, /id="savePlaybackSettingsBtn"[^>]*>保存播放与设备设置/, "playback and devices must have its own save control");
const tabNavigation = {};
vm.createContext(tabNavigation);
vm.runInContext(`${functionSource("settingsTabIndexForKey")}\nglobalThis.settingsTabIndexForKey = settingsTabIndexForKey;`, tabNavigation);
assert.equal(tabNavigation.settingsTabIndexForKey("ArrowRight", 0, 5), 1);
assert.equal(tabNavigation.settingsTabIndexForKey("ArrowLeft", 0, 5), 4, "left navigation must wrap to the final tab");
assert.equal(tabNavigation.settingsTabIndexForKey("ArrowDown", 4, 5), 0, "down navigation must wrap to the first tab");
assert.equal(tabNavigation.settingsTabIndexForKey("Home", 3, 5), 0);
assert.equal(tabNavigation.settingsTabIndexForKey("End", 0, 5), 4);
assert.equal(tabNavigation.settingsTabIndexForKey("Enter", 0, 5), -1, "activation keys must not be mistaken for tab movement");
assert.equal(tabNavigation.settingsTabIndexForKey("ArrowRight", 0, 0), -1, "empty tab sets must be ignored");
assert.match(index, /id="saveRuntimeSettingsBtn"[^>]*>保存高级设置/, "the advanced pane must have its own save button");
assert.match(app, /function saveRuntimePaneSettings\(\) \{[\s\S]*saveRuntimeSettings\(\)/, "the runtime save button must call the runtime save path");
assert.doesNotMatch(index, /id="chooseFolderBtn"/, "the settings dialog must not expose a global save button");
assert.match(index, /role="tablist"[^>]*aria-label="设置分类"/, "the settings tablist must be labelled");
assert.match(index, /role="tabpanel"[^>]*aria-labelledby="settings-tab-runtime"/, "the runtime pane must expose tabpanel semantics");
assert.match(index, /id="playbackSettingsStatus"[^>]*aria-live="polite"/, "playback settings reads need a page-local live status");

// 4) 路由字符串两端对齐：UI 拼的是相对路径，服务端注册 GET 与 POST 两条。
assert.equal((app.match(/"api\/config\/runtime"/g) || []).length, 4, "the advanced and playback panes share exactly two read/write pairs");
assert.ok(/path == "\/api\/config\/runtime"/.test(serverPy), "the server must answer GET on the runtime config route");
assert.ok(/parsed\.path == "\/api\/config\/runtime"/.test(serverPy), "the server must answer POST on the runtime config route");

// 5) 真跑读写函数：假节点 + 假 fetch，判别「回显服务端值」而不是「相信自己的点击」。
const budgetConstLine = budgetConst[0];
const sources = [
  constLine[0],
  budgetConstLine,
  rendererNameKey[0],
  functionSource("runtimeConnectionPoolInput"),
  functionSource("runtimeLyricsBudgetInput"),
  functionSource("playbackRendererNameInput"),
  functionSource("applyRuntimeLyricsBudget"),
  functionSource("formatSize"),
  functionSource("loadRuntimeSettings"),
  functionSource("saveRuntimeSettings"),
  functionSource("loadPlaybackSettings"),
  functionSource("savePlaybackSettings"),
  "globalThis.loadRuntimeSettings = loadRuntimeSettings; globalThis.saveRuntimeSettings = saveRuntimeSettings; globalThis.loadPlaybackSettings = loadPlaybackSettings; globalThis.savePlaybackSettings = savePlaybackSettings;",
].join("\n");

function selectNode(presetValues, initial = "") {
  // Real <select> semantics: assigning a value with no matching option leaves
  // the control empty, so an implementation that "trusts" its own write cannot
  // pass here, and neither can one that silently drops an out-of-preset budget.
  const writes = [];
  return {
    _value: initial,
    options: presetValues.map(value => ({ value })),
    writes,
    appended: [],
    appendChild(option) { this.options.push(option); this.appended.push(option); },
    set value(next) {
      writes.push(next);
      this._value = this.options.some(option => option.value === String(next)) ? String(next) : "";
    },
    get value() { return this._value; },
  };
}

function harness(poolChecked, responses, budgetValue = "8388608") {
  const budget = selectNode(PRESET_BUDGETS, budgetValue);
  const nodes = {
    libraryConnectionPoolInput: { checked: poolChecked },
    lyricsCacheBudgetInput: budget,
    rendererNameInput: { value: "客厅 fnAudio" },
    runtimeSettingsStatus: { textContent: "" },
    playbackSettingsStatus: { textContent: "" },
  };
  const calls = [];
  const context = {
    $: id => nodes[id] || null,
    apiFetch: (url, init = {}) => {
      calls.push({ url, init, body: init.body == null ? null : JSON.parse(init.body) });
      return Promise.resolve(responses.shift());
    },
    readResponseJsonBounded: async response => response.json,
    document: { createElement: tag => ({ tag, value: "", textContent: "" }) },
    JSON, Object, Promise, Error, String, Number, Boolean,
  };
  vm.createContext(context);
  vm.runInContext(sources, context);
  return { context, nodes, calls, budget };
}

const okResponse = { ok: true, json: { ok: true, config: { library_connection_pool: false, renderer_name: "书房播放器" } } };

(async () => {
  // 5a) 读回：服务端说关，界面就不许留「开」，哪怕用户刚才勾上了。
  let h = harness(true, [{ ok: true, json: { ok: true, config: { library_connection_pool: false, renderer_name: "厨房播放器" } } }]);
  let data = await h.context.loadRuntimeSettings();
  assert.deepEqual(h.calls.map(call => [call.url, call.init.method || "GET"]), [["api/config/runtime", "GET"]], "reading must be a single GET");
  assert.equal(h.nodes.libraryConnectionPoolInput.checked, false, "the checkbox must echo the server value");
  assert.equal(h.nodes.rendererNameInput.value, "客厅 fnAudio", "the advanced read must not mutate the playback identity field");
  assert.equal(h.nodes.runtimeSettingsStatus.textContent, "", "a successful read must not leave an error behind");
  assert.ok(data && data.ok === true);

  // 5b) 读失败：保留上一次已知状态，只报一句话，不许自己编一个默认值。
  h = harness(true, [{ ok: false, json: { ok: false, message: "boom" } }]);
  data = await h.context.loadRuntimeSettings();
  assert.equal(data, null, "a failed read must not report data");
  assert.equal(h.nodes.libraryConnectionPoolInput.checked, true, "a failed read must not invent a value");
  assert.match(h.nodes.runtimeSettingsStatus.textContent, /无法读取运行设置/, "a failed read has to say so");

  // 5c) 保存：请求体只能有这一个键，值必须是真布尔，且回显以服务端为准。
  h = harness(true, [okResponse]);
  data = await h.context.saveRuntimeSettings();
  assert.equal(h.calls.length, 1, "saving must issue exactly one request");
  assert.equal(h.calls[0].url, "api/config/runtime");
  assert.equal(h.calls[0].init.method, "POST");
  assert.deepEqual(Object.keys(h.calls[0].body), ["library_connection_pool", budgetConst[1]], "the advanced save must carry exactly the two live settings");
  assert.equal(h.calls[0].body.library_connection_pool, true);
  assert.equal(typeof h.calls[0].body.library_connection_pool, "boolean", "text booleans must never leave the UI");
  assert.equal(h.nodes.libraryConnectionPoolInput.checked, false, "the checkbox must follow the server echo, not the click");
  assert.equal(data.config.library_connection_pool, false);

  // 5d) 关到开同样只带一个键。
  h = harness(false, [{ ok: true, json: { ok: true, config: { library_connection_pool: true } } }]);
  await h.context.saveRuntimeSettings();
  assert.deepEqual(h.calls[0].body, { library_connection_pool: false, [budgetConst[1]]: 8388608 }, "the unchecked box must send false rather than omit a setting");
  assert.equal(h.nodes.libraryConnectionPoolInput.checked, true);

  // 5e) Renderer identity is saved independently from the advanced controls.
  h = harness(true, [{ ok: true, json: { ok: true, config: { renderer_name: "书房播放器" } } }]);
    await h.context.savePlaybackSettings();
  assert.deepEqual(h.calls[0].body, { [rendererNameKey[1]]: "客厅 fnAudio" }, "the playback save must carry only the renderer identity");
  assert.equal(h.nodes.rendererNameInput.value, "书房播放器");

  // Playback read feedback is scoped to its pane and a successful retry clears only that stale warning.
  h = harness(true, [{ ok: true, json: { ok: true, config: { renderer_name: "书房播放器" } } }]);
  h.nodes.runtimeSettingsStatus.textContent = "音乐库设置已保存。";
  h.nodes.playbackSettingsStatus.textContent = "无法读取播放与设备设置，当前显示的是上一次已知状态";
  await h.context.loadPlaybackSettings();
  assert.equal(h.nodes.playbackSettingsStatus.textContent, "", "a successful playback read must clear its previous warning");
  assert.equal(h.nodes.runtimeSettingsStatus.textContent, "音乐库设置已保存。", "a playback read must not erase another pane's save feedback");
  h = harness(true, [{ ok: false, json: { ok: false, message: "boom" } }]);
  h.nodes.runtimeSettingsStatus.textContent = "音乐库设置已保存。";
  await h.context.loadPlaybackSettings();
  assert.match(h.nodes.playbackSettingsStatus.textContent, /无法读取播放与设备设置/, "a failed playback read must report in its own pane");
  assert.equal(h.nodes.runtimeSettingsStatus.textContent, "音乐库设置已保存。", "a playback read error must not overwrite another pane's status");

  // 5e) 保存失败必须抛出：调用方靠这个异常决定不关对话框，静默返回就是谎报成功。
  h = harness(true, [{ ok: true, json: { ok: false, message: "保存运行设置失败" } }]);
  await assert.rejects(() => h.context.saveRuntimeSettings(), /保存运行设置失败/, "a rejected save must throw with the server message");
  h = harness(true, [{ ok: false, json: {} }]);
  await assert.rejects(() => h.context.saveRuntimeSettings(), /保存运行设置失败/, "an HTTP error with no message must still throw");

  // 5f) 控件不见了就是不可用，不许当作「用户没改动」。
  const missing = {
    $: () => null,
    apiFetch: () => { throw new Error("must not reach the network"); },
    readResponseJsonBounded: async () => ({}),
    JSON, Object, Promise, Error, String, Boolean,
  };
  vm.createContext(missing);
  vm.runInContext(sources, missing);
  assert.equal(await missing.loadRuntimeSettings(), null, "a missing control must make the read a no-op");
  await assert.rejects(() => missing.saveRuntimeSettings(), /运行设置控件不可用/);

  // 5g) 预算回显：命中预设值时只赋值，不许凭空增删 option，也不许顺手改开关。
  h = harness(true, [{ ok: true, json: { ok: true, config: { library_connection_pool: true, [budgetConst[1]]: 262144 } } }]);
  await h.context.loadRuntimeSettings();
  assert.equal(h.budget.value, "262144", "the select must echo the running budget");
  assert.equal(h.budget.appended.length, 0, "a preset budget must not add options");
  assert.equal(h.nodes.libraryConnectionPoolInput.checked, true, "reading the budget must not clobber the pool echo");

  // 5h) 服务端跑的是非预设预算：追加恰一项自定义，不许静默落回预设值。
  h = harness(true, [{ ok: true, json: { ok: true, config: { [budgetConst[1]]: 4194304 } } }]);
  await h.context.loadRuntimeSettings();
  assert.equal(h.budget.appended.length, 1, "an off-preset budget must add exactly one option");
  assert.equal(h.budget.value, "4194304", "the custom budget must be the selected value");
  assert.match(h.budget.appended[0].textContent, /^自定义 · /, "the custom option has to name itself");
  assert.equal(h.budget.options.length, PRESET_BUDGETS.length + 1);

  // 5i) 服务端没给出可用预算：一次写入都不许发生，更不许编一个默认值。
  for (const unusable of [undefined, 0, -1, "8 MiB", 4.5, null]) {
    h = harness(true, [{ ok: true, json: { ok: true, config: { library_connection_pool: true, [budgetConst[1]]: unusable } } }]);
    h.budget.writes.length = 0;
    await h.context.loadRuntimeSettings();
    assert.equal(h.budget.writes.length, 0, `an unusable budget ${unusable} must not touch the control`);
    assert.equal(h.nodes.libraryConnectionPoolInput.checked, true, "an unusable budget must not disturb the switch");
  }

  // 5j) 保存：预算以 JSON 整数出门，回来后仍以服务端回显为准，哪怕它既不是
  // 预设值也不是刚发出去的那个数字。
  h = harness(true, [{ ok: true, json: { ok: true, config: { library_connection_pool: true, [budgetConst[1]]: 4194304 } } }], "262144");
  await h.context.saveRuntimeSettings();
  assert.equal(h.calls.length, 1);
  assert.equal(h.calls[0].init.method, "POST");
  assert.equal(typeof h.calls[0].body[budgetConst[1]], "number", "the budget must leave the UI as a number, not a string");
  assert.equal(h.calls[0].body[budgetConst[1]], 262144, "the UI must send what the select showed");
  assert.equal(h.budget.value, "4194304", "the select must follow the server echo, not the click");
  assert.equal(h.budget.appended.length, 1, "an echoed off-preset budget has to stay selectable");

  // 5k) 预算控件解析不出值：抛出，且一个请求都不发。
  h = harness(true, [okResponse]);
  h.budget.writes.length = 0;
  h.budget.value = "";
  await assert.rejects(() => h.context.saveRuntimeSettings(), /运行设置控件不可用/, "an unparseable budget is not 'no change'");
  assert.equal(h.calls.length, 0, "an unparseable budget must not reach the network");

  h = harness(true, [okResponse]);
  h.nodes.rendererNameInput.value = "   ";
  await assert.rejects(() => h.context.savePlaybackSettings(), /播放与设备设置控件不可用/, "a blank renderer name must not be saved");
  assert.equal(h.calls.length, 0, "an invalid renderer name must be rejected before the request");

  h = harness(true, [okResponse]);
  h.nodes.rendererNameInput.value = "客厅\u0085播放器";
  await assert.rejects(() => h.context.savePlaybackSettings(), /播放与设备设置控件不可用/, "a C1 control character must be rejected before the request");
  assert.equal(h.calls.length, 0, "a renderer name with control characters must not reach the server");

  console.log("Runtime settings regression checks passed.");
})();
