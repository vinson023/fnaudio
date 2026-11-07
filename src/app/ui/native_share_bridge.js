/* Driving fnOS's own file manager from inside the player.

Two jobs share one set of lookups:

1. 「打开包含的文件夹」 — the host bridge only navigates, it never selects. Landing
   on a directory leaves the song unfound inside it, so the player locates the
   file itself: read the row for that exact path, page the virtualised list when
   the row is not rendered yet, and select it.
2. 「分享外部链接」 — that panel is internal React state of the file manager (its
   bundle has no message listener, no global and no route that opens it). The one
   supported way in is the file manager's own context menu.

Neither needs a private API: the player shares an origin with the file manager
(the app is served from /cgi/ThirdParty/fnaudio/index.cgi/ on the desktop's own
port), so the parent document is readable.

Everything here is a pure lookup or a DOM event so the pieces can be tested
without a desktop: given a document, find the search box, the row for a path, the
menu item, the scrolling element; given an element, type into it, scroll it, or
activate it.
*/
(function (root) {
  "use strict";

  // The file manager's search box takes a keyword, not a path. Long names are
  // cut so the field stays readable and the query stays selective.
  const SEARCH_LIMIT = 24;

  function searchTerm(fileName) {
    const name = String(fileName || "").trim();
    if (!name) return "";
    const dot = name.lastIndexOf(".");
    const stem = dot > 0 ? name.slice(0, dot) : name;
    return stem.slice(0, SEARCH_LIMIT).trim();
  }

  // The file manager writes `data-path` without the leading slash while the
  // player's own location payload carries an absolute path. Normalising both
  // sides is what keeps the two spellings from being two different files.
  function relativePath(value) {
    return String(value || "").trim().replace(/^\/+/, "").replace(/\/{2,}/g, "/");
  }

  function parentOf(value) {
    const path = relativePath(value);
    const slash = path.lastIndexOf("/");
    return slash > 0 ? path.slice(0, slash) : "";
  }

  function rectOf(element) {
    if (!element || typeof element.getBoundingClientRect !== "function") return null;
    const rect = element.getBoundingClientRect();
    return rect && rect.width > 0 && rect.height > 0 ? rect : null;
  }

  function textOf(element) {
    return String((element && element.textContent) || "").trim();
  }

  function all(doc, selector) {
    if (!doc || typeof doc.querySelectorAll !== "function") return [];
    try {
      return Array.from(doc.querySelectorAll(selector));
    } catch (error) {
      return [];
    }
  }

  // The file manager's own search field: the only visible input that offers
  // 「搜索」 as its placeholder.
  function findSearchInput(doc) {
    return all(doc, "input").find(element =>
      rectOf(element) && /搜索/.test(String(element.getAttribute("placeholder") || ""))
    ) || null;
  }

  // Whether the listing is rendered with the table this bridge knows how to read.
  // A folder listing that is still loading and one that never uses this markup
  // look the same to `findRowCell`, so the caller uses this to stop waiting on a
  // shell it will never be able to drive.
  function hasTable(doc) {
    return all(doc, ".trim-ui__table--td").some(element => rectOf(element));
  }

  // A row's name cell. Matching the whole cell text is what keeps 「GALA - 水手公园」
  // from also matching 「GALA - 水手公园 (Live)」.
  function findRowCell(doc, fileName) {
    const wanted = String(fileName || "").trim();
    if (!wanted) return null;
    return all(doc, ".trim-ui__table--td").find(element =>
      rectOf(element) && textOf(element) === wanted
    ) || null;
  }

  // The row of one file. Matching the path, not the visible name, is what keeps
  // two folders that hold the same file name apart.
  function findFileRow(doc, path) {
    const wanted = relativePath(path);
    if (!wanted) return null;
    return all(doc, "tr[data-path]").find(element =>
      relativePath(element.dataset && element.dataset.path) === wanted && rectOf(element)
    ) || null;
  }

  // Whether the window currently lists that folder. Rows only exist for the slice
  // the table has rendered, so this asks about any row living directly inside the
  // folder — enough to tell "the folder I asked for is up" from "the previous
  // listing is still on screen while the host switches".
  function isFolderListing(doc, folder) {
    const wanted = relativePath(folder);
    if (!wanted) return false;
    return all(doc, "tr[data-path]").some(element =>
      parentOf(element.dataset && element.dataset.path) === wanted
    );
  }

  // The element that actually scrolls the listing: the table body is virtualised,
  // so rows on later pages do not exist until this element moves.
  function findListScroller(doc) {
    return all(doc, ".trim-ui__table--scrollbar").find(element =>
      element.scrollHeight > element.clientHeight + 20 && element.clientHeight > 80
    ) || null;
  }

  function scrollListBy(scroller, delta) {
    if (!scroller) return false;
    const before = Number(scroller.scrollTop || 0);
    const limit = Math.max(0, Number(scroller.scrollHeight || 0) - Number(scroller.clientHeight || 0));
    scroller.scrollTop = Math.max(0, Math.min(limit, before + Number(delta || 0)));
    fire(scroller, "Event", "scroll", { bubbles: true });
    return Number(scroller.scrollTop || 0) !== before;
  }

  // Centre the row inside the list box. `scrollIntoView` would also move whatever
  // window hosts the file manager, which reads as the whole page jumping.
  function revealRow(row, scroller) {
    const box = rectOf(scroller);
    const rect = rectOf(row);
    if (!box || !rect) return false;
    scroller.scrollTop = Number(scroller.scrollTop || 0) + (rect.top - box.top) - (box.height - rect.height) / 2;
    fire(scroller, "Event", "scroll", { bubbles: true });
    return true;
  }

  // The row's name cell, which is where the file manager's own menu is opened
  // from; falling back to the row keeps a shell with a different column set usable.
  function nameCellOf(row) {
    if (!row) return null;
    return all(row, ".trim-ui__table--td").find(element => rectOf(element)) || null;
  }

  function isRowSelected(row) {
    return Boolean(row) && /(^|\s)trim-ui__table--tr-selected(\s|$)/.test(String(row.className || ""));
  }

  // Selecting is a plain press; the file manager's rows are list items rather than
  // buttons, so the press sequence is replayed exactly as it is for menu items.
  function selectRow(row) {
    return activate(row);
  }

  // The menu item whose whole label is the wanted text, preferring the innermost
  // node so the click lands on the item and not on a wrapper that contains it.
  function findMenuItem(doc, label) {
    const wanted = String(label || "").trim();
    if (!wanted) return null;
    const matches = all(doc, "div,span,li,button,a").filter(element =>
      rectOf(element) && textOf(element) === wanted
    );
    return matches.find(element => !matches.some(other => other !== element && element.contains(other))) || null;
  }

  function eventOf(element, constructorName, type, init) {
    const view = element && element.ownerDocument && element.ownerDocument.defaultView;
    const Constructor = (view && view[constructorName]) || root[constructorName];
    if (typeof Constructor !== "function") return null;
    return new Constructor(type, init);
  }

  function fire(element, constructorName, type, init) {
    const event = eventOf(element, constructorName, type, init);
    if (!event) return false;
    element.dispatchEvent(event);
    return true;
  }

  // React reads `value` through its own setter, so assigning `element.value`
  // leaves the app's state untouched and the search never runs. Going through the
  // prototype setter (the one belonging to the element's own document) is what
  // makes the framework see the change.
  function typeInto(input, value) {
    if (!input) return false;
    const view = input.ownerDocument && input.ownerDocument.defaultView;
    const prototype = view && view.HTMLInputElement && view.HTMLInputElement.prototype;
    const descriptor = prototype && Object.getOwnPropertyDescriptor(prototype, "value");
    if (typeof input.focus === "function") input.focus();
    if (descriptor && typeof descriptor.set === "function") descriptor.set.call(input, String(value));
    else input.value = String(value);
    fire(input, "Event", "input", { bubbles: true });
    fire(input, "KeyboardEvent", "keydown", { key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true });
    fire(input, "KeyboardEvent", "keyup", { key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true });
    return true;
  }

  // The file manager opens its menu on a right press, so the press and the
  // contextmenu event are both sent; some builds only listen for one of them.
  function openContextMenu(element) {
    const rect = rectOf(element);
    if (!rect) return false;
    const init = {
      bubbles: true,
      cancelable: true,
      button: 2,
      buttons: 2,
      clientX: rect.x + Math.min(rect.width / 2, 40),
      clientY: rect.y + rect.height / 2,
    };
    fire(element, "MouseEvent", "mousedown", init);
    fire(element, "MouseEvent", "mouseup", init);
    fire(element, "MouseEvent", "contextmenu", init);
    return true;
  }

  // Menu items are plain divs with pointer handlers; `element.click()` alone does
  // not reach them, so the full press sequence is replayed.
  function activate(element) {
    if (!element) return false;
    const init = { bubbles: true, cancelable: true, button: 0, buttons: 1 };
    fire(element, "MouseEvent", "mouseover", init);
    fire(element, "MouseEvent", "mousedown", init);
    fire(element, "MouseEvent", "mouseup", init);
    fire(element, "MouseEvent", "click", init);
    return true;
  }

  root.fnAudioNativeShare = {
    relativePath,
    parentOf,
    searchTerm,
    findSearchInput,
    hasTable,
    findRowCell,
    findFileRow,
    isFolderListing,
    findListScroller,
    scrollListBy,
    revealRow,
    nameCellOf,
    isRowSelected,
    selectRow,
    findMenuItem,
    typeInto,
    openContextMenu,
    activate,
  };
})(globalThis);
