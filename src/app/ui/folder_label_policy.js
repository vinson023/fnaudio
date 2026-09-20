(function (root) {
  "use strict";
  function text(value) { return typeof value === "string" ? value : ""; }
  function display(path) {
    const value = text(path).replace(/[\\/]+$/, "");
    const parts = value.split(/[\\/]/).filter(Boolean);
    return parts[parts.length - 1] || "根目录";
  }
  function label(rootPath, folderPath) {
    if (!text(rootPath)) return "根目录";
    const parts = [display(rootPath)];
    const relative = text(folderPath);
    if (relative) parts.push(...relative.split("/").filter(Boolean));
    return parts.join(" / ");
  }
  root.fnAudioFolderLabelPolicy = Object.freeze({ display, label });
})(globalThis);
