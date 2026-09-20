(function (global) {
  "use strict";

  const MAX_RATE = 768000;
  const MAX_BITS = 64;
  const MAX_DSD_RATES = 16;
  const MAX_TEXT = 32;

  function finitePositive(value, maximum) {
    if (typeof value !== "number" && typeof value !== "string") return 0;
    const number = Number(value);
    return Number.isFinite(number) && number > 0 && number <= maximum ? number : 0;
  }

  function boundedText(value) {
    return typeof value === "string" && value.trim() && value.length <= MAX_TEXT
      ? value.trim()
      : "";
  }

  function rates(value) {
    try {
      if (!Array.isArray(value)) return [];
      return value.slice(0, MAX_DSD_RATES).map(boundedText).filter(Boolean);
    } catch (_) {
      return [];
    }
  }

  function format(caps) {
    if (!caps || typeof caps !== "object") return "未知设备能力";
    let rate = 0;
    let bits = 0;
    let dsdRates = [];
    let dsd = false;
    try { rate = finitePositive(caps.pcm_max_rate, MAX_RATE); } catch (_) {}
    try { bits = finitePositive(caps.pcm_max_bits, MAX_BITS); } catch (_) {}
    try { dsdRates = rates(caps.dsd_rates); } catch (_) {}
    try { dsd = caps.dsd === true; } catch (_) {}
    const pcmRate = rate ? `${Math.round(rate / 1000)}kHz` : "未知采样率";
    const pcmBits = bits ? `${Math.round(bits)}bit` : "未知位深";
    const dsdText = dsd ? ` · DSD ${dsdRates.length ? dsdRates.join("/") : "支持"}` : "";
    return `PCM ${pcmRate}/${pcmBits}${dsdText}`;
  }

  global.fnAudioDeviceCapsPresentation = { format };
})(typeof window !== "undefined" ? window : globalThis);
