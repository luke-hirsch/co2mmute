import { expect, test } from "@playwright/test";

/**
 * The credential pages and the front door — S22.
 *
 * The Django half's login, sign-up and password pages were the last Tailwind UI
 * boilerplate in the project, and under it three pages of "Passwort vergessen?"
 * did not compile. The backend suite reads what each page says
 * (`co2mmute/tests/test_credentials.py`); this reads them in WebKit, where the
 * forms and the landing page's join box are actually used.
 *
 * **No failed login in here, on purpose.** The login throttle counts wrong
 * passwords per address for 15 minutes, and every spec's `loginAsHost` comes
 * from the same address — one deliberate miss per run and the suite locks
 * itself out a few runs later (`docs/testfaelle.md`, the note under S-09). A refused
 * sign-up is safe: that door counts only accounts it created.
 */
test.describe("credential pages", () => {
  test("the login page asks for a name and a password, and offers to stay", async ({ page }) => {
    await page.goto("/accounts/login/");

    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Anmelden");
    await expect(page.getByLabel("Benutzername")).toBeVisible();
    await expect(page.getByLabel("Passwort", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Angemeldet bleiben")).not.toBeChecked();
  });

  test("a weak password on sign-up is refused rule by rule, in German", async ({ page }) => {
    await page.goto("/accounts/signup/");
    await page.getByLabel("Benutzername").fill(`e2e-refused-${Date.now()}`);
    await page.getByLabel("E-Mail-Adresse").fill("e2e-refused@example.com");
    await page.getByLabel("Passwort").fill("abc");
    await page.getByRole("button", { name: "Konto anlegen" }).click();

    const refusal = page.getByRole("alert");
    await expect(refusal).toBeVisible();
    // One line per broken rule, not a Python list on one line.
    expect(await refusal.locator("li").count()).toBeGreaterThan(1);
    await expect(refusal).not.toContainText("[");
    await expect(refusal).not.toContainText("password");
  });

  test("Passwort vergessen leads to a form, not a server error", async ({ page }) => {
    await page.goto("/accounts/login/");
    await page.getByRole("link", { name: "Passwort vergessen?" }).click();

    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Passwort vergessen");
    await expect(page.getByLabel("E-Mail-Adresse")).toBeVisible();
  });
});

test.describe("the front door", () => {
  test("Los on the landing page goes to the game's join screen", async ({ page }) => {
    await page.goto("/");
    await page.locator("#join-code").fill("abc123");
    await page.getByRole("button", { name: "Los" }).click();

    await page.waitForURL(/\/app\/join\/ABC123$/);
  });

  test("Los with nothing typed asks for the id instead", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Los" }).click();

    await page.waitForURL(/\/app\/join\/?$/);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("Django's old join page is gone", async ({ page }) => {
    const response = await page.goto("/join/");

    expect(response?.status()).toBe(404);
  });
});
