const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "app.js"), "utf8");
const start = source.indexOf("function normalizeUserMediaState");
const end = source.indexOf("async function loadServerUserState", start);
assert.ok(start >= 0 && end > start, "Unable to locate user-state merge helpers");

const context = vm.createContext({
  state: {
    favorites: ["keep", "local-add"],
    playlists: [{ id: "local", name: "Local edit", trackIds: ["two"] }],
    userStateBase: {
      favorites: ["keep", "removed-locally"],
      playlists: [
        { id: "local", name: "Before", trackIds: ["one"] },
        { id: "deleted", name: "Deleted", trackIds: ["old"] },
      ],
    },
  },
  localStorage: { setItem() {} },
  FAVORITE_STORE_KEY: "favorites",
  PLAYLIST_STORE_KEY: "playlists",
  clearTimeout() {},
  setTimeout() {},
  apiFetch() {},
});
vm.runInContext(source.slice(start, end), context);

const changes = vm.runInContext("userStateChanges()", context);
assert.deepEqual(Array.from(changes.favorites_add), ["local-add"]);
assert.deepEqual(Array.from(changes.favorites_remove), ["removed-locally"]);
assert.deepEqual(Array.from(changes.playlist_delete), ["deleted"]);
assert.equal(changes.playlist_upserts[0].name, "Local edit");

context.remote = {
  favorites: ["keep", "remote-add", "removed-locally"],
  playlists: [
    { id: "local", name: "Before", trackIds: ["one"] },
    { id: "remote", name: "Remote", trackIds: ["three"] },
    { id: "deleted", name: "Deleted", trackIds: ["old"] },
  ],
};
context.changes = changes;
const merged = vm.runInContext("applyUserStateChanges(remote, changes)", context);
assert.deepEqual(Array.from(merged.favorites), ["keep", "remote-add", "local-add"]);
assert.deepEqual(Array.from(merged.playlists.map(item => item.id)), ["local", "remote"]);
assert.equal(merged.playlists[0].name, "Local edit");

assert.match(source, /if \(state\.userStateSaveInFlight\) \{\s*state\.userStateDirty = true;/, "Saving during an in-flight request must mark the state dirty");
assert.match(source, /if \(state\.userStateDirty\) scheduleUserStateSave\(retryDelay\)/, "Dirty state must be retried after the active save finishes");
assert.doesNotMatch(source, /function mergeUserState\(/, "Union-based conflict merging must not return");

console.log("User-state concurrency regression checks passed.");
