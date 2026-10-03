import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

import { loginAsHost } from "./host";

/**
 * F14: deleting a version in the editor.
 *
 * The website could not, and the admin's delete took the bare version and left
 * every street that was only in it in no version — invisible in the editor,
 * still in the export. Now the version panel asks the server what goes, names
 * it, and the delete takes exactly that.
 *
 * Runs on a map of its own, imported here and deleted afterwards, with one
 * version drawn on top of it: on the shipped map nothing is in one version
 * only, so a delete there takes nothing but the version — the second case.
 */

const SHIPPED_MAP = fileURLToPath(
  new URL("../../map_examples/Berlin_Mitte-West.json", import.meta.url),
);

type Version = { id: number; name: string; base_version: boolean };
type Graph = { nodes: { id: number }[]; edges: { id: number }[] };

async function csrf(page: Page) {
  const cookies = await page.context().cookies();
  return {
    "X-CSRFToken": cookies.find((c) => c.name === "csrftoken")?.value ?? "",
    Referer: page.url(),
  };
}

async function versionsOf(page: Page, mapId: number) {
  return (await (
    await page.request.get(`/api/maps/${mapId}/versions/`)
  ).json()) as Version[];
}

/** The version panel's row for `name`, opened. */
async function openVersion(page: Page, name: string) {
  const row = page
    .locator("div")
    .filter({ has: page.getByText(name, { exact: true }) })
    .filter({ has: page.getByRole("button", { name: "Bearbeiten" }) })
    .last();
  await row.getByRole("button", { name: "Bearbeiten" }).click();
  return row;
}

test.describe("deleting a map version", () => {
  let mapId: number | null = null;
  let gameId: string | null = null;

  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1500, height: 1000 });
    await loginAsHost(page);
    const file = JSON.parse(await readFile(SHIPPED_MAP, "utf-8"));
    delete file.background_image; // ~1 MB the editor does not need here
    const imported = await page.request.post("/api/maps/import/", {
      headers: await csrf(page),
      multipart: {
        map_name: `F14 Versionen ${Date.now()}`,
        max_players: "6",
        json_file: {
          name: "map.json",
          mimeType: "application/json",
          buffer: Buffer.from(JSON.stringify(file)),
        },
      },
    });
    expect(imported.status()).toBe(201);
    mapId = (await imported.json()).id;

    // A version drawn and never combined: a new node and a street to it both
    // ways. The three rows are in this version and nowhere else.
    const base = (await versionsOf(page, mapId!)).find((v) => v.base_version)!;
    const graph = (await (
      await page.request.get(`/api/maps/${mapId}/graph/baseversion/`)
    ).json()) as Graph;
    const drawn = await page.request.post(
      `/api/maps/${mapId}/versions/create-from-diff/`,
      {
        headers: await csrf(page),
        data: {
          source_version_id: base.id,
          version_name: "Neubaugebiet",
          poll_text: "Soll das Neubaugebiet angeschlossen werden?",
          new_nodes: [{ temp_id: "neu", x_position: 1, y_position: 1 }],
          new_edges: [
            {
              temp_start_node: String(graph.nodes[0].id),
              temp_end_node: "neu",
              bidirectional: true,
              walking: true,
              speed_limit: 30,
              lanes: 1,
            },
          ],
        },
      },
    );
    expect(drawn.status()).toBe(201);
  });

  test.afterEach(async ({ page }) => {
    const headers = await csrf(page);
    if (gameId !== null) {
      await page.request.patch(`/api/game/${gameId}/`, {
        headers,
        data: { is_active: false },
      });
      await page.request.delete(`/api/game/${gameId}/`, { headers });
      gameId = null;
    }
    if (mapId !== null) {
      await page.request.delete(`/api/maps/${mapId}/`, { headers });
      mapId = null;
    }
  });

  async function openManager(page: Page) {
    await page.goto(`/app/maps/${mapId}/editor`);
    await page.getByRole("button", { name: "Versionen", exact: true }).click();
    await page.getByRole("button", { name: "Verwalten", exact: true }).click();
  }

  test("a version of its own goes with what only it holds", async ({ page }) => {
    const id = mapId as number;
    const nodesBefore = (await (
      await page.request.get(`/api/maps/${id}/nodes/`)
    ).json()) as unknown[];

    await openManager(page);
    await openVersion(page, "Neubaugebiet");
    await page.getByRole("button", { name: "Version löschen" }).click();

    const dialog = page.getByRole("dialog");
    await expect(
      dialog.getByRole("heading", { name: "Version „Neubaugebiet“ löschen?" }),
    ).toBeVisible();
    await expect(dialog.getByText("Nur in dieser Version, das geht mit:")).toBeVisible();
    await expect(dialog.getByText("1 Knoten", { exact: true })).toBeVisible();
    await expect(dialog.getByText("2 Kanten", { exact: true })).toBeVisible();
    await expect(dialog.getByText("2 Straßen", { exact: true })).toBeVisible();

    await dialog.getByRole("button", { name: "Endgültig löschen" }).click();
    await expect(dialog).toBeHidden();
    await expect(page.getByText("Neubaugebiet", { exact: true })).toHaveCount(0);

    expect((await versionsOf(page, id)).map((v) => v.name)).not.toContain(
      "Neubaugebiet",
    );
    const nodesAfter = (await (
      await page.request.get(`/api/maps/${id}/nodes/`)
    ).json()) as unknown[];
    expect(nodesAfter).toHaveLength(nodesBefore.length - 1);
  });

  test("a change its combinations hold takes only itself, and base has no button", async ({
    page,
  }) => {
    const id = mapId as number;
    await openManager(page);

    await openVersion(page, "Berlin Mitte-West - Base");
    await expect(page.getByRole("button", { name: "Version löschen" })).toHaveCount(0);
    await page.getByRole("button", { name: "Schließen" }).click();

    await openVersion(page, "Busspuren");
    await page.getByRole("button", { name: "Version löschen" }).click();
    const dialog = page.getByRole("dialog");
    await expect(
      dialog.getByText(
        "Alles in ihr steht auch in anderen Versionen – es geht nur die Version selbst.",
      ),
    ).toBeVisible();
    await expect(dialog.getByText(/^Ihre Änderung bleibt in /)).toContainText(
      "»Buslinie + Busspuren + Umgehungsstraßen«",
    );

    await dialog.getByRole("button", { name: "Abbrechen" }).click();
    await expect(dialog).toBeHidden();
    expect((await versionsOf(page, id)).map((v) => v.name)).toContain("Busspuren");
  });

  test("a running game refuses it, in the server's words", async ({ page }) => {
    const id = mapId as number;
    const name = `F14 läuft ${Date.now()}`;
    const created = await page.request.post("/api/game/", {
      headers: await csrf(page),
      data: {
        game_name: name,
        game_password: "",
        game_map: id,
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
    gameId = (await created.json()).game_id as string;
    const started = await page.request.patch(`/api/game/${gameId}/`, {
      headers: await csrf(page),
      data: { is_active: true },
    });
    expect(started.status()).toBe(200);

    await openManager(page);
    await openVersion(page, "Neubaugebiet");
    await page.getByRole("button", { name: "Version löschen" }).click();

    const dialog = page.getByRole("dialog");
    await expect(dialog.getByText(/läuft gerade das Spiel/)).toContainText(`»${name}«`);
    await expect(dialog.getByRole("button", { name: "Endgültig löschen" })).toHaveCount(0);
    expect((await versionsOf(page, id)).map((v) => v.name)).toContain("Neubaugebiet");
  });
});
