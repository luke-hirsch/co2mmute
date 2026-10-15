import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

import { loginAsHost } from "./host";

/**
 * A map in and out again through the SPA.
 *
 * `/map/upload/` was the last staff tool on Django. The screen that replaced
 * it posts a file to `api/maps/import/`, which is new, and deleting a map asks
 * in a dialog rather than `window.confirm`. Neither half is visible to the
 * backend suite: it can prove the endpoint, not that the screen sends a
 * multipart body the endpoint reads, nor that the dialog is the thing that
 * deletes.
 *
 * Makes its own map and deletes it again, so it needs no seed beyond the staff
 * account.
 */

const SHIPPED_MAP = fileURLToPath(
  new URL("../../map_examples/Berlin_Mitte-West.json", import.meta.url),
);

async function csrf(page: Page) {
  const cookies = await page.context().cookies();
  return {
    "X-CSRFToken": cookies.find((c) => c.name === "csrftoken")?.value ?? "",
    Referer: page.url(),
  };
}

async function upload(page: Page, name: string) {
  await page.goto("/app/maps/upload");
  await page.getByLabel("Name der Karte").fill(name);
  await page.getByLabel("Kartendatei (JSON)").setInputFiles(SHIPPED_MAP);
  await page.getByRole("button", { name: "Karte anlegen" }).click();
  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
  return Number(new URL(page.url()).pathname.match(/\/maps\/(\d+)/)?.[1]);
}

test("the old upload page leads to the new one", async ({ page }) => {
  await loginAsHost(page);

  await page.goto("/map/upload/");

  await expect(page).toHaveURL(/\/app\/maps\/upload$/);
  await expect(
    page.getByRole("heading", { level: 1, name: "Karte hochladen" }),
  ).toBeVisible();
});

test("a broken file is refused with what is wrong in it", async ({ page }) => {
  await loginAsHost(page);
  await page.goto("/app/maps/upload");

  await page.getByLabel("Name der Karte").fill(`Kaputt ${Date.now()}`);
  await page.getByLabel("Kartendatei (JSON)").setInputFiles({
    name: "kaputt.json",
    mimeType: "application/json",
    buffer: Buffer.from(
      JSON.stringify({
        nodes: [{ id: "a", x: 0, y: 0 }],
        edges: [{ start_node: "a", end_node: "z" }],
      }),
    ),
  });
  await page.getByRole("button", { name: "Karte anlegen" }).click();

  await expect(page.getByText("In der Datei stimmt etwas nicht:")).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("'z'");
  await expect(page).toHaveURL(/\/app\/maps\/upload$/);
});

test("a map uploaded here opens, and deleting it asks first", async ({ page }) => {
  const name = `Hochgeladen ${Date.now()}`;
  await loginAsHost(page);
  await page.goto("/app/maps");

  await page.getByRole("link", { name: "Karte hochladen" }).click();
  await expect(page).toHaveURL(/\/app\/maps\/upload$/);

  // The format is there, but not in the way.
  const toggle = page.getByRole("button", { name: "So ist die Datei aufgebaut" });
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await toggle.click();
  await expect(page.locator("#file-format")).toContainText("start_node");

  await page.getByLabel("Name der Karte").fill(name);
  await page.getByLabel("Kartendatei (JSON)").setInputFiles(SHIPPED_MAP);
  await page.getByRole("button", { name: "Karte anlegen" }).click();

  await expect(page).toHaveURL(/\/app\/maps\/\d+\/?$/);
  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();

  // No browser dialog may appear: that was the old `window.confirm`.
  page.on("dialog", (dialog) => {
    throw new Error(`unexpected browser dialog: ${dialog.message()}`);
  });
  await page.getByRole("button", { name: "Karte löschen" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText(name);
  await expect(dialog).toContainText("auf der schon gespielt wurde, bleibt");

  // Cancelling keeps it.
  await dialog.getByRole("button", { name: "Abbrechen" }).click();
  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();

  await page.getByRole("button", { name: "Karte löschen" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Endgültig löschen" }).click();

  await expect(page).toHaveURL(/\/app\/maps\/?$/);
  await expect(page.getByRole("heading", { level: 1, name: "Karten" })).toBeVisible();
  await expect(page.getByText(name)).toHaveCount(0);
});

test("a map a game was on stays, in the server's words", async ({ page }) => {
  const name = `Gespielt ${Date.now()}`;
  const game = `Auf der Karte ${Date.now()}`;

  await loginAsHost(page);
  const mapId = await upload(page, name);
  const created = await page.request.post("/api/game/", {
    headers: await csrf(page),
    data: {
      game_name: game,
      game_password: "",
      game_map: mapId,
      map_updates: true,
      max_players: 2,
      agent_per_player: 1,
      max_rounds: 2,
      max_CO2_level: 32000,
      people_per_agent: 100,
      idle_end_days: 1,
      chat_enabled: false,
    },
  });
  expect(created.status()).toBe(201);
  const gameId = (await created.json()).game_id as string;

  await page.getByRole("button", { name: "Karte löschen" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Endgültig löschen" }).click();

  await expect(page.getByRole("alert")).toContainText(`»${game}«`);
  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();

  // Once the game is gone, so can the map be.
  const headers = await csrf(page);
  expect((await page.request.delete(`/api/game/${gameId}/`, { headers })).status()).toBe(204);
  await page.getByRole("button", { name: "Karte löschen" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Endgültig löschen" }).click();
  await expect(page).toHaveURL(/\/app\/maps\/?$/);
  await expect(page.getByText(name)).toHaveCount(0);
});
