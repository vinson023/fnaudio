const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const app = fs.readFileSync("app/ui/app.js", "utf8");
const match = app.match(/^async function saveSettingsPane\([\s\S]*?^}/m);
assert.ok(match, "saveSettingsPane must remain extractable");

const context = { Promise, Error, String };
vm.createContext(context);
vm.runInContext(`${match[0]}\nglobalThis.saveSettingsPane = saveSettingsPane;`, context);

function button() {
  return { disabled: false, textContent: "保存" };
}

(async () => {
  const okButton = button();
  const okStatus = { textContent: "旧提示" };
  let closeCalls = 0;
  const ok = await context.saveSettingsPane(okButton, okStatus, async () => true, "已保存");
  assert.equal(ok, true);
  assert.equal(okStatus.textContent, "已保存");
  assert.equal(closeCalls, 0, "a page save must not close the settings dialog");
  assert.equal(okButton.disabled, false);
  assert.equal(okButton.textContent, "保存");

  const failedButton = button();
  const failedStatus = { textContent: "旧提示" };
  const failed = await context.saveSettingsPane(failedButton, failedStatus, async () => {
    throw new Error("当前页保存失败");
  });
  assert.equal(failed, false);
  assert.equal(failedStatus.textContent, "当前页保存失败");
  assert.equal(failedButton.disabled, false);
  assert.equal(failedButton.textContent, "保存");

  const source = name => app.match(new RegExp("^function " + name + "\\([\\s\\S]*?^}", "m"))[0];
  const nodes = {
    saveMetadataSettingsBtn: { disabled: false, textContent: "保存概览设置" },
    saveMetadataTagSettingsBtn: { disabled: false, textContent: "保存 Tag 写回设置" },
    metadataOverviewSettingsStatus: { textContent: "" },
    metadataTagSettingsStatus: { textContent: "Tag 页原提示" },
  };
  const scoped = { $: id => nodes[id], saveSettingsPane: context.saveSettingsPane };
  let resolveOverview;
  scoped.saveMetadataOverviewSettings = () => new Promise(resolve => { resolveOverview = resolve; });
  scoped.saveMetadataTagSettings = async () => true;
  vm.runInNewContext(source("saveMetadataOverviewPaneSettings") + "\n" + source("saveMetadataTagPaneSettings"), scoped);
  const pendingOverview = scoped.saveMetadataOverviewPaneSettings();
  assert.equal(nodes.saveMetadataSettingsBtn.disabled, true);
  assert.equal(nodes.saveMetadataTagSettingsBtn.disabled, false, "a pending overview save must not disable Tag actions");
  await scoped.saveMetadataTagPaneSettings();
  assert.equal(nodes.metadataTagSettingsStatus.textContent, "Tag 写回设置已保存。");
  assert.equal(nodes.metadataOverviewSettingsStatus.textContent, "");
  resolveOverview(true);
  await pendingOverview;
  assert.equal(nodes.metadataOverviewSettingsStatus.textContent, "概览设置已保存。");
  assert.equal(nodes.metadataTagSettingsStatus.textContent, "Tag 写回设置已保存。", "late overview completion must not overwrite Tag status");
  assert.equal(nodes.saveMetadataTagSettingsBtn.textContent, "保存 Tag 写回设置");
  assert.equal(nodes.saveMetadataSettingsBtn.textContent, "保存概览设置");
  let rejectTag;
  scoped.saveMetadataTagSettings = () => new Promise((_resolve, reject) => { rejectTag = reject; });
  scoped.saveMetadataOverviewSettings = async () => true;
  const pendingTag = scoped.saveMetadataTagPaneSettings();
  assert.equal(nodes.saveMetadataTagSettingsBtn.disabled, true);
  assert.equal(nodes.saveMetadataSettingsBtn.disabled, false);
  await scoped.saveMetadataOverviewPaneSettings();
  rejectTag(new Error("Tag 保存网络失败"));
  assert.equal(await pendingTag, false);
  assert.equal(nodes.metadataTagSettingsStatus.textContent, "Tag 保存网络失败");
  assert.equal(nodes.metadataOverviewSettingsStatus.textContent, "概览设置已保存。", "late Tag failure must not overwrite overview success");
  assert.equal(nodes.saveMetadataSettingsBtn.disabled, false);
  assert.equal(nodes.saveMetadataTagSettingsBtn.disabled, false);
  console.log("Settings save scope and overlapping metadata save isolation checks passed.");
})();
