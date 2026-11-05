// Base-sheet self-sufficiency: app.css must be able to paint the player on its
// own.  The theme layer restyles these glyphs too, but it is not guaranteed to
// be reachable — a stale cache, a blocked sheet or an older WebView that drops
// a construct all leave the page with app.css only.  When the transport fill
// lived exclusively in fnos-theme.css, that state painted a black triangle on
// the blue play button and a native #efefef seek rail on a dark bar.
const fs = require("node:fs");
const assert = require("node:assert/strict");

const appCss = fs.readFileSync("app/ui/app.css", "utf8");

function ruleBody(css, selector) {
  const index = css.indexOf(selector);
  assert.notEqual(index, -1, "missing rule: " + selector);
  let open = index + selector.length;
  while (open < css.length && /\s/.test(css[open])) open += 1;
  assert.equal(css[open], "{", "rule is not a plain declaration block: " + selector);
  const end = css.indexOf("}", open);
  assert.notEqual(end, -1, "unterminated rule: " + selector);
  return css.slice(open + 1, end);
}

// Collects every `@media(condition){...}` body in the sheet.  app.css repeats
// the same phone breakpoint many times, so callers must look across all of
// them rather than assume the first one owns a given rule.
function mediaBodies(css, condition) {
  const needle = "@media(" + condition + "){";
  const bodies = [];
  let from = 0;
  for (;;) {
    const index = css.indexOf(needle, from);
    if (index === -1) break;
    const start = index + needle.length;
    let depth = 0;
    let end = -1;
    for (let i = start; i < css.length; i += 1) {
      if (css[i] === "{") depth += 1;
      else if (css[i] === "}") {
        if (depth === 0) { end = i; break; }
        depth -= 1;
      }
    }
    assert.notEqual(end, -1, "unterminated media block: " + condition);
    bodies.push(css.slice(start, end));
    from = end + 1;
  }
  assert.ok(bodies.length, "missing media block: " + condition);
  return bodies;
}

// 1. The three transport glyphs are solid shapes and need their own fill.
const transport = ruleBody(appCss, ".player-button svg");
assert.match(transport, /fill:currentColor/, "transport glyphs must take their colour from the button");
assert.match(transport, /stroke:none/, "transport glyphs are filled, not stroked");
assert.doesNotMatch(transport, /fill:#/, "transport fill must stay a token, not a literal");

// 2. The missing-artwork record is stroked outline plus solid spindle.
const record = ruleBody(appCss, ".record-placeholder");
assert.match(record, /fill:none/, "the record outline must not be filled");
assert.match(record, /stroke:currentColor/, "the record outline takes the cover colour");
assert.match(ruleBody(appCss, ".record-placeholder-center"), /fill:currentColor/, "the record spindle is solid");

// 3. The phone seek rail must not depend on the theme layer.
const phone = mediaBodies(appCss, "max-width:760px");
const rail = phone.filter(body => /\.progress input\{[^}]*appearance:none/.test(body)
  && /\.progress input::-webkit-slider-runnable-track\{[^}]*--seek-fill/.test(body));
assert.equal(rail.length, 1, "exactly one phone block owns the seek rail");
assert.match(rail[0], /\.progress input::-webkit-slider-thumb\{[^}]*border-radius:50%/, "phone thumb is a dot, not the native handle");

// 4. The theme layer may restyle these, but it must not be the only place that
//    declares the paint.  Keep the base declaration and the theme declaration
//    in agreement so neither layer drifts.
const themeCss = fs.readFileSync("app/ui/fnos-theme.css", "utf8");
assert.match(ruleBody(themeCss, ".player-button .transport-icon"), /fill: currentColor/, "theme keeps the same contract");

console.log("base sheet paint contract ok");
