import { expect, test, type Page } from "@playwright/test";

import { MAP_NAME, createGame } from "./game";
import { loginAsHost } from "./host";

/** Set `E2E_SHOTS` to a folder and the new game's screens are saved there too. */
const shots = process.env.E2E_SHOTS;

async function shot(page: Page, name: string) {
  if (shots) await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true });
}

/**
 * The study pages, as staff: a study, its codes and their cards, a game from a
 * lobby, a note with fields. What only a browser shows is the card sheet — no
 * header above it, and the toolbar gone under print media.
 */
test("a study with codes, a linked game and a note, and its card sheet", async ({
  page,
}) => {
  await loginAsHost(page);
  const gameId = await createGame(page, { name: "Studien-Spiel" });

  await page.goto("/app/game/create");
  const header = page.getByRole("banner");
  await header.getByRole("button", { name: "Studien" }).click();
  await header.getByRole("link", { name: "Alle Studien" }).click();
  await expect(page).toHaveURL(/\/app\/studies\/?$/);

  await page.getByRole("button", { name: "Neue Studie" }).click();
  await page.getByLabel("Name").fill("E2E Studie");
  await page.getByRole("button", { name: "Studie anlegen" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "E2E Studie" })).toBeVisible();

  // Codes are optional; twelve of them.
  await page.getByRole("button", { name: "Codes erzeugen" }).click();
  await expect(page.getByText("12 Codes")).toBeVisible();

  // A game that waits in its lobby.
  await page.getByLabel("Spiel-ID").fill(gameId);
  await page.getByRole("button", { name: "Spiel verknüpfen" }).click();
  await expect(page.getByText("wartet in der Lobby")).toBeVisible();

  // A note with two fields.
  await page.getByRole("button", { name: "Notiz hinzufügen" }).click();
  await page.getByLabel("Text", { exact: true }).fill("Zwei Klassen, laut.");
  await page.getByRole("button", { name: "Zeile hinzufügen" }).click();
  await page.getByRole("button", { name: "Zeile hinzufügen" }).click();
  await page.getByLabel("Feld").nth(0).fill("Ort");
  await page.getByLabel("Wert").nth(0).fill("Aula");
  await page.getByLabel("Feld").nth(1).fill("Schüler");
  await page.getByLabel("Wert").nth(1).fill("24");
  await page.getByRole("button", { name: "Notiz speichern" }).click();
  await expect(page.getByText("Zwei Klassen, laut.")).toBeVisible();
  await expect(page.getByText("Aula")).toBeVisible();

  // The card sheet.
  await page.getByRole("link", { name: "Karten drucken" }).click();
  await expect(page.getByRole("heading", { level: 1, name: /Teilnahmekarten/ })).toBeVisible();
  await expect(page.getByRole("img", { name: /QR-Code für/ })).toHaveCount(12);
  await expect(page.getByRole("banner")).toHaveCount(0);
  await page.emulateMedia({ media: "print" });
  await expect(page.getByRole("button", { name: "Drucken" })).toBeHidden();
  await page.emulateMedia({ media: "screen" });

  // And the study goes again: nothing in it started.
  await page.getByRole("link", { name: "Zurück zur Studie" }).click();
  await page.getByRole("button", { name: "Studie löschen" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Löschen" }).click();
  await expect(page).toHaveURL(/\/app\/studies\/?$/);
});

test("a new game from the study page lands in the study, CO₂ hidden", async ({
  page,
}) => {
  await loginAsHost(page);
  await page.goto("/app/studies");
  await page.getByRole("button", { name: "Neue Studie" }).click();
  await page.getByLabel("Name").fill("E2E Neues Spiel");
  await page.getByRole("button", { name: "Studie anlegen" }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: "E2E Neues Spiel" }),
  ).toBeVisible();
  const studyUrl = page.url();

  await page.getByRole("link", { name: "Neues Spiel" }).click();
  await expect(
    page.getByText("Das Spiel kommt in die Studie „E2E Neues Spiel“."),
  ).toBeVisible();
  await page.locator("#game_name").fill("E2E Studienspiel");
  await page.locator("#game_map").selectOption({ label: MAP_NAME });
  // The research section is open already: a study's game is a research game.
  await page.getByLabel("bis zur Auswertung verdecken").check();
  await shot(page, "formular-studie");
  await page.getByRole("button", { name: "Spiel anlegen" }).click();
  await page.waitForURL(/\/app\/game\/(?!create)[^/]+\/?$/);
  const gameId = new URL(page.url()).pathname.split("/").filter(Boolean).pop();

  await page.goto(studyUrl);
  const row = page.getByRole("listitem").filter({ hasText: gameId! });
  await expect(row).toContainText("E2E Studienspiel");
  await expect(row).toContainText("CO₂ verdeckt");
  await expect(row).toContainText("wartet in der Lobby");
  await shot(page, "studie-spiele");
});
