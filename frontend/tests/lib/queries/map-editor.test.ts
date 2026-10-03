import { MutationObserver, QueryClient, QueryObserver } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as editor from "@/lib/queries/map-editor";
import { mapKeys } from "@/lib/queries/map-graph";

/**
 * The editor's writes, pinned.
 *
 * This file exists for one reason: **these are the only calls in the app that
 * change a real map**, and F7 moved every one of them out of
 * `hooks/mapEditorHooks.ts`. Maps take real work to build, so the port was
 * allowed to move this code and not to change what it sends. A wrong path here
 * does not 404 into a test failure either — DRF answers a bad map id with a 404
 * and a bad *shape* with a 400 that a screen swallows, so the damage shows up
 * later as a map that quietly stopped saving.
 *
 * So each case names the URL, the method and the body the backend has been
 * getting all along. If one of these has to change, it changes here first and
 * on purpose.
 */

function stubFetch(status = 200, body: unknown = {}) {
  // 204 must not carry a body — `new Response(json, { status: 204 })` throws.
  // A delete really does answer 204, so the helper has to model that.
  const empty = status === 204 || status === 205 || status === 304;
  const spy = vi.fn<typeof fetch>(() =>
    Promise.resolve(
      new Response(empty ? null : JSON.stringify(body), {
        status,
        headers: empty ? undefined : { "Content-Type": "application/json" },
      }),
    ),
  );
  vi.stubGlobal("fetch", spy);
  return spy;
}

/** What actually went over the wire. */
function sent(spy: ReturnType<typeof stubFetch>) {
  const [url, init] = spy.mock.calls[0];
  return {
    url: String(url),
    method: (init?.method ?? "GET").toUpperCase(),
    body: init?.body ? JSON.parse(String(init.body)) : undefined,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("nodes", () => {
  it("sends only the position on a drag", async () => {
    // The drag is the hot path: EditorCanvas resolves it to x + dx/100 and
    // this saves it. It must not carry the rest of the node along, or a
    // rename made elsewhere is overwritten by whatever the canvas last saw.
    const spy = stubFetch();

    await editor.updateNodePosition(5, 127, 9.02, 4.17);

    expect(sent(spy)).toEqual({
      url: "/api/maps/5/nodes/127/",
      method: "PATCH",
      body: { x_position: 9.02, y_position: 4.17 },
    });
  });

  it("creates a node with the map id in the body", async () => {
    const spy = stubFetch(201);

    await editor.createNode(5, { name: "Schule", x_position: 1, y_position: 2 });

    expect(sent(spy)).toEqual({
      url: "/api/maps/5/nodes/",
      method: "POST",
      body: { game_map: 5, name: "Schule", x_position: 1, y_position: 2 },
    });
  });

  it("updates and deletes a node by id", async () => {
    const patch = stubFetch();
    await editor.updateNode(5, 127, { name: "Neu" });
    expect(sent(patch)).toEqual({
      url: "/api/maps/5/nodes/127/",
      method: "PATCH",
      body: { name: "Neu" },
    });
    vi.unstubAllGlobals();

    const del = stubFetch(204);
    await editor.deleteNode(5, 127);
    expect(sent(del).url).toBe("/api/maps/5/nodes/127/");
    expect(sent(del).method).toBe("DELETE");
  });
});

describe("edges", () => {
  it("creates an edge with the map id in the body", async () => {
    const spy = stubFetch(201);

    await editor.createEdge(5, { start_node: 1, end_node: 2, bidirectional: true });

    expect(sent(spy)).toEqual({
      url: "/api/maps/5/edges/",
      method: "POST",
      body: { game_map: 5, start_node: 1, end_node: 2, bidirectional: true },
    });
  });

  it("puts street and train edges on their own paths, without the map id", async () => {
    // These two hang off an edge and carry `edge` instead of `game_map` —
    // the asymmetry is the backend's and the port kept it.
    const street = stubFetch(201);
    await editor.createStreetEdge(5, { edge: 9, speed_limit: 30 });
    expect(sent(street)).toEqual({
      url: "/api/maps/5/street-edges/",
      method: "POST",
      body: { edge: 9, speed_limit: 30 },
    });
    vi.unstubAllGlobals();

    const train = stubFetch(201);
    await editor.createTrainEdge(5, { edge: 9 });
    expect(sent(train)).toEqual({
      url: "/api/maps/5/train-edges/",
      method: "POST",
      body: { edge: 9 },
    });
  });
});

describe("public transport lines", () => {
  it("replaces a line's edges with PUT, not PATCH", async () => {
    // The whole list is replaced. A PATCH here would read as "add these",
    // which is not what the panel does.
    const bus = stubFetch();
    await editor.updateBusLineEdges(5, 3, [1, 2, 3]);
    expect(sent(bus)).toEqual({
      url: "/api/maps/5/bus-lines/3/edges/",
      method: "PUT",
      body: { edges: [1, 2, 3] },
    });
    vi.unstubAllGlobals();

    const train = stubFetch();
    await editor.updateTrainLineEdges(5, 4, [7]);
    expect(sent(train)).toEqual({
      url: "/api/maps/5/train-lines/4/edges/",
      method: "PUT",
      body: { edges: [7] },
    });
  });

  it("routes a delete to the segment its line type lives under", async () => {
    const bus = stubFetch(204);
    await editor.deletePTLine(5, 3, "bus");
    expect(sent(bus).url).toBe("/api/maps/5/bus-lines/3/");
    vi.unstubAllGlobals();

    const train = stubFetch(204);
    await editor.deletePTLine(5, 3, "train");
    expect(sent(train).url).toBe("/api/maps/5/train-lines/3/");
  });
});

describe("the map row and its image", () => {
  it("writes the image placement onto the map itself", async () => {
    // Offsets, scale and crops are columns on GameMap, not on an image
    // resource — which is why this is a PATCH of the map row.
    const spy = stubFetch();

    await editor.updateImageTransform(5, {
      image_offset_x: 2,
      image_offset_y: 1,
      image_scale: 1.5,
    } as never);

    expect(sent(spy)).toEqual({
      url: "/api/maps/5/",
      method: "PATCH",
      body: { image_offset_x: 2, image_offset_y: 1, image_scale: 1.5 },
    });
  });

  it("deletes the background image on its own path", async () => {
    const spy = stubFetch(204);
    await editor.deleteBackgroundImage(5);
    expect(sent(spy).url).toBe("/api/maps/5/background-image/");
    expect(sent(spy).method).toBe("DELETE");
  });

  it("uploads the image as multipart, not as JSON", async () => {
    // It cannot go through apiFetch: that sets a JSON content type, which
    // would strip the multipart boundary and the upload would fail.
    const spy = stubFetch(201);

    await editor.uploadBackgroundImage(5, new File(["x"], "berlin.png"));

    const [url, init] = spy.mock.calls[0];
    expect(String(url)).toBe("/api/maps/5/background-image/");
    expect(init?.method).toBe("POST");
    expect(init?.body).toBeInstanceOf(FormData);
    expect((init?.body as FormData).get("image")).toBeInstanceOf(File);
  });
});

describe("versions", () => {
  it("creates a version from a diff", async () => {
    const spy = stubFetch(201);

    await editor.createVersionFromDiff(5, { name: "Tempo 30" } as never);

    expect(sent(spy)).toEqual({
      url: "/api/maps/5/versions/create-from-diff/",
      method: "POST",
      body: { name: "Tempo 30" },
    });
  });

  it("deletes a version under its own map", async () => {
    // F14. The server scopes the version to the map in the URL since then, so
    // a version id under the wrong map is a 404, not a delete.
    const spy = stubFetch(204);

    await editor.deleteVersion(5, 31);

    expect(sent(spy)).toEqual({
      url: "/api/maps/5/versions/31/",
      method: "DELETE",
      body: undefined,
    });
  });

  it("carries the server's refusal as the message", async () => {
    stubFetch(409, { detail: "Die Grundversion lässt sich nicht löschen.", reason: "base" });

    await expect(editor.deleteVersion(5, 1)).rejects.toMatchObject({
      status: 409,
      reason: "base",
      message: "Die Grundversion lässt sich nicht löschen.",
    });
  });
});

describe("the failure path", () => {
  it("throws an ApiError carrying the status", async () => {
    // The old hooks threw `new Error("Failed to upload image")`, which told a
    // screen nothing. A 403 here means the staff session expired and is a
    // different screen from a 400.
    stubFetch(403, { detail: "nope" });

    await expect(editor.deleteNode(5, 1)).rejects.toMatchObject({ status: 403 });
  });
});

describe("a write and the graph that shows it", () => {
  /**
   * F10. "+ Gegenrichtung anlegen" answered in 20 ms and the graph that drew
   * the new direction took 1.8 s to build. The button was enabled again for
   * all of that time with "Einbahn" still on the panel, and a second click
   * wrote a second edge — Bellevue – Großer Stern sits twice in the box's base
   * version. A write stays pending until the refetch it caused has landed.
   */
  it("stays pending until the refetched graph has arrived", async () => {
    const qc = new QueryClient();
    let deliverGraph: (graph: unknown) => void = () => {};
    const graphQuery = new QueryObserver(qc, {
      queryKey: mapKeys.graph("5", null),
      queryFn: () => new Promise((resolve) => (deliverGraph = resolve)),
    });
    const unsubscribe = graphQuery.subscribe(() => {});
    deliverGraph({ edges: [] });
    await vi.waitFor(() => expect(graphQuery.getCurrentResult().isSuccess).toBe(true));

    const write = new MutationObserver(
      qc,
      editor.mapMutationOptions(qc, "5", () => Promise.resolve({ id: 1 }), (id) => [
        editor.mapEditorKeys.graph(id),
      ]),
    );
    const done = write.mutate(undefined);
    await vi.waitFor(() => expect(graphQuery.getCurrentResult().isFetching).toBe(true));

    expect(write.getCurrentResult().isPending).toBe(true);

    deliverGraph({ edges: [{ id: 1 }] });
    await done;
    expect(write.getCurrentResult().isPending).toBe(false);
    expect(graphQuery.getCurrentResult().data).toEqual({ edges: [{ id: 1 }] });
    unsubscribe();
  });
});
