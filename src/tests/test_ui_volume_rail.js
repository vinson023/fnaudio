// R488: the volume popover's rail is a 3px line with a white-core handle, the
// same language the progress rail got in R484.  Three things can rot here, and
// each one has a guard below:
//
//   * the UA slider coming back (any `appearance: auto` / `slider-vertical`
//     makes the track and thumb unpaintable again, and every rule below it
//     silently stops applying);
//   * the fill stop drifting to the wrong end of the gradient, which paints the
//     rail full when the volume is low;
//   * the handle losing its negative *right* margin -- on a vertical slider a
//     negative left margin moves nothing, so the handle ends up 4.5px off its
//     rail, which is visible at 4x.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const app = fs.readFileSync("app/ui/app.js", "utf8");
const theme = fs.readFileSync("app/ui/fnos-theme.css", "utf8");

// The theme sheet is layered: a selector can appear twice and only the last copy
// paints.  Every lookup below reads the last match, except the geometry checks,
// which accept any copy that still declares the size.
function blocks(selector) {
  const pattern = new RegExp(selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\s*\\{([^}]*)\\}", "g");
  const matches = [...theme.matchAll(pattern)];
  assert.ok(matches.length, `${selector} must stay a rule in the theme sheet`);
  return matches.map(match => match[1]);
}
function block(selector) {
  const all = blocks(selector);
  return all[all.length - 1];
}
function functionSource(name) {
  const match = app.match(new RegExp("^function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable`);
  return match[0];
}

// ------------------------------------------------------------- the rebuild --
const slider = block(".volume-slider");
assert.match(slider, /appearance:\s*none\s*!important/, "the UA slider has to be switched off before anything can be painted");
assert.match(slider, /-webkit-appearance:\s*none\s*!important/);
assert.doesNotMatch(slider, /appearance:\s*auto/, "a leftover appearance:auto re-enables the UA paint and voids every rule below");
assert.doesNotMatch(slider, /slider-vertical/, "the UA vertical appearance cannot be styled at all");
assert.match(slider, /writing-mode:\s*vertical-rl\s*!important/, "vertical-rl is what makes a range input run bottom-to-top");
assert.match(slider, /direction:\s*rtl\s*!important/, "rtl puts the low end at the bottom");

// Geometry: the popover and the slider keep the sizes they had before R488.
const panelSizes = blocks(".volume-panel").filter(css => /width:\s*48px/.test(css));
assert.equal(panelSizes.length, 1, "the popover stays 48px wide");
assert.match(panelSizes[0], /height:\s*144px/, "the popover stays 144px tall");
assert.match(slider, /width:\s*24px\s*!important/, "the slider box stays 24px wide, so the drag target is unchanged");
assert.match(slider, /height:\s*112px\s*!important/);

// ----------------------------------------------------------------- the rail --
const track = block(".volume-slider::-webkit-slider-runnable-track");
assert.match(track, /width:\s*3px\s*!important/, "the rail is a 3px line");
assert.match(track, /height:\s*112px\s*!important/, "the rail spans the slider box");
assert.match(track, /var\(--ui-accent\)\s+0\s+var\(--volume-fill,\s*0%\)/,
  "the played part has to be the first stop, or the fill paints from the wrong end");
assert.match(track, /var\(--volume-rail\)\s+var\(--volume-fill,\s*0%\)\s+100%/,
  "everything above the fill is the empty rail");
assert.doesNotMatch(track, /rgba\(/, "the rail takes its colours from tokens, not from literals in the rule");

const thumb = block(".volume-slider::-webkit-slider-thumb");
assert.match(thumb, /width:\s*12px\s*!important/);
assert.match(thumb, /height:\s*12px\s*!important/);
assert.match(thumb, /margin-right:\s*-4\.5px\s*!important/,
  "a vertical thumb is centred with a negative right margin");
assert.doesNotMatch(thumb, /margin-left/, "a negative left margin moves nothing on a vertical slider and hides the real bug");
assert.match(thumb, /background:\s*var\(--ui-surface\)\s*!important/, "the core is the surface colour, so it reads on the accent band");
assert.match(thumb, /box-shadow:\s*0 0 0 2px var\(--ui-accent\)\s*!important/, "the ring is what makes the core read as a handle");

// The rail's neutral is its own token: a control is not a divider, and the
// divider colour is below the contrast where a 3px line reads at all.  It is
// mixed from --ui-text rather than written as a literal, so the theme file stays
// free of rgb() and the rail flips with the theme without a second branch.  The
// selector appears in several layers (base, phone override), so this looks for
// the declaration rather than the last block.
const railDecl = /--volume-rail:\s*color-mix\(in srgb,\s*var\(--ui-text\)\s*22%,\s*transparent\)/;
const railLight = blocks(".volume-panel").filter(css => railDecl.test(css));
assert.equal(railLight.length, 1, "the rail is declared once, from the text token");
assert.doesNotMatch(railLight[0], /rgba?\(/, "the rail is derived, not a literal");
assert.equal((theme.match(railDecl) || []).length, 1, "no per-theme duplicate of the rail colour");
assert.doesNotMatch(theme, /--volume-rail:\s*rgba?\(/, "a literal rail colour breaks the token-only theme contract");

// --------------------------------------------------------------- the wiring --
assert.ok(app.includes("function updateVolumeRail"), "the fill is written by updateVolumeRail");
assert.match(app, /\$\("volume"\)\.oninput = e => \{[\s\S]{0,240}updateVolumeRail\(value\);/,
  "dragging the slider has to repaint the rail");
assert.match(app, /if \(\$\("volume"\)\) \$\("volume"\)\.value = "1";\s*\n(?:\/\/[^\n]*\n)*updateVolumeRail\(\);/,
  "boot pushes the initial value once, or the popover opens with an empty rail");

const updateSource = functionSource("updateVolumeRail");
assert.match(updateSource, /setStyleVarIfChanged\(\$\("volume"\),\s*"--volume-fill"/,
  "the property is written on the input: the track pseudo-element inherits from it");
assert.match(updateSource, /Math\.min\(1,\s*Math\.max\(0,\s*value\)\)/, "a restored or out-of-range value cannot paint past either end");

// ------------------------------------------------------------- the behaviour --
const writes = [];
const inputNode = {
  style: {
    _props: new Map(),
    getPropertyValue(name) { return this._props.get(name) || ""; },
    setProperty(name, value) { this._props.set(name, value); writes.push([name, value]); },
  },
};
const context = {
  $: id => (id === "volume" ? inputNode : null),
  writes,
};
context.setStyleVarIfChanged = (node, name, value) => {
  if (!node || !node.style) return;
  const text = String(value ?? "");
  if (node.style.getPropertyValue(name) === text) return;
  node.style.setProperty(name, text);
};
vm.runInNewContext(
  functionSource("setStyleVarIfChanged") + "\n" + functionSource("updateVolumeRail") + "\nthis.updateVolumeRail = updateVolumeRail;",
  context,
);

context.updateVolumeRail(0.62);
assert.deepEqual(writes.at(-1), ["--volume-fill", "62%"], "62% of the way up is 62% of the rail");
context.updateVolumeRail(1);
assert.deepEqual(writes.at(-1), ["--volume-fill", "100%"]);
context.updateVolumeRail(0);
assert.deepEqual(writes.at(-1), ["--volume-fill", "0%"], "zero still writes: the rail must collapse, not keep the last value");
const before = writes.length;
context.updateVolumeRail(0);
assert.equal(writes.length, before, "a repeat value is not written twice");
context.updateVolumeRail(1.4);
assert.deepEqual(writes.at(-1), ["--volume-fill", "100%"], "above the range clamps instead of overflowing the gradient");
context.updateVolumeRail(-0.3);
assert.deepEqual(writes.at(-1), ["--volume-fill", "0%"], "below the range clamps to empty");

// Called with no argument it reads the slider, which is what boot does.
inputNode.value = "0.05";
context.updateVolumeRail();
assert.deepEqual(writes.at(-1), ["--volume-fill", "5%"], "the default argument reads the slider's own value");

console.log("test_ui_volume_rail: ok");
