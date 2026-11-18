// R588: the sleep timer is a deadline, not a countdown.
//
// A countdown kept in a `setTimeout` is the wrong shape for this feature: the
// WebView is suspended while the host player keeps playing, so a 30-minute
// timer either fires late or never. Everything here works from an absolute
// epoch deadline instead -- the page stores it, the foreground service arms its
// own handler from the same number, and whichever one is still awake pauses at
// the same instant.
//
// The module is pure: no DOM, no timers, no storage side effects it cannot
// swallow. app.js owns the wiring; the guard test owns the arithmetic.
(() => {
  const MIN_MINUTES = 1;
  // A timer longer than a day is a mis-typed number, not a plan.
  const MAX_MINUTES = 24 * 60;
  const OPTIONS = [15, 30, 45, 60];
  const STORAGE_KEY = "fnaudio.sleep.deadline.v1";
  // A deadline this far in the past is "it just fired" (the page was hidden,
  // not closed). Anything older is a leftover from a previous day and must not
  // pause the music the listener has just started.
  const GRACE_MS = 60 * 1000;

  function minutes(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return 0;
    const whole = Math.floor(number);
    if (whole < MIN_MINUTES) return 0;
    return Math.min(whole, MAX_MINUTES);
  }

  function now(value) {
    return Number.isFinite(value) ? value : Date.now();
  }

  function deadlineFrom(value, at) {
    const span = minutes(value);
    return span ? now(at) + span * 60000 : 0;
  }

  function deadline(value) {
    const number = Number(value);
    if (!Number.isFinite(number) || number <= 0) return 0;
    return Math.floor(number);
  }

  function remainingMs(value, at) {
    const target = deadline(value);
    if (!target) return 0;
    return Math.max(0, target - now(at));
  }

  function isActive(value, at) {
    return remainingMs(value, at) > 0;
  }

  function isExpired(value, at) {
    const target = deadline(value);
    return Boolean(target) && now(at) >= target;
  }

  function isFreshExpiry(value, at) {
    const target = deadline(value);
    if (!target) return false;
    const current = now(at);
    return current >= target && current - target <= GRACE_MS;
  }

  function formatRemaining(ms) {
    const total = Math.max(0, Math.ceil((Number(ms) || 0) / 1000));
    const hours = Math.floor(total / 3600);
    const mins = Math.floor((total % 3600) / 60);
    const secs = total % 60;
    if (hours) return mins ? `${hours} 小时 ${mins} 分` : `${hours} 小时`;
    if (mins) return `${mins} 分 ${String(secs).padStart(2, "0")} 秒`;
    return `${secs} 秒`;
  }

  function describe(value, at) {
    const remaining = remainingMs(value, at);
    return {
      active: remaining > 0,
      remainingMs: remaining,
      text: remaining > 0 ? `睡眠定时：还剩 ${formatRemaining(remaining)}` : "",
    };
  }

  // Storage may be absent (private mode) or full; neither may break playback.
  function readStored(storage) {
    try {
      const raw = storage?.getItem?.(STORAGE_KEY) || "";
      return deadline(Number(raw));
    } catch (_) {
      return 0;
    }
  }

  function writeStored(storage, value) {
    const target = deadline(value);
    try {
      if (!target) {
        storage?.removeItem?.(STORAGE_KEY);
        return true;
      }
      // Reporting success without a store would make "the timer is set" a claim
      // the page cannot keep across a reload.
      if (typeof storage?.setItem !== "function") return false;
      storage.setItem(STORAGE_KEY, String(target));
      return true;
    } catch (_) {
      return false;
    }
  }

  window.fnAudioSleepTimerPolicy = {
    GRACE_MS,
    MAX_MINUTES,
    MIN_MINUTES,
    OPTIONS,
    STORAGE_KEY,
    deadlineFrom,
    describe,
    formatRemaining,
    isActive,
    isExpired,
    isFreshExpiry,
    minutes,
    readStored,
    remainingMs,
    writeStored,
  };
})();
