const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const app = fs.readFileSync("app/ui/app.js", "utf8");

function region(startMarker, endMarker) {
  const start = app.indexOf(startMarker);
  const end = app.indexOf(endMarker, start);
  assert.ok(start >= 0 && end > start, `cover-source region missing: ${startMarker}`);
  return app.slice(start, end);
}

const source = [
  region("function mediaUrl(", "function coverUrl("),
  region("function coverUrl(", "function usableCoverSource("),
  region("function usableCoverSource(", "function resetPlaybackProgress("),
].join("\n");
const DOCUMENT = "http://nas.local:8000/app/index.html";
// A `vm` context has the language intrinsics but not the host web globals, so
// URL has to be injected: without it every parse throws into the catch and the
// rejection assertions would pass for the wrong reason.
const context = { window: { location: { href: DOCUMENT } }, URL };
vm.runInNewContext(
  `${source}\nglobalThis.mediaUrl = mediaUrl; globalThis.coverUrl = coverUrl; globalThis.usableCoverSource = usableCoverSource;`,
  context,
);

// The contract of both helpers is "an address the <img> can load, or the empty
// string", and every consumer branches on that emptiness. mediaUrl() answers a
// rejected scheme with "", but `new URL("", base)` does not throw: it resolves
// to the base itself. Re-parsing that empty string therefore turns "unusable"
// into a truthy address pointing at the application document.
const rejectedSchemes = [
  "file:///etc/passwd",
  "javascript:alert(1)",
  "data:image/png;base64,AA",
  "ftp://nas.example/a.png",
  "blob:http://nas.example/a.png",
];
for (const value of rejectedSchemes) {
  assert.equal(context.mediaUrl(value), "", `fixture must be one mediaUrl rejects: ${value}`);
  assert.equal(context.usableCoverSource(value), "", `usableCoverSource must keep ${value} unusable`);
  assert.equal(context.coverUrl({ cover_url: value }, 512), "", `coverUrl must keep ${value} unusable`);
  assert.equal(
    context.coverUrl({ cover_thumbnail_url: value, cover_url: "" }, 160), "",
    `coverUrl must keep ${value} unusable through the thumbnail field as well`,
  );
}

// Consequence worth pinning: two metadata lanes write a truthy result straight
// into item.cover_url/item.cover_thumbnail_url behind a `!item.cover_url`
// guard, so a poisoned value both renders as a broken tile forever and
// suppresses every later legitimate cover.
assert.notEqual(context.usableCoverSource("data:image/png;base64,AA"), DOCUMENT);
assert.notEqual(context.coverUrl({ cover_url: "file:///etc/passwd" }, 512), new URL(`${DOCUMENT}?size=512`).href);

// Positive controls: the rejection must not widen into the paths that work.
assert.equal(context.usableCoverSource("/api/cover/1?size=160"), "http://nas.local:8000/api/cover/1?size=160");
assert.equal(context.usableCoverSource("  https://img.example/a.png  "), "https://img.example/a.png");
assert.equal(context.coverUrl({ cover_url: "/api/cover/1" }, 512), "http://nas.local:8000/api/cover/1?size=512");
assert.equal(
  context.coverUrl({ cover_thumbnail_url: "/api/cover/1?t=1" }, 160),
  "http://nas.local:8000/api/cover/1?t=1&size=160",
);
assert.equal(context.coverUrl({ cover_url: "https://img.example/a.png" }, 0), "https://img.example/a.png");
assert.equal(context.usableCoverSource(""), "");
assert.equal(context.coverUrl({}, 512), "");

// The rejection matters because every metadata lane answers "does this item
// already carry artwork?" with `!item.cover_url`, so a truthy junk value both
// pins a broken tile and suppresses every later legitimate cover. The guard is
// part of the contract, so an unguarded write into ``item.cover_url`` fails here.
const appLines = app.split("\n");
let guardedWrites = 0;
for (let index = 0; index < appLines.length; index += 1) {
  if (!/^\s*item\.cover_url = /.test(appLines[index])) continue;
  const preceding = appLines.slice(Math.max(0, index - 2), index).join("\n");
  assert.ok(
    preceding.includes("!item.cover_url"),
    `item.cover_url assignment at line ${index + 1} must sit behind a !item.cover_url guard`,
  );
  guardedWrites += 1;
}
assert.ok(guardedWrites >= 5, `expected the metadata lanes to still write cover_url, saw ${guardedWrites}`);

console.log("Cover source rejection regression checks passed.");