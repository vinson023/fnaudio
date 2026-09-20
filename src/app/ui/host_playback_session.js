(function (global) {
  "use strict";

  // This adapter is deliberately opt-in.  fnOS currently does not document a
  // third-party playback-session bridge, so never probe private Pigeon names
  // or invoke arbitrary WebView objects.  A future public bridge can expose
  // one of the names below without requiring changes to the player itself.
  const CANDIDATE_NAMES = [
    "fnOSPlaybackSession",
    "FnOSPlaybackSession",
    "fnAudioHostPlaybackSession",
  ];
  const METHODS = ["initialize", "synchronize", "requestActivation", "reportState", "release"];

  function finiteInt(value, fallback = 0) {
    try {
      if (typeof value === "boolean" || (typeof value !== "number" && typeof value !== "string")) return fallback;
      const number = Number(value);
      return Number.isFinite(number) ? Math.max(0, Math.min(2147483647, Math.floor(number))) : fallback;
    } catch (error) {
      return fallback;
    }
  }

  function text(value, limit = 256) {
    try {
      if (value == null) return "";
      if (typeof value !== "string" && typeof value !== "number" && typeof value !== "boolean") return "";
      return String(value).slice(0, limit);
    } catch (error) {
      return "";
    }
  }

  function nonNegativeNumber(value) {
    try {
      if (typeof value === "boolean" || (typeof value !== "number" && typeof value !== "string")) return 0;
      const number = Number(value);
      return Number.isFinite(number) ? Math.max(0, number) : 0;
    } catch (error) {
      return 0;
    }
  }

  function read(object, key, fallback) {
    try { return object == null ? fallback : object[key]; } catch (error) { return fallback; }
  }

  function copyMetadata(value) {
    if (!value || typeof value !== "object") return {};
    const result = {};
    try {
      for (const key of Object.keys(value)) {
        try { result[key] = value[key]; } catch (error) { /* Skip hostile fields. */ }
      }
    } catch (error) {
      return {};
    }
    return result;
  }

  function findBridge(root) {
    for (const name of CANDIDATE_NAMES) {
      let candidate;
      try { candidate = root?.[name]; } catch (error) { candidate = null; }
      if (!candidate || typeof candidate !== "object") continue;
      const methods = [];
      for (const method of METHODS) {
        try {
          if (typeof candidate[method] === "function") methods.push(method);
        } catch (error) {
          // A hostile/partial WebView object must not break page startup.
        }
      }
      if (methods.length) return { name, bridge: candidate, methods };
    }
    return { name: "", bridge: null, methods: [] };
  }

  // flutter_inappwebview is a generic WebView transport, not a playback API.
  // Record its presence for diagnostics only; never call an unknown handler.
  function inspectGenericWebViewBridge(root) {
    let candidate;
    try { candidate = root?.flutter_inappwebview; } catch (error) { candidate = null; }
    if (!candidate || (typeof candidate !== "object" && typeof candidate !== "function")) {
      return { detected: false, methods: [] };
    }
    const methods = [];
    try {
      if (typeof candidate.callHandler === "function") methods.push("callHandler");
    } catch (error) {
      // A partial bridge must remain diagnostic-only and never break startup.
    }
    return { detected: methods.length > 0, methods };
  }

  function createHostPlaybackSession(root = global) {
    const found = findBridge(root);
    const genericWebView = inspectGenericWebViewBridge(root);
    const diagnostics = {
      detected: Boolean(found.bridge),
      name: found.name,
      methods: [...found.methods],
      genericWebViewBridgeDetected: genericWebView.detected,
      genericWebViewBridgeMethods: [...genericWebView.methods],
      lastAction: "",
      lastError: "",
    };

    function invoke(method, payload) {
      if (!found.bridge) return false;
      try {
        if (typeof found.bridge[method] !== "function") return false;
        const result = found.bridge[method](payload);
        if (result && typeof result.catch === "function") {
          result.catch(error => {
            diagnostics.lastError = `${method}: ${text(error?.message || error)}`;
          });
        }
        diagnostics.lastAction = method;
        diagnostics.lastError = "";
        return true;
      } catch (error) {
        diagnostics.lastError = `${method}: ${text(error?.message || error)}`;
        return false;
      }
    }

    return {
      available: diagnostics.detected,
      diagnostics() { return { ...diagnostics, methods: [...diagnostics.methods] }; },
      initialize({ participantId, generation, engineEpoch, capabilities } = {}) {
        return invoke("initialize", {
          participantId: text(participantId || "fnaudio-web"),
          generation: finiteInt(generation),
          engineEpoch: finiteInt(engineEpoch),
          capabilities: { ...(capabilities || {}) },
        });
      },
      synchronize(snapshot = {}) {
        return invoke("synchronize", {
          generation: finiteInt(read(snapshot, "generation", 0)),
          engineEpoch: finiteInt(read(snapshot, "engineEpoch", 0)),
          stateVersion: finiteInt(read(snapshot, "stateVersion", 0)),
          trackId: text(read(snapshot, "trackId", "")),
          playing: read(snapshot, "playing", false) === true,
          position: nonNegativeNumber(read(snapshot, "position", 0)),
          duration: nonNegativeNumber(read(snapshot, "duration", 0)),
          outputTarget: text(read(snapshot, "outputTarget", ""), 128),
          metadata: copyMetadata(read(snapshot, "metadata", null)),
        });
      },
      requestActivation(mediaContextId = "") {
        return invoke("requestActivation", { mediaContextId: text(mediaContextId, 128) });
      },
      reportState(snapshot = {}) { return this.synchronize(snapshot); },
      release() { return invoke("release", {}); },
    };
  }

  global.fnAudioCreateHostPlaybackSession = createHostPlaybackSession;
})(typeof window !== "undefined" ? window : globalThis);
