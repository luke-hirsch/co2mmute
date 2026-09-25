import { expect, test } from "@playwright/test";

/**
 * The harness itself: WebKit reaches nginx, the self-signed certificate is
 * accepted, and both halves of the hybrid answer — the Django-rendered funnel
 * and the Vite bundle under `/app/`.
 *
 * Deliberately shallow. It exists so that a red e2e run can be read as "the
 * feature broke" rather than "the setup broke", and it is the first thing to
 * check when every other spec fails at once.
 */

test.describe("the funnel answers", () => {
  test("the landing page is served by Django", async ({ page }) => {
    const response = await page.goto("/");

    expect(response?.status()).toBe(200);
    await expect(page).toHaveTitle(/CO2MMUTE/);
    // The transit-line diagram is the landing page, so its first terminus is
    // the load-bearing thing on it rather than any one heading.
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  // Fixed links in the base.html footer, and part of the deliverable — a
  // missing one is a legal problem, not a cosmetic one.
  for (const path of ["/legal/impressum/", "/legal/dsgvo/", "/legal/cookies/"]) {
    test(`${path} is reachable`, async ({ page }) => {
      const response = await page.goto(path);

      expect(response?.status()).toBe(200);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    });
  }

  test("the SPA boots under /app/", async ({ page }) => {
    const response = await page.goto("/app/join");

    expect(response?.status()).toBe(200);
    // React has mounted, rather than nginx having served the index shell and
    // the bundle having thrown. #root is empty until it does.
    await expect(page.locator("#root")).not.toBeEmpty();
  });

  test("a websocket reaches Daphne", async ({ page }) => {
    // The one piece neither a page load nor an API call exercises. In the
    // container nginx upgrades the connection; natively the Vite proxy does
    // (`ws: true`), and that rule is easy to break without anything else
    // noticing until a round silently stops broadcasting.
    //
    // A made-up game id is on purpose: the point is that the handshake is
    // ANSWERED. Daphne rejects it with 4401 for having no cookie, and the
    // browser surfaces a rejected upgrade as `error` — either way something
    // replied. A dead proxy gives no reply at all.
    await page.goto("/app/join");

    const outcome = await page.evaluate(
      () =>
        new Promise<string>((resolve) => {
          const socket = new WebSocket(
            `${location.origin.replace(/^http/, "ws")}/ws/game/NOPE00/`,
          );
          socket.onopen = () => resolve("open");
          socket.onclose = (event) => resolve(`close ${event.code}`);
          socket.onerror = () => resolve("error");
          setTimeout(() => resolve("timeout"), 8000);
        }),
    );

    expect(outcome).not.toBe("timeout");
  });

  test("the colour-mode bootstrap ran before anything painted", async ({ page }) => {
    await page.goto("/");

    // The inline <head> script is the one piece of JS both halves share, and
    // when it has run <html> carries a resolved class rather than nothing.
    const hasMode = await page.evaluate(() => {
      const html = document.documentElement;
      return html.classList.contains("dark") || html.dataset.theme !== undefined
        ? true
        : window.matchMedia("(prefers-color-scheme: dark)").matches === false;
    });
    expect(hasMode).toBe(true);
  });
});
