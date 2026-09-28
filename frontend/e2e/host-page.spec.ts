import { expect, test } from "@playwright/test";

import { createGame } from "./game";
import { loginAsHost } from "./host";

/**
 * `/app/host` — the host's own page. S13.
 *
 * It replaces `/accounts/profile/`, a Django template with the game list and a
 * `ProfileForm` on it. Three things are worth a browser rather than a unit
 * test: that the old URL still lands somewhere (it is Django's
 * `LOGIN_REDIRECT_URL`, so it is where every host goes after signing in), that
 * deleting a game asks first and refuses a running one, and that the way to
 * erase the account is still reachable — that last one used to be asserted by
 * grepping the template for a URL, and the template is gone.
 */

test("the old profile URL lands on the host's page, with their games on it", async ({
  page,
}) => {
  await loginAsHost(page);
  const gameId = await createGame(page, { name: "E2E Hostseite" });

  const response = await page.goto("/accounts/profile/");

  // Status first: a content check alone would pass against the login redirect
  // an anonymous request gets instead.
  expect(response?.status()).toBe(200);
  await page.waitForURL(/\/app\/host\/?$/);

  // By id, not by name: a run that fails halfway leaves a row behind, and two
  // games called the same thing then make every later run fail on the locator
  // rather than on what it was testing.
  const row = page.locator("li", { hasText: gameId });
  await expect(row).toBeVisible();
  await expect(row).toContainText("E2E Hostseite");

  await cleanUp(page, gameId);
});

test("a running game is refused, an ended one is thrown away", async ({
  page,
  baseURL,
}) => {
  await loginAsHost(page);
  const gameId = await createGame(page, { name: "E2E Wegwerfspiel" });

  // Start it over the API rather than through the lobby: this spec is about
  // the delete dialog, and what makes a game refuse deletion is `is_active`.
  await api(page, baseURL!, "patch", `/api/game/${gameId}/`, {
    is_active: true,
  });

  await page.goto("/app/host");
  const row = page.locator("li", { hasText: gameId });
  await row.getByRole("button", { name: "Löschen" }).click();

  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("E2E Wegwerfspiel");
  await dialog.getByRole("button", { name: "Endgültig löschen" }).click();

  // Ending it is what writes `end_reason`, and that cannot be worked out
  // afterwards — which is why deleting a game in progress is refused.
  await expect(dialog).toContainText("läuft gerade");
  await expect(row).toBeVisible();

  await api(page, baseURL!, "patch", `/api/game/${gameId}/`, {
    is_active: false,
  });
  await page.reload();

  const again = page.locator("li", { hasText: gameId });
  await again.getByRole("button", { name: "Löschen" }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Endgültig löschen" })
    .click();

  await expect(again).toHaveCount(0);
});

test("the account details save, and the refusal names the field", async ({
  page,
}) => {
  await loginAsHost(page);
  await page.goto("/app/host");

  const name = page.locator("#first_name");
  await expect(name).toBeVisible();
  await name.fill("Spielleitung");
  await page.getByRole("button", { name: "Speichern", exact: true }).click();
  await expect(page.getByText("Gespeichert.")).toBeVisible();

  // The header greets by username and reads `whoami`; a save that left the old
  // value in the corner of every screen would look like it had not taken.
  await page.reload();
  await expect(page.locator("#first_name")).toHaveValue("Spielleitung");

  // A rule the screen cannot check for itself. Its message is the server's, so
  // the assertion is that one arrives under the field it is about and is
  // German — never the sentence, which stays free to improve.
  await page.locator("#email").fill("nicht-eine-adresse");
  await page.getByRole("button", { name: "Speichern", exact: true }).click();
  await expect(page.locator("#email")).toHaveAttribute("aria-invalid", "true");
  const refusal = page.locator("#email-error");
  await expect(refusal).toBeVisible();
  await expect(refusal).not.toContainText(/enter|valid|address|email/i);

  // Put the account back the way the other specs expect it.
  await page.reload();
  await page.locator("#first_name").fill("");
  await page.getByRole("button", { name: "Speichern", exact: true }).click();
  await expect(page.getByText("Gespeichert.")).toBeVisible();
});

/**
 * DSGVO erasure has to be something a host can actually reach.
 *
 * This was a Django test grepping `registration/profile.html` for the URL.
 * The template is gone, so the link is pinned here and the backend keeps only
 * "the page it leads to answers".
 */
test("the way to erase the account is one click from the host's page", async ({
  page,
}) => {
  await loginAsHost(page);
  await page.goto("/app/host");

  await page.getByRole("link", { name: "Konto löschen" }).click();

  await page.waitForURL(/\/accounts\/profile\/delete\/?$/);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});

async function api(
  page: import("@playwright/test").Page,
  baseURL: string,
  method: "patch" | "delete",
  path: string,
  data?: object,
) {
  const cookies = await page.context().cookies();
  const csrf = cookies.find((cookie) => cookie.name === "csrftoken")?.value;
  const headers = { "X-CSRFToken": csrf ?? "", Referer: baseURL };
  if (method === "patch") {
    await page.request.patch(path, { headers, data: data ?? {} });
  } else {
    await page.request.delete(path, { headers });
  }
}

/** End the game and delete it, so a run leaves no row behind. */
async function cleanUp(
  page: import("@playwright/test").Page,
  gameId: string,
): Promise<void> {
  const baseURL = new URL(page.url()).origin;
  await api(page, baseURL, "patch", `/api/game/${gameId}/`, {
    is_active: false,
  });
  await api(page, baseURL, "delete", `/api/game/${gameId}/`);
}
