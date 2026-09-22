const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

// R162 - the "library-response invalidation / keyed track-list commit / per-row
// patch" face of app.js (source lines 3401-3653 at intake, 9 named functions).
//
// Deep reading this face found a real, user-reachable defect in the one-sided
// branch of patchTrackRowNode():
//
//   renderTrack() emits the `.track-main` title cell only for the "title"
//   column, and the column dialog lets a user uncheck or re-check 标题 for any
//   scope (normalizeTrackColumns() filters against TRACK_COLUMN_DEFINITIONS and
//   only falls back to the defaults when nothing is left, so it never pins
//   "title"). When such a change is committed through the keyed path of
//   commitTrackListHtml(), the live row and the freshly rendered row disagree on
//   exactly one structural child, and this branch ran
//
//       currentMain?.replaceWith?.(nextMain);
//
//   in both directions:
//
//   (a) title removed -> nextMain is null. ChildNode.replaceWith() stringifies a
//       non-Node argument, so the live row gained a text node containing the
//       literal "null" where the title cell used to be;
//   (b) title re-added -> currentMain is null, the optional chain short-circuits,
//       and the new title cell is silently dropped.
//
//   Both outcomes are sticky rather than transient: state.renderedTrackListHtml
//   is then updated to markup the DOM does not match, and every later commit
//   re-enters this patch through the same rowChanged comparison and re-fails it
//   the same way, so the row never converges.
//
//   The fix edits the single node instead: remove the stale title cell, or adopt
//   the new one at its column ordinal, and let the existing cell pass finish.
//
//   Also settled by this suite (read-only, no production change):
//   - invalidateLibraryResponseForTrack() matches the cached shapes that exist
//     (api/library -> {items}, groups/folders -> no items), and it deliberately
//     does not advance libraryResponseEpoch: every one of its four call sites
//     only fills previously-empty INHERIT_FIELDS after writing state.itemCache,
//     and fnAudioLibraryMetadataMergePolicy.merge() re-applies exactly those
//     fields, so a superseded in-flight write-back cannot resurrect an old value.
//   - needsVisibleTrackCoverHydration()'s no-scheduler expression only inflates
//     coverHydrations; cover_load_scheduler.js ships in index.html, so the
//     scheduler is always constructed before this function can be consulted.

const uiDir = path.join(__dirname, "..", "app", "ui");
const appSource = fs.readFileSync(path.join(uiDir, "app.js"), "utf8");

function functionSource(name) {
  const match = appSource.match(new RegExp("^function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable for the track row patch regression`);
  return match[0];
}

const shipped = [
  "directTrackChild",
  "copyTrackRowAttributes",
  "preserveTrackCoverNode",
  "patchTrackRowNode",
  "trackRowComparableHtml",
  "invalidateLibraryResponseForTrack",
].map(functionSource).join("\n");

// --- minimal, spec-faithful DOM ------------------------------------------------
// replaceWith() deliberately applies the DOM spec's string conversion, which is
// what makes failure mode (a) observable at all.
let mutations = 0;
const innerHTMLWrites = [];
const isNode = value => !!value && typeof value === "object" && typeof value.nodeType === "number";

class TextNode {
  constructor(data) { this.nodeType = 3; this.data = String(data); this.parentNode = null; }
  get textContent() { return this.data; }
  remove() {
    mutations += 1;
    const parent = this.parentNode;
    if (parent) { parent.childNodes.splice(parent.childNodes.indexOf(this), 1); this.parentNode = null; }
  }
}

function parseCompound(compound) {
  const step = { tag: "", classes: [], attrs: [] };
  const re = /\[([^\]]+)\]|([.#][\w-]+)|([\w-]+)/g;
  let match;
  while ((match = re.exec(compound))) {
    if (match[1] !== undefined) {
      const inner = match[1];
      const eq = inner.indexOf("=");
      if (eq < 0) step.attrs.push([inner, null]);
      else step.attrs.push([inner.slice(0, eq), inner.slice(eq + 1).replace(/^["']|["']$/g, "")]);
    } else if (match[2] !== undefined) {
      if (match[2][0] === ".") step.classes.push(match[2].slice(1));
      else step.attrs.push(["id", match[2].slice(1)]);
    } else {
      step.tag = match[3].toUpperCase();
    }
  }
  return step;
}

class Element {
  constructor(tag, attrs = [], children = []) {
    this.nodeType = 1;
    this.tagName = String(tag).toUpperCase();
    this._attrs = new Map();
    this.childNodes = [];
    this.parentNode = null;
    attrs.forEach(([name, value]) => this._attrs.set(name, String(value)));
    children.forEach(child => this._append(child));
  }
  _append(child) {
    if (!isNode(child)) throw new Error("fixture only accepts nodes");
    if (child.parentNode) child.parentNode.childNodes.splice(child.parentNode.childNodes.indexOf(child), 1);
    child.parentNode = this;
    this.childNodes.push(child);
    return child;
  }
  get classList() {
    const self = this;
    const list = () => String(self._attrs.get("class") || "").split(/\s+/).filter(Boolean);
    return {
      contains: name => list().includes(name),
      remove: name => { const rest = list().filter(item => item !== name); self._attrs.set("class", rest.join(" ")); },
      add: name => { const next = list(); if (!next.includes(name)) next.push(name); self._attrs.set("class", next.join(" ")); },
    };
  }
  get children() { return this.childNodes.filter(node => node.nodeType === 1); }
  get attributes() { return [...this._attrs.entries()].map(([name, value]) => ({ name, value })); }
  get dataset() {
    const data = {};
    this._attrs.forEach((value, name) => {
      if (!name.startsWith("data-")) return;
      const key = name.slice(5).replace(/-([a-z])/g, (_, ch) => ch.toUpperCase());
      data[key] = value;
    });
    return data;
  }
  getAttribute(name) { return this._attrs.has(name) ? this._attrs.get(name) : null; }
  setAttribute(name, value) {
    mutations += 1;
    this._attrs.set(name, String(value));
  }
  removeAttribute(name) {
    if (!this._attrs.has(name)) return;
    mutations += 1;
    this._attrs.delete(name);
  }
  hasAttribute(name) { return this._attrs.has(name); }
  appendChild(child) { mutations += 1; return this._append(child); }
  insertBefore(child, reference) {
    mutations += 1;
    this._append(child);
    const index = this.childNodes.indexOf(child);
    this.childNodes.splice(index, 1);
    // Spec-faithful: a null reference appends at the end. Without this, a mutant
    // that drops the ordinal bound would be caught for the wrong reason.
    const at = reference === null || reference === undefined ? this.childNodes.length : this.childNodes.indexOf(reference);
    this.childNodes.splice(Math.max(0, at), 0, child);
    return child;
  }
  remove() {
    mutations += 1;
    const parent = this.parentNode;
    if (parent) { parent.childNodes.splice(parent.childNodes.indexOf(this), 1); this.parentNode = null; }
  }
  replaceWith(...args) {
    mutations += 1;
    const parent = this.parentNode;
    if (!parent) return;
    const index = parent.childNodes.indexOf(this);
    const replacements = args.map(arg => (isNode(arg) ? arg : new TextNode(arg)));
    parent.childNodes.splice(index, 1, ...replacements);
    replacements.forEach(node => { node.parentNode = parent; });
    this.parentNode = null;
  }
  _descendants(out = []) {
    this.childNodes.forEach(node => { if (node.nodeType === 1) { out.push(node); node._descendants(out); } });
    return out;
  }
  _matches(step) {
    if (step.tag && this.tagName !== step.tag) return false;
    if (!step.classes.every(name => this.classList.contains(name))) return false;
    return step.attrs.every(([name, value]) => (value === null ? this.hasAttribute(name) : this.getAttribute(name) === value));
  }
  querySelectorAll(selector) {
    const groups = String(selector).split(",").map(part => part.trim().split(/\s+/).map(parseCompound));
    return this._descendants().filter(node => groups.some(steps => {
      if (!node._matches(steps[steps.length - 1])) return false;
      let cursor = node.parentNode;
      for (let index = steps.length - 2; index >= 0; index -= 1) {
        while (cursor && !cursor._matches(steps[index])) cursor = cursor.parentNode;
        if (!cursor) return false;
        cursor = cursor.parentNode;
      }
      return true;
    }));
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  cloneNode(deep) {
    const copy = new Element(this.tagName, this.attributes.map(({ name, value }) => [name, value]));
    if (deep) this.childNodes.forEach(node => copy._append(node.nodeType === 1 ? node.cloneNode(true) : new TextNode(node.data)));
    return copy;
  }
  get innerHTML() { return this.childNodes.map(node => (node.nodeType === 1 ? node.outerHTML : node.data)).join(""); }
  set innerHTML(value) {
    // app.js legitimately rewrites .track-info / .track-cover markup (:3589,
    // :3592). The setter is therefore real rather than a tripwire, and each
    // case states its own contract: the row element and its .track-main child
    // must never be rewritten wholesale, which assertNoRowRewrite() checks.
    mutations += 1;
    innerHTMLWrites.push([this, String(value)]);
    this.childNodes.forEach(node => { node.parentNode = null; });
    this.childNodes = [];
    parseMarkup(String(value)).forEach(node => this._append(node));
  }
  get outerHTML() {
    const attrs = [...this._attrs.entries()].map(([name, value]) => ` ${name}="${value}"`).join("");
    return `<${this.tagName.toLowerCase()}${attrs}>${this.innerHTML}</${this.tagName.toLowerCase()}>`;
  }
}

function parseMarkup(markup) {
  // Inverse of the serializer above for the fixture alphabet (div/span/strong/img).
  const roots = [];
  const stack = [];
  const add = node => {
    if (stack.length) stack[stack.length - 1]._append(node);
    else roots.push(node);
  };
  const tagRe = /<(\/?)\s?([A-Za-z][\w-]*)((?:\s+[A-Za-z_:][-:\w.]*(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'=<>`]+))?)*)\s*(\/?)>/g;
  const attrRe = /([A-Za-z_:][-:\w.]*)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g;
  let cursor = 0;
  let match;
  while ((match = tagRe.exec(markup))) {
    if (match.index > cursor) add(new TextNode(markup.slice(cursor, match.index)));
    cursor = tagRe.lastIndex;
    const closing = match[1];
    const name = match[2].toUpperCase();
    const rawAttrs = match[3] || "";
    const selfClose = match[4];
    if (closing) {
      const open = stack.pop();
      if (!open || open.tagName !== name) throw new Error("fixture markup is not well formed near " + name);
      continue;
    }
    const attrs = [];
    let attr;
    while ((attr = attrRe.exec(rawAttrs))) attrs.push([attr[1], attr[2] ?? attr[3] ?? attr[4] ?? ""]);
    const element = new Element(name, attrs);
    add(element);
    if (!selfClose) stack.push(element);
  }
  if (cursor < markup.length) add(new TextNode(markup.slice(cursor)));
  if (stack.length) throw new Error("fixture markup left unclosed elements");
  return roots;
}

function el(tag, attrs = [], children = []) { return new Element(tag, attrs, children); }
function text(data) { return new TextNode(data); }
function childClasses(node) { return node.children.map(child => child.classList.contains("track-main") ? "track-main" : (child.getAttribute("class") || "").split(/\s+/)[0]); }
function textNodes(node) { return node.childNodes.filter(child => child.nodeType === 3); }
function assertNoRowRewrite(node, label) {
  const rewritten = innerHTMLWrites.filter(([target]) => target === node || target.classList?.contains("track-main"));
  assert.equal(rewritten.length, 0, `${label}: patchTrackRowNode() rewrote a row/title cell with innerHTML instead of patching the single node`);
}

const context = { state: {}, mutations: () => mutations, assert, Element, TextNode };
vm.runInNewContext(shipped + "\nthis.directTrackChild = directTrackChild; this.copyTrackRowAttributes = copyTrackRowAttributes; this.preserveTrackCoverNode = preserveTrackCoverNode; this.patchTrackRowNode = patchTrackRowNode; this.trackRowComparableHtml = trackRowComparableHtml; this.invalidateLibraryResponseForTrack = invalidateLibraryResponseForTrack;", context);
const { patchTrackRowNode, directTrackChild, trackRowComparableHtml, invalidateLibraryResponseForTrack } = context;

const coverImg = (src, extra = []) => el("img", [["data-cover-src", src], ["loading", "lazy"], ["decoding", "async"], ["alt", ""]].concat(extra), []);
const coverCell = src => el("div", [["class", "track-cover"]], [coverImg(src), el("span", [["class", "track-cover-fallback"]], [text("\u266b")])]);
const infoCell = title => el("div", [["class", "track-info"]], [el("div", [["class", "track-title-line"]], [el("strong", [["class", "track-title"]], [text(title)])])]);
const mainCell = (title, src = "/cover/a") => el("div", [["class", "track-main"], ["data-play", "a"]], [coverCell(src), infoCell(title)]);
const cell = (key, value) => el("span", [["class", `track-cell track-cell-${key}`]], [text(value)]);
const row = (children, signature = "sig") => el("div", [["class", "track"], ["data-track-row-key", "a::0"], ["data-track-row-signature", signature], ["data-track-id", "a"]], children);

const cases = [];
function test(name, body) { cases.push([name, body]); }

// 1. Title column unchecked: the live row must lose the cell, not gain "null".
test("removing the title column drops the cell without injecting a null text node", () => {
  const current = row([mainCell("Song A"), cell("duration", "3:12")]);
  const next = row([cell("duration", "3:12")]);
  patchTrackRowNode(current, next);
  assertNoRowRewrite(current, "title column removed");
  assert.equal(textNodes(current).length, 0, "patchTrackRowNode leaked a synthetic text node where the title cell was removed");
  assert.equal(directTrackChild(current, "track-main"), null);
  assert.equal(current.children.length, 1);
  assert.equal(current.children[0].outerHTML, next.children[0].outerHTML);
});

// 2. Title column re-checked: the row must actually adopt the new cell.
test("re-adding the title column inserts the cell into the live row", () => {
  const current = row([cell("duration", "3:12")]);
  const next = row([mainCell("Song A"), cell("duration", "3:12")]);
  patchTrackRowNode(current, next);
  assertNoRowRewrite(current, "title column re-added");
  const adopted = directTrackChild(current, "track-main");
  assert.ok(adopted, "the patched row never received the title cell renderTrack() asked for");
  assert.equal(childClasses(current).join("|"), "track-main|track-cell");
  assert.equal(adopted.querySelector(".track-title").childNodes[0].data, "Song A");
  assert.equal(adopted.parentNode, current);
});

// 3. The adopted cell keeps its position inside the column order.
test("re-adding the title column in the middle preserves the column order", () => {
  const current = row([cell("artist", "A"), cell("duration", "3:12")]);
  const next = row([cell("artist", "A"), mainCell("Song A"), cell("duration", "3:12")]);
  patchTrackRowNode(current, next);
  assertNoRowRewrite(current, "title column re-added in the middle");
  assert.equal(childClasses(current).join("|"), "track-cell|track-main|track-cell");
});

// 4. Convergence is stable: a second patch over the same markup writes nothing.
test("a converged row is patched again with zero DOM writes", () => {
  const current = row([cell("duration", "3:12")]);
  const signature = () => current.outerHTML;
  patchTrackRowNode(current, row([mainCell("Song A"), cell("duration", "3:12")]));
  const settled = signature();
  const before = mutations;
  patchTrackRowNode(current, row([mainCell("Song A"), cell("duration", "3:12")]));
  assertNoRowRewrite(current, "converged row re-patched");
  assert.equal(current.outerHTML, settled, "the second patch changed an already converged row");
  assert.equal(mutations, before, "the second patch wrote to the DOM even though nothing changed");
});

// 5. The symmetric path still preserves the decoded cover node identity.
test("a same-source cover survives a metadata patch unchanged", () => {
  const liveImage = coverImg("/cover/a");
  const current = row([el("div", [["class", "track-main"], ["data-play", "a"]], [el("div", [["class", "track-cover"]], [liveImage, el("span", [["class", "track-cover-fallback"]], [text("\u266b")])]), infoCell("Song A")]), cell("duration", "3:12")]);
  const next = row([mainCell("Song B"), cell("duration", "3:12")]);
  patchTrackRowNode(current, next);
  assertNoRowRewrite(current, "metadata-only patch");
  assert.equal(directTrackChild(current, "track-main").querySelector("img"), liveImage, "the decoded cover was replaced for a metadata-only change");
  assert.equal(directTrackChild(current, "track-main").querySelector(".track-title").childNodes[0].data, "Song B");
  assert.equal(textNodes(current).length, 0);
});

// 6. Non-track rows keep the wholesale replacement contract.
test("a group row is still replaced wholesale", () => {
  const current = el("div", [["class", "group"]], [text("old")]);
  const parent = el("section", [], [current]);
  const next = el("div", [["class", "group"]], [text("new")]);
  patchTrackRowNode(current, next);
  assert.equal(parent.children.length, 1);
  assert.equal(parent.children[0], next);
});

// 7. Reachability premises + the exact shape that caused the defect.
test("the title cell is conditional and no replaceWith is used on it", () => {
  assert.match(appSource, /const titleCell = `<div class="track-main"/, "renderTrack() must keep building the title cell conditionally");
  assert.match(appSource, /columns\.map\(key => key === "title" \? titleCell/, "the title cell must stay tied to the title column");
  const normaliser = functionSource("normalizeTrackColumns");
  assert.doesNotMatch(normaliser, /"title"/, "normalizeTrackColumns() must not pin the title column, or the asymmetric patch is unreachable");
  assert.doesNotMatch(appSource, /replaceWith\?\.\(nextMain\)/, "patchTrackRowNode() must never replaceWith() a possibly-null title cell");
  const adoptBranch = functionSource("patchTrackRowNode");
  assert.match(adoptBranch, /currentMain\.remove\(\)/, "the stale title cell must be removed outright");
  assert.match(adoptBranch, /mainOrdinal >= 0 && mainOrdinal < liveChildren\.length/, "the adopted title cell must stay inside the live child range");
  assert.match(adoptBranch, /current\.insertBefore\(nextMain, liveChildren\[mainOrdinal\]\)/, "the adopted title cell must keep its column ordinal");
});

// 8. The response invalidator matches exactly the cached shapes that exist.
test("invalidateLibraryResponseForTrack only evicts pages containing the track", () => {
  let predicate = null;
  context.state = { libraryResponseCache: { deleteWhere: fn => { predicate = fn; return 0; } } };
  invalidateLibraryResponseForTrack("7");
  assert.equal(typeof predicate, "function");
  assert.equal(predicate({ items: [{ id: "7" }] }), true);
  assert.equal(predicate({ items: [{ id: 7 }] }), true);
  assert.equal(predicate({ items: [{ id: "8" }] }), false);
  assert.equal(predicate({ groups: [{ id: "7" }] }), false);
  assert.equal(predicate({ folders: [{ root: "7" }] }), false);
  assert.equal(predicate({}), false);
  assert.equal(predicate(null), false);
  predicate = null;
  context.state = { libraryResponseCache: { deleteWhere: fn => { predicate = fn; return 0; } } };
  invalidateLibraryResponseForTrack("");
  assert.equal(predicate, null, "an empty track id must not touch the response cache");
});

// 9. The DOM guard treats transport-only cover state as unchanged presentation.
test("trackRowComparableHtml normalises cover transport state", () => {
  // renderTrack() emits data-cover-src first (app.js:3193); the scheduler then
  // appends its transport bookkeeping and a decoded cover hides the glyph. The
  // row signature lives on the row element itself, not on the title cell.
  const hydratedImage = el("img", [["data-cover-src", "/cover/a"], ["loading", "lazy"], ["decoding", "async"], ["alt", ""], ["src", "/cover/a"], ["data-cover-queued", "3"], ["data-cover-loaded-src", "/cover/a"], ["data-cover-observed", "1"]], []);
  const live = row([el("div", [["class", "track-main"], ["data-play", "a"]], [
    el("div", [["class", "track-cover"]], [hydratedImage, el("span", [["class", "track-cover-fallback"], ["hidden", ""]], [text("\u266b")])]),
    infoCell("Song A"),
  ]), cell("duration", "3:12")], "old");
  const fresh = row([mainCell("Song A"), cell("duration", "3:12")], "new");
  assert.notEqual(live.outerHTML, fresh.outerHTML, "the fixture must start out visibly different");
  assert.equal(trackRowComparableHtml(live), trackRowComparableHtml(fresh), "a hydrated cover still looked different to the DOM guard");
  assert.equal(trackRowComparableHtml(live), trackRowComparableHtml(live.cloneNode(true)), "the guard must not mutate the node it inspects");
});

let failures = 0;
for (const [name, body] of cases) {
  try { body(); } catch (error) { failures += 1; console.error(`FAIL ${name}\n  ${error.message}`); continue; }
  console.log(`ok   ${name}`);
}
if (failures) { console.error(`${failures} of ${cases.length} track row patch checks failed`); process.exit(1); }
console.log("track row patch regression checks passed.");
