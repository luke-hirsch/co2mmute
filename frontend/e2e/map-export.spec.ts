import { expect, test } from "@playwright/test";

import { loginAsHost } from "./host";

/**
 * The backup button on the map detail page.
 *
 * A map only ever moves between boxes as this file, and until S14 it carried
 * one version flattened — so the other versions, `compatible_versions` (which
 * *is* the vote) and both poll texts were lost on every move. The button now
 * writes the whole map, and this is the only place that proves the browser
 * actually receives that: the export is built in Django, handed to the SPA over
 * `apiFetch`, turned into a Blob and downloaded, and any of those three could
 * drop it.
 *
 * Needs the seeded map with its versions:
 *
 *     npm run e2e:seed && node e2e/seed-versions.mjs
 */

test("the map detail page downloads the whole map, versions and all", async ({
  page,
}) => {
  await loginAsHost(page);

  const maps = await (await page.request.get("/api/maps/")).json();
  const seeded = maps.find(
    (candidate: { name: string }) => candidate.name === "E2E Berlin",
  );
  expect(seeded, "seed the map first: npm run e2e:seed").toBeTruthy();

  await page.goto(`/app/maps/${seeded.id}/`);
  const button = page.getByRole("button", { name: "Karte sichern (JSON)" });
  await expect(button).toBeVisible();

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    button.click(),
  ]);
  const path = await download.path();
  expect(path).toBeTruthy();

  const file = JSON.parse(
    await (await import("node:fs/promises")).readFile(path as string, "utf-8"),
  );

  // More than one version, exactly one of them the base one.
  expect(file.versions.length).toBeGreaterThan(1);
  expect(
    file.versions.filter((v: { base_version: boolean }) => v.base_version),
  ).toHaveLength(1);

  // The ballot: the base version has to reach the versions a class votes on.
  const base = file.versions.findIndex(
    (v: { base_version: boolean }) => v.base_version,
  );
  expect(file.versions[base].compatible_versions.length).toBeGreaterThan(0);
  for (const index of file.versions[base].compatible_versions) {
    expect(file.versions[index].poll_text).toBeTruthy();
  }

  // And every element says where it belongs, lines included.
  expect(file.nodes.every((n: { versions: number[] }) => n.versions.length)).toBe(
    true,
  );
  expect(file.bus_lines.length).toBeGreaterThan(0);
  for (const line of file.bus_lines) {
    expect(line.chains.length).toBeGreaterThan(0);
  }
});
