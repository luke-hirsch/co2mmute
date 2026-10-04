import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

import { loginAsHost } from "./host";

/**
 * The version comparison in the editor: "Verwalten" puts a version on the
 * canvas and draws what it changes.
 *
 * Before it, "Verwalten" changed nothing on the canvas, and what `Busspuren`
 * does could only be read out of the database. On the shipped map the three
 * changes are small and exact, so the counts below are the whole of each:
 * `Busspuren` gives 15 streets a bus lane both ways (30 links) and touches no
 * line — although every line over those streets moved onto the clones.
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

/** The version list's row for `name`. */
function row(page: Page, name: string) {
  return page
    .locator("div")
    .filter({ has: page.getByText(name, { exact: true }) })
    .filter({ has: page.getByRole("button", { name: "Bearbeiten" }) })
    .last();
}

test.describe("the version comparison", () => {
  let mapId: number | null = null;

  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1500, height: 1000 });
    await loginAsHost(page);
    const file = JSON.parse(await readFile(SHIPPED_MAP, "utf-8"));
    delete file.background_image; // ~1 MB the editor does not need here
    const imported = await page.request.post("/api/maps/import/", {
      headers: await csrf(page),
      multipart: {
        map_name: `Versionsvergleich ${Date.now()}`,
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
  });

  test.afterEach(async ({ page }) => {
    if (mapId !== null) {
      await page.request.delete(`/api/maps/${mapId}/`, { headers: await csrf(page) });
      mapId = null;
    }
  });

  test("Ansehen draws what a version changes, and the other way round goes hollow", async ({
    page,
  }) => {
    await page.goto(`/app/maps/${mapId}/editor`);
    await page.getByRole("button", { name: "Versionen", exact: true }).click();
    await page.getByRole("button", { name: "Verwalten", exact: true }).click();

    const diff = page.locator('[data-layer="version-diff"]');

    // Base is on the canvas and is nothing's change: nothing drawn yet.
    await expect(page.getByText("Was „Berlin Mitte-West - Base“ ändert")).toBeVisible();
    await expect(diff).toHaveCount(0);

    await row(page, "Busspuren").getByRole("button", { name: "Ansehen" }).click();
    await expect(page.getByText("Was „Busspuren“ ändert")).toBeVisible();
    await expect(page.getByText("Bus & Bahn (15)")).toBeVisible();
    await expect(page.getByText("Hansaplatz – Großer Stern")).toBeVisible();
    await expect(diff.locator('[data-network="pt"]')).toHaveCount(30);
    await expect(diff.locator('[data-network="street"]')).toHaveCount(0);
    await expect(diff.locator("[data-hollow]")).toHaveCount(0);

    await row(page, "Buslinie").getByRole("button", { name: "Ansehen" }).click();
    await expect(page.getByText("Bus 147", { exact: true })).toBeVisible();
    await expect(page.getByText("Bus 147 reverse", { exact: true })).toBeVisible();

    // Base against Busspuren: the same thirty bus lanes, going.
    await row(page, "Berlin Mitte-West - Base")
      .getByRole("button", { name: "Ansehen" })
      .click();
    await page.getByLabel("Verglichen mit").selectOption({ label: "Busspuren" });
    await expect(diff.locator("[data-hollow]")).toHaveCount(30);
    await expect(page.getByText("die Busspur wird wieder Autospur").first()).toBeVisible();
  });
});
