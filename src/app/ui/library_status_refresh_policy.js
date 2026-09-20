(() => {
  function plan(inFlight, refresh) {
    const hasActiveRequest = inFlight === true;
    const forceRefresh = refresh === true;
    return {
      reuse: hasActiveRequest,
      queueRefresh: hasActiveRequest && forceRefresh,
    };
  }

  globalThis.fnAudioLibraryStatusRefreshPolicy = { plan };
})();
