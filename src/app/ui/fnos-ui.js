/* Presentation-only behavior for the FNOS theme layer. No playback, fetch, or
 * device calls. Owns the data-theme attribute exactly like the approved
 * prototype: "light" and "dark" pin a scheme, an absent value follows the OS. */
(() => {
  const STORAGE_KEY = "fnaudio.theme";
  const VALID = new Set(["light", "dark"]);
  const root = document.documentElement;

  // The Android WebView injects this bridge before loading the shared page.
  // Keep its compact player presentation separate from ordinary web browsers.
  try {
    root.classList.toggle("android-app", Boolean(window.FnAudioNative &&
      typeof window.FnAudioNative.isAvailable === "function" && window.FnAudioNative.isAvailable()));
  } catch (_) { /* A missing bridge uses the regular browser layout. */ }

  function applyTheme(value) {
    if (VALID.has(value)) root.dataset.theme = value;
    else delete root.dataset.theme;
  }

  function storedTheme() {
    try { return localStorage.getItem(STORAGE_KEY); } catch (_) { return null; }
  }

  applyTheme(storedTheme());

  document.addEventListener("change", event => {
    const control = event.target.closest("[data-theme-choice]");
    if (!control) return;
    const value = control.value;
    try {
      if (VALID.has(value)) localStorage.setItem(STORAGE_KEY, value);
      else localStorage.removeItem(STORAGE_KEY);
    } catch (_) { /* A refused write keeps the in-session choice. */ }
    applyTheme(value);
  });
})();
