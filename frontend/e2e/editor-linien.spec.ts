import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

import { loginAsHost } from "./host";

/**
 * A bus line drawn in base, or its route cut short there, reaches the version
 * built on it ("Busspuren"), over that version's own clones of the streets.
 *
 * Runs on a map of its own, imported here and deleted afterwards.
 */

const SHIPPED_MAP = fileURLToPath(
  new URL("../../map_examples/Berlin_Mitte-West.json", import.meta.url),
);

type GraphNode = { id: number; name: string; x_position: number; y_position: number };
type GraphEdge = {
  id: number;
  name: string | null;
  start_node: number;
  end_node: number;
  street_edge: { speed_limit: number } | null;
  train_edge: unknown;
};
type BusLine = { id: number; name: string; edges: number[] };
type Graph = {
  version_id: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
  bus_lines: BusLine[];
};

async function csrf(page: Page) {
  const cookies = await page.context().cookies();
  return {
    "X-CSRFToken": cookies.find((c) => c.name === "csrftoken")?.value ?? "",
    Referer: page.url(),
  };
}

/** The shipped map under a name of its own, for a spec to draw on and delete. */
async function importShippedMap(page: Page) {
  const file = JSON.parse(await readFile(SHIPPED_MAP, "utf-8"));
  delete file.background_image; // ~1 MB the editor does not need here
  const name = `Editor ${Date.now()}`;
  const response = await page.request.post("/api/maps/import/", {
    headers: await csrf(page),
    multipart: {
      map_name: name,
      max_players: "6",
      json_file: {
        name: "map.json",
        mimeType: "application/json",
        buffer: Buffer.from(JSON.stringify(file)),
      },
    },
  });
  expect(response.status()).toBe(201);
  return { id: (await response.json()).id as number, name };
}

async function graphOf(page: Page, mapId: number, versionId?: number) {
  const path = versionId
    ? `/api/maps/${mapId}/graph/version/${versionId}/`
    : `/api/maps/${mapId}/graph/baseversion/`;
  return (await (await page.request.get(path)).json()) as Graph;
}

/** Click an edge a quarter of the way from its start. */
async function clickEdge(page: Page, a: GraphNode, b: GraphNode) {
  const point = await page.evaluate(
    ([from, to]) => {
      const svg = document.querySelector("svg") as SVGSVGElement;
      const p = svg.createSVGPoint();
      p.x = (from.x_position * 0.75 + to.x_position * 0.25) * 100;
      p.y = (from.y_position * 0.75 + to.y_position * 0.25) * 100;
      const s = p.matrixTransform(svg.getScreenCTM() as DOMMatrix);
      return { x: s.x, y: s.y };
    },
    [a, b],
  );
  await page.mouse.click(point.x, point.y);
}

const SHOTS = process.env.E2E_SHOTS;

test.describe("a line in base reaches the version built on it", () => {
  let mapId: number | null = null;

  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1500, height: 1000 });
    await loginAsHost(page);
    mapId = (await importShippedMap(page)).id;
  });

  test.afterEach(async ({ page }) => {
    if (mapId === null) return;
    await page.request.delete(`/api/maps/${mapId}/`, { headers: await csrf(page) });
    mapId = null;
  });

  async function busspuren(page: Page, id: number) {
    const versions = (await (
      await page.request.get(`/api/maps/${id}/versions/`)
    ).json()) as { id: number; name: string }[];
    return versions.find((v) => v.name === "Busspuren")!.id;
  }

  test("a bus line drawn in base is in Busspuren", async ({ page }) => {
    const id = mapId as number;
    const graph = await graphOf(page, id);
    const node = new Map(graph.nodes.map((n) => [n.id, n]));
    const edge = new Map(graph.edges.map((e) => [e.id, e]));
    const bus100 = graph.bus_lines.find((l) => l.name === "100")!;
    const route = bus100.edges.slice(0, 3);

    await page.goto(`/app/maps/${id}/editor`);
    await page.getByRole("button", { name: "Linien", exact: true }).click();
    await page.getByRole("button", { name: "+ Buslinie" }).click();
    for (const edgeId of route) {
      const e = edge.get(edgeId)!;
      await clickEdge(page, node.get(e.start_node)!, node.get(e.end_node)!);
    }
    await expect(page.getByText("Route (3 Kanten ausgewählt)")).toBeVisible();
    await page.getByRole("button", { name: "Linie speichern" }).click();
    await expect(page.getByRole("heading", { name: "Neue Buslinie" })).toHaveCount(0);
    if (SHOTS) await page.screenshot({ path: `${SHOTS}/base-linie-gezeichnet.png` });

    const there = await graphOf(page, id, await busspuren(page, id));
    const drawn = there.bus_lines.find((l) => l.name === "Neue Buslinie");
    expect(drawn, "the line is in Busspuren").toBeTruthy();
    expect(drawn!.edges).toHaveLength(3);
  });

  test("cutting a line's route short in base cuts it in Busspuren", async ({ page }) => {
    const id = mapId as number;
    const before = await graphOf(page, id);
    const was = before.bus_lines.find((l) => l.name === "100")!.edges.length;
    const versionId = await busspuren(page, id);
    const inBusspuren = (await graphOf(page, id, versionId)).bus_lines.find(
      (l) => l.name === "100",
    )!;
    expect(inBusspuren.edges).toHaveLength(was);

    await page.goto(`/app/maps/${id}/editor`);
    await page.getByRole("button", { name: "Linien", exact: true }).click();
    const row = page.locator("li", { hasText: /^\s*Bus\s*100/ }).first();
    await row.getByRole("button", { name: "Bearbeiten" }).click();
    await page.getByTitle("Anklicken, um sie aus der Route zu nehmen").last().click();
    await page.getByRole("button", { name: "Änderungen speichern" }).click();
    await expect(page.getByRole("heading", { name: "Buslinie bearbeiten" })).toHaveCount(0);
    if (SHOTS) await page.screenshot({ path: `${SHOTS}/base-route-gekuerzt.png` });

    const base = (await graphOf(page, id)).bus_lines.find((l) => l.name === "100")!;
    const there = (await graphOf(page, id, versionId)).bus_lines.find(
      (l) => l.name === "100",
    )!;
    expect(base.edges).toHaveLength(was - 1);
    expect(there.edges).toHaveLength(was - 1);
  });
});
