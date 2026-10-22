const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/track_presentation.js", "utf8");
const context = { window: {} };
vm.createContext(context);
vm.runInContext(source, context);
const presentation = context.window.fnAudioTrackPresentation;

assert.equal(presentation.quality({ sample_rate: 96000, bit_depth: 24 }), "96kHz/24bit");
assert.equal(presentation.quality({ is_dsd: true, sample_rate: 2822400, bit_depth: 1 }), "2.8MHz");
assert.equal(presentation.quality({ is_dsd: true, sample_rate: 5644800, bit_depth: 1 }), "5.6MHz");
assert.equal(presentation.quality({ is_dsd: true, sample_rate: 11289600, bit_depth: 1 }), "11.3MHz");
assert.equal(presentation.quality({ is_dsd: true, sample_rate: 22579200, bit_depth: 1 }), "22.6MHz");
assert.equal(presentation.quality({ is_dsd: true, sample_rate: 705600, bit_depth: 8 }), "5.6MHz");
assert.equal(presentation.quality({ is_dsd: true, sample_rate: 352800, bit_depth: 8 }), "2.8MHz");
assert.equal(presentation.quality({ is_dsd: true, sample_rate: 1411200, bit_depth: 8 }), "11.3MHz");
assert.equal(presentation.quality({ is_dsd: true, sample_rate: 2822400, bit_depth: 8 }), "22.6MHz");
assert.equal(presentation.quality({ is_dsd: true, sample_rate: 705600, bit_depth: 1 }), "—");
assert.equal(presentation.quality({ is_dsd: true, sample_rate: 48000, bit_depth: 1 }), "—");
assert.equal(presentation.quality({ is_dsd: true, sample_rate: 0, bitrate: 320000 }), "—");
assert.equal(presentation.quality({ bitrate: 320000 }), "320kbps");
assert.equal(presentation.rowSelectionKey({ id: "track-1" }, 4), "track-1::4");
assert.equal(presentation.rowSelectionKey({}, -2), "::0");
assert.equal(presentation.columnValue({ track_no: 3 }, "track_no", { escapeHtml: value => value }), "03");
assert.equal(presentation.columnValue({ title: "ignored" }, "missing", { escapeHtml: value => value }), "—");
assert.equal(presentation.columnValue({ artist: "<artist>" }, "artist", { displayText: value => value, escapeHtml: value => value.replaceAll("<", "&lt;") }), "&lt;artist>");
assert.deepEqual(
  { ...presentation.columnValues({ track_no: 3, artist: "<artist>", duration: 65 }, ["track_no", "artist", "duration"], { displayText: value => value, clock: value => `${value}s`, escapeHtml: value => value.replaceAll("<", "&lt;") }) },
  { track_no: "03", artist: "&lt;artist>", duration: "65s" },
);
const hostile = new Proxy({}, { get() { throw new Error("row getter"); } });
assert.equal(presentation.quality(hostile), "—");
assert.equal(presentation.addedDate(hostile, () => { throw new Error("clock"); }), "—");
assert.equal(presentation.columnValue(hostile, "duration", { escapeHtml: value => value }), "—");
assert.equal(presentation.rowSelectionKey({ id: { toString() { throw new Error("id"); } } }, { valueOf() { throw new Error("index"); } }), "::0");
assert.match(source, /function columnValues\(item = \{\}, keys = \[\], helpers = \{\}\)/);

console.log("Track presentation regression checks passed.");
