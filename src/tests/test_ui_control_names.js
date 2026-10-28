const assert = require("node:assert/strict");
const fs = require("node:fs");

// R140 deep read of src/app/ui/index.html (TODO.md:99 欠读面). The document declares 92
// form controls; 5 of them resolved to an empty accessible name under every source the
// accname algorithm falls back to (aria-labelledby, aria-label, <label for>, the text of a
// wrapping <label>, button text, title, placeholder), so a screen reader announced them as
// a bare role: "slider" / "checkbox" with nothing to say what is being seeked, what volume
// is being set, or which of the three share options is being switched.
//
// The two range sliders have no text alternative available at all: an input[type=range]
// ignores placeholder, and #seek sits between #elapsed and #duration, which hold times
// rather than a label. The three switches are wrapped in <label class="switch-control">
// whose only child is the empty <span> the stylesheet paints as the pill, so the wrapping
// label contributes an empty string (app.css: .switch-control input{opacity:0} and
// .switch-control span{position:absolute;inset:0} -- putting copy inside that span would
// render on top of the pill and break it).
const html = fs.readFileSync("app/ui/index.html", "utf8");

const CONTROL_RE = /<(button|input|select|textarea)\b([^>]*)>/gi;
const LABEL_RE = /<label\b[^>]*>([\s\S]*?)<\/label>/gi;
const ANY_ID_RE = /\bid="([^"]+)"/g;

function attrs(raw) {
  const out = {};
  for (const m of raw.matchAll(/([\w:.-]+)\s*=\s*"([^"]*)"/g)) out[m[1].toLowerCase()] = m[2];
  return out;
}
function stripTags(fragment) {
  return fragment
    .replace(/<svg\b[\s\S]*?<\/svg>/gi, " ")
    .replace(/<[^>]*>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

const ids = [];
for (const m of html.matchAll(ANY_ID_RE)) ids.push(m[1]);
const seen = new Set();
const duplicated = [];
for (const id of ids) {
  if (seen.has(id)) duplicated.push(id);
  seen.add(id);
}
assert.deepEqual(duplicated, [], "index.html must not declare an id twice: 144 ids were unique before R140");

const labels = [];
for (const m of html.matchAll(LABEL_RE)) labels.push({ start: m.index, end: m.index + m[0].length, text: stripTags(m[1]) });

function enclosingLabel(offset) {
  let found = null;
  for (const label of labels) {
    if (label.start <= offset && offset < label.end) {
      if (!found || label.start > found.start) found = label;
    }
  }
  return found;
}
function elementText(id) {
  const m = html.match(new RegExp(`<[a-zA-Z][^>]*\\bid="${id}"[^>]*>([\\s\\S]*?)<\\/[a-zA-Z]+>`));
  return m ? stripTags(m[1]) : "";
}

function accessibleName(tag, attr, offset, innerText) {
  if (attr["aria-labelledby"]) {
    const named = attr["aria-labelledby"]
      .split(/\s+/)
      .filter(Boolean)
      .map((ref) => {
        assert.ok(seen.has(ref), `aria-labelledby="${ref}" must resolve to an id that exists in index.html`);
        return elementText(ref);
      })
      .join(" ")
      .trim();
    if (named) return { name: named, source: "aria-labelledby" };
  }
  if (attr["aria-label"] && attr["aria-label"].trim()) return { name: attr["aria-label"].trim(), source: "aria-label" };
  const label = enclosingLabel(offset);
  if (label && label.text) return { name: label.text, source: "wrapping <label>" };
  if (tag === "button" && innerText) return { name: innerText, source: "button text" };
  if (attr.title && attr.title.trim()) return { name: attr.title.trim(), source: "title" };
  if (attr.placeholder && attr.placeholder.trim()) return { name: attr.placeholder.trim(), source: "placeholder" };
  return { name: "", source: "" };
}

const controls = [];
for (const m of html.matchAll(CONTROL_RE)) {
  const tag = m[1].toLowerCase();
  const attr = attrs(m[2]);
  if (attr.type === "hidden") continue;
  const close = html.indexOf(`</${tag}>`, m.index + m[0].length);
  const innerText = close >= 0 ? stripTags(html.slice(m.index + m[0].length, close)) : "";
  const resolved = accessibleName(tag, attr, m.index, innerText);
  controls.push({ tag, attr, offset: m.index, ...resolved });
}
assert.equal(controls.length, 100, "index.html declares 100 visible form controls, including independent metadata and DLNA save actions");
assert.equal(controls.find(control => control.attr.id === "saveMetadataTagSettingsBtn")?.name, "保存 Tag 写回设置");

const nameless = controls.filter((control) => !control.name).map((control) => control.attr.id || control.tag);
assert.deepEqual(nameless, [], `every control in index.html needs an accessible name, these have none: ${nameless.join(", ")}`);

// Settings panels use aria-labelledby for their tab relationship. Keep the tab
// ids explicit so assistive technology can announce the active settings page
// instead of receiving a panel with an unresolved label reference.
for (const [paneId, tabId] of [
  ["settings-pane-library", "settings-tab-library"],
  ["settings-pane-playback", "settings-tab-playback"],
  ["settings-pane-metadata", "settings-tab-metadata"],
  ["settings-pane-dlna", "settings-tab-dlna"],
  ["settings-pane-runtime", "settings-tab-runtime"],
]) {
  assert.match(
    html,
    new RegExp(`<section[^>]*id="${paneId}"[^>]*aria-labelledby="${tabId}"`),
    `#${paneId} must be labelled by #${tabId}`,
  );
  assert.match(
    html,
    new RegExp(`<button[^>]*id="${tabId}"[^>]*aria-controls="${paneId}"`),
    `#${tabId} must target #${paneId}`,
  );
}

// The two sliders are the only range inputs in the document, and neither has any fallback
// left to fall through to, so pin them by hand rather than relying on the sweep above.
for (const [id, name] of [["seek", "播放进度"], ["volume", "音量"]]) {
  const slider = controls.find((control) => control.attr.id === id);
  assert.ok(slider, `#${id} must stay in index.html`);
  assert.equal(slider.tag, "input");
  assert.equal(slider.attr.type, "range", `#${id} is expected to stay a range input`);
  assert.equal(slider.attr["aria-label"], name, `#${id} needs this exact name: nothing else in the row labels it`);
  assert.equal(slider.source, "aria-label");
}

// Each share switch is named by the <strong> the sighted user reads, so the copy has one
// owner. Duplicating the string in an aria-label would let the two drift apart.
const SWITCH_ROWS = [
  ["shareExpiryEnabled", "shareExpiryLabel", "到期时间"],
  ["sharePasswordEnabled", "sharePasswordLabel", "密码"],
  ["shareAccessEnabled", "shareAccessLabel", "可访问次数"],
];
for (const [inputId, labelId, text] of SWITCH_ROWS) {
  const toggle = controls.find((control) => control.attr.id === inputId);
  assert.ok(toggle, `#${inputId} must stay in index.html`);
  assert.equal(toggle.attr.type, "checkbox");
  assert.ok(!toggle.attr["aria-label"], `#${inputId} must be labelled by the visible row copy, not by a second string`);
  assert.equal(toggle.attr["aria-labelledby"], labelId);
  assert.equal(toggle.source, "aria-labelledby");
  assert.equal(toggle.name, text, `#${inputId} must announce the row heading it controls`);
  assert.ok(html.includes(`id="${labelId}">${text}</strong>`), `#${labelId} has to stay on the <strong> that shows "${text}"`);
}

// Guard the shape this fix deliberately did not touch: the pill is drawn from the empty
// span, so "fixing" the name by filling the label with copy would break the rendering.
assert.equal(
  (html.match(/<label class="switch-control">(?:(?!<\/label>)[\s\S])*?<span><\/span><\/label>/g) || []).length,
  3,
  "the three switches must keep their pill span empty"
);

// The keyboard path the deep read confirmed already exists (app.js binds Enter/Space for
// the only role="button" div), so the ARIA wiring it depends on must not be dropped.
assert.match(html, /<div class="now-playing" id="nowPlayingSummary" role="button" tabindex="0"/,
  "#nowPlayingSummary keeps the role/tabindex pair its Enter and Space handler needs");

console.log(`index.html control names: ${controls.length} controls, 0 nameless, 3 labelledby rows, 1 keyboard role kept`);
