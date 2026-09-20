/* Mobile pager visibility policy. DOM access stays in the caller; this keeps
 * the scroll/visibility decision independently testable. */
(function (global) {
  function updateMobilePagerVisibility({
    searchActive = false,
    isMobile = false,
    pager = null,
    list = null,
    requestFrame = (callback) => callback(),
  } = {}) {
    if (searchActive || !pager) return;
    const hasPager = Boolean(pager.querySelector?.(".pager-inner"));
    if (!hasPager || !isMobile) {
      pager.classList?.toggle("mobile-visible", hasPager);
      return;
    }
    const atBottom = !list || list.scrollHeight <= list.clientHeight + 1
      || list.scrollTop + list.clientHeight >= list.scrollHeight - 2;
    const wasVisible = pager.classList?.contains("mobile-visible");
    pager.classList?.toggle("mobile-visible", atBottom);
    if (atBottom && !wasVisible && list) {
      requestFrame(() => {
        if (pager.classList?.contains("mobile-visible")) list.scrollTop = list.scrollHeight;
      });
    }
  }

  global.fnAudioLibraryPagerVisibility = { updateMobilePagerVisibility };
})(globalThis);
