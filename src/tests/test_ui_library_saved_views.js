// R585: saved views and capability negotiation are only useful if both sides
// agree. The Python policy is the validator; these checks keep the client copy
// of the whitelists identical to it, and keep a missing capability block
// degrading to the *old* behaviour instead of silently enabling a feature the
// server cannot honour.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

function load(file, name) {
  const source = fs.readFileSync(file, "utf8");
  const sandbox = { window: {} };
  sandbox.globalThis = sandbox.window;
  vm.createContext(sandbox);
  vm.runInContext(source, sandbox, { filename: file });
  assert.ok(sandbox.window[name], `${name} must register itself`);
  return sandbox.window[name];
}

const views = load("app/ui/library_saved_view_policy.js", "fnAudioLibrarySavedViewPolicy");
const caps = load("app/ui/library_capability_policy.js", "fnAudioLibraryCapabilityPolicy");

// Values produced inside the vm belong to another realm, so their prototypes
// differ from this file's Object/Array and deepStrictEqual would reject equal
// data. Comparing plain JSON keeps the assertions about values, not realms.
const plain = value => JSON.parse(JSON.stringify(value));

function pythonTuple(file, name) {
  const source = fs.readFileSync(file, "utf8");
  const match = source.match(new RegExp(name + "\\s*=\\s*\\(([\\s\\S]*?)\\)"));
  assert.ok(match, `${name} must stay readable in ${file}`);
  return match[1].split(",").map(value => value.trim().replace(/^["']|["']$/g, "")).filter(Boolean);
}

// --- cross-language guards -------------------------------------------------

const serverViews = pythonTuple("app/server/library_saved_view_policy.py", "VIEW_NAMES");
const serverSorts = pythonTuple("app/server/library_saved_view_policy.py", "SORT_KEYS");
assert.deepEqual(Array.from(views.VIEW_NAMES), serverViews, "client and server view names must match");
assert.deepEqual(Array.from(views.SORT_KEYS), serverSorts, "client and server sort keys must match");

const serverMax = Number(
  fs.readFileSync("app/server/library_saved_view_policy.py", "utf8").match(/MAX_VIEWS\s*=\s*(\d+)/)[1]
);
assert.equal(views.MAX_VIEWS, serverMax, "the cap must be the same on both sides");

// --- capability negotiation ------------------------------------------------

const degraded = caps.features(null);
assert.equal(degraded.savedViews.enabled, false, "a missing status must not enable saved views");
assert.equal(degraded.search.fieldSyntax, false, "a missing status must not advertise field syntax");
assert.equal(caps.searchPlaceholder(degraded), "搜索音乐", "the hint must not promise unsupported syntax");

const full = caps.features({
  capabilities: {
    version: 1,
    saved_views: { enabled: true, limit: 24 },
    search: { mode: "fts5-trigram", min_chars: 3, field_syntax: true, fields: ["title", "artist"] },
    sort: { keys: ["title", "added"], directions: ["asc", "desc"] },
    views: ["all", "dsd"],
    formats: ["FLAC", "MP3"],
  },
});
assert.equal(full.savedViews.enabled, true);
assert.equal(full.savedViews.limit, 24);
assert.equal(full.search.mode, "fts5-trigram");
assert.equal(full.search.minChars, 3);
assert.ok(caps.supportsField(full, "artist"));
assert.equal(caps.supportsField(full, "bpm"), false);
// The placeholder stays short at every capability level; the syntax hint that the
// toolbar used to show was cut off mid-word, so it lives in the tooltip instead.
assert.equal(caps.searchPlaceholder(full), "搜索音乐");
assert.ok(caps.searchHint(full).includes("artist:"), "the tooltip must still teach the syntax");

// A server that reports the mode but not the syntax must not get the hint.
const likeOnly = caps.features({ capabilities: { search: { mode: "like", min_chars: 0 } } });
assert.equal(likeOnly.search.fieldSyntax, false);
assert.equal(caps.searchPlaceholder(likeOnly), "搜索音乐");
assert.equal(caps.searchHint(likeOnly), "搜索音乐", "a degraded server must not be taught field syntax");

// --- capturing the current filter -----------------------------------------

const captured = views.capture(
  { view: "dsd", sortKey: "added", sortDir: "desc", groupName: "", folderRoot: "/music", folderPath: "" },
  "  floyd  "
);
assert.deepEqual(plain(captured), {
  view: "dsd", group: "", album: "", folder: "", root: "", search: "floyd",
  sort: "added", dir: "desc", subtree: false,
});

const folderCaptured = views.capture({ view: "folders", folderRoot: "/music", folderPath: "/music/rock" }, "");
assert.equal(folderCaptured.root, "/music", "a folder view keeps its root so the path is resolvable");
assert.equal(folderCaptured.folder, "/music/rock");

// Unknown state must not leak into a stored view.
const sanitized = views.capture({ view: "playlist:abc", sortKey: "bpm", sortDir: "sideways" }, "x".repeat(900));
assert.equal(sanitized.view, "all");
assert.equal(sanitized.sort, "title");
assert.equal(sanitized.dir, "asc");
assert.equal(sanitized.search.length, 512);

// --- projecting a stored view back into query parameters -------------------

assert.deepEqual(plain(views.toQueryParams({ view: "dsd", sort: "added", dir: "desc" })), {
  view: "dsd", sort: "added", dir: "desc",
});
assert.deepEqual(plain(views.toQueryParams({ view: "folders", folder: "/music/rock", root: "/music", subtree: true })), {
  view: "folders", sort: "title", dir: "asc", folder: "/music/rock", root: "/music", subtree: "1",
});

// --- names, summaries, list arithmetic -------------------------------------

assert.equal(views.validateName("  夜晚  "), "夜晚");
assert.equal(views.validateName("   "), "");
assert.equal(views.validateName("x".repeat(120)).length, views.MAX_NAME_CHARS);

const summary = views.summary({ search: "floyd", sort: "added", dir: "desc" });
assert.ok(summary.includes("搜索：floyd"));
assert.ok(summary.includes("按加入时间"));
assert.ok(summary.includes("降序"));

const merged = views.merge([{ id: "sv_a", name: "a" }], { id: "sv_b", name: "b" });
assert.deepEqual(Array.from(merged, item => item.id), ["sv_b", "sv_a"]);
const replaced = views.merge(merged, { id: "sv_a", name: "a2" });
assert.deepEqual(Array.from(replaced, item => item.id), ["sv_a", "sv_b"], "re-saving moves the view to the top");
assert.deepEqual(Array.from(views.remove(replaced, "sv_a"), item => item.id), ["sv_b"]);

const capped = views.merge(
  Array.from({ length: views.MAX_VIEWS }, (_, index) => ({ id: `sv_${index}`, name: String(index) })),
  { id: "sv_new", name: "new" }
);
assert.equal(capped.length, views.MAX_VIEWS);
assert.equal(capped[0].id, "sv_new");

console.log("Library saved-view and capability checks passed.");
