const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

const ui = path.join(__dirname, "..", "app", "ui");
const app = fs.readFileSync(path.join(ui, "app.js"), "utf8");
const css = fs.readFileSync(path.join(ui, "app.css"), "utf8");

// Only the DOM boundary is doubled: execute the actual provider/result renderers.
class Element {
  constructor(tagName) {
    this.tagName = tagName;
    this.className = "";
    this.dataset = {};
    this.attributes = {};
    this.children = [];
    this.hidden = false;
  }
  // The renderer tags the fixed fallback row's order pair through classList.
  get classList() {
    const owner = this;
    return {
      add(name) { if (!owner.className.split(" ").includes(name)) owner.className = `${owner.className} ${name}`.trim(); },
      remove(name) { owner.className = owner.className.split(" ").filter(item => item && item !== name).join(" "); },
      toggle(name, force) { force ? this.add(name) : this.remove(name); },
      contains(name) { return owner.className.split(" ").includes(name); },
    };
  }
  append(...nodes) {
    for (const node of nodes) {
      node.parentElement = this;
      this.children.push(node);
    }
  }
  replaceChildren(...nodes) { this.children = []; this.append(...nodes); }
  addEventListener() {}
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name] ?? null; }
  querySelector(selector) {
    for (const child of this.children) {
      if (selector === "[data-metadata-provider-result]"
          && child.dataset.metadataProviderResult) return child;
      const found = child.querySelector(selector);
      if (found) return found;
    }
    return null;
  }
}

function fixture() {
  const list = new Element("div");
  const sandbox = {
    document: { createElement: tag => new Element(tag) },
    $: id => id === "metadataProviderList" ? list : null,
    state: { metadataProviders: [], metadataProviderResults: {} },
    METADATA_PROVIDER_SAFE_ORDER: ["netease", "kuwo", "kugou", "migu", "joox", "musicbrainz"],
    MUSICBRAINZ_PROVIDER_ID: "musicbrainz",
    displayText: value => String(value ?? ""),
    ensureMetadataProviderSaveAction() {},
    updateMetadataSettingsOverview() {},
  };
  for (const name of [
    "metadataProviderFallbackEntries", "normalizeMetadataProviderEntries",
    "metadataProviderLabel", "metadataProviderDisplayName", "metadataProviderCapabilityText",
    "metadataProviderResultMark", "metadataProviderResultText", "metadataProviderResultDetails",
    "metadataProviderStatusNode", "metadataProviderResultFor", "metadataProviderGripMarkup",
    "renderMetadataProviderTestResult", "renderMetadataProviders",
  ]) {
    const source = app.match(new RegExp(`^function ${name}\\b[\\s\\S]*?^}`, "m"));
    assert.ok(source, `missing renderer dependency: ${name}`);
    vm.runInNewContext(source[0], sandbox);
  }
  sandbox.renderMetadataProviders();
  return { list, sandbox };
}

// Resolve the provider rules in source order, including both responsive blocks.
// This checks the CSS layout contract without launching a browser; pixel/visual
// verification belongs to the parent task. No synthetic pixel layout is used.
function providerRules(source, maxWidth = Infinity) {
  const rules = [];
  source = source.replace(/\/\*[\s\S]*?\*\//g, "");
  let offset = 0;
  while (offset < source.length) {
    const open = source.indexOf("{", offset);
    if (open < 0) break;
    let end = open + 1;
    let depth = 1;
    while (depth && end < source.length) {
      if (source[end] === "{") depth++;
      if (source[end] === "}") depth--;
      end++;
    }
    assert.equal(depth, 0, "unbalanced stylesheet");
    const prelude = source.slice(offset, open).trim();
    const body = source.slice(open + 1, end - 1);
    if (prelude.startsWith("@media")) {
      const width = prelude.match(/max-width:\s*(\d+)px/);
      if (width) rules.push(...providerRules(body, Math.min(maxWidth, Number(width[1]))));
    } else if (prelude.includes(".metadata-provider-") && !prelude.startsWith("@")) {
      for (const selector of prelude.split(",")) rules.push({ selector: selector.trim(), body, maxWidth });
    }
    offset = end;
  }
  return rules;
}
const rules = providerRules(css);

function matches(node, selector) {
  const parts = selector.split(/\s+/);
  function compound(element, part) {
    if (!element || /:/.test(part)) return false;
    if (part.includes("[hidden]") && !element.hidden) return false;
    const tag = part.match(/^[a-z]+/);
    return (!tag || element.tagName === tag[0])
      && [...part.matchAll(/\.([\w-]+)/g)].every(match => element.className.split(/\s+/).includes(match[1]));
  }
  if (!compound(node, parts.pop())) return false;
  for (const part of parts.reverse()) {
    do { node = node.parentElement; } while (node && !compound(node, part));
    if (!node) return false;
  }
  return true;
}

function style(node, width) {
  const result = {};
  const weights = {};
  for (const rule of rules) {
    if (width > rule.maxWidth || !matches(node, rule.selector)) continue;
    const specificity = (rule.selector.match(/[.\[]/g) || []).length * 10
      + (rule.selector.match(/(?:^|\s)[a-z]+/g) || []).length;
    for (const declaration of rule.body.split(";")) {
      const colon = declaration.indexOf(":");
      if (colon < 0) continue;
      const property = declaration.slice(0, colon).trim();
      const value = declaration.slice(colon + 1).trim();
      const weight = specificity + (/!important/.test(value) ? 1000 : 0);
      if (weight < (weights[property] ?? -1)) continue;
      weights[property] = weight;
      result[property] = value.replace(/\s*!important\s*$/, "");
    }
  }
  return result;
}

// R494 turned the row into one flex line (grip, name/capabilities, order pair,
// test, switch) with the test result on its own line underneath.  The invariants
// that still matter: the name block keeps a real minimum width, the result takes
// a full line, and long provider errors wrap instead of widening the card.
for (const width of [1280, 761, 760, 560, 375, 320]) {
  test(`provider results keep their own line without squeezing the name at ${width}px`, () => {
    const { list, sandbox } = fixture();
    for (const row of list.children) {
      assert.equal(row.children.length, 6, "each row is grip, name block, order pair, test, switch, result");
      const [, body, , , , result] = row.children;
      assert.equal(body.className, "metadata-provider-body", "name and capabilities share one block");
      const rowFlow = style(row, width);
      if (width <= 560) {
        assert.equal(rowFlow.display, "grid", "a phone row moves to named cells instead of wrapping five controls");
        assert.match(String(rowFlow["grid-template-areas"]), /sw/, "the switch keeps a named cell beside the name");
        assert.match(String(rowFlow["grid-template-areas"]), /move/, "the order pair drops to its own line");
      } else {
        assert.equal(rowFlow.display, "flex", "one line holds the whole row");
      }
      const minWidth = Number(String(style(body, width)["min-width"]).replace("px", ""));
      assert.ok(minWidth >= 100, `the name block may not shrink to a gutter: ${minWidth}px`);
      assert.equal(style(result, width).display, "none", "untested sources must not show an empty result strip");
      for (const ok of [true, false]) {
        sandbox.renderMetadataProviderTestResult(row, {
          ok, response_ms: 80,
          search: { available: ok, supported: true, title: "Long title ".repeat(30) },
          cover: { available: ok, supported: true, url: `https://example.invalid/${"cover".repeat(100)}` },
          lyrics: { available: false, supported: true },
          error: ok ? "" : "ProviderError".repeat(100),
        });
        const resolved = style(result, width);
        assert.equal(result.hidden, false);
        assert.equal(resolved.display, "grid");
        if (width <= 560) {
          assert.equal(resolved["grid-column"], "1/-1",
            "on a phone the result spans the named grid instead of a squeezed column");
        } else {
          assert.match(String(resolved.flex ?? ""), /100%/,
            "the result must take a full line beneath the row instead of a squeezed column");
        }
        assert.equal(resolved["min-width"], "0");
        assert.equal(resolved["overflow-wrap"], "anywhere", "long errors/URLs must not widen the card");
        assert.equal(style(result.children[1], width)["white-space"], "normal", "details must wrap instead of disappearing into ellipsis");
      }
    }
  });
}
