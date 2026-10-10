(() => {
  function create(options = {}) {
    if (!options || typeof options !== "object") options = {};
    const doc = options.document || globalThis.document;
    const candidateTimerHost = options.timerHost;
    const timerHost = candidateTimerHost && (typeof candidateTimerHost === "object" || typeof candidateTimerHost === "function")
      ? candidateTimerHost : globalThis;
    const intervals = [];
    const setIntervalSafe = typeof timerHost.setInterval === "function" ? timerHost.setInterval.bind(timerHost) : () => null;
    const clearIntervalSafe = typeof timerHost.clearInterval === "function" ? timerHost.clearInterval.bind(timerHost) : () => {};
    const call = name => {
      const fn = options[name];
      if (typeof fn === "function") fn();
    };
    const check = name => {
      const fn = options[name];
      return typeof fn === "function" && Boolean(fn());
    };
    const visible = () => !doc || doc.visibilityState !== "hidden";
    const every = (milliseconds, callback) => {
      const id = setIntervalSafe(() => {
        if (!visible()) return;
        // A library page replacement owns the few HTTP/1.1 connections the browser
        // keeps to the app gateway, and on fnOS every one of these ticks also starts a
        // CGI worker. Yielding the background lanes for that window is what turns a
        // queued half-second-late click into an immediate one.
        if (check("isInteractionBlocked")) return;
        callback();
      }, milliseconds);
      if (id !== null && id !== undefined) intervals.push(id);
    };
    const resume = () => {
      if (!visible()) return;
      call("refreshLibraryStatus");
      call("refreshCurrentTranscodeStatus");
      call("refreshRendererSession");
      call("refreshServerUserState");
      if (check("isRemoteTarget")) {
        call("startRemoteEventStream");
        call("refreshRemoteStatus");
        call("updateRemoteUi");
      }
    };
    const onVisibilityChange = () => {
      if (visible()) resume();
      else call("stopRemoteEventStream");
    };

    every(30000, () => call("refreshLibraryStatus"));
    every(1000, () => { if (check("isLibraryScanning")) call("refreshLibraryStatus"); });
    every(1200, () => call("refreshCurrentTranscodeStatus"));
    every(5000, () => {
      if (check("isRemoteTarget") && !check("isRemoteEventConnected")) call("refreshRemoteStatus");
    });
    every(1500, () => call("refreshRendererSession"));
    // An incoming DLNA render paints the same transport row but is not a remote
    // play target, so the 500ms tick has to recognise both states.
    every(500, () => { if (check("isRemoteTarget") || check("isIncomingRendererSession")) call("updateRemoteUi"); });
    every(10000, () => call("refreshServerUserState"));
    if (doc?.addEventListener) doc.addEventListener("visibilitychange", onVisibilityChange);

    return {
      resume,
      visible,
      stop() {
        intervals.splice(0).forEach(id => clearIntervalSafe(id));
        if (doc?.removeEventListener) doc.removeEventListener("visibilitychange", onVisibilityChange);
      },
    };
  }

  globalThis.fnAudioUiSyncScheduler = { create };
})();
