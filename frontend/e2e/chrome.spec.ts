import { expect, test } from "@playwright/test";

import { loginAsHost } from "./host";

/**
 * One header and one footer, on both halves of the site (S20).
 *
 * The list is the server's (`co2mmute/navigation.py`), and its contents are
 * pinned by `co2mmute/tests/test_navigation.py`. What only a browser can show
 * is the behaviour: the flyouts are native popovers and the phone menu a
 * native `<dialog>` on *both* halves, and on the SPA's a link into the app is
 * followed by the router — a menu that navigated but stayed open, or a link
 * that reloaded the whole document, would both pass every unit test.
 */

test("a host's header in the app has the map menu and follows it without a reload", async ({
  page,
}) => {
  await loginAsHost(page);
  await page.goto("/app/game/create");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

  // Survives a router navigation, not a document load.
  await page.evaluate(() => {
    (window as unknown as { sameDocument: boolean }).sameDocument = true;
  });

  const header = page.getByRole("banner");
  await header.getByRole("button", { name: "Karten" }).click();
  const allMaps = header.getByRole("link", { name: "Alle Karten" });
  await expect(allMaps).toBeVisible();
  await allMaps.click();

  await expect(page).toHaveURL(/\/app\/maps\/?$/);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(allMaps).toBeHidden();
  expect(
    await page.evaluate(
      () => (window as unknown as { sameDocument?: boolean }).sameDocument,
    ),
  ).toBe(true);

  await expect(header.getByRole("link", { name: /Abmelden/ })).toHaveAttribute(
    "href",
    "/accounts/logout/",
  );
});

test("the Django header offers the same menu", async ({ page }) => {
  await loginAsHost(page);
  await page.goto("/docs/hintergrund/");

  const header = page.getByRole("banner");
  await header.getByRole("button", { name: "Karten" }).click();
  await expect(header.getByRole("link", { name: "Alle Karten" })).toHaveAttribute(
    "href",
    "/app/maps",
  );
  await expect(header.getByRole("link", { name: "Hochladen" })).toHaveAttribute(
    "href",
    "/app/maps/upload",
  );
});

test("on a phone the menu opens, and following a link closes it", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await loginAsHost(page);
  await page.goto("/app/maps");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

  await page.getByRole("button", { name: "Menü", exact: true }).click();
  const menu = page.getByRole("dialog", { name: "Menü" });
  // The <dialog> itself draws no box — the panel inside it is `position:
  // fixed`, as on the Django side — so it is its contents that are visible.
  await expect(menu.getByRole("link", { name: "Abmelden" })).toBeVisible();

  await menu.getByText("Spielen", { exact: true }).click();
  await menu.getByRole("link", { name: "Erstellen" }).click();

  await expect(page).toHaveURL(/\/app\/game\/create\/?$/);
  await expect(menu.getByRole("link", { name: "Abmelden" })).toBeHidden();
  // A closed menu gives the page its scrolling back.
  expect(await page.evaluate(() => document.documentElement.style.overflow)).toBe("");
});

test("a player on the join screen sees no map menu and no way to sign out", async ({
  page,
}) => {
  await page.goto("/app/join");

  const header = page.getByRole("banner");
  await expect(header.getByRole("link", { name: /Anmelden/ })).toBeVisible();
  await expect(header.getByRole("button", { name: "Karten" })).toHaveCount(0);
  await expect(header.getByText("Abmelden")).toHaveCount(0);

  const footer = page.getByRole("contentinfo");
  for (const name of ["Impressum", "Datenschutz", "Cookies", "Quellcode"]) {
    await expect(footer.getByRole("link", { name })).toBeVisible();
  }
});

test("the docs menu leads to both languages, and every page to its twin (F13)", async ({
  page,
}) => {
  await page.goto("/app/join");

  const header = page.getByRole("banner");
  await header.getByRole("button", { name: "Docs" }).click();
  const panel = page.locator("#nav-docs");
  for (const [name, href] of [
    ["Schnellstart", "/docs/schnellstart/"],
    ["Hintergrund", "/docs/hintergrund/"],
    ["Ablaufdiagramme", "/docs/ablaufdiagramme/"],
  ]) {
    await expect(panel.getByRole("link", { name, exact: true })).toHaveAttribute("href", href);
  }
  // One rule, between the German three and the English three.
  await expect(panel.locator("hr")).toHaveCount(1);
  const background = panel.getByRole("link", { name: "Background", exact: true });
  await expect(background).toHaveAttribute("lang", "en");

  // A Django page: the browser leaves the SPA for it.
  await background.click();
  await expect(page).toHaveURL(/\/docs\/en\/background\/$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("What’s behind a round");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByRole("banner")).toHaveAttribute("lang", "de");

  await page.getByRole("main").getByRole("link", { name: "Diese Seite auf Deutsch" }).click();
  await expect(page).toHaveURL(/\/docs\/hintergrund\/$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Was hinter einer Runde steckt");
});

test("on a phone the Django menu offers the docs in both languages", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/docs/schnellstart/");

  await page.getByRole("button", { name: "Menü", exact: true }).click();
  const menu = page.getByRole("dialog", { name: "Menü" });
  await menu.getByText("Docs", { exact: true }).click();
  await expect(menu.getByRole("link", { name: "Ablaufdiagramme" })).toBeVisible();
  await expect(menu.getByRole("link", { name: "Flowcharts" })).toHaveAttribute(
    "href",
    "/docs/en/flowcharts/",
  );
});
