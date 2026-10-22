const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const UI_DIR = path.join(__dirname, "..", "app", "ui");
const app = fs.readFileSync(path.join(UI_DIR, "app.js"), "utf8");
const index = fs.readFileSync(path.join(UI_DIR, "index.html"), "utf8");

assert.match(app, /function syncMetadataSettingsSaveAction\(/, "metadata save action must follow the active subpane");
assert.match(app, /syncMetadataSettingsSaveAction\(name\)/, "metadata subtab changes must update the save action");
assert.match(app, /保存概览设置/, "overview must use a scoped save label");
assert.match(app, /保存 Tag 写回设置/, "Tag writes must use a scoped save label");

function functionSource(name) {
  const match = app.match(new RegExp("^(?:async )?function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `${name} must be declared as an extractable pure helper`);
  return match[0];
}

const sandbox = {
  METADATA_PROVIDER_SAFE_ORDER: ["netease", "kuwo", "kugou", "migu", "joox", "musicbrainz"],
  MUSICBRAINZ_PROVIDER_ID: "musicbrainz",
};
vm.runInNewContext([
  functionSource("metadataProviderFallbackEntries"),
  functionSource("normalizeMetadataProviderEntries"),
  functionSource("serializeMetadataProviderEntries"),
  functionSource("moveMetadataProviderEntries"),
  functionSource("moveMetadataProviderToIndex"),
  functionSource("metadataProviderDropTargetIndex"),
].join("\n"), sandbox);
const policy = {
  normalize: sandbox.normalizeMetadataProviderEntries,
  serialize: sandbox.serializeMetadataProviderEntries,
  move: sandbox.moveMetadataProviderEntries,
  moveTo: sandbox.moveMetadataProviderToIndex,
  dropTarget: sandbox.metadataProviderDropTargetIndex,
};

const safe = policy.normalize([]);
assert.deepEqual(
  safe.map(entry => entry.id),
  ["netease", "kuwo", "kugou", "migu", "joox", "musicbrainz"],
  "an empty provider configuration must use the safe recommended order",
);
assert.equal(safe.at(-1).id, "musicbrainz");

const custom = [
  { id: "joox", name: "JOOX", enabled: false },
  { id: "kuwo", name: "酷我音乐", enabled: true },
  { id: "netease", name: "网易云音乐", enabled: false },
  { id: "migu", name: "咪咕音乐", enabled: true },
  { id: "kugou", name: "酷狗音乐", enabled: true },
  { id: "musicbrainz", name: "MusicBrainz", enabled: true, fixed_last: true },
];
assert.equal(
  JSON.stringify(policy.serialize(policy.normalize(custom))),
  JSON.stringify(custom.map(({ id, enabled }) => ({ id, enabled }))),
  "valid order and enabled flags must survive the UI projection",
);
assert.equal(
  JSON.stringify(policy.move(custom, "musicbrainz", -1).map(entry => entry.id)),
  JSON.stringify(custom.map(entry => entry.id)),
  "MusicBrainz must not move away from the last position",
);
assert.equal(policy.move(custom, "joox", 1).at(-1).id, "musicbrainz");
assert.equal(policy.moveTo(custom, "kugou", 0)[0].id, "kugou");
assert.equal(policy.moveTo(custom, "joox", 99).at(-1).id, "musicbrainz");
const adjacentDropIndex = policy.dropTarget(custom, "netease", "kuwo", true);
assert.equal(adjacentDropIndex, 2, "dropping just below the next provider must move down one slot");
assert.equal(
  JSON.stringify(policy.moveTo(custom, "netease", adjacentDropIndex).map(entry => entry.id)),
  JSON.stringify(["joox", "kuwo", "netease", "migu", "kugou", "musicbrainz"]),
  "dropping below a row must insert after it instead of remaining in the same order",
);
assert.equal(policy.dropTarget(custom, "musicbrainz", "kuwo", false), -1);
assert.equal(policy.dropTarget(custom, "netease", "missing", false), -1);

assert.match(index, /id="metadataProviderList"/);
assert.match(index, /id="metadataCandidateProviderSelect"/);
assert.match(index, /单独选择数据源不会改变全局排序/);
assert.match(index, /id="restoreMetadataProvidersBtn"/);
assert.match(index, /id="metadataProbeTitleInput"/);
assert.match(index, /id="metadataProbeArtistInput"/);
assert.match(index, /id="metadataProbeAlbumInput"/);
assert.match(index, /每个数据源可单独测试/);
assert.match(app, /function ensureMetadataProviderSaveAction\(\)/);
assert.match(app, /id = "saveMetadataProvidersBtn"/);
assert.match(functionSource("renderMetadataProviders"), /ensureMetadataProviderSaveAction\(\)/, "rendering providers must materialize the provider save action");
assert.match(app, /function saveMetadataProviderPaneSettings\(\)/);
assert.match(app, /function saveMetadataProvidersOnly\(\)/);
assert.match(functionSource("saveMetadataProvidersOnly"), /body: JSON\.stringify\(\{ providers: metadataProviderPayload\(\) \}\)/);
assert.doesNotMatch(functionSource("saveMetadataProvidersOnly"), /metadataTagWriteConfirmation/);
assert.doesNotMatch(app, /\$\("saveMetadataProvidersBtn"\)\.onclick\s*=/, "the dynamically-created provider save button must not be bound before it exists");
assert.match(app, /点击“保存数据源设置”后生效/);
assert.doesNotMatch(app, /数据源配置已修改，点击“保存设置”后生效/);
assert.match(functionSource("updateMetadataProviderDirtyStatus"), /saveButton\.disabled = state\.metadataProviderDirty !== true/);
assert.match(functionSource("refreshMetadataLibrary"), /apiFetch\("api\/metadata\/refresh", \{ method: "POST" \}\)/);
assert.doesNotMatch(functionSource("refreshMetadataLibrary"), /saveMetadataSettings/);
assert.match(functionSource("refreshMetadataLibrary"), /已请求后台元数据补全/);
assert.doesNotMatch(index, /MusicBrainz.*始终排在最后/);
assert.doesNotMatch(index, /MusicBrainz.*最后回退/);
assert.doesNotMatch(app, /最后回退/);
assert.doesNotMatch(app, /MusicBrainz.*始终排在最后/);
assert.doesNotMatch(app, /MusicBrainz.*固定排在最后/, "provider help must not expose MusicBrainz ranking commentary");
assert.match(index, /<h3>基础与安全<\/h3>/, "metadata settings must separate safety controls");
assert.match(index, /<h3>补全任务<\/h3>/, "metadata settings must separate background jobs");
assert.match(index, /<h3>Tag 写回<\/h3>/, "metadata settings must separate file-writing controls");
assert.match(index, /role="tablist" aria-label="元数据设置分类"/, "metadata settings must expose their own labelled tablist");
for (const name of ["overview", "providers", "tasks", "tags"]) {
  assert.match(index, new RegExp(`data-metadata-settings-tab="${name}"`), `${name} must have a metadata tab`);
  assert.match(index, new RegExp(`data-metadata-settings-pane="${name}"`), `${name} must have its own panel`);
}
assert.match(index, /id="metadataTagWriteActions"/, "tag write actions must have their own region");
assert.match(app, /\$\("metadataTagWriteActions"\)\?\.append\(retryButton\)/, "retry writes must render in the tag write region");
assert.match(app, /function setMetadataSettingsTab\(/, "metadata tabs need an independent state switcher");
assert.match(app, /function metadataSettingsTabIndexForKey\(/, "metadata tabs must support standard keyboard navigation");
assert.match(app, /function bindMetadataSettingsTabs\(/, "metadata tabs must bind click and keyboard interaction");
assert.match(app, /state\.metadataSettingsTab = name;/, "metadata subtab selection must persist while switching top-level panes");
assert.match(functionSource("setSettingsTab"), /setMetadataSettingsTab\(state\.metadataSettingsTab \|\| "overview"\)/, "reopening metadata must preserve the selected subtab");

const metadataTabNodes = ["overview", "providers", "tasks", "tags"].map(name => ({
  dataset: { metadataSettingsTab: name },
  attrs: {},
  active: false,
  focus() { metadataTabsSandbox.focused = this; },
  classList: { toggle(_className, active) { this.node.active = active; }, node: null },
  setAttribute(name, value) { this.attrs[name] = value; },
}));
const metadataPaneNodes = ["overview", "providers", "tasks", "tags"].map(name => ({
  dataset: { metadataSettingsPane: name }, hidden: true, active: false,
  classList: { toggle(_className, active) { this.node.active = active; }, node: null },
}));
for (const node of [...metadataTabNodes, ...metadataPaneNodes]) node.classList.node = node;
const metadataTabsSandbox = {
  state: { metadataSettingsTab: "overview" },
  focus: null,
  $() { return null; },
  document: { querySelectorAll(selector) {
    return selector === "[data-metadata-settings-tab]" ? metadataTabNodes : metadataPaneNodes;
  }, querySelector() { return null; } },
};
vm.runInNewContext([
  functionSource("setMetadataSettingsTab"),
  functionSource("syncMetadataSettingsSaveAction"),
  functionSource("metadataSettingsTabIndexForKey"),
  functionSource("bindMetadataSettingsTabs"),
].join("\n"), metadataTabsSandbox);
metadataTabsSandbox.bindMetadataSettingsTabs();
let keyboardPrevented = false;
metadataTabNodes[0].onkeydown({ key: "ArrowRight", preventDefault() { keyboardPrevented = true; } });
assert.equal(keyboardPrevented, true);
assert.equal(metadataTabsSandbox.focused, metadataTabNodes[1], "keyboard navigation must focus its newly selected tab");
assert.deepEqual(metadataPaneNodes.map(node => node.hidden), [true, false, true, true]);
metadataTabNodes[2].onclick();
assert.equal(metadataTabNodes[2].attrs["aria-selected"], "true", "clicking a metadata tab must select it");
assert.equal(metadataTabsSandbox.setMetadataSettingsTab("providers"), "providers");
assert.equal(metadataTabsSandbox.state.metadataSettingsTab, "providers");
assert.deepEqual(metadataTabNodes.map(node => node.attrs["aria-selected"]), ["false", "true", "false", "false"]);
assert.deepEqual(metadataPaneNodes.map(node => node.hidden), [true, false, true, true]);
assert.equal(metadataTabsSandbox.setMetadataSettingsTab("missing"), "overview", "unknown metadata tabs must fall back to the overview");
const saveButton = { hidden: false, textContent: "保存概览设置" };
const tagSaveButton = { hidden: false, textContent: "保存 Tag 写回设置" };
const saveActionSandbox = {
  saveMetadataOverviewPaneSettings() {},
  saveMetadataTagPaneSettings() {},
  $: id => id === "saveMetadataSettingsBtn" ? saveButton : id === "saveMetadataTagSettingsBtn" ? tagSaveButton : null,
  document: { querySelector() { throw new Error("save actions must remain in their owning subpages"); } },
};
vm.runInNewContext(functionSource("syncMetadataSettingsSaveAction") + "\nglobalThis.syncMetadataSettingsSaveAction = syncMetadataSettingsSaveAction;", saveActionSandbox);
for (const name of ["overview", "providers", "tasks", "tags"]) {
  saveActionSandbox.syncMetadataSettingsSaveAction(name);
  assert.equal(saveButton.onclick, saveActionSandbox.saveMetadataOverviewPaneSettings);
  assert.equal(tagSaveButton.onclick, saveActionSandbox.saveMetadataTagPaneSettings);
  assert.equal(saveButton.hidden, false, "the overview pane controls its own button visibility");
  assert.equal(tagSaveButton.hidden, false, "the Tag pane controls its own button visibility");
}
assert.equal(saveButton.textContent, "保存概览设置");
assert.equal(tagSaveButton.textContent, "保存 Tag 写回设置");
const sectionStack = [];
const buttonOwners = {};
for (const token of index.matchAll(/<\/?section\b[^>]*>|<button\b[^>]*>/g)) {
  if (token[0].startsWith("</section")) sectionStack.pop();
  else if (token[0].startsWith("<section")) sectionStack.push(token[0].match(/\bid="([^"]+)"/)?.[1] || "");
  else {
    const id = token[0].match(/\bid="([^"]+)"/)?.[1];
    if (id) buttonOwners[id] = sectionStack.filter(Boolean);
  }
}
assert.ok(buttonOwners.saveMetadataSettingsBtn.includes("metadata-settings-pane-overview"), "overview save must be owned by the overview DOM pane");
assert.ok(buttonOwners.saveMetadataTagSettingsBtn.includes("metadata-settings-pane-tags"), "Tag save must be owned by the Tag DOM pane");
assert.ok(!buttonOwners.saveMetadataSettingsBtn.includes("metadata-settings-pane-tags"));
assert.deepEqual(metadataTabNodes.map(node => node.tabIndex), [0, -1, -1, -1], "only the active metadata tab belongs in the tab sequence");
assert.equal(metadataTabsSandbox.metadataSettingsTabIndexForKey("ArrowRight", 3, 4), 0, "right arrow wraps to the first metadata tab");
assert.equal(metadataTabsSandbox.metadataSettingsTabIndexForKey("ArrowLeft", 0, 4), 3, "left arrow wraps to the last metadata tab");
assert.equal(metadataTabsSandbox.metadataSettingsTabIndexForKey("Home", 2, 4), 0);
assert.equal(metadataTabsSandbox.metadataSettingsTabIndexForKey("End", 0, 4), 3);
assert.equal(metadataTabsSandbox.metadataSettingsTabIndexForKey("Escape", 0, 4), -1, "unrelated keys must not change tabs");

assert.match(app, /function renderMetadataProviders\(/);
assert.match(app, /function moveMetadataProvider\(/);
assert.match(app, /function testMetadataProvider\(/);
assert.match(app, /function metadataProviderProbeResponse\(/);
assert.match(app, /function metadataProviderUnavailableResult\(/);
assert.match(app, /api\/metadata\/provider-test/);
assert.match(app, /api\/config\/metadata/);
assert.match(app, /provider_id: \$\("metadataCandidateProviderSelect"\)\?\.value \|\| ""/);
assert.match(app, /function renderMetadataCandidateProviderPicker\(/);
assert.match(app, /function metadataCandidateSourceLabel\(/);
assert.match(app, /metadataProviderDisplayName\(providerId\)/);
assert.match(app, /metadataProviderDisplayName\(entry\.id\)/);

const displayNameSandbox = {
  METADATA_PROVIDER_SAFE_ORDER: ["netease", "kuwo", "kugou", "migu", "joox", "musicbrainz"],
  displayText: value => typeof value === "string" ? value : "",
  state: { metadataProviders: [{ id: "netease", enabled: true }], metadataProviderRecommended: [] },
};
vm.runInNewContext(functionSource("metadataProviderDisplayName"), displayNameSandbox);
assert.equal(displayNameSandbox.metadataProviderDisplayName("netease"), "网易云音乐");
assert.equal(displayNameSandbox.metadataProviderDisplayName("musicbrainz"), "MusicBrainz");
assert.match(app, /restoreMetadataProvidersBtn/);
assert.match(functionSource("saveMetadataProvidersOnly"), /metadataProviderPayload\(\)/);
assert.doesNotMatch(app, /function saveMetadataSettings\(/, "the obsolete full metadata save path must stay removed");
assert.match(app, /搜索/);
assert.match(app, /封面/);
assert.match(app, /歌词/);
assert.match(app, /响应时间/);
assert.doesNotMatch(app, /MusicBrainz、网易云、QQ、酷狗、咪咕、JOOX、千千音乐/);

const probeResponseSandbox = {};
vm.runInNewContext(functionSource("metadataProviderProbeResponse"), probeResponseSandbox);
const providerProbeResult = {
  provider_id: "kugou",
  search: { supported: true, available: true },
  cover: { supported: true, available: true },
  lyrics: { supported: true, available: true },
  response_ms: 384,
  ok: true,
};
const providerProbeEnvelope = { ok: true, result: providerProbeResult };
assert.deepEqual(
  JSON.parse(JSON.stringify(probeResponseSandbox.metadataProviderProbeResponse(providerProbeEnvelope))),
  providerProbeEnvelope,
  "a provider-test response must retain the outer ok/result envelope",
);
assert.deepEqual(
  JSON.parse(JSON.stringify(probeResponseSandbox.metadataProviderProbeResponse({ data: providerProbeEnvelope }))),
  providerProbeEnvelope,
  "a host-wrapped provider-test response must retain the outer ok/result envelope",
);
const rejectedProbeEnvelope = { ok: false, message: "proxy rejected request", result: providerProbeResult };
assert.deepEqual(
  JSON.parse(JSON.stringify(probeResponseSandbox.metadataProviderProbeResponse(rejectedProbeEnvelope))),
  rejectedProbeEnvelope,
  "a failed API envelope must not be replaced by its nested provider result",
);

const restoreSandbox = {
  METADATA_PROVIDER_SAFE_ORDER: ["netease", "kuwo", "kugou", "migu", "joox", "musicbrainz"],
  MUSICBRAINZ_PROVIDER_ID: "musicbrainz",
  displayText: value => typeof value === "string" ? value : "",
  state: {
    metadataProvidersLoaded: false,
    metadataProviderRecommended: [],
    metadataProviders: [],
    metadataProviderResults: Object.create(null),
  },
  renderMetadataProviders() {},
  updateMetadataProviderDirtyStatus() {},
};
const recommended = restoreSandbox.METADATA_PROVIDER_SAFE_ORDER.map(id => ({
  id,
  enabled: true,
  fixed_last: id === "musicbrainz",
}));
const configured = [
  { id: "joox", enabled: false },
  { id: "kuwo", enabled: true },
  { id: "netease", enabled: false },
  { id: "migu", enabled: true },
  { id: "kugou", enabled: true },
  { id: "musicbrainz", enabled: false },
];
let restoredPayload = null;
restoreSandbox.loadMetadataStatus = async () => {
  restoreSandbox.state.metadataProvidersLoaded = true;
  restoreSandbox.state.metadataProviderRecommended = recommended;
  restoreSandbox.state.metadataProviders = configured;
  return { ok: true };
};
restoreSandbox.saveMetadataSettings = async () => {
  restoredPayload = restoreSandbox.state.metadataProviders.map(({ id, enabled }) => ({ id, enabled }));
};
restoreSandbox.saveMetadataProvidersOnly = restoreSandbox.saveMetadataSettings;
vm.runInNewContext([
  functionSource("metadataProviderFallbackEntries"),
  functionSource("normalizeMetadataProviderEntries"),
  functionSource("metadataProviderUnavailableResult"),
  functionSource("restoreRecommendedMetadataProviders"),
  functionSource("restoreAndSaveRecommendedMetadataProviders"),
].join("\n"), restoreSandbox);

restoreSandbox.state.metadataProviders = [
  { id: "musicbrainz", enabled: true, capabilities: ["search", "track", "album", "cover"] },
  { id: "netease", enabled: true, capabilities: ["search", "track", "album", "cover", "lyrics"] },
];
const musicBrainzUnavailable = restoreSandbox.metadataProviderUnavailableResult("musicbrainz", "network down");
assert.deepEqual(JSON.parse(JSON.stringify(musicBrainzUnavailable.lyrics)), {
  supported: false,
  available: false,
});
assert.deepEqual(JSON.parse(JSON.stringify(musicBrainzUnavailable.cover)), {
  supported: true,
  available: false,
});
assert.equal(musicBrainzUnavailable.search.supported, true);
assert.equal(musicBrainzUnavailable.error, "network down");

(async () => {
  await restoreSandbox.restoreAndSaveRecommendedMetadataProviders();
  assert.deepEqual(
    JSON.parse(JSON.stringify(restoredPayload)),
    recommended.map(({ id, enabled }) => ({ id, enabled })),
    "restoring before the first settings read must save the recommendation, not the loaded custom order",
  );

  const probeFlow = {
    state: {
      metadataProviderTestInFlight: "",
      metadataProviders: [{ id: "kugou", capabilities: ["search", "cover", "lyrics"] }],
      metadataProviderRecommended: [],
      metadataProviderResults: Object.create(null),
    },
    values: {
      metadataProbeTitleInput: { value: "晴天" },
      metadataProbeArtistInput: { value: "周杰伦" },
      metadataProbeAlbumInput: { value: "叶惠美" },
      metadataProviderStatusText: { textContent: "" },
    },
    $: id => id === "metadataProviderList"
      ? { querySelector: () => ({}) }
      : probeFlow.values[id],
    apiFetch: async (url, init) => {
      probeFlow.request = { url, init };
      return { ok: true };
    },
    readResponseJsonBounded: async () => providerProbeEnvelope,
    displayText: value => typeof value === "string" ? value : "",
    renderMetadataProviders() {},
    metadataProviderUnavailableResult: () => ({ ok: false, error: "unexpected fallback" }),
  };
  vm.runInNewContext([
    functionSource("metadataProviderProbeResponse"),
    functionSource("metadataProviderProbePayload"),
    functionSource("testMetadataProvider"),
  ].join("\n"), probeFlow);
  const result = await probeFlow.testMetadataProvider("kugou");
  assert.deepEqual(
    JSON.parse(JSON.stringify(result)),
    providerProbeResult,
    "the settings test flow must return the nested provider result rather than an empty object",
  );
  assert.deepEqual(
    JSON.parse(JSON.stringify(probeFlow.state.metadataProviderResults.kugou)),
    providerProbeResult,
    "the settings test flow must retain search, cover, lyrics, and response-time fields",
  );
  assert.equal(probeFlow.request.url, "api/metadata/provider-test");
  assert.deepEqual(JSON.parse(probeFlow.request.init.body), {
    provider_id: "kugou", title: "晴天", artist: "周杰伦", album: "叶惠美",
  });
  console.log("Metadata provider settings UI regression checks passed.");
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
