/* The bridge that drives fnOS's own 「分享外部链接」 panel.

The panel is private to the file manager, so the player opens it the way a person
would: search the song, right-click its row, click the menu item. These tests pin
each of those lookups against a fake document, and pin the order the player uses
them in — the whole thing degrades to the built-in panel, so a silently wrong
order would look like "native panel sometimes just doesn't open".
*/
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.resolve(__dirname, "..");
const source = fs.readFileSync(path.join(root, "app/ui/native_share_bridge.js"), "utf8");
const app = fs.readFileSync(path.join(root, "app/ui/app.js"), "utf8");
const html = fs.readFileSync(path.join(root, "app/ui/index.html"), "utf8");

const sandbox = { console };
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(source, sandbox);
const bridge = sandbox.fnAudioNativeShare;
assert.ok(bridge, "the bridge must publish fnAudioNativeShare");

// ---- fake DOM ---------------------------------------------------------------

function makeView() {
  class FakeEvent {
    constructor(type, init) {
      this.type = type;
      this.bubbles = Boolean(init && init.bubbles);
    }
  }
  class FakeMouseEvent extends FakeEvent {
    constructor(type, init) {
      super(type, init);
      Object.assign(this, init || {});
    }
  }
  class FakeKeyboardEvent extends FakeMouseEvent {}
  class FakeInput {}
  Object.defineProperty(FakeInput.prototype, "value", {
    get() { return this._value; },
    set(next) { this._value = next; },
  });
  return { Event: FakeEvent, MouseEvent: FakeMouseEvent, KeyboardEvent: FakeKeyboardEvent, HTMLInputElement: FakeInput };
}

const view = makeView();

function makeElement(options = {}) {
  const { text = "", width = 120, height = 24, placeholder = "", value = "" } = options;
  const events = [];
  const children = [];
  const element = {
    textContent: text,
    value,
    children,
    events,
    getAttribute: name => (name === "placeholder" ? placeholder : null),
    getBoundingClientRect: () => ({ x: 40, y: 60, width, height }),
    dispatchEvent: event => { events.push(event); return true; },
    focus: () => { element.focused = true; },
    contains: other => children.includes(other),
    ownerDocument: { defaultView: view },
  };
  return element;
}

function makeDocument(buckets) {
  return {
    querySelectorAll: selector => buckets[selector] || [],
  };
}

// ---- searchTerm -------------------------------------------------------------

assert.equal(bridge.searchTerm("GALA - 水手公园.flac"), "GALA - 水手公园");
assert.equal(bridge.searchTerm("074. Cody Johnson - 'Til You Can't.mp3"), "074. Cody Johnson - 'Til");
assert.equal(bridge.searchTerm("no-extension"), "no-extension");
assert.equal(bridge.searchTerm("  spaced.mp3  "), "spaced");
assert.equal(bridge.searchTerm(".hidden"), ".hidden");
assert.equal(bridge.searchTerm(""), "");
assert.equal(bridge.searchTerm(null), "");
assert.ok(bridge.searchTerm("x".repeat(80)).length === 24, "long names must be cut to the search limit");

// ---- findSearchInput --------------------------------------------------------

{
  const hidden = makeElement({ placeholder: "搜索", width: 0 });
  const other = makeElement({ placeholder: "请输入密码" });
  const search = makeElement({ placeholder: "搜索" });
  const doc = makeDocument({ input: [hidden, other, search] });
  assert.equal(bridge.findSearchInput(doc), search, "only the visible 搜索 field counts");
  assert.equal(bridge.findSearchInput(makeDocument({})), null);
  assert.equal(bridge.findSearchInput(null), null);
}

// ---- hasTable ---------------------------------------------------------------

{
  const rendered = makeElement({ text: "GALA - 水手公园.flac" });
  const hidden = makeElement({ text: "GALA - 水手公园.flac", width: 0 });
  assert.equal(bridge.hasTable(makeDocument({ ".trim-ui__table--td": [rendered] })), true);
  assert.equal(bridge.hasTable(makeDocument({ ".trim-ui__table--td": [hidden] })), false,
    "an unrendered table is not a table we can read");
  assert.equal(bridge.hasTable(makeDocument({})), false, "a shell with other markup reads as no table");
  assert.equal(bridge.hasTable(null), false);
}

// ---- findRowCell ------------------------------------------------------------

{
  const song = makeElement({ text: "GALA - 水手公园.flac" });
  const live = makeElement({ text: "GALA - 水手公园 (Live).flac" });
  const offscreen = makeElement({ text: "GALA - 水手公园.flac", width: 0 });
  const doc = makeDocument({ ".trim-ui__table--td": [live, offscreen, song] });
  assert.equal(bridge.findRowCell(doc, "GALA - 水手公园.flac"), song, "the cell text must match whole");
  assert.equal(bridge.findRowCell(doc, "GALA"), null, "a partial name is not the row");
  assert.equal(bridge.findRowCell(doc, ""), null);
}

// ---- findMenuItem -----------------------------------------------------------

{
  const inner = makeElement({ text: "分享外部链接" });
  const wrapper = makeElement({ text: "分享外部链接" });
  wrapper.children.push(inner);
  const otherItem = makeElement({ text: "详细信息" });
  const doc = makeDocument({ "div,span,li,button,a": [wrapper, inner, otherItem] });
  assert.equal(bridge.findMenuItem(doc, "分享外部链接"), inner, "the innermost node is the click target");
  assert.equal(bridge.findMenuItem(doc, "创建外部链接"), null);
}

// ---- typeInto ---------------------------------------------------------------

{
  const input = makeElement({ placeholder: "搜索" });
  assert.equal(bridge.typeInto(input, "GALA - 水手公园"), true);
  assert.equal(input.focused, true, "the field must take focus before typing");
  assert.equal(input._value, "GALA - 水手公园", "the framework setter must be the one that writes");
  const kinds = input.events.map(event => event.type);
  assert.deepEqual(kinds, ["input", "keydown", "keyup"], "input then Enter, so the search actually runs");
  assert.equal(input.events[1].key, "Enter");
  assert.equal(bridge.typeInto(null, "x"), false);
}

// ---- openContextMenu --------------------------------------------------------

{
  const cell = makeElement({ text: "GALA - 水手公园.flac" });
  assert.equal(bridge.openContextMenu(cell), true);
  assert.deepEqual(cell.events.map(event => event.type), ["mousedown", "mouseup", "contextmenu"]);
  cell.events.forEach(event => {
    assert.equal(event.button, 2, "the press must be the right button");
    assert.equal(event.bubbles, true);
    assert.ok(event.clientX >= 40 && event.clientX <= 160, "the press must land inside the row");
  });
  const flat = makeElement({ width: 0 });
  assert.equal(bridge.openContextMenu(flat), false, "an unrendered row cannot be right-clicked");
}

// ---- activate ---------------------------------------------------------------

{
  const item = makeElement({ text: "分享外部链接" });
  assert.equal(bridge.activate(item), true);
  assert.deepEqual(item.events.map(event => event.type), ["mouseover", "mousedown", "mouseup", "click"]);
  item.events.forEach(event => assert.equal(event.button, 0));
}

// ---- raiseHostWindow --------------------------------------------------------

function functionSource(name) {
  const match = app.match(new RegExp("^(?:async )?function " + name + "\\([^]*?^}", "m"));
  assert.ok(match, `app.js has no function ${name}`);
  return match[0];
}

{
  const events = [];
  class FakeMouseEvent {
    constructor(type, init) { this.type = type; Object.assign(this, init || {}); }
  }
  const frame = {
    ownerDocument: { defaultView: { MouseEvent: FakeMouseEvent } },
    dispatchEvent: event => { events.push(event); return true; },
  };
  const hosted = { window: { frameElement: frame }, MouseEvent: FakeMouseEvent, console };
  hosted.globalThis = hosted;
  vm.createContext(hosted);
  vm.runInContext(functionSource("raiseHostWindow"), hosted);
  assert.equal(hosted.raiseHostWindow(), true);
  assert.deepEqual(events.map(event => event.type), ["mousedown", "mouseup"],
    "the desktop raises a window on a press, so both halves are sent");
  assert.ok(events.every(event => event.bubbles === true), "the press must bubble to the window frame");

  const plain = { window: { frameElement: null }, MouseEvent: FakeMouseEvent, console };
  plain.globalThis = plain;
  vm.createContext(plain);
  vm.runInContext(functionSource("raiseHostWindow"), plain);
  assert.equal(plain.raiseHostWindow(), false, "a plain tab has no frame to press");
}

// ---- the player's order -----------------------------------------------------

assert.match(app, /const bridge = globalThis\.fnAudioNativeShare;/);
assert.match(app, /const shell = parentShellDocument\(\);/);
assert.match(app, /try \{\s*const shell = window\.parent;[\s\S]{0,220}\} catch \(error\) \{\s*return null;/, "a cross-origin parent must read as null, not throw");

const shareBody = app.slice(app.indexOf("async function shareTrack("), app.indexOf("async function createExternalShareLink("));
assert.ok(shareBody.indexOf("openNativeExternalShare(location)") >= 0, "shareTrack must try the native panel");
assert.ok(shareBody.indexOf("openNativeExternalShare(location)") < shareBody.indexOf('$("externalShareDialog").showModal()'),
  "the built-in panel is the fallback, so it must come after the native attempt");

// The failed attempt leaves the file manager in front of the player, so the
// fallback panel has to raise the player's own window first or it opens unseen.
const raiseAt = shareBody.indexOf("raiseHostWindow()");
assert.ok(raiseAt > shareBody.indexOf("openNativeExternalShare(location)"),
  "raising the window belongs to the failed hand-off, not to every share");
assert.ok(raiseAt < shareBody.indexOf('$("externalShareDialog").showModal()'),
  "the window must be raised before the panel opens, not after");

const nativeBody = app.slice(app.indexOf("async function openNativeExternalShare("), app.indexOf("async function openExternalShareInFileManager("));
// R500 moved "find the row" into findNativeFileRow (shared with 打开包含的文件夹),
// so the share path is now: open the folder, find that file's row, right-click it,
// click the menu item.
const order = [
  'runTrimHostAction("openFileManager"',
  "findNativeFileRow(shell, location)",
  "openContextMenu",
  'findMenuItem(shell, "分享外部链接")',
  "activate(menuItem)",
].map(token => nativeBody.indexOf(token));
order.forEach((at, index) => {
  assert.ok(at >= 0, `missing step: ${index}`);
  if (index > 0) assert.ok(at > order[index - 1], `step ${index} is out of order`);
});
assert.ok(!/findRowCell|typeInto/.test(nativeBody),
  "the share path shares the locate step instead of searching on its own");

// The right press goes to the name cell, which is where the file manager's own
// menu opens from; a shell with different columns still gets a usable target.
assert.match(nativeBody, /openContextMenu\(bridge\.nameCellOf\(row\) \|\| row\)/);

// The module has to be loaded before app.js runs.
const moduleTag = html.indexOf("native_share_bridge.js");
const appTag = html.indexOf("app.js?v=");
assert.ok(moduleTag > 0 && moduleTag < appTag, "native_share_bridge.js must load before app.js");

console.log("native share bridge: all assertions passed");
