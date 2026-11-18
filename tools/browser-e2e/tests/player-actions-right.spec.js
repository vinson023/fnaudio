/* The bottom-right icon row must not move when the window narrows.

Owner's report: inside the fnOS desktop, dragging the app window to its narrowest
made the row of player icons slide left; it had been reported before and come
back.  The cause was the 761-1100px breakpoint centring the row: measured on this
fixture the last icon sat 20px from the player's right edge at 1440, 103px at
1100 and 78px at 1000.  The row is right-aligned at every width now, so the gap
is constant and this test is what keeps it that way.
*/
const path = require("path");
const { spawn } = require("child_process");
const { test, expect } = require("@playwright/test");

let fixture;
let baseUrl;

test.beforeAll(async () => {
  const script = path.resolve(__dirname, "..", "..", "ui_e2e_fixture.py");
  fixture = spawn(process.env.PYTHON || "python", ["-B", script, "--port", "0"], {
    cwd: path.resolve(__dirname, "..", "..", ".."),
    stdio: ["ignore", "pipe", "pipe"],
  });
  baseUrl = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("UI fixture did not start")), 8000);
    fixture.once("error", reject);
    fixture.stderr.on("data", data => process.stderr.write(data));
    fixture.stdout.once("data", data => {
      clearTimeout(timer);
      resolve(String(data).trim());
    });
  });
});

test.afterAll(() => {
  if (fixture && !fixture.killed) fixture.kill();
});

// Both sides of every breakpoint that touches the player row, plus the two
// widths where the regression was measured.
const WIDTHS = [1440, 1200, 1100, 1000, 900, 820, 780, 761];

test("the player icon row keeps its right edge at every width", async ({ page }) => {
  const measured = [];
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
    await expect(page.locator(".track")).toHaveCount(4);
    const gap = await page.evaluate(() => {
      const player = document.querySelector(".player");
      const actions = document.querySelector(".player-actions");
      const buttons = Array.from(actions.querySelectorAll("button"))
        .filter(button => button.offsetParent !== null);
      const last = buttons[buttons.length - 1];
      return player.getBoundingClientRect().right - last.getBoundingClientRect().right;
    });
    measured.push({ width, gap });
  }
  const widest = measured[0];
  for (const row of measured) {
    // A centred row put this gap at 103px; right-aligned it is the player's own
    // padding.  The tolerance covers the two padding tokens the breakpoints use.
    expect(
      Math.abs(row.gap - widest.gap),
      `width ${row.width}: gap ${row.gap.toFixed(1)}px vs ${widest.gap.toFixed(1)}px at ${widest.width}`,
    ).toBeLessThanOrEqual(3);
    expect(row.gap, `width ${row.width}: the icon row left the right edge`).toBeLessThan(40);
  }
});
