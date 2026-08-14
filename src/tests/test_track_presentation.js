const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/track_presentation.js", "utf8");
const context = { window: {} };
vm.createContext(context);
vm.runInContext(source, context);
const presentation = context.window.fnAudioTrackPresentation;

assert.equal(presentation.quality({ sample_rate: 96000, bit_depth: 24 }), "96kHz/24bit");
assert.equal(presentation.quality({ bitrate: 320000 }), "320kbps");
assert.equal(presentation.rowSelectionKey({ id: "track-1" }, 4), "track-1::4");
assert.equal(presentation.rowSelectionKey({}, -2), "::0");
assert.equal(presentation.columnValue({ track_no: 3 }, "track_no", { escapeHtml: value => value }), "03");
assert.equal(presentation.columnValue({ title: "ignored" }, "missing", { escapeHtml: value => value }), "—");
assert.equal(presentation.columnValue({ artist: "<artist>" }, "artist", { displayText: value => value, escapeHtml: value => value.replaceAll("<", "&lt;") }), "&lt;artist>");

console.log("Track presentation regression checks passed.");
