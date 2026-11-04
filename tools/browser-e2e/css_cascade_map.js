// Cascade map: for every (element, property) pair in every sampled state, work
// out which declaration actually wins, and whether that declaration would still
// win if its `!important` were dropped.
//
// Why this exists: 68% of the declarations in app.css + fnos-theme.css are
// `!important`, so "which of them are load-bearing" cannot be answered by
// reading the file. The snapshot harness proves a change is inert; this map
// tells you which change is worth attempting.
//
//   node css_cascade_map.js <out.json>
//
// Design notes:
//  * Shorthands are expanded by the browser itself, not by a hand-written table:
//    setting `padding: 4px` on a detached probe element and reading back
//    `style[i]` yields exactly the longhands this engine expands it to. That
//    keeps `border`, `background`, `flex`, `font`, `inset`, `place-*` honest
//    without a map that could drift.
//  * A declaration is only called removable when it demonstrably wins somewhere
//    (wins > 0) and would still win everywhere it wins. Declarations that never
//    win are left alone: they are either dead or exercised only by states this
//    harness does not sample (`:hover`, `:focus-visible`, a breakpoint between
//    two viewports), and "never won here" is not proof of "never wins".
//  * Selectors carrying a pseudo-element or a dynamic pseudo-class are excluded
//    from removal for the same reason: the map cannot observe them.
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const BASE = "http://127.0.0.1:8745/";
const OUT = process.argv[2] || path.join(__dirname, "..", "..", "artifacts", "css_cascade_map.json");

const VIEWPORTS = [
  { name: "w1440", w: 1440, h: 900 },
  { name: "w1024", w: 1024, h: 768 },
  { name: "w390", w: 390, h: 844 },
  { name: "w360", w: 360, h: 740 },
];

// Injected into the page. Returns { declarations: [...], unsupported: [...] }.
function buildMap() {
  const probe = document.createElement("div");

  // `style[i]` enumeration reports the longhands of a shorthand that carries
  // `var()`, so `border: 1px solid var(--x)` shows up as six border-*-* entries
  // that do not exist in the source. `style.cssText` keeps the shorthand, so the
  // identity of an editable declaration is parsed from there and expanded here.
  function parseDeclarations(cssText) {
    const out = [];
    let start = 0, depth = 0, quote = null;
    const chunks = [];
    for (let i = 0; i <= cssText.length; i += 1) {
      const ch = cssText[i];
      if (i === cssText.length || (ch === ";" && depth === 0 && !quote)) {
        chunks.push(cssText.slice(start, i));
        start = i + 1;
        continue;
      }
      if (quote) {
        if (ch === "\\") { i += 1; continue; }
        if (ch === quote) quote = null;
      } else if (ch === '"' || ch === "'") quote = ch;
      else if (ch === "(") depth += 1;
      else if (ch === ")") depth = Math.max(0, depth - 1);
    }
    chunks.forEach((chunk, index) => {
      const split = chunk.indexOf(":");
      if (split < 0) return;
      const prop = chunk.slice(0, split).trim().toLowerCase();
      if (!prop || prop.startsWith("--")) return;
      let value = chunk.slice(split + 1).trim();
      let important = false;
      const bang = value.match(/\s*!\s*important\s*$/i);
      if (bang) {
        important = true;
        value = value.slice(0, bang.index).trim();
      }
      out.push({ prop, value, important, index });
    });
    return out;
  }

  const longhandCache = new Map();
  function longhands(prop, value) {
    const key = prop + "\u0000" + value;
    const hit = longhandCache.get(key);
    if (hit) return hit;
    probe.style.cssText = "";
    try { probe.style.setProperty(prop, value); } catch (e) { /* invalid: treat as opaque */ }
    const out = [];
    for (let i = 0; i < probe.style.length; i += 1) out.push(probe.style[i]);
    if (!out.length) out.push(prop);
    longhandCache.set(key, out);
    return out;
  }

  // Specificity of one complex selector. Unknown constructs are treated as
  // "stronger than anything", which only ever makes the map keep an
  // `!important` instead of dropping it.
  const specCache = new Map();
  function specificity(part) {
    const hit = specCache.get(part);
    if (hit) return hit;
    let a = 0, b = 0, c = 0;
    let text = part;
    const take = (re, weight) => {
      text = text.replace(re, (match, inner) => {
        if (weight === "a") a += 1;
        else if (weight === "b") b += 1;
        else c += 1;
        return inner === undefined ? " " : inner;
      });
    };
    // Functional pseudo-classes first, so their arguments are handled by rule.
    text = text.replace(/:where\(([^()]*)\)/g, " ");
    text = text.replace(/:(?:not|is|has|matches)\(([^()]*)\)/g, (match, inner) => {
      let best = [0, 0, 0];
      for (const piece of inner.split(",")) {
        const s = specificity(piece.trim());
        if (s[0] > best[0] || (s[0] === best[0] && (s[1] > best[1] || (s[1] === best[1] && s[2] > best[2])))) best = s;
      }
      a += best[0]; b += best[1]; c += best[2];
      return " ";
    });
    take(/#[\w-]+/g, "a");
    take(/\.[\w-]+/g, "b");
    take(/\[[^\]]*\]/g, "b");
    take(/::[\w-]+(?:\([^()]*\))?/g, "c");
    take(/:[\w-]+(?:\([^()]*\))?/g, "b");
    take(/(?:^|[\s>+~,])([a-zA-Z][\w-]*)/g, "c");
    take(/\*/, "c");
    const value = [a, b, c];
    specCache.set(part, value);
    return value;
  }

  const DYNAMIC = /:(hover|active|focus|focus-visible|focus-within|visited|target|checked|disabled|enabled|placeholder-shown|autofill|user-invalid|user-valid|open|popover-open|modal)\b/;
  const PSEUDO_ELEMENT = /::|:(before|after|first-line|first-letter|selection|marker|placeholder|backdrop)\b/;

  // Logical and physical properties are the same computed property: a
  // `padding-block` declaration competes with `padding`, not with nothing. The
  // probe expands them to `padding-block-start` / `padding-top` respectively, so
  // without this map the two never meet and the logical one looks uncontested --
  // which is exactly how the first attempt demoted `.sidebar-settings .nav-item
  // { padding-block: 4px !important }` and let `.nav-item`'s 8px win.
  const LOGICAL = {
    "padding-block-start": "padding-top",
    "padding-block-end": "padding-bottom",
    "padding-inline-start": "padding-left",
    "padding-inline-end": "padding-right",
    "margin-block-start": "margin-top",
    "margin-block-end": "margin-bottom",
    "margin-inline-start": "margin-left",
    "margin-inline-end": "margin-right",
    "inset-block-start": "top",
    "inset-block-end": "bottom",
    "inset-inline-start": "left",
    "inset-inline-end": "right",
    "border-block-start-width": "border-top-width",
    "border-block-end-width": "border-bottom-width",
    "border-inline-start-width": "border-left-width",
    "border-inline-end-width": "border-right-width",
    "border-block-start-color": "border-top-color",
    "border-block-end-color": "border-bottom-color",
    "border-inline-start-color": "border-left-color",
    "border-inline-end-color": "border-right-color",
    "border-block-start-style": "border-top-style",
    "border-block-end-style": "border-bottom-style",
    "border-inline-start-style": "border-left-style",
    "border-inline-end-style": "border-right-style",
    "inline-size": "width",
    "block-size": "height",
    "min-inline-size": "min-width",
    "min-block-size": "min-height",
    "max-inline-size": "max-width",
    "max-block-size": "max-height",
  };

  // `vertical-rl` swaps which physical side a logical property refers to, so the
  // map is only applied to elements laid out horizontally; elsewhere a logical
  // declaration is marked unremovable instead of being compared under the wrong
  // assumption.
  const writingModes = new WeakMap();
  function horizontal(element) {
    let value = writingModes.get(element);
    if (value === undefined) {
      value = getComputedStyle(element).writingMode.indexOf("horizontal") === 0;
      writingModes.set(element, value);
    }
    return value;
  }

  // Collect style rules in document order, skipping subtrees that are not style
  // rules (@keyframes frames, @font-face, @page).
  const rules = [];
  const unsupported = [];
  let order = 0;

  function walk(list, context, active, sheetName) {
    for (const rule of list) {
      const kind = rule.constructor.name;
      if (kind === "CSSStyleRule") {
        rules.push({
          sheet: sheetName,
          selector: rule.selectorText,
          style: rule.style,
          context,
          active,
          order: order += 1,
        });
        continue;
      }
      if (kind === "CSSMediaRule") {
        let matches = true;
        try { matches = window.matchMedia(rule.conditionText).matches; } catch (e) { matches = false; }
        walk(rule.cssRules, context + "@media " + rule.conditionText, active && matches, sheetName);
        continue;
      }
      if (kind === "CSSSupportsRule") {
        let ok = true;
        try { ok = CSS.supports(rule.conditionText); } catch (e) { ok = false; }
        walk(rule.cssRules, context + "@supports " + rule.conditionText, active && ok, sheetName);
        continue;
      }
      if (kind === "CSSLayerBlockRule" || kind === "CSSLayerStatementRule") {
        unsupported.push("layer:" + (rule.name || ""));
        if (rule.cssRules) walk(rule.cssRules, context + "@layer", active, sheetName);
        continue;
      }
      // @font-face, @page, @keyframes (and its frames), @property, @container.
      if (kind === "CSSContainerRule") {
        unsupported.push("container:" + rule.conditionText);
      }
    }
  }

  for (const sheet of document.styleSheets) {
    let list;
    try { list = sheet.cssRules; } catch (e) { continue; }
    if (!list) continue;
    const href = sheet.href || "";
    const name = sheet.ownerNode && sheet.ownerNode.id
      ? "#" + sheet.ownerNode.id
      : href.split("/").pop().split("?")[0];
    walk(list, "", true, name);
  }

  // rule -> elements, and per element the declarations that reach it.
  const byElement = new Map();
  const partsCache = new Map();
  for (const rule of rules) {
    if (!rule.active) continue;
    let parts = partsCache.get(rule.selector);
    if (!parts) {
      parts = rule.selector.split(",").map(p => p.trim()).filter(Boolean);
      partsCache.set(rule.selector, parts);
    }
    let elements;
    try { elements = document.querySelectorAll(rule.selector); } catch (e) { continue; }
    for (const element of elements) {
      let spec = null;
      if (parts.length === 1) {
        spec = specificity(parts[0]);
      } else {
        for (const part of parts) {
          let hit = false;
          try { hit = element.matches(part); } catch (e) { hit = false; }
          if (!hit) continue;
          const s = specificity(part);
          if (!spec || s[0] > spec[0] || (s[0] === spec[0] && (s[1] > spec[1] || (s[1] === spec[1] && s[2] > spec[2])))) spec = s;
        }
        if (!spec) spec = [0, 0, 0];
      }
      let bucket = byElement.get(element);
      if (!bucket) { bucket = []; byElement.set(element, bucket); }
      bucket.push({ rule, spec });
    }
  }

  // Every element, including ones no rule matches (they still inherit, and an
  // inherited value never competes with a declaration, so they are skipped).
  const aggregate = new Map();

  for (const [element, bucket] of byElement) {
    const perProperty = new Map();
    const isHorizontal = horizontal(element);
    const expand = (decl) => {
      const raw = longhands(decl.prop, decl.value);
      // A logical property on a vertically-laid-out element cannot be compared
      // with its physical counterpart here; flag it so it is never demoted.
      const unsafe = !isHorizontal && raw.some(name => LOGICAL[name]);
      return raw.map(name => ({ name: isHorizontal ? (LOGICAL[name] || name) : name, unsafe }));
    };
    for (const entry of bucket) {
      for (const decl of parseDeclarations(entry.rule.style.cssText)) {
        for (const longhand of expand(decl)) {
          let list = perProperty.get(longhand.name);
          if (!list) { list = []; perProperty.set(longhand.name, list); }
          list.push({
            rule: entry.rule,
            spec: entry.spec,
            prop: decl.prop,
            value: decl.value,
            important: decl.important,
            order: entry.rule.order,
            index: decl.index,
            inline: false,
            logical: longhand.unsafe,
          });
        }
      }
    }
    const attr = element.getAttribute("style");
    if (attr) {
      for (const decl of parseDeclarations(attr)) {
        for (const longhand of expand(decl)) {
          let list = perProperty.get(longhand.name);
          if (!list) { list = []; perProperty.set(longhand.name, list); }
          list.push({
            rule: null,
            spec: [1000, 0, 0],
            prop: decl.prop,
            value: decl.value,
            important: decl.important,
            order: 1e9,
            index: decl.index,
            inline: true,
            logical: longhand.unsafe,
          });
        }
      }
    }

    for (const [, list] of perProperty) {
      const rank = d => [d.important ? 1 : 0, d.spec[0], d.spec[1], d.spec[2], d.order, d.index];
      const better = (x, y) => {
        const a = rank(x), b = rank(y);
        for (let i = 0; i < a.length; i += 1) {
          if (a[i] !== b[i]) return a[i] > b[i];
        }
        return false;
      };
      let winner = list[0];
      for (const candidate of list) if (better(candidate, winner)) winner = candidate;
      if (!winner.important || winner.inline) continue;
      // Identity is the declaration as written, not the longhand it expanded to:
      // `font: 14px/1.5 var(--ui-font) !important` is one editable declaration,
      // and its eight expanded longhands have to agree before it can be demoted.
      const id = [winner.rule.sheet, winner.rule.selector, winner.rule.context,
                  winner.prop, winner.index].join("|");

      // Would it still win as a normal declaration?
      let stillWins = true;
      for (const other of list) {
        if (other === winner) continue;
        const demoted = { ...winner, important: false };
        if (better(other, demoted)) { stillWins = false; break; }
      }
      // Aggregate inside the page: a state produces hundreds of thousands of
      // (element, property) verdicts, and shipping those to Node would dwarf the
      // data that actually matters (~4k distinct declarations).
      let entry = aggregate.get(id);
      if (!entry) {
        entry = {
          id,
          sheet: winner.rule.sheet,
          selector: winner.rule.selector,
          prop: winner.prop,
          value: winner.value,
          context: winner.rule.context,
          static: !DYNAMIC.test(winner.rule.selector) && !PSEUDO_ELEMENT.test(winner.rule.selector),
          wins: 0,
          winsWithout: 0,
          blocked: false,
        };
        aggregate.set(id, entry);
      }
      entry.wins += 1;
      // A logical declaration on a vertically-written element is never demoted:
      // the map cannot tell which physical side it lands on, so "it still wins"
      // would be a guess. (`vertical-rl` is used by the volume slider.)
      if (stillWins && !winner.logical) entry.winsWithout += 1;
      else entry.blocked = true;
    }
  }

  return {
    declarations: Array.from(aggregate.values()),
    unsupported: Array.from(new Set(unsupported)),
    rules: rules.length,
  };
}

async function settle(page) {
  await page.waitForTimeout(900);
}

(async () => {
  const browser = await chromium.launch({
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  });
  const aggregate = new Map();
  let unsupported = new Set();
  let states = 0;
  let rulesSeen = 0;

  for (const vp of VIEWPORTS) {
    for (const theme of ["light", "dark"]) {
      const page = await browser.newPage({ viewport: { width: vp.w, height: vp.h } });
      await page.goto(BASE, { waitUntil: "networkidle" });
      await page.evaluate((t) => {
        document.documentElement.setAttribute("data-theme", t);
        try { localStorage.setItem("fnaudio-theme", t); } catch (e) {}
      }, theme);
      await page.waitForTimeout(1600);

      const collect = async (label) => {
        const result = await page.evaluate(buildMap);
        states += 1;
        rulesSeen = result.rules;
        for (const u of result.unsupported) unsupported.add(u);
        for (const item of result.declarations) {
          const key = item.id;
          let entry = aggregate.get(key);
          if (!entry) {
            entry = {
              id: item.id, sheet: item.sheet, selector: item.selector, prop: item.prop,
              value: item.value, context: item.context, static: item.static,
              wins: 0, winsWithout: 0, blocked: false, states: 0,
            };
            aggregate.set(key, entry);
          }
          entry.wins += item.wins;
          entry.winsWithout += item.winsWithout;
          if (item.blocked) entry.blocked = true;
          entry.states += 1;
        }
      };

      const tag = `${vp.name}-${theme}`;
      await collect(`${tag}/library`);

      await page.evaluate(() => document.getElementById("folderDialog").showModal());
      await settle(page);
      for (const tab of ["library", "playback", "metadata", "dlna", "runtime"]) {
        await page.click(`[data-settings-tab="${tab}"]`).catch(() => {});
        await settle(page);
        await collect(`${tag}/settings-${tab}`);
        if (tab === "metadata") {
          for (const sub of ["overview", "providers", "tasks", "tags"]) {
            await page.click(`[data-metadata-settings-tab="${sub}"]`).catch(() => {});
            await settle(page);
            await collect(`${tag}/settings-metadata-${sub}`);
          }
        }
      }
      await page.evaluate(() => {
        try { document.getElementById("folderDialog").close(); } catch (e) {}
      });
      await settle(page);

      await page.evaluate(() => {
        const d = document.getElementById("deviceDialog");
        if (d) d.showModal();
      });
      await settle(page);
      await collect(`${tag}/device`);
      await page.evaluate(() => {
        try { document.getElementById("deviceDialog").close(); } catch (e) {}
      });
      await settle(page);

      await page.evaluate(() => {
        const btn = document.getElementById("lyricsBtn");
        if (btn) btn.click();
      });
      await settle(page);
      await collect(`${tag}/lyrics`);

      await page.close();
      console.log(`  ${tag}: ${states} states so far`);
    }
  }

  const out = { states, rules: rulesSeen, unsupported: Array.from(unsupported), declarations: {} };
  for (const [key, entry] of aggregate) {
    out.declarations[key] = {
      sheet: entry.sheet,
      selector: entry.selector,
      prop: entry.prop,
      value: entry.value,
      context: entry.context,
      static: entry.static,
      wins: entry.wins,
      winsWithout: entry.winsWithout,
      blocked: entry.blocked,
      removable: entry.static && entry.wins > 0 && !entry.blocked && entry.winsWithout === entry.wins,
    };
  }
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify(out));
  const values = Object.values(out.declarations);
  console.log(`wrote ${OUT}`);
  console.log(`states=${states} rules=${rulesSeen} declarations=${values.length}`);
  console.log(`removable=${values.filter(v => v.removable).length}`);
  if (out.unsupported.length) console.log("unsupported:", out.unsupported.join(", "));
  await browser.close();
})();
