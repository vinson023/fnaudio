(function (global) {
  "use strict";
  // Keep the active hydration identity as an array rather than a joined key: a
  // large imported playlist must not create an unbounded string merely to
  // decide whether its already-running request can be reused.
  function create(view, ids) {
    return {
      view: typeof view === "string" ? view : "",
      ids: Array.isArray(ids) ? ids.slice() : [],
    };
  }
  function matches(request, view, ids) {
    if (!request || request.view !== (typeof view === "string" ? view : "")) return false;
    if (!Array.isArray(request.ids) || !Array.isArray(ids) || request.ids.length !== ids.length) return false;
    return request.ids.every((id, index) => id === ids[index]);
  }
  global.fnAudioItemHydrationRequest = { create, matches };
})(typeof window !== "undefined" ? window : globalThis);
