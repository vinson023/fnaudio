const path = require("path");
const { spawn } = require("child_process");
const { chromium } = require(path.resolve("tools/browser-e2e/node_modules/playwright"));

(async () => {
  const script = path.resolve("tools/ui_e2e_fixture.py");
  const fixture = spawn(process.env.PYTHON || "python", ["-B", script, "--port", "0"], { stdio: ["ignore", "pipe", "pipe"] });
  const baseUrl = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("fixture timeout")), 8000);
    fixture.stdout.once("data", data => { clearTimeout(timer); resolve(String(data).trim()); });
  });
  const browser = await chromium.launch({ executablePath: process.env.FNAUDIO_BROWSER || "C://Program Files//Google//Chrome//Application//chrome.exe" });
  for (const [name, width, height] of [["desktop", 1440, 900], ["phone", 390, 844]]) {
    const page = await browser.newPage({ viewport: { width, height } });
    await page.goto(baseUrl, { waitUntil: "networkidle" });
    await page.locator(".track").first().waitFor();
    if (width <= 760) await page.locator("#mobileNavBtn").click();
    await page.locator("#mobileSettingsNavBtn").click();
    await page.locator("[data-settings-tab='metadata']").click();
    const chip = page.locator('[data-metadata-stat-issues="failed"]');
    await chip.scrollIntoViewIfNeeded();
    await page.screenshot({ path: `artifacts/r519/${name}-pane.png` });
    await chip.click();
    await page.locator("#metadataLogDialog").waitFor();
    await page.waitForTimeout(300);
    await page.screenshot({ path: `artifacts/r519/${name}-log.png` });
    const box = await page.locator("#metadataLogDialog").boundingBox();
    console.log(name, JSON.stringify(box));
    await page.close();
  }
  await browser.close();
  fixture.kill();
})();
