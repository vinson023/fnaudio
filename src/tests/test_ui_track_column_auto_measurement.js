const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const app = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "app.js"), "utf8");
const start = app.indexOf("function measureTrackContentWidth(");
const end = app.indexOf("function measureAutoTrackColumnWidths(", start);
assert.ok(start >= 0 && end > start, "measureTrackContentWidth must stay before auto measurement");
const source = app.slice(start, end).trim();

const calls = [];
const constrained = {
  style: { cssText: "color: red" },
  scrollWidth: 320,
  cloneNode() {
    const probe = {
      style: { cssText: "color: red" },
      scrollWidth: 320,
      getBoundingClientRect() {
        calls.push(this.style.cssText);
        return { width: 147 };
      },
      remove() { calls.push("remove"); },
    };
    return probe;
  },
};
const document = {
  body: {
    appendChild(node) { calls.push(node); },
  },
};
const context = { document, Number, String };
vm.createContext(context);
vm.runInContext(`${source}\nthis.measureTrackContentWidth = measureTrackContentWidth;`, context);

assert.equal(context.measureTrackContentWidth(constrained), 147,
  "auto width must use the unconstrained max-content probe, not the ellipsized cell width");
assert.match(calls[1], /width:max-content/);
assert.match(calls[1], /overflow:visible/);
assert.equal(calls.at(-1), "remove", "the measurement probe must be removed after reading its width");

assert.equal(context.measureTrackContentWidth({}), 0, "malformed nodes must safely produce no width");

const fallbackCalls = [];
const legacyNode = {
  style: { cssText: "" },
  cloneNode() {
    const parentNode = { removeChild(node) { fallbackCalls.push(node); } };
    return {
      style: { cssText: "" },
      parentNode,
      getBoundingClientRect() { return { width: 91 }; },
    };
  },
};
const legacyContext = { document, Number, String };
vm.createContext(legacyContext);
vm.runInContext(`${source}\nthis.measureTrackContentWidth = measureTrackContentWidth;`, legacyContext);
assert.equal(legacyContext.measureTrackContentWidth(legacyNode), 91);
assert.equal(fallbackCalls.length, 1, "legacy WebView nodes must be removed through parentNode.removeChild");
