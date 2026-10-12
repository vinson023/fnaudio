const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/visible_metadata_prefetch_policy.js", "utf8");
const app = fs.readFileSync("app/ui/app.js", "utf8");
const index = fs.readFileSync("app/ui/index.html", "utf8");

assert.match(source, /result\.length >= bounded/);
assert.match(source, /if \(result\.length >= bounded\) break;/);
assert.match(source, /!value\.trim\(\)\) return fallback/);
assert.match(source, /MAX_LIMIT = 12/);
assert.match(source, /attempt >= boundedAttempts - 1/);
assert.match(app, /fnAudioVisibleMetadataPrefetchPolicy\?\.selectCandidates/);
assert.match(app, /fnAudioVisibleMetadataPrefetchPolicy\?\.shouldRetry/);
assert.match(app, /selectDisplayArtwork/, "Artwork must be projected independently when candidate payload is sparse");
assert.match(app, /if \(!best && !artwork\)/, "Artwork-only metadata responses must remain usable without a candidate");
assert.ok(index.indexOf('src="visible_metadata_prefetch_policy.js') < index.indexOf('src="app.js'), "Policy must load before app.js");
const sandbox = { globalThis: {}, window: null };
sandbox.window = sandbox;
vm.runInNewContext(source, sandbox);
const policy = sandbox.fnAudioVisibleMetadataPrefetchPolicy;
assert.equal(policy.selectCandidates([
  { id: "1", album: "", artist: "" },
  { id: "2", cover_url: "x", album: "A", artist: "B" },
  { id: "3", album: "", artist: "" },
], 1).length, 1);
assert.equal(policy.selectCandidates([
  { id: "title-missing", title: "", cover_url: "x", album: "A", artist: "B" },
  { id: "complete", title: "Song", cover_url: "x", album: "A", artist: "B" },
], 6).map(item => item.id).join(","), "title-missing");
assert.equal(policy.selectCandidates([
  { id: "dup", album: "", artist: "" },
  { id: "dup", album: "", artist: "" },
  { id: {}, album: "", artist: "" },
  { id: "ok", album: "", artist: "" },
], 6).map(item => item.id).join(","), "dup,ok");
assert.equal(policy.shouldRetry({ pending: true }, 0, 4), true);
assert.equal(policy.shouldRetry({ pending: true }, 3, 4), false);
assert.equal(policy.shouldRetry(null, 0, 4), true, "Transient empty metadata responses must retry");
assert.equal(policy.shouldRetry(null, 3, 4), false, "Empty metadata retries remain bounded");
assert.equal(policy.shouldRetry({ ok: true }, 0, 4), true, "Generic HTTP 200 envelopes must remain recoverable");
assert.equal(policy.shouldRetry({ ok: true }, 3, 4), false, "Generic envelope recovery remains bounded");
assert.equal(policy.shouldRetry({ pending: true }, 10), true, "Default retry budget must match the visible prefetch lane");
assert.equal(policy.shouldRetry({ pending: true }, 11), false);
assert.equal(policy.shouldRetry({ retryable: true }, 10, 12), true);
assert.equal(policy.shouldRetry({ retryable: true }, 11, 12), false);
assert.equal(policy.shouldReleaseKey({ status: "failed" }), true);
assert.equal(policy.shouldReleaseKey({ status: "no_match" }), true);
assert.equal(policy.shouldReleaseKey({ status: "pending", retryable: true }), true);
assert.equal(policy.shouldReleaseKey({ status: "pending" }), false);
assert.equal(policy.shouldReleaseKey({ ok: true }), true, "Generic envelopes must not lock the dedupe key");
assert.equal(policy.shouldReleaseKey(null), true);
assert.equal(policy.shouldRearmPending({ pending: true }, 12, 0), true, "A still-pending job should receive one quiet recovery window");
assert.equal(policy.shouldRearmPending({ pending: true }, 11, 0), false, "A re-arm must wait for the ordinary bounded polls");
assert.equal(policy.shouldRearmPending({ pending: true }, 12, 2), false, "Pending re-arms must remain finite");
assert.equal(policy.shouldRearmPending({ status: "no_match" }, 12, 0), false, "Terminal negative matches use the normal retry path");
assert.equal(policy.shouldRearmPending({ ok: true }, 12, 0), true, "Generic host envelopes should not permanently strand a row");
assert.equal(policy.pendingRearmDelayMs(1), 3500);
assert.equal(policy.pendingRearmDelayMs(2), 7000);
assert.equal(policy.shouldReuseActiveLane(7, 7, true, true), true);
assert.equal(policy.shouldReuseActiveLane(7, 8, true, true), false);
assert.equal(policy.shouldReuseActiveLane(7, 7, false, true), false);
assert.equal(policy.shouldReuseActiveLane(7, 7, true, false), false);
assert.equal(policy.ownsCurrentTrackLane("current", "current", {}, 0), true);
assert.equal(policy.ownsCurrentTrackLane("current", "current", null, 1), true);
assert.equal(policy.ownsCurrentTrackLane("current", "current", null, 0), false, "Past attempts alone must not keep the current row excluded");
assert.equal(policy.ownsCurrentTrackLane("current", "other", {}, 1), false);
assert.equal(policy.selectCandidates([{ id: "unsafe", title: {}, album: "A", artist: "B", cover_url: "x" }], 6).length, 1, "Malformed metadata fields should be treated as missing");
assert.equal(policy.selectCandidates([{ id: "placeholder", title: "Song", album: "未知专辑", artist: "未知歌手", cover_url: "x" }], 6).map(item => item.id).join(","), "placeholder", "Placeholder tags must remain eligible for metadata lookup");
assert.equal(policy.needsMetadata({ title: "Song", artist: "Artist", album: "Album", cover_url: "cover" }), false);
assert.equal(policy.needsMetadata({ title: "Song", artist: "未知歌手", album: "Album", cover_url: "cover" }), true);
assert.equal(policy.needsMetadata({ title: "Song", artist: "Artist", album: "Album" }), true);
assert.equal(policy.needsMetadata({ title: "Song", artist: "Artist", album: "Album", metadata_artwork_id: "a".repeat(64) }), false);
assert.equal(policy.needsMetadata({ title: "Song", artist: "Artist", album: "Album", metadata_artwork_id: "broken" }), true);
assert.equal(policy.needsMetadata(null), false);
const brokenMetadataRow = new Proxy({ id: "broken" }, { get(target, key) {
  if (key === "album") throw new Error("broken album");
  return target[key];
} });
assert.equal(policy.needsMetadata(brokenMetadataRow), true, "Broken metadata fields must remain eligible for recovery");
const brokenId = new Proxy({ title: "x" }, { get() { throw new Error("broken id"); } });
assert.equal(policy.selectCandidates([brokenId, { id: "ok", title: "", album: "", artist: "" }], 6).map(item => item.id).join(","), "ok", "A broken row must not abort later metadata candidates");
assert.equal(policy.selectCandidates([
  { id: "x".repeat(257), title: "", album: "", artist: "" },
  { id: "ok-long-id-check", title: "", album: "", artist: "" },
], 6).map(item => item.id).join(","), "ok-long-id-check", "Overlong IDs must be rejected instead of colliding after truncation");
assert.doesNotThrow(() => policy.selectCandidates([{ id: "x", title: "" }], { valueOf() { throw new Error("limit"); } }));
// The bounded lane takes its budget before each row, so zero really means none
// and a skipped row cannot spend the allowance. Both sides of every boundary are
// pinned because the clamp, the cap, and the default are separate decisions.
const needy = (count) => Array.from({ length: count }, (_unused, index) => ({
  id: "needy-" + index, title: "", album: "", artist: "",
}));
const ids = (items) => Array.prototype.map.call(items, (item) => item.id).join(",");
assert.equal(policy.selectCandidates(needy(14), 0).length, 0, "A zero prefetch budget must select nothing");
assert.equal(ids(policy.selectCandidates(needy(14), 1)), "needy-0", "A budget of one must select exactly one");
assert.equal(ids(policy.selectCandidates(needy(14), 2)), "needy-0,needy-1");
assert.equal(policy.selectCandidates(needy(14), -5).length, 0, "A negative budget must clamp to nothing");
assert.equal(policy.selectCandidates(needy(14)).length, 6, "The default lane width is six rows");
assert.equal(policy.selectCandidates(needy(14), 30).length, 12, "The lane width is capped, not the candidate list");
assert.equal(
  ids(policy.selectCandidates([
    { id: "complete", title: "Song", cover_url: "x", album: "A", artist: "B" },
    null,
    { id: {}, title: "" },
    { id: "needy", title: "", album: "", artist: "" },
  ], 1)),
  "needy",
  "Rows that are skipped must not spend the bounded budget",
);
// A blank limit is an unset value, not zero: a bridge that hands over an empty
// field has to keep the default lane instead of switching metadata off.
assert.equal(policy.selectCandidates(needy(14), "").length, 6, "An empty-string limit must fall back to the default");
assert.equal(policy.selectCandidates(needy(14), "   ").length, 6, "A whitespace-only limit must fall back to the default");
assert.equal(ids(policy.selectCandidates(needy(14), "2")), "needy-0,needy-1", "A numeric string limit is still honoured");
assert.equal(policy.selectCandidates(needy(14), { valueOf() { throw new Error("limit"); } }).length, 6, "A hostile limit falls back to the default");
assert.equal(policy.shouldRetry(null, 0, "12"), true, "A numeric string attempt budget is honoured");
assert.equal(policy.shouldRetry(null, 0, ""), true, "A blank max-attempt value keeps the bounded retry window");
assert.equal(policy.shouldRetry(null, 0, 0), false, "An explicit zero attempt budget is respected");
// R205: a terminal provider verdict must not hand the page dedupe key straight
// back. On the real device the same visible no_match row was re-queued about
// every 780 ms for as long as the page stayed up, which is permanent background
// traffic for a row that is never going to match.
assert.equal(policy.terminalNegativeCooldownMs({ status: "no_match" }), 30000,
  "A terminal no_match gets the default cooldown");
assert.equal(policy.terminalNegativeCooldownMs({ status: "FAILED" }), 30000,
  "A terminal failure is case-insensitive and cooled the same way");
assert.equal(policy.terminalNegativeCooldownMs({ status: "pending" }), 0,
  "Pending work keeps the immediate release: the poll window still owns it");
assert.equal(policy.terminalNegativeCooldownMs({ status: "no_match", best: { id: 1 } }), 30000,
  "A terminal verdict with a stale projection is still cooled: the projection shape is not the exemption");
assert.equal(policy.terminalNegativeCooldownMs({ status: "no_match", image_url: "x" }), 30000,
  "Cover-only results are cooled too, the cover is already on the row");
assert.equal(policy.terminalNegativeCooldownMs({ status: "failed", candidates: [] }), 30000,
  "An empty candidate array is a verdict, not a reason to hammer the endpoint");
assert.equal(policy.terminalNegativeCooldownMs({ retryable: true }, 30000, { informative: false }), 30000,
  "A retryable verdict means ask again later, not ask again now");
assert.equal(policy.terminalNegativeCooldownMs({ status: "success", best: { id: 1 } }, 30000, { recoverable: true }), 30000,
  "A filename fallback that may gain an album later is cooled instead of re-requested at once");
assert.equal(policy.terminalNegativeCooldownMs({ status: "no_match", best: { id: 1 } }, 30000, { informative: true }), 0,
  "A lookup that actually filled the row stays immediately eligible");
assert.equal(policy.terminalNegativeCooldownMs({ status: "no_match" }, 30000, null), 30000,
  "A missing decision falls back to the conservative cooldown");
assert.equal(policy.terminalNegativeCooldownMs(null), 0, "No payload releases immediately");
assert.equal(policy.terminalNegativeCooldownMs([]), 0, "An array payload is not a verdict");
assert.equal(policy.terminalNegativeCooldownMs({ get status() { throw new Error("status"); } }), 0,
  "A hostile status accessor cannot claim a cooldown");
assert.equal(policy.terminalNegativeCooldownMs({ status: "no_match" }, 999999), 300000,
  "A configured cooldown stays bounded");
assert.equal(policy.terminalNegativeCooldownMs({ status: "no_match" }, 0), 0,
  "An explicit zero switches the cooldown off, restoring immediate release");
assert.equal(policy.terminalNegativeCooldownMs({ status: "no_match" }, "abc"), 30000,
  "A non-numeric override falls back to the default instead of disabling it");
assert.equal(policy.releaseCompletedKey("k", { status: "no_match" }, () => true), true,
  "A cooled terminal key is retained and reported as handled");
assert.equal(policy.releaseCompletedKey("k", { status: "pending" }, () => true), false,
  "A pending result is not taken over by the cooldown lane");
let sunk = null;
assert.equal(policy.releaseCompletedKey("k", { status: "no_match" }, (key, ms) => { sunk = [key, ms]; return true; }), true,
  "The sink is the single place that learns the cooldown length");
assert.deepEqual(sunk, ["k", 30000], "The sink receives the key and the default cooldown");
assert.equal(policy.releaseCompletedKey("k", { status: "no_match" }, () => false), false,
  "A sink that refuses the key falls back to the immediate release");
assert.equal(policy.releaseCompletedKey("k", { status: "no_match" }, undefined), false,
  "Without a cooldown sink nothing may be retained");
assert.equal(policy.releaseCompletedKey("k", { best: { id: 1 } }, () => true), false,
  "A successful row is never cooled");
// Escalation: repeated nothing-gained verdicts for one row go quiet on their own.
assert.equal(policy.escalatedCooldownMs(30000, 0), 30000, "The first streak is the base window");
assert.equal(policy.escalatedCooldownMs(30000, 1), 30000, "and a streak of one is the same base window");
assert.equal(policy.escalatedCooldownMs(30000, 2), 60000, "the second nothing-gained verdict doubles it");
assert.equal(policy.escalatedCooldownMs(30000, 10), 300000, "ten streaks reach the five minute cap");
assert.equal(policy.escalatedCooldownMs(30000, 99), 300000, "and it never grows past the cap");
assert.equal(policy.escalatedCooldownMs(30000, "abc"), 30000, "a bogus streak falls back to one window");
  assert.equal(policy.escalatedCooldownMs(100000, 99), 300000, "an oversized base is still capped");
assert.equal(policy.escalatedCooldownMs(0, 5), 0, "a zero window stays off whatever the streak is");
// releaseCompletedKey owns the verdict, including the information-gain exemption.
assert.equal(policy.releaseCompletedKey("k", { status: "no_match", best: { id: 1 } }, () => true, { informative: false }), true,
  "A projection-bearing negative is handed to the cooldown lane");
assert.equal(policy.releaseCompletedKey("k", { status: "no_match", best: { id: 1 } }, () => true, { informative: true }), false,
  "but a lookup that filled the row is released for the next missing field");
let sunkRecoverable = null;
assert.equal(policy.releaseCompletedKey("k", { status: "success", best: { id: 1 } },
  (key, ms) => { sunkRecoverable = [key, ms]; return true; }, { recoverable: true }), true,
  "A recoverable filename verdict travels through the same sink");
assert.deepEqual(sunkRecoverable, ["k", 30000], "and the sink learns the window, not a payload-shape guess");
assert.equal(policy.releaseCompletedKey("k", { status: "success", best: { id: 1 } }, () => true, {}), false,
  "An authoritative match that is not marked recoverable is left to the caller");
console.log("Visible metadata prefetch policy regression checks passed.");
