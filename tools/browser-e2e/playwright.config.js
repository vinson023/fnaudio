const fs = require("fs");
const path = require("path");
const { defineConfig } = require("@playwright/test");

const candidates = [
  process.env.FNAUDIO_BROWSER_EXECUTABLE,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
].filter(Boolean);
const executablePath = candidates.find(candidate => fs.existsSync(candidate));
if (!executablePath) {
  throw new Error("Set FNAUDIO_BROWSER_EXECUTABLE to a Chrome/Edge/Chromium executable.");
}

module.exports = defineConfig({
  testDir: path.join(__dirname, "tests"),
  timeout: 20000,
  fullyParallel: false,
  workers: 1,
  reporter: "line",
  use: {
    headless: true,
    launchOptions: { executablePath },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});
