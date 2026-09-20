// D9 的判别测试：曲库连接池开关必须真的接在设置页「运行」pane 上，读写都只带
// 它自己那一个键，并且任何一步都不能把失败说成成功。方向各断一面：控件放错
// pane、保存走成音乐库分支、请求体多带键、服务端回落布尔后仍回显旧值、失败
// 时静默关闭对话框，这五类都会红。
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const UI_DIR = "app/ui";
const app = fs.readFileSync(path.join(UI_DIR, "app.js"), "utf8");
const index = fs.readFileSync(path.join(UI_DIR, "index.html"), "utf8");
const serverPy = fs.readFileSync(path.join("app", "server", "server.py"), "utf8");
const libraryPy = fs.readFileSync(path.join("app", "server", "library.py"), "utf8");

function functionSource(name) {
  const match = app.match(new RegExp("^(?:async )?function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable`);
  return match[0];
}

// 1) 控件必须存在，而且必须落在「运行」pane 里，不是元数据 pane 的搭车项。
const paneMatch = index.match(/<section class="settings-pane"[^>]*data-settings-pane="runtime"[^>]*>([\s\S]*?)<\/section>/);
assert.ok(paneMatch, "the runtime settings pane must exist");
assert.match(paneMatch[1], /<input id="libraryConnectionPoolInput" type="checkbox">/, "the pool toggle belongs to the runtime pane");
assert.match(paneMatch[1], /<label class="metadata-toggle">/, "the toggle must reuse the established settings-toggle shape");
assert.doesNotMatch(index.match(/data-settings-pane="metadata"[^>]*>([\s\S]*?)<\/section>/)[1], /libraryConnectionPoolInput/, "the metadata pane must not claim the pool switch");
// 端口那两句话不能被挤掉：它仍是「改端口要重启」的唯一说明。
assert.match(paneMatch[1], /修改端口后，请停止并重新启动 fnAudio/, "the port restart notice must survive in the same pane");
assert.match(paneMatch[1], /这个开关即时生效，不需要重启/, "the toggle has to say it takes effect without a restart");

// 2) 常量口径必须与服务端配置键逐字相同，两侧任一改名都会在这里断掉。
const constLine = app.match(/^const LIBRARY_CONNECTION_POOL_SETTING_KEY = "([^"]+)";$/m);
assert.ok(constLine, "the setting key must be a single top-level constant");
assert.equal(constLine[1], "library_connection_pool");
assert.ok(libraryPy.includes("LIBRARY_CONNECTION_POOL_CONFIG_KEY = \"library_connection_pool\""), "the reader path must key off the same name");
assert.ok(/_library_connection_pool_enabled as library_connection_pool_enabled/.test(serverPy), "the handler must reuse the reader predicate, not invent a default");

// 3) 接线：切到运行 pane 要读回；保存必须先进运行分支，不能被音乐库兜底分支吃掉。
assert.match(functionSource("setSettingsTab"), /if \(name === "runtime"\) loadRuntimeSettings\(\);/, "opening the runtime pane must read the setting back");
const chooser = functionSource("chooseCurrentFolder");
const runtimeAt = chooser.indexOf('state.settingsTab === "runtime"');
const libraryAt = chooser.indexOf("saveLibraryPathsFromDialog()");
assert.ok(runtimeAt >= 0, "the save path must know the runtime pane");
assert.ok(libraryAt > runtimeAt, "the runtime pane must be routed before the library fallback branch");

// 4) 路由字符串两端对齐：UI 拼的是相对路径，服务端注册 GET 与 POST 两条。
assert.equal((app.match(/"api\/config\/runtime"/g) || []).length, 2, "exactly one read call and one write call");
assert.ok(/path == "\/api\/config\/runtime"/.test(serverPy), "the server must answer GET on the runtime config route");
assert.ok(/parsed\.path == "\/api\/config\/runtime"/.test(serverPy), "the server must answer POST on the runtime config route");

// 5) 真跑读写函数：假节点 + 假 fetch，判别「回显服务端值」而不是「相信自己的点击」。
const sources = [
  constLine[0],
  functionSource("runtimeConnectionPoolInput"),
  functionSource("loadRuntimeSettings"),
  functionSource("saveRuntimeSettings"),
  "globalThis.loadRuntimeSettings = loadRuntimeSettings; globalThis.saveRuntimeSettings = saveRuntimeSettings;",
].join("\n");

function harness(poolChecked, responses) {
  const nodes = {
    libraryConnectionPoolInput: { checked: poolChecked },
    folderSaveStatus: { textContent: "" },
  };
  const calls = [];
  const context = {
    $: id => nodes[id] || null,
    apiFetch: (url, init = {}) => {
      calls.push({ url, init, body: init.body == null ? null : JSON.parse(init.body) });
      return Promise.resolve(responses.shift());
    },
    readResponseJsonBounded: async response => response.json,
    JSON, Object, Promise, Error, String, Boolean,
  };
  vm.createContext(context);
  vm.runInContext(sources, context);
  return { context, nodes, calls };
}

const okResponse = { ok: true, json: { ok: true, config: { library_connection_pool: false } } };

(async () => {
  // 5a) 读回：服务端说关，界面就不许留「开」，哪怕用户刚才勾上了。
  let h = harness(true, [{ ok: true, json: { ok: true, config: { library_connection_pool: false } } }]);
  let data = await h.context.loadRuntimeSettings();
  assert.deepEqual(h.calls.map(call => [call.url, call.init.method || "GET"]), [["api/config/runtime", "GET"]], "reading must be a single GET");
  assert.equal(h.nodes.libraryConnectionPoolInput.checked, false, "the checkbox must echo the server value");
  assert.equal(h.nodes.folderSaveStatus.textContent, "", "a successful read must not leave an error behind");
  assert.ok(data && data.ok === true);

  // 5b) 读失败：保留上一次已知状态，只报一句话，不许自己编一个默认值。
  h = harness(true, [{ ok: false, json: { ok: false, message: "boom" } }]);
  data = await h.context.loadRuntimeSettings();
  assert.equal(data, null, "a failed read must not report data");
  assert.equal(h.nodes.libraryConnectionPoolInput.checked, true, "a failed read must not invent a value");
  assert.match(h.nodes.folderSaveStatus.textContent, /无法读取运行设置/, "a failed read has to say so");

  // 5c) 保存：请求体只能有这一个键，值必须是真布尔，且回显以服务端为准。
  h = harness(true, [okResponse]);
  data = await h.context.saveRuntimeSettings();
  assert.equal(h.calls.length, 1, "saving must issue exactly one request");
  assert.equal(h.calls[0].url, "api/config/runtime");
  assert.equal(h.calls[0].init.method, "POST");
  assert.deepEqual(Object.keys(h.calls[0].body), ["library_connection_pool"], "the runtime save must not carry other settings");
  assert.equal(h.calls[0].body.library_connection_pool, true);
  assert.equal(typeof h.calls[0].body.library_connection_pool, "boolean", "text booleans must never leave the UI");
  assert.equal(h.nodes.libraryConnectionPoolInput.checked, false, "the checkbox must follow the server echo, not the click");
  assert.equal(data.config.library_connection_pool, false);

  // 5d) 关到开同样只带一个键。
  h = harness(false, [{ ok: true, json: { ok: true, config: { library_connection_pool: true } } }]);
  await h.context.saveRuntimeSettings();
  assert.deepEqual(h.calls[0].body, { library_connection_pool: false }, "the unchecked box must send false rather than omit the key");
  assert.equal(h.nodes.libraryConnectionPoolInput.checked, true);

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

  console.log("Runtime settings regression checks passed.");
})();
