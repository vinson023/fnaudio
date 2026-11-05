// R495: the device picker row is a projection of what the server says about a
// target, and three of its five decisions are policy rather than formatting --
// which section a row belongs to, whether the row is reachable at all, and which
// of 「离线 / 正在播放 / 可用」 it carries.  A wrong guess in any of them either
// hides an output that works or invites a tap on one that is already gone, so
// each decision is pinned here instead of only being looked at in a screenshot.
//
// The whole projection is pure: every function takes a target and returns a
// string.  Nothing here doubles the DOM.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

const ui = path.join(__dirname, "..", "app", "ui");
const app = fs.readFileSync(path.join(ui, "app.js"), "utf8");

const PROJECTIONS = [
  "deviceTargetGroupKey",
  "deviceTargetKindLabel",
  "deviceTargetIsOnline",
  "deviceTargetStatusText",
  "deviceTargetDetail",
];

function sandbox() {
  const context = {
    // The real helper collapses whitespace and turns null into an empty string;
    // a target message has to survive that or the subtitle loses its content.
    displayText: value => String(value ?? "").replace(/\s+/g, " ").trim(),
    dacCapsText: caps => (Array.isArray(caps) ? caps.join(" / ") : ""),
  };
  for (const name of PROJECTIONS) {
    const source = app.match(new RegExp(`^function ${name}\\b[\\s\\S]*?^}`, "m"));
    assert.ok(source, `missing device projection: ${name}`);
    vm.runInNewContext(source[0], context);
  }
  return context;
}

const device = sandbox();

test("a target is grouped by what it can reach, and an unknown kind stays local", () => {
  // The picker has exactly two sections.  A kind nobody has taught the client
  // about is a host-side output until proven otherwise: filing it under the
  // network section would label a machine-local sink as a remote one.
  const cases = [
    [{ id: "local" }, "host"],
    [{ id: "dac-1", kind: "usb_dac" }, "host"],
    [{ id: "renderer-1", kind: "dlna_push" }, "network"],
    [{ id: "mystery", kind: "something_new" }, "host"],
    [{ id: "no-kind" }, "host"],
  ];
  for (const [target, group] of cases) {
    assert.equal(device.deviceTargetGroupKey(target), group, JSON.stringify(target));
  }
});

test("the kind label is the same split said in words, and it is not derived from the group", () => {
  // Three labels, two groups: the browser row and the DAC row share a section
  // but must not share a title, so one cannot be computed from the other.
  assert.equal(device.deviceTargetKindLabel({ id: "local" }), "浏览器播放");
  assert.equal(device.deviceTargetKindLabel({ id: "r", kind: "dlna_push" }), "UPnP / DLNA");
  assert.equal(device.deviceTargetKindLabel({ id: "d", kind: "usb_dac" }), "USB DAC");
  assert.equal(device.deviceTargetKindLabel({ id: "x", kind: "unknown" }), "USB DAC");
  assert.notEqual(
    device.deviceTargetKindLabel({ id: "local" }),
    device.deviceTargetKindLabel({ id: "d", kind: "usb_dac" }),
  );
});

test("a target without an online flag counts as reachable", () => {
  // Older servers do not send the field at all.  Reading absence as "offline"
  // would grey out the entire picker against those servers, so only an explicit
  // boolean false may do that -- and a string "false" is not a boolean.
  assert.equal(device.deviceTargetIsOnline({ id: "a" }), true);
  assert.equal(device.deviceTargetIsOnline({ id: "a", online: undefined }), true);
  assert.equal(device.deviceTargetIsOnline({ id: "a", online: true }), true);
  assert.equal(device.deviceTargetIsOnline({ id: "a", online: false }), false);
  assert.equal(device.deviceTargetIsOnline({ id: "a", online: "false" }), false);
  assert.equal(device.deviceTargetIsOnline({ id: "a", online: 0 }), false);
});

test("reachability outranks the current-target wording", () => {
  // A device that is playing and has since dropped must read 离线: the row is
  // disabled, and a disabled row still saying 正在播放 explains nothing.
  assert.equal(device.deviceTargetStatusText({ id: "a", online: false }, true), "离线");
  assert.equal(device.deviceTargetStatusText({ id: "a", online: true }, true), "正在播放");
  assert.equal(device.deviceTargetStatusText({ id: "a", online: true }, false), "可用");
  assert.equal(device.deviceTargetStatusText({ id: "a" }, false), "可用");
  // Inside the reachable branch the current flag is the only difference.
  assert.notEqual(
    device.deviceTargetStatusText({ id: "a" }, true),
    device.deviceTargetStatusText({ id: "a" }, false),
  );
});

test("the subtitle prefers the reason a device is unusable over its capability list", () => {
  // A server message is the only text that explains a failure, so it wins; the
  // capability string is the fallback, and the bare kind is the floor.  An empty
  // or whitespace-only message is not content and must not blank the line.
  assert.equal(
    device.deviceTargetDetail({ id: "a", kind: "usb_dac", message: "USB 设备被拔出", caps: ["96k"] }),
    "USB 设备被拔出",
  );
  assert.equal(
    device.deviceTargetDetail({ id: "a", kind: "usb_dac", message: "   ", caps: ["96k"] }),
    "USB DAC · 96k",
  );
  assert.equal(device.deviceTargetDetail({ id: "a", kind: "usb_dac", caps: ["96k"] }), "USB DAC · 96k");
  assert.equal(device.deviceTargetDetail({ id: "a", kind: "usb_dac" }), "USB DAC");
  assert.equal(device.deviceTargetDetail({ id: "a" }), "USB DAC");
});

test("the renderer is the only caller, so these cannot drift into dead code", () => {
  // Naming the functions here would be worthless if the row template stopped
  // using them; the row is drawn from exactly these answers.  The kind label is
  // reached through the subtitle rather than called by the template, so it is
  // checked on that edge instead of being demanded where it never stood.
  const source = app.match(/^function renderDeviceTargets\b[\s\S]*?^}/m);
  assert.ok(source, "missing renderDeviceTargets");
  for (const name of ["deviceTargetGroupKey", "deviceTargetIsOnline", "deviceTargetStatusText", "deviceTargetDetail"]) {
    assert.match(source[0], new RegExp(`\\b${name}\\(`), `renderDeviceTargets stopped calling ${name}`);
  }
  assert.doesNotMatch(source[0], /\bdeviceTargetKindLabel\(/, "the label belongs to the subtitle, not the template");
  const detail = app.match(/^function deviceTargetDetail\b[\s\S]*?^}/m);
  assert.ok(detail, "missing deviceTargetDetail");
  assert.match(detail[0], /\bdeviceTargetKindLabel\(/, "the subtitle must keep building on the kind label");
  // The row carries the three facts the picker promises: a group icon, the name
  // plus subtitle, and a status word beside a radio mark.
  for (const part of ["device-row-icon is-", "device-row-text", "device-row-status", "device-row-radio"]) {
    assert.ok(source[0].includes(part), `device row lost ${part}`);
  }
  // Offline rows are disabled at the template, not only dimmed by CSS.
  assert.match(source[0], /\$\{online \? "" : " disabled"\}/, "offline rows must be disabled in the markup");
});
