(function (root) {
  "use strict";
  function isPrivateHost(host) {
    if (typeof host !== "string") return false;
    const value = host.trim().toLowerCase();
    if (!value || value === "localhost" || value === "127.0.0.1" || value === "::1" || value.endsWith(".local") || value.endsWith(".lan")) return true;
    // Common private IPv6 ranges: ULA fc00::/7 and link-local fe80::/10.
    if (/^(?:fc|fd)[0-9a-f]{2}:/i.test(value) || /^fe[89ab][0-9a-f]:/i.test(value)) return true;
    const parts = value.split(".");
    if (parts.length !== 4 || parts.some(part => !/^\d{1,3}$/.test(part))) return false;
    const numbers = parts.map(Number);
    if (numbers.some(number => number < 0 || number > 255)) return false;
    return numbers[0] === 10 || numbers[0] === 127
      || (numbers[0] === 172 && numbers[1] >= 16 && numbers[1] <= 31)
      || (numbers[0] === 192 && numbers[1] === 168)
      || (numbers[0] === 169 && numbers[1] === 254);
  }
  root.fnAudioHostPrivacyPolicy = Object.freeze({ isPrivateHost });
})(globalThis);
