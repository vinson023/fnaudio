const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

// The DLNA trace is the only place fnAudio records who is talking to it. The server has always
// put `client_ip` on every entry (dlna/request_context.py), but the row rendered
// `entry.user_agent || entry.client_ip`, so the address was only ever visible for a client that
// sent no User-Agent at all - i.e. almost never. The owner's report was exactly that: "dlna日志
// 应该记录对端IP才对". Two televisions of the same model report the same User-Agent, so the
// address is also the only thing that tells them apart.
const source = fs.readFileSync("app/ui/app.js", "utf8");

function functionSource(name) {
  const start = source.indexOf("function " + name + "(");
  assert.notEqual(start, -1, "app.js no longer declares " + name);
  let depth = 0;
  for (let index = source.indexOf("{", start); index < source.length; index += 1) {
    if (source[index] === "{") depth += 1;
    if (source[index] === "}") {
      depth -= 1;
      if (depth === 0) return source.slice(start, index + 1);
    }
  }
  throw new Error("unbalanced braces in " + name);
}

const sandbox = {
  displayText: value => (typeof value === "string" ? value.trim() : ""),
  escapeHtml: value => String(value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"),
};
vm.createContext(sandbox);
vm.runInContext(
  functionSource("dlnaDiagnosticDetail") + "\n" + functionSource("dlnaDiagnosticPeer"),
  sandbox,
);

// The peer is rendered as its own marked element, so it cannot be swallowed by the
// single-line, ellipsis-clipped User-Agent paragraph.
assert.equal(
  sandbox.dlnaDiagnosticPeer({ client_ip: "192.168.5.22", user_agent: "Linux/1.0 UPnP/1.1" }),
  '<span class="diagnostic-peer">192.168.5.22</span>',
);
assert.equal(
  sandbox.dlnaDiagnosticPeer({ client_ip: "192.168.5.22" }),
  '<span class="diagnostic-peer">192.168.5.22</span>',
  "an entry with no User-Agent must still show the address",
);
assert.equal(sandbox.dlnaDiagnosticPeer({ user_agent: "Linux/1.0" }), "",
  "a missing address renders nothing rather than an empty chip");
assert.equal(sandbox.dlnaDiagnosticPeer({ client_ip: 42 }), "",
  "a non-text address is not stringified into the page");
assert.equal(
  sandbox.dlnaDiagnosticPeer({ client_ip: '<img src=x onerror=alert(1)>' }),
  '<span class="diagnostic-peer">&lt;img src=x onerror=alert(1)&gt;</span>',
  "the address is escaped, not injected",
);

// The row template must call it, and the old "user_agent || client_ip" fallback must be gone:
// that expression is what made the address invisible in the first place.
const list = source.slice(
  source.indexOf("async function loadDlnaDiagnostics"),
  source.indexOf("function openDlnaDiagnostics"),
);
assert.match(list, /<small>\$\{dlnaDiagnosticPeer\(entry\)\}/,
  "the row must render the peer chip in the detail line");
assert.doesNotMatch(list, /entry\.user_agent \|\| entry\.client_ip/,
  "the fallback that hid the address whenever a User-Agent existed is back");
assert.match(list, /entry\.user_agent \|\| "未知设备"/,
  "an entry with no User-Agent still needs a readable label");
// "来自 N 个设备" counted distinct User-Agents; counting addresses is the honest number.
assert.match(list, /new Set\(entries\.map\(entry => String\(entry\.client_ip \|\| ""\)\.trim\(\)\)\.filter\(Boolean\)\)/,
  "the device count must be taken from the addresses when the server reported them");
assert.match(list, /peers\.size \|\| Object\.keys\(data\.clients \|\| \{\}\)\.length/,
  "a payload without addresses must still fall back to the server's client summary");

// The chip has to survive the theme sheet, which forces every span inside a diagnostic entry to
// the muted colour with !important; without its own !important rule the address would render as
// grey as the detail text it is meant to lead.
const theme = fs.readFileSync("app/ui/fnos-theme.css", "utf8");
assert.match(theme, /\.diagnostic-entry \.diagnostic-peer \{ color: var\(--ui-text\) !important;/,
  "the peer chip lost its theme override and will render muted");
const base = fs.readFileSync("app/ui/app.css", "utf8");
assert.match(base, /\.diagnostic-entry \.diagnostic-peer\{[^}]*tabular-nums/,
  "addresses should line up, which needs tabular figures");

console.log("dlna diagnostics peer: ok");
