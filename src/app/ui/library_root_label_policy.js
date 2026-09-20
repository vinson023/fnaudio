(function (global) {
  "use strict";

  function pathParts(value) {
    if (typeof value !== "string") return [];
    return value.replace(/[\\\/]+$/, "").split(/[\\\/]/).filter(Boolean);
  }

  function rootLabels(paths) {
    if (!Array.isArray(paths)) return [];
    const bases = paths.map(path => {
      const parts = pathParts(path);
      return parts[parts.length - 1] || "音乐目录";
    });
    const counts = bases.reduce((map, name) => {
      map[name] = (map[name] || 0) + 1;
      return map;
    }, Object.create(null));
    return paths.map((path, index) => {
      const parts = pathParts(path);
      const base = bases[index];
      return counts[base] > 1 && parts.length > 1
        ? `${parts[parts.length - 2]}/${base}`
        : base;
    });
  }

  global.fnAudioLibraryRootLabelPolicy = { rootLabels };
})(typeof window !== "undefined" ? window : globalThis);
