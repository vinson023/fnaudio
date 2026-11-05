// A stylesheet that fails to arrive stays failed for the whole page load: the
// browser does not re-request it.  Losing fnos-theme.css alone is the subtle
// case, because app.css and design-tokens.css still carry the layout and the
// palette — only the transport glyphs (SVG default black) and the phone seek
// rail (native #efefef control) betray it.  index.html therefore re-requests any
// sheet that produced no rules, once, with a fresh query.
//
// This guard pins the contract, not the wording.
const fs = require("node:fs");
const assert = require("node:assert/strict");

const html = fs.readFileSync("app/ui/index.html", "utf8");

const open = html.indexOf('<script id="stylesheet-retry">');
assert.notEqual(open, -1, "index.html must keep the stylesheet retry hook");
const close = html.indexOf("</script>", open);
assert.notEqual(close, -1, "the retry hook is unterminated");
const script = html.slice(open, close);

// The retry has to cover exactly the sheets the page links, or a dropped request
// to one of them silently keeps its broken rendering.
for (const name of ["app.css", "design-tokens.css", "fnos-theme.css"]) {
  assert.ok(
    script.includes("'" + name + "'"),
    "the retry list must include " + name + ", otherwise a dropped request to it is never repaired",
  );
}

// `link.sheet` is non-null even for an aborted request, so treating it as the
// success signal makes the whole hook a no-op.  The discriminator has to be the
// rule list, with the throw from an unparsed sheet treated as failure.
assert.ok(
  script.includes("link.sheet.cssRules.length > 0"),
  "the retry must decide from the rule list; link.sheet alone is non-null even when the request failed",
);
assert.match(
  script,
  /try \{\s*return link\.sheet\.cssRules\.length > 0;\s*\} catch \(error\) \{\s*return false;/,
  "an unparsed sheet throws on cssRules access and must count as not applied",
);

// A retry that can retry itself is an infinite loop on a genuinely missing file.
assert.ok(
  script.includes("setAttribute('data-fnaudio-retried', '1')"),
  "the replacement link must be marked so it is never retried again",
);
assert.ok(
  script.includes("if (link.getAttribute('data-fnaudio-retried') || applied(link)) continue;"),
  "a sheet that applied, and one already retried, must both be skipped",
);

// The retry must stay inside the original directory.  Rebuilding the URL from
// the bare file name would drop any prefix and turn the retry into a 404.
assert.ok(
  script.includes("'?retry=' + Date.now()") && script.includes("fresh.setAttribute('href', path + "),
  "the retried request must keep the original path and only add a cache-busting query",
);
assert.ok(
  !script.includes("fresh.setAttribute('href', base +"),
  "the retried request must not be rebuilt from the bare file name, which loses the directory",
);

// The replacement has to land in the same cascade position as the link it
// replaces: the theme layer only wins because it is the last sheet.
const insert = script.indexOf("insertBefore(fresh, link)");
const remove = script.indexOf("removeChild(link)");
assert.notEqual(insert, -1, "the retry must insert the replacement in place");
assert.notEqual(remove, -1, "the failed link must be removed, not left behind");
assert.ok(insert < remove, "insert the replacement before dropping the failed link");

// The Android client replaces all three <link> nodes with <style> elements, so
// the hook must find nothing and do nothing there instead of throwing.
assert.ok(
  script.includes("querySelectorAll('link[rel=\"stylesheet\"]')"),
  "the retry must discover sheets from the live <link> list so the inlined client page is a no-op",
);
