const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/app.js", "utf8");
const start = source.indexOf("const MAX_UI_PREFERENCE_STORAGE_CHARS");
const end = source.indexOf("const TRACK_COLUMN_DEFINITIONS", start);
assert.ok(start >= 0 && end > start, "Unable to locate bounded local-storage parser");

const values = new Map();
const context = {
  localStorage: {
    getItem: key => values.has(key) ? values.get(key) : null,
  },
};
vm.runInNewContext(`${source.slice(start, end)}; this.parseStoredJson = parseStoredJson;`, context);

values.set("normal", '{"ok":true}');
assert.deepEqual(JSON.parse(JSON.stringify(context.parseStoredJson("normal", {}))), { ok: true });

values.set("oversized", "x".repeat(256 * 1024 + 1));
assert.deepEqual(JSON.parse(JSON.stringify(context.parseStoredJson("oversized", { rejected: true }))), { rejected: true });

values.set("broken", "{");
assert.deepEqual(JSON.parse(JSON.stringify(context.parseStoredJson("broken", []))), []);

assert.match(source, /parseStoredJson\(TRACK_COLUMNS_STORE_KEY, \[\]\)/);
assert.match(source, /parseStoredJson\(TRACK_COLUMN_WIDTHS_STORE_KEY, \{\}\)/);
assert.match(source, /parseStoredJson\(PLAYLIST_STORE_KEY, \[\], MAX_USER_MEDIA_STORAGE_CHARS\)/);
assert.match(source, /parseStoredJson\(FAVORITE_STORE_KEY, \[\], MAX_USER_MEDIA_STORAGE_CHARS\)/);

console.log("UI storage bounds regression checks passed.");
