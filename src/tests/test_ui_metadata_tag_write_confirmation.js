const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const app = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "app.js"), "utf8");
const index = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "index.html"), "utf8");

function functionSource(name) {
  const match = app.match(new RegExp("^(?:async )?function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `${name} must be a declared function`);
  return match[0];
}

assert.match(index, /id="metadataTagWriteEnabledInput"/);
assert.match(app, /function metadataTagWriteConfirmation\(/, "Tag write activation needs a single confirmation policy");
assert.match(functionSource("loadMetadataStatus"), /tagWriteInput\.dataset\.savedEnabled = String\(tagWriteInput\.checked\)/, "server state must be the confirmation baseline");
assert.match(functionSource("saveMetadataTagSettings"), /body: JSON\.stringify\(\{ tag_write_enabled: tagWriteInput\.checked === true \}\)/, "Tag save must send only the Tag write setting");
assert.match(functionSource("saveMetadataTagSettings"), /if \(!metadataTagWriteConfirmation\(tagWriteInput, confirm\)\) throw new Error\("已取消启用 Tag 写回"\)/, "the Tag save path must confirm before POST");
assert.match(functionSource("saveMetadataTagSettings"), /tagWriteInput\.dataset\.savedEnabled = String\(data\.tag_write_enabled === true\)/, "the Tag baseline must advance only after a successful save");
assert.doesNotMatch(functionSource("saveMetadataTagSettings"), /metadataProviderPayload|metadataGraceDaysInput|metadataEnabledInput/, "Tag save must not carry overview or provider fields");
assert.match(functionSource("saveMetadataOverviewSettings"), /body: JSON\.stringify\(\{ enabled: enabledInput\.checked === true, orphan_grace_days: graceDays \}\)/, "overview save must send only overview fields");
assert.doesNotMatch(functionSource("saveMetadataOverviewSettings"), /metadataTagWriteConfirmation|metadataTagWriteEnabledInput/, "overview save must not trigger Tag confirmation");

const sandbox = { confirm: () => true };
vm.runInNewContext(functionSource("metadataTagWriteConfirmation"), sandbox);
assert.equal(sandbox.metadataTagWriteConfirmation({ checked: false, dataset: {} }, () => { throw new Error("must not prompt while disabled"); }), true);
assert.equal(sandbox.metadataTagWriteConfirmation({ checked: true, dataset: { savedEnabled: "true" } }, () => { throw new Error("must not prompt for an already-enabled setting"); }), true);
assert.equal(sandbox.metadataTagWriteConfirmation({ checked: true, dataset: { savedEnabled: "false" } }, () => false), false, "declining activation must block the request");
let prompt = "";
assert.equal(sandbox.metadataTagWriteConfirmation({ checked: true, dataset: { savedEnabled: "false" } }, message => { prompt = message; return true; }), true);
assert.match(prompt, /原始歌曲文件/, "the confirmation must state that source files can be modified");

console.log("Metadata Tag write confirmation regression checks passed.");

function saveHarness(response = { ok: true, enabled: false, orphan_grace_days: 0, tag_write_enabled: false }) {
  const nodes = {
    metadataEnabledInput: { checked: true },
    metadataGraceDaysInput: { value: "0" },
    metadataTagWriteEnabledInput: { checked: false, dataset: { savedEnabled: "false" } },
    metadataStatusText: { textContent: "" },
  };
  const draft = [{ id: "kuwo", enabled: true }, { id: "netease", enabled: false }];
  const state = { metadataProviders: draft, metadataProviderDirty: true, metadataProviderRecommended: [] };
  const requests = [];
  const overviewSnapshots = [];
  const context = {
    state, $: id => nodes[id], confirm: () => true,
    apiFetch: async (url, init) => { requests.push({ url, body: JSON.parse(init.body) }); return { ok: response.ok }; },
    readResponseJsonBounded: async () => ({ ...response, providers: [{ id: "netease", enabled: true }] }),
    unwrapMetadataResponsePayload: value => value,
    normalizeMetadataProviderEntries: value => value || [],
    renderMetadataProviders() {}, updateMetadataProviderDirtyStatus() {},
    metadataStatusSummary: () => "后台状态", renderMetadataTagJobs() {},
    updateMetadataSettingsOverview: () => overviewSnapshots.push({ enabled: nodes.metadataEnabledInput.checked, tag: nodes.metadataTagWriteEnabledInput.checked }),
  };
  vm.runInNewContext([
    functionSource("applyMetadataProviderSettings"),
    functionSource("metadataTagWriteConfirmation"),
    functionSource("saveMetadataOverviewSettings"),
    functionSource("saveMetadataTagSettings"),
  ].join("\n"), context);
  return { context, state, draft, nodes, requests, overviewSnapshots };
}

(async () => {
  for (const name of ["saveMetadataOverviewSettings", "saveMetadataTagSettings"]) {
    const h = saveHarness();
    await h.context[name]();
    assert.equal(h.state.metadataProviders, h.draft, `${name} must retain the other page's provider draft`);
    assert.equal(h.state.metadataProviderDirty, true, `${name} must not disable the other page's save action`);
    assert.equal(h.overviewSnapshots.length, 1, "refresh the summary after applying the owning page's server echo");
    assert.equal(h.requests.length, 1);
    assert.equal(h.requests[0].url, "api/config/metadata");
    if (name === "saveMetadataOverviewSettings") {
      assert.deepEqual(h.requests[0].body, { enabled: true, orphan_grace_days: 0 });
      assert.equal(h.overviewSnapshots[0].enabled, false, "summary must observe the new server echo");
      assert.equal(h.nodes.metadataTagWriteEnabledInput.dataset.savedEnabled, "false");
    } else {
      assert.deepEqual(h.requests[0].body, { tag_write_enabled: false });
      assert.equal(h.nodes.metadataEnabledInput.checked, true, "Tag save must preserve overview draft");
      assert.equal(h.nodes.metadataGraceDaysInput.value, "0");
    }
    const failed = saveHarness({ ok: false, message: "保存失败" });
    await assert.rejects(() => failed.context[name](), /保存失败/);
    assert.equal(failed.state.metadataProviders, failed.draft);
    assert.equal(failed.state.metadataProviderDirty, true);
    assert.equal(failed.overviewSnapshots.length, 0);
  }
  const cancelled = saveHarness();
  cancelled.nodes.metadataTagWriteEnabledInput.checked = true;
  cancelled.context.confirm = () => false;
  await assert.rejects(() => cancelled.context.saveMetadataTagSettings(), /已取消启用/);
  assert.equal(cancelled.requests.length, 0, "cancelling Tag activation must send no POST");
  assert.equal(cancelled.state.metadataProviders, cancelled.draft);
  console.log("Metadata scoped saves preserve provider drafts, server echoes and cancellation checks passed.");
})().catch(error => { console.error(error); process.exitCode = 1; });
