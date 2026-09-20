const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "library_pager_visibility.js"), "utf8");
const context = { globalThis: {}, console };
vm.runInNewContext(source, context);
const update = context.globalThis.fnAudioLibraryPagerVisibility.updateMobilePagerVisibility;
function pager(hasPager) {
  return { classList: { values: new Set(), toggle(name, value) { value ? this.values.add(name) : this.values.delete(name); }, contains(name) { return this.values.has(name); } }, querySelector() { return hasPager ? {} : null; } };
}
const list = { scrollHeight: 100, clientHeight: 40, scrollTop: 60 };
const target = pager(true);
let frames = 0;
update({ isMobile: true, pager: target, list, requestFrame: (fn) => { frames += 1; fn(); } });
assert.equal(target.classList.contains("mobile-visible"), true);
assert.equal(frames, 1);
assert.equal(list.scrollTop, 100);
const hidden = pager(true);
update({ searchActive: true, isMobile: true, pager: hidden, list });
assert.equal(hidden.classList.contains("mobile-visible"), false);
console.log("Library pager visibility regression checks passed.");
