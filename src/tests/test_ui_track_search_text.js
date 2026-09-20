const fs = require("fs");
const vm = require("vm");
const assert = require("assert");

const source = fs.readFileSync(require.resolve("../app/ui/track_search_text.js"), "utf8");
const appSource = fs.readFileSync(require.resolve("../app/ui/app.js"), "utf8");
assert.ok(appSource.includes("slice(0, 4096)"));
const searchFn = appSource.match(/function trackMatchesSearch[\s\S]*?\r?\n}\r?\nfunction hasMultipleLibraryRoots/);
assert.ok(searchFn && !searchFn[0].includes("String(value || \"\")"));
const context = { globalThis: {} };
vm.runInNewContext(source, context);
const api = context.globalThis.fnAudioTrackSearchText;
assert.strictEqual(api.trackSearchText({ title: "Song", artist: "Singer", format: "FLAC" }), "song singer flac");
assert.ok(api.trackSearchText({ title: "x".repeat(5000) }).length <= api.MAX_SEARCH_TEXT);
assert.strictEqual(api.trackSearchText({ title: { toString() { throw new Error("unsafe"); } } }), "");
const broken = new Proxy({ title: "ok" }, { get(target, key) { if (key === "artist") throw new Error("broken"); return target[key]; } });
assert.strictEqual(api.trackSearchText(broken), "ok");
assert.strictEqual(api.trackSearchText(null), "");
console.log("ui track search text tests passed");
