import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

import { loginAsHost } from "./host";

/**
 * The editor's street buttons, end to end.
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
  name: string | null;
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

/** Click the canvas at a point in map coordinates. */
async function clickAt(page: Page, x: number, y: number) {
  const point = await page.evaluate(
    ([px, py]) => {
      const svg = document.querySelector("svg") as SVGSVGElement;
      const p = svg.createSVGPoint();
      p.x = px * 100;
      p.y = py * 100;
      const s = p.matrixTransform(svg.getScreenCTM() as DOMMatrix);
      return { x: s.x, y: s.y };
    },
    [x, y],
  );
  await page.mouse.click(point.x, point.y);
}

/** The point on the map farthest from every node and edge, and how far that is. */
function emptySpot(graph: Graph) {
  const node = new Map(graph.nodes.map((n) => [n.id, n]));
  const xs = graph.nodes.map((n) => n.x_position);
  const ys = graph.nodes.map((n) => n.y_position);
  const toEdge = (px: number, py: number, e: GraphEdge) => {
    const a = node.get(e.start_node)!;
    const b = node.get(e.end_node)!;
    const dx = b.x_position - a.x_position;
    const dy = b.y_position - a.y_position;
    const t = Math.max(
      0,
      Math.min(1, ((px - a.x_position) * dx + (py - a.y_position) * dy) / (dx * dx + dy * dy || 1)),
    );
    return Math.hypot(px - a.x_position - t * dx, py - a.y_position - t * dy);
  };
  let best = { x: 0, y: 0, clear: -1 };
  for (let x = Math.min(...xs); x <= Math.max(...xs); x += 0.1) {
    for (let y = Math.min(...ys); y <= Math.max(...ys); y += 0.1) {
      const clear = Math.min(
        ...graph.nodes.map((n) => Math.hypot(x - n.x_position, y - n.y_position)),
        ...graph.edges.map((e) => toEdge(x, y, e)),
      );
      if (clear > best.clear) best = { x, y, clear };
    }
  }
  return best;
}

/** The sidebar panel under this heading. */
function panel(page: Page, heading: string) {
  return page.locator("section", {
    has: page.getByRole("heading", { name: heading, exact: true }),
  });
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
    mapId = (await importShippedMap(page)).id;
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
    // not come back. It used to be disabled for the ~20 ms of the write
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

/**
 * What the editor calls what it draws. A node drawn by hand was "Knoten 4587",
 * its id, so a new map started in the thousands: now a click names it after
 * the map, counted from 1, and the panels won't save that or an empty name.
 */
const ADD_NODE_HINT = "Klick auf die Fläche, um einen Knoten zu setzen.";
const ADD_EDGE_HINT = "Klick zwei Knoten an, um sie zu verbinden.";

test.describe("the map editor's names", () => {
  let shipped: { id: number; name: string } | null = null;

  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1500, height: 1000 });
    await loginAsHost(page);
    shipped = await importShippedMap(page);
  });

  test.afterEach(async ({ page }) => {
    if (shipped === null) return;
    await page.request.delete(`/api/maps/${shipped.id}/`, { headers: await csrf(page) });
    shipped = null;
  });

  test("a drawn node and edge are named after the map, from 1", async ({ page }) => {
    const { id, name: map } = shipped!;
    const graph = await graphOf(page, id);
    const spot = emptySpot(graph);
    const drawn = async () => {
      const now = await graphOf(page, id);
      return {
        nodes: now.nodes.filter((n) => !graph.nodes.some((old) => old.id === n.id)),
        edges: now.edges.filter((e) => !graph.edges.some((old) => old.id === e.id)),
      };
    };

    await page.goto(`/app/maps/${id}/editor`);
    await page.getByRole("button", { name: "Graph", exact: true }).click();
    await page.getByRole("button", { name: "+ Knoten" }).click();
    await clickAt(page, spot.x, spot.y);
    await expect.poll(async () => (await drawn()).nodes.map((n) => n.name)).toEqual([
      `${map} Knoten 1`,
    ]);
    // The canvas takes the next click once the editor has the new graph,
    // which is after the server has the node.
    await expect(page.getByText(ADD_NODE_HINT)).toBeVisible();
    await clickAt(page, spot.x + spot.clear / 2, spot.y);
    await expect.poll(async () => (await drawn()).nodes.map((n) => n.name)).toEqual([
      `${map} Knoten 1`,
      `${map} Knoten 2`,
    ]);

    await expect(page.getByText(ADD_NODE_HINT)).toBeVisible();
    const [first, second] = (await drawn()).nodes;
    await page.getByRole("button", { name: "+ Kante" }).click();
    await clickAt(page, first.x_position, first.y_position);
    await clickAt(page, second.x_position, second.y_position);
    // Both directions, the way a new edge is drawn unless told one way.
    await expect.poll(async () => (await drawn()).edges.map((e) => e.name)).toEqual([
      `${map} Kante 1`,
      `${map} Kante 1`,
    ]);
    await expect(page.getByText(ADD_EDGE_HINT)).toBeVisible();

    // Its panel asks for a better one before it saves.
    await page.getByRole("button", { name: "Auswählen" }).click();
    await clickAt(page, first.x_position, first.y_position);
    const name = panel(page, "Knoten").getByRole("textbox");
    await expect(name).toHaveValue(`${map} Knoten 1`);
    const save = page.getByRole("button", { name: "Speichern" });
    await expect(page.getByText("Gib einen besseren Namen.")).toBeVisible();
    await expect(save).toBeDisabled();
    await name.fill("Am Neubaugebiet");
    await expect(page.getByText("Gib einen besseren Namen.")).toHaveCount(0);
    await save.click();
    await expect
      .poll(async () => (await drawn()).nodes.map((n) => n.name))
      .toEqual(["Am Neubaugebiet", `${map} Knoten 2`]);
  });

  test("an edge without a name is not saved until it has one", async ({ page }) => {
    const { id } = shipped!;
    const graph = await graphOf(page, id);
    const node = new Map(graph.nodes.map((n) => [n.id, n]));
    const path = graph.edges.find((e) => !e.name && !e.street_edge && !e.train_edge);
    expect(path, "the shipped map has footpaths without a name").toBeTruthy();
    const edge = path as GraphEdge;

    await page.goto(`/app/maps/${id}/editor`);
    await page.getByRole("button", { name: "Graph", exact: true }).click();
    await select(page, node.get(edge.start_node)!, node.get(edge.end_node)!);

    const name = panel(page, "Kante").getByRole("textbox");
    const save = page.getByRole("button", { name: "Speichern" });
    await expect(name).toHaveValue("");
    await expect(save).toBeDisabled();
    await expect(page.getByText("Gib einen besseren Namen.")).toBeVisible();
    await name.fill("Kante 7");
    await expect(save).toBeDisabled();

    await name.fill("Uferweg");
    await expect(save).toBeEnabled();
    await save.click();
    // The click may land on either direction; a save names both.
    await expect
      .poll(async () =>
        (await graphOf(page, id)).edges
          .filter(
            (e) =>
              [e.start_node, e.end_node].sort().join() ===
              [edge.start_node, edge.end_node].sort().join(),
          )
          .map((e) => e.name),
      )
      .toContain("Uferweg");
  });
});
