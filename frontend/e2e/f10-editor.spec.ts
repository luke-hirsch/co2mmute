import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

import { loginAsHost } from "./host";

/**
 * F10: the editor's street buttons, end to end.
 *
 * "+ Straße anlegen" saved the street and showed nothing — the graph endpoint
 * kept serving its cached copy for an hour — and "+ Gegenrichtung anlegen"
 * answered in 20 ms and drew the new direction 1.8 s later, with the button
 * enabled again in between. Both reached the box's map as duplicates. Neither
 * showed up in a test, because both live between a write and the read after it.
 *
 * Runs on a map of its own, imported here and deleted afterwards: the game
 * specs play on the seeded map, and a street drawn into it would change their
 * routes.
 */

const SHIPPED_MAP = fileURLToPath(
  new URL("../../map_examples/Berlin_Mitte-West.json", import.meta.url),
);

type GraphNode = { id: number; name: string; x_position: number; y_position: number };
type GraphEdge = {
  id: number;
  start_node: number;
  end_node: number;
  street_edge: { speed_limit: number } | null;
  train_edge: unknown;
};
type Graph = { version_id: number; nodes: GraphNode[]; edges: GraphEdge[] };

async function csrf(page: Page) {
  const cookies = await page.context().cookies();
  return {
    "X-CSRFToken": cookies.find((c) => c.name === "csrftoken")?.value ?? "",
    Referer: page.url(),
  };
}

async function graphOf(page: Page, mapId: number, versionId?: number) {
  const path = versionId
    ? `/api/maps/${mapId}/graph/version/${versionId}/`
    : `/api/maps/${mapId}/graph/baseversion/`;
  return (await (await page.request.get(path)).json()) as Graph;
}

/**
 * Select an edge by clicking on it a quarter of the way from its start.
 *
 * Not the middle: the three homes' paths all run into Bellevue, so near that
 * end a click lands on whichever of them is drawn last. And the panel is asked
 * which edge it got, so a click that lands on a neighbour fails here rather
 * than as a puzzling assertion about the wrong street further down.
 */
async function select(page: Page, a: GraphNode, b: GraphNode) {
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
  const direction = page.getByText(/ → /).first();
  await expect(direction).toContainText(a.name);
  await expect(direction).toContainText(b.name);
}

test.describe("the map editor's street buttons", () => {
  let mapId: number | null = null;

  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1500, height: 1000 });
    await loginAsHost(page);
    const file = JSON.parse(await readFile(SHIPPED_MAP, "utf-8"));
    delete file.background_image; // ~1 MB the editor does not need here
    const response = await page.request.post("/api/maps/import/", {
      headers: await csrf(page),
      multipart: {
        map_name: `F10 Editor ${Date.now()}`,
        max_players: "6",
        json_file: {
          name: "map.json",
          mimeType: "application/json",
          buffer: Buffer.from(JSON.stringify(file)),
        },
      },
    });
    expect(response.status()).toBe(201);
    mapId = (await response.json()).id;
  });

  test.afterEach(async ({ page }) => {
    if (mapId === null) return;
    await page.request.delete(`/api/maps/${mapId}/`, { headers: await csrf(page) });
    mapId = null;
  });

  test("a street laid under a path shows at once, in every version", async ({
    page,
  }) => {
    const id = mapId as number;
    const graph = await graphOf(page, id);
    const node = new Map(graph.nodes.map((n) => [n.id, n]));
    // A path: a link with neither a street nor a railway under it.
    const path = graph.edges.find((e) => !e.street_edge && !e.train_edge);
    expect(path, "the shipped map has footpaths").toBeTruthy();
    const edge = path as GraphEdge;

    await page.goto(`/app/maps/${id}/editor`);
    await page.getByRole("button", { name: "Graph", exact: true }).click();
    await select(page, node.get(edge.start_node)!, node.get(edge.end_node)!);

    const addStreet = page.getByRole("button", { name: "+ Straße anlegen" });
    await addStreet.click();
    // Locked while the street is on its way, so a second click cannot write a
    // second street row under the same edge.
    await expect(addStreet).toBeDisabled();
    await expect(page.getByText(/^Straße \(50 km\/h, 1 Spur\)/)).toBeVisible();
    await expect(addStreet).toHaveCount(0);

    // Drawn in base, so in every version: here the one the class plays when
    // it votes in all three changes.
    const versions = (await (
      await page.request.get(`/api/maps/${id}/versions/`)
    ).json()) as { id: number; name: string }[];
    const all = versions.find((v) => v.name.split(" + ").length === 3);
    const there = await graphOf(page, id, all!.id);
    const both = there.edges.filter(
      (e) =>
        [e.start_node, e.end_node].sort().join() ===
        [edge.start_node, edge.end_node].sort().join(),
    );
    expect(both).toHaveLength(2);
    for (const direction of both) expect(direction.street_edge).not.toBeNull();
  });

  test("the other direction is drawn once, and the button waits for it", async ({
    page,
  }) => {
    const id = mapId as number;
    const graph = await graphOf(page, id);
    const node = new Map(graph.nodes.map((n) => [n.id, n]));
    // A two-way street: one direction is taken away, then drawn back. The
    // longest one, so a click a quarter of the way along is clear of its nodes.
    const length = (e: GraphEdge) => {
      const a = node.get(e.start_node)!;
      const b = node.get(e.end_node)!;
      return Math.hypot(a.x_position - b.x_position, a.y_position - b.y_position);
    };
    const street = graph.edges
      .filter(
        (e) =>
          e.street_edge &&
          !e.train_edge &&
          graph.edges.some(
            (r) => r.start_node === e.end_node && r.end_node === e.start_node,
          ),
      )
      .sort((x, y) => length(y) - length(x))[0];
    const between = async () =>
      (await graphOf(page, id)).edges.filter(
        (e) =>
          [e.start_node, e.end_node].sort().join() ===
          [street.start_node, street.end_node].sort().join(),
      );

    await page.goto(`/app/maps/${id}/editor`);
    await page.getByRole("button", { name: "Graph", exact: true }).click();
    await select(page, node.get(street.start_node)!, node.get(street.end_node)!);

    await page.getByRole("button", { name: "Zur Einbahn machen …" }).click();
    await page.getByRole("button", { name: / behalten$/ }).first().click();
    const back = page.getByRole("button", { name: "+ Gegenrichtung anlegen" });
    await expect(back).toBeEnabled();
    expect(await between()).toHaveLength(1);

    await back.click();
    await expect(back).toBeDisabled();
    // Every frame from here until the new direction is drawn: the button must
    // not come back. Before F10 it was disabled for the ~20 ms of the write
    // and enabled again for the ~1.8 s the graph took, over a panel still
    // saying "Einbahn" — which is how a second click wrote a second edge.
    const enabledAgain = await page.evaluate(
      () =>
        new Promise<boolean>((resolve) => {
          let enabled = false;
          const frame = () => {
            const buttons = [...document.querySelectorAll("button")];
            const back = buttons.find((b) =>
              b.textContent?.includes("Gegenrichtung anlegen"),
            );
            if (back && !back.disabled) enabled = true;
            if (buttons.some((b) => b.textContent?.includes("Zur Einbahn machen"))) {
              resolve(enabled);
            } else {
              requestAnimationFrame(frame);
            }
          };
          frame();
        }),
    );
    expect(enabledAgain, "the button came back before the new direction").toBe(false);
    await expect(back).toHaveCount(0);

    const after = await between();
    expect(after).toHaveLength(2);
    for (const direction of after) expect(direction.street_edge).not.toBeNull();
  });
});
