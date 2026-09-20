/* Small TTL/in-flight cache for the access profile used by the mode badge. */
(function (root) {
  function createAccessProfileLoader(options = {}) {
    const fetchProfile = typeof options.fetchProfile === "function" ? options.fetchProfile : null;
    const now = typeof options.now === "function" ? options.now : () => Date.now();
    let ttlMs = 10000;
    try {
      if (typeof options.ttlMs === "number" || typeof options.ttlMs === "string") {
        const numericTtl = Number(options.ttlMs);
        if (Number.isFinite(numericTtl)) ttlMs = Math.max(1000, Math.min(60000, numericTtl));
      }
    } catch (_) {
      // Keep the bounded default for hostile bridge configuration.
    }
    let cached = null;
    let expiresAt = 0;
    let inflight = null;
    return {
      load(force = false) {
        if (!fetchProfile) return Promise.resolve(null);
        if (!force && cached && now() < expiresAt) return Promise.resolve(cached);
        if (inflight) return inflight;
        inflight = Promise.resolve().then(fetchProfile).then(value => {
          const profile = value && typeof value.profile === "string" ? value.profile : "lan";
          cached = { profile };
          expiresAt = now() + ttlMs;
          return cached;
        }).finally(() => { inflight = null; });
        return inflight;
      },
      clear() {
        cached = null;
        expiresAt = 0;
      },
    };
  }
  root.fnAudioAccessProfileLoader = { create: createAccessProfileLoader };
})(globalThis);
