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
    saveMetadataSettingsBtn: { disabled: false, textContent: "保存" },
    saveMetadataTagSettingsBtn: { disabled: false, textContent: "保存" },
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
  assert.equal(nodes.saveMetadataTagSettingsBtn.textContent, "保存");
  assert.equal(nodes.saveMetadataSettingsBtn.textContent, "保存");
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

// Every settings block that owns a control has to be reachable from the footer.
//
// `markSettingsDirty` silently drops a block that belongs to no group, so a
// control in an unmapped block can be changed but never saved - the footer with
// the save button simply never appears. That is how R630 shipped the software
// volume switch (reported 2026-11-26 as "勾选后没有保存按钮"). Blocks that apply
// on click are listed here instead of being mapped, because they must not queue
// a save at all.
(() => {
  const html = fs.readFileSync("app/ui/index.html", "utf8");
  const groupsLiteral = app.match(/const SETTINGS_GROUPS = \[([\s\S]*?)\n\];/);
  assert.ok(groupsLiteral, "SETTINGS_GROUPS must stay a literal array");
  const mapped = new Set();
  for (const entry of groupsLiteral[1].matchAll(/blocks:\s*\[(.*?)\]/g)) {
    for (const id of entry[1].matchAll(/"([^"]+)"/g)) mapped.add(id[1]);
  }
  const tabsLiteral = app.match(/const SETTINGS_BLOCK_TABS = \{([\s\S]*?)\n\};/);
  assert.ok(tabsLiteral, "SETTINGS_BLOCK_TABS must stay a literal object");
  const tabbed = new Set(
    [...tabsLiteral[1].matchAll(/(?:^|\n)\s*"?([A-Za-z0-9_-]+)"?\s*:/g)].map(m => m[1])
  );
  const APPLIES_ON_CLICK = new Set([
    "playback-output", "playback-sleep", "appearance-theme", "advanced-paging",
    "advanced-maintenance", "network-port", "metadata-tasks", "advanced-about",
  ]);
  const blocks = [...html.matchAll(/data-settings-block="([^"]+)"/g)].map(m => m[1]);
  assert.ok(blocks.length > 8, "the settings dialog must still declare its blocks");
  for (const id of new Set(blocks)) {
    if (APPLIES_ON_CLICK.has(id)) continue;
    assert.ok(mapped.has(id), id + " belongs to no SETTINGS_GROUPS entry, so its save button never appears");
    assert.ok(tabbed.has(id), id + " is missing from SETTINGS_BLOCK_TABS");
  }
  for (const id of mapped) {
    assert.ok(blocks.includes(id), id + " is mapped for saving but no longer exists in index.html");
  }
  console.log("Every saveable settings block is reachable from the footer.");
})();
