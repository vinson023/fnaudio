const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/device_caps_presentation.js", "utf8");
const context = { globalThis: {} };
vm.runInNewContext(source, context);
const api = context.globalThis.fnAudioDeviceCapsPresentation;
assert.equal(typeof api.format, "function");
assert.equal(api.format({ pcm_max_rate: 384000, pcm_max_bits: 32, dsd: true, dsd_rates: ["DSD64", "DSD128"] }), "PCM 384kHz/32bit · DSD DSD64/DSD128");
assert.equal(api.format({ pcm_max_rate: Infinity, pcm_max_bits: {}, dsd: true, dsd_rates: [{ toString() { throw new Error("must not stringify"); } }] }), "PCM 未知采样率/未知位深 · DSD 支持");
assert.equal(api.format({ pcm_max_rate: 999999999, pcm_max_bits: 128, dsd: "true", dsd_rates: ["ok"] }), "PCM 未知采样率/未知位深");
assert.equal(api.format(null), "未知设备能力");
const hostile = new Proxy({}, { get() { throw new Error("unexpected capability access"); } });
assert.doesNotThrow(() => api.format(hostile), "broken capability fields must not abort device rendering");
assert.equal(api.format(hostile), "PCM 未知采样率/未知位深");
const brokenRates = new Proxy([], { get() { throw new Error("unexpected rate access"); } });
assert.equal(api.format({ pcm_max_rate: 44100, pcm_max_bits: 24, dsd: true, dsd_rates: brokenRates }), "PCM 44kHz/24bit · DSD 支持");
// The server reports an unmeasured DAC with exactly this shape, so the
// "unknown is unknown" contract has to hold on the rendering side too.
assert.equal(api.format({
  source: "unknown", pcm_rates: [], pcm_max_rate: 0, pcm_max_bits: 0, dsd: false, dsd_rates: [], notes: [],
}), "PCM \u672a\u77e5\u91c7\u6837\u7387/\u672a\u77e5\u4f4d\u6df1");
console.log("Device capability presentation regression checks passed.");
