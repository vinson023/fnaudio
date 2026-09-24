const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "app.js"), "utf8");
const policySource = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "user_media_state_policy.js"), "utf8");
const responseJsonLoader = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "response_json_loader.js"), "utf8");
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
  MAX_LOCAL_PLAYLISTS: 1000,
  MAX_LOCAL_PLAYLIST_TRACK_IDS: 10000,
  MAX_LOCAL_FAVORITES: 50000,
  clearTimeout() {},
  setTimeout() {},
  apiFetch() {},
});
// Mirror index.html's production load order: the pure policy module precedes app.js.
vm.runInContext(policySource, context);
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
context.hostile = new Proxy(["a"], { get(target, key) { if (key === "length") throw new Error("bad length"); return target[key]; } });
const merged = vm.runInContext("applyUserStateChanges(remote, changes)", context);
assert.deepEqual(Array.from(merged.favorites), ["keep", "remote-add", "local-add"]);
assert.deepEqual(Array.from(merged.playlists.map(item => item.id)), ["local", "remote"]);
assert.equal(merged.playlists[0].name, "Local edit");

const huge = vm.runInContext("normalizeUserMediaState({favorites: Array.from({length: 60000}, (_, i) => String(i)), playlists: [{id: 'big', name: 'Big', trackIds: Array.from({length: 12000}, (_, i) => String(i))}]})", context);
assert.equal(huge.favorites.length, 50000);
assert.equal(huge.playlists[0].trackIds.length, 10000);
const hostile = new Proxy(["a"], { get(target, key) { if (key === "length") throw new Error("bad length"); return target[key]; } });
assert.equal(JSON.stringify(vm.runInContext("normalizeUserMediaState({favorites: hostile})", context)), JSON.stringify({ favorites: [], playlists: [] }));
const revisionStart = source.indexOf("function userStateRevision");
const revisionEnd = source.indexOf("function mediaUrl", revisionStart);
assert.ok(revisionStart >= 0 && revisionEnd > revisionStart, "Revision helper must be present");
vm.runInContext(source.slice(revisionStart, revisionEnd), context);
assert.equal(vm.runInContext("userStateRevision(12)", context), 12);
assert.equal(vm.runInContext("userStateRevision(12.5)", context), 0);
assert.equal(vm.runInContext("userStateRevision(Infinity)", context), 0);
assert.equal(vm.runInContext("userStateRevision(true)", context), 0);
assert.equal(vm.runInContext("userStateRevision('9'.repeat(65))", context), 0);
const hostileId = { toString() { throw new Error("must not stringify id"); } };
const hostileDelta = { favorites_add: [hostileId], favorites_remove: [hostileId], playlist_delete: [hostileId] };
context.hostileDelta = hostileDelta;
assert.doesNotThrow(() => vm.runInContext("fnAudioUserMediaStatePolicy.apply({favorites: ['keep'], playlists: []}, hostileDelta)", context));
const hostilePlaylist = { id: hostileId, name: "bad", trackIds: [hostileId] };
context.hostilePlaylist = hostilePlaylist;
assert.deepEqual(Array.from(vm.runInContext("fnAudioUserMediaStatePolicy.normalize({playlists: [hostilePlaylist]})", context).playlists), []);

assert.match(source, /if \(state\.userStateSaveInFlight\) \{\s*state\.userStateDirty = true;/, "Saving during an in-flight request must mark the state dirty");
assert.match(source, /if \(state\.userStateDirty\) scheduleUserStateSave\(retryDelay\)/, "Dirty state must be retried after the active save finishes");
assert.match(source, /async function saveUserStateNow\(\)[\s\S]*?signal: controller\.signal[\s\S]*?fnAudioResponseJsonLoader\.read\(\{[\s\S]*?timeoutMs: 6000,[\s\S]*?onTimeout:[\s\S]*?state\.userStateSaveInFlight = false;/, "User-state saves must have a bounded deadline and release their in-flight guard");
assert.doesNotMatch(source, /function mergeUserState\(/, "Union-based conflict merging must not return");
assert.match(source, /const pendingChanges = userStateChanges\(\);[\s\S]*?await applyServerUserState\(serverState\);[\s\S]*?const latestChanges = userStateChanges\(\);[\s\S]*?const merged = applyUserStateChanges\(serverState, mergedChanges\);[\s\S]*?persistUserMediaState\(merged\)/, "Background server refreshes must restore edits made before and during asynchronous reconciliation");
assert.match(source, /const favoriteOperations = new Map\(\);[\s\S]*?latestChanges\.favorites_remove[\s\S]*?favorites_add: \[\.\.\.favoriteOperations\]/, "The latest local favorite operation must win an async refresh conflict");
assert.match(source, /const playlistOperations = new Map\(\);[\s\S]*?latestChanges\.playlist_delete[\s\S]*?playlist_delete: \[\.\.\.playlistOperations\]/, "The latest local playlist operation must win an async refresh conflict");
assert.match(source, /const visibleSignatureBefore = visibleUserStatePresentationSignature\(\);[\s\S]*?const visibleListChanged = visibleSignatureBefore !== visibleUserStatePresentationSignature\(\);/, "Merged local edits must drive the visible-list refresh decision");
assert.match(source, /async function loadServerUserState\(\)[\s\S]*?catch \(error\) \{[\s\S]*?state\.userStateHydrated = true;[\s\S]*?state\.userStateDirty = true;[\s\S]*?scheduleUserStateSave\(2000\);[\s\S]*?renderAfterUserStateHydration\(\);/, "A failed initial user-state read must enable retryable local persistence instead of disabling sync for the session");
assert.match(source, /async function loadServerUserState\(\)[\s\S]*?cache: "no-store"[\s\S]*?fnAudioResponseJsonLoader\.read\(\{[\s\S]*?timeoutMs: 6000,[\s\S]*?onTimeout:/, "Initial user-state hydration must have a bounded request deadline");
assert.match(source, /async function refreshServerUserState\(\)[\s\S]*?cache: "no-store"[\s\S]*?fnAudioResponseJsonLoader\.read\(\{[\s\S]*?timeoutMs: 6000,[\s\S]*?onTimeout:[\s\S]*?state\.userStateRefreshInFlight = false;/, "Periodic user-state refresh must release its in-flight guard after a bounded timeout");
assert.match(responseJsonLoader, /Promise\.race\(\[operation, timeout\]\)/, "Shared user-state loader must release its deadline after headers or body settle");

// A rejected local shadow write must cost the offline cache only: never the
// edit itself, the queued server save, or the favorite repaint (R171).
const guardedWriterStart = source.indexOf("function writeStoredUserMedia");
const guardedWriterEnd = source.indexOf("function loadStoredPlaylists", guardedWriterStart);
assert.ok(guardedWriterStart >= 0 && guardedWriterEnd > guardedWriterStart,
  "A guarded local-cache writer must sit next to the user-media writers that need it");

const shadowCalls = [];
function userMediaShadowContext(failing) {
  shadowCalls.length = 0;
  const context = vm.createContext({
    state: {
      favorites: ["one"],
      playlists: [{ id: "p", name: "P", trackIds: ["one"] }],
      userStateHydrated: true,
      userStateDirty: false,
      userStateSaveInFlight: false,
      userStateSaveTimer: 0,
    },
    localStorage: {
      setItem(key, value) {
        shadowCalls.push({ key, value });
        if (failing) throw new Error("local storage is full");
      },
    },
    FAVORITE_STORE_KEY: "fnaudio.favorites",
    PLAYLIST_STORE_KEY: "fnaudio.playlists",
    MAX_USER_MEDIA_STORAGE_CHARS: 4 * 1024 * 1024,
    clearTimeout() {},
    setTimeout(fn, delay) { shadowCalls.push({ timer: delay }); return 9; },
    apiFetch() {},
    updateFavoriteControls() { shadowCalls.push({ repaint: 1 }); },
    parseStoredJson() { return []; },
  });
  vm.runInContext(policySource, context);
  vm.runInContext(source.slice(guardedWriterStart, end), context);
  return context;
}
function runUserMedia(context, code) {
  try {
    vm.runInContext(code, context);
    return null;
  } catch (error) {
    return String((error && error.message) || error);
  }
}
const shadowKeys = () => shadowCalls.filter(call => call.key).map(call => call.key);
const shadowTimerDelays = () => shadowCalls.filter(call => call.timer !== undefined).map(call => call.timer);
const shadowRepaintCount = () => shadowCalls.filter(call => call.repaint).length;

const brokenStore = userMediaShadowContext(true);
assert.equal(runUserMedia(brokenStore, "saveFavorites()"), null,
  "A rejected favorite-cache write must not escape the writer");
assert.deepEqual(shadowKeys(), ["fnaudio.favorites"], "The cache write must still be attempted");
assert.deepEqual(shadowTimerDelays(), [350],
  "A rejected cache write must not cancel the queued server save");

const brokenPlaylistStore = userMediaShadowContext(true);
assert.equal(runUserMedia(brokenPlaylistStore, "savePlaylists()"), null,
  "A rejected playlist-cache write must not escape the writer");
assert.deepEqual(shadowKeys(), ["fnaudio.playlists"], "The playlist cache write must still be attempted");
assert.deepEqual(shadowTimerDelays(), [350],
  "A rejected playlist cache write must not cancel the queued server save");

const brokenHydration = userMediaShadowContext(true);
assert.equal(runUserMedia(brokenHydration, "persistUserMediaState({ favorites: ['two'], playlists: [] })"), null,
  "A rejected cache write must not abort server-state hydration");
assert.deepEqual(shadowKeys(), ["fnaudio.favorites", "fnaudio.playlists"],
  "Both stores must be attempted even when the first write fails");
assert.equal(shadowRepaintCount(), 1,
  "Favorite controls must repaint even when the cache write failed");
assert.deepEqual(Array.from(brokenHydration.state.favorites), ["two"],
  "The in-memory copy must still take the new value");

const workingStore = userMediaShadowContext(false);
assert.equal(runUserMedia(workingStore, "persistUserMediaState({ favorites: ['two', 'three'], playlists: [{ id: 'q', name: 'Q', trackIds: [] }] })"), null);
assert.deepEqual(shadowKeys(), ["fnaudio.favorites", "fnaudio.playlists"],
  "Guarding the write must not stop the write from happening");
assert.deepEqual(JSON.parse(shadowCalls[0].value), ["two", "three"], "The favorites cache must hold the new ids");
assert.deepEqual(JSON.parse(shadowCalls[1].value), [{ id: "q", name: "Q", trackIds: [] }], "The playlist cache must hold the new list");
assert.equal(shadowRepaintCount(), 1);

// Source-level sentinels: the writers must not regress to bare writes, and the
// guard must swallow storage failures only.
for (const [name, next] of [
  ["savePlaylists", "function loadStoredFavorites"],
  ["saveFavorites", "function normalizeUserMediaState"],
  ["persistUserMediaState", "function userStatePayload"],
]) {
  const from = source.indexOf("function " + name + "(");
  const to = source.indexOf(next, from);
  assert.ok(from >= 0 && to > from, "Unable to locate " + name);
  assert.doesNotMatch(source.slice(from, to), /localStorage\s*\./,
    name + " must persist through the guarded writer instead of touching storage directly");
}
assert.match(source.slice(guardedWriterStart, guardedWriterEnd),
  /function writeStoredUserMedia\(key, value\) \{[\s\S]{0,420}?try \{[\s\S]{0,80}?localStorage\.setItem\(key, JSON\.stringify\(value\)\);[\s\S]{0,40}?\} catch \(_\) \{/,
  "The guarded writer must wrap exactly the storage call");

console.log("User-state concurrency regression checks passed.");
