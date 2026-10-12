const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const app = fs.readFileSync("app/ui/app.js", "utf8");
function extract(name, signature) {
  const match = app.match(new RegExp(`function ${name}\\(${signature}\\) \\{[\\s\\S]*?\\n\\}`));
  assert.ok(match, `${name} must remain an independently testable top-level function`);
  return match[0];
}
const functions = [
  extract("configuredLibraryRoots", "status = state\\.libraryStatus"),
  extract("currentQueryText", ""),
  extract("libraryQueryParamsFor", "folderRoot, folderPath, page, view = state\\.view"),
  extract("folderNavigationUrls", "root, path, folderPage = 1, trackPage = 1, view = state\\.view"),
  extract("folderEntryRootUrl", ""),
  extract("folderNavigationPrefetchKey", ""),
  extract("cancelFolderNavigationPrefetch", ""),
  extract("prefetchFolderNavigationEntry", ""),
].join("\n");

function createContext({ roots = ["/music"], scanning = false, rootsResponse = null, rejectUrl = "" } = {}) {
  const requests = [];
  const state = {
    view: "all",
    libraryStatus: { library_paths: roots, scanning },
    folderNavigationPrefetchKey: "",
    sortKey: "title",
    sortDir: "asc",
    pageSize: 96,
    folderPageSize: 100,
    folderRoot: "",
    folderPath: "",
    page: 1,
    folderPage: 1,
    groupName: "",
  };
  const paramsPolicy = {
    buildLibraryQueryParams(options) {
      const params = new URLSearchParams();
      params.set("view", options.view);
      params.set("page", String(options.page));
      params.set("limit", String(options.pageSize));
      if (options.folderRoot) params.set("root", options.folderRoot);
      if (options.folderPath) params.set("folder", options.folderPath);
      if (options.search) params.set("search", options.search);
      return params;
    },
  };
  const context = {
    Array, String, JSON, URLSearchParams,
    state,
    document: { hidden: false },
    $: () => ({ value: "Live Query" }),
    currentQueryText: () => "Live Query",
    fnAudioLibraryQueryParams: paramsPolicy,
    groupViews: {},
    isCreatorView: () => false,
    currentCreatorName: () => "",
    isPlaylistView: () => false,
    browseCursorForPage: () => "",
    fetchLibraryResponse(url) {
      requests.push(url);
      if (rejectUrl && (rejectUrl === "*" || url === rejectUrl)) return Promise.reject(new Error("offline"));
      if (url.startsWith("api/library/roots")) {
        return Promise.resolve(rootsResponse || { roots: roots.map(root => ({ root })) });
      }
      return Promise.resolve({ items: [], folders: [], count: 0 });
    },
  };
  vm.runInNewContext(functions + "\nglobalThis.prefetch = prefetchFolderNavigationEntry; globalThis.pair = folderNavigationUrls;", context);
  return { context, requests, state };
}

(async () => {
  {
    const { context, requests, state } = createContext();
    assert.equal(context.prefetch(), true, "a known single root starts the paired folder-entry prefetch");
    const expected = Array.from(context.pair("/music", "", 1, 1, "folders"));
    assert.deepEqual(requests, expected, "the prefetch URLs must exactly match folder navigation URLs");
    assert.equal(new URLSearchParams(requests[1].split("?")[1]).get("view"), "folders",
      "warming the list before setView must still request the folder view, not the outgoing view");
    assert.equal(context.prefetch(), false, "same query identity cannot issue a duplicate pair");
    assert.equal(requests.length, 2);
    state.view = "folders";
  }
  {
    const { context, requests, state } = createContext({ roots: [], rootsResponse: { roots: [{ root: "/music" }] } });
    state.libraryStatus = null;
    assert.equal(context.prefetch(), true, "unknown roots use the authoritative roots request");
    await Promise.resolve();
    await Promise.resolve();
    assert.equal(requests[0], "api/library/roots?search=Live+Query");
    assert.deepEqual(requests.slice(1), Array.from(context.pair("/music", "", 1, 1, "folders")),
      "a discovered single root warms the exact paired page after the shared roots response");
  }
  {
    const { context, requests } = createContext({ roots: ["/music", "/archive"] });
    context.prefetch();
    await Promise.resolve();
    assert.equal(requests.length, 1, "multiple roots warm only the root listing, not a guessed child path");
    assert.equal(requests[0], "api/library/roots?search=Live+Query");
  }
  {
    const { context, requests, state } = createContext({ scanning: true });
    assert.equal(context.prefetch(), false, "speculation must not add load while a scan is active");
    assert.equal(requests.length, 0);
    state.libraryStatus.scanning = false;
    state.view = "folders";
    assert.equal(context.prefetch(), false, "the active folder view does not recursively prefetch itself");
    assert.equal(requests.length, 0);
  }
  {
    const { context, requests, state } = createContext({ rejectUrl: "*" });
    context.prefetch();
    await new Promise(resolve => setTimeout(resolve, 0));
    await new Promise(resolve => setTimeout(resolve, 0));
    assert.equal(state.folderNavigationPrefetchKey, "", "a failed speculative response releases its de-dupe key");
    context.prefetch();
    assert.equal(requests.length, 4, "a later category entry can retry both failed/paired requests");
  }
  console.log("Folder category entry prefetch regression checks passed.");
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
