import { describe, expect, it } from "vitest";

import { imageRect, viewBox, type ViewBoxInput } from "@/lib/map/view-box";

/**
 * The SVG view box every map is drawn in, and the one place K-02 is fixed.
 *
 * The bug it exists for: all three renderers sized their box from the node
 * extent and the map's nominal `x_dim`/`y_dim`, and then drew the background
 * image at `image_offset_* × 100` scaled by `image_scale`. An image pushed
 * right or scaled past 1 therefore hangs outside the box and is cut off —
 * "Karte über Bildrand" on the old README list. The box has to cover the
 * image's **drawn rectangle**, not the dimensions it nominally occupies.
 *
 * Kept pure and shared because the same arithmetic was written three times
 * (GameMapViewer, MapViewer, EditorCanvas) and each copy has to agree with the
 * others: the editor places the image, and the game draws it.
 *
 * Coordinates are map units × 100 throughout, which is what the renderers use.
 */

const PAD = 40;

function input(over: Partial<ViewBoxInput> = {}): ViewBoxInput {
  return {
    nodes: [{ x_position: 1, y_position: 1 }],
    mapWidth: 1000,
    mapHeight: 1000,
    image: null,
    padding: PAD,
    ...over,
  };
}

describe("imageRect", () => {
  it("is null when the map has no background", () => {
    expect(imageRect({ background_image_url: null, x_dim: 10, y_dim: 10 })).toBeNull();
  });

  it("places the image from the offsets and scales it from x_dim/y_dim", () => {
    expect(
      imageRect({
        background_image_url: "/media/berlin.png",
        x_dim: 10,
        y_dim: 8,
        image_scale: 1,
        image_offset_x: 0,
        image_offset_y: 0,
      }),
    ).toEqual({ x: 0, y: 0, width: 1000, height: 800 });
  });

  it("grows with the scale and moves with the offset", () => {
    // This is the case the old view box could not contain: scaled up and
    // pushed right, the image ends at 2·1500 + 1500 = 4500, well past the
    // 1000-unit map box the renderers were sizing to.
    expect(
      imageRect({
        background_image_url: "/media/berlin.png",
        x_dim: 10,
        y_dim: 10,
        image_scale: 1.5,
        image_offset_x: 2,
        image_offset_y: 1,
      }),
    ).toEqual({ x: 200, y: 100, width: 1500, height: 1500 });
  });

  it("defaults a missing scale and offset rather than producing NaN", () => {
    // `image_scale` and the offsets are all optional on the payload.
    expect(
      imageRect({ background_image_url: "/media/x.png", x_dim: 4, y_dim: 4 }),
    ).toEqual({ x: 0, y: 0, width: 400, height: 400 });
  });
});

describe("viewBox", () => {
  it("covers the map box with its padding when the nodes sit inside it", () => {
    expect(viewBox(input())).toEqual({
      minX: -PAD,
      minY: -PAD,
      width: 1000 + 2 * PAD,
      height: 1000 + 2 * PAD,
    });
  });

  it("stretches to a node outside the map box", () => {
    // A node dragged past the nominal map size still has to be visible, which
    // is the behaviour the old code already had and must not lose.
    const box = viewBox(input({ nodes: [{ x_position: 15, y_position: 1 }] }));

    expect(box.minX).toBe(-PAD);
    expect(box.minX + box.width).toBe(1500 + PAD);
  });

  it("stretches to an image that hangs outside the map box", () => {
    // K-02. Before the fix this box stopped at 1000 + padding and the image
    // was cut off at its right edge.
    const box = viewBox(
      input({ image: { x: 200, y: 100, width: 1500, height: 1500 } }),
    );

    expect(box.minX + box.width).toBe(1700 + PAD);
    expect(box.minY + box.height).toBe(1600 + PAD);
  });

  it("stretches to an image placed at a negative offset", () => {
    // The editor allows dragging the image up and left, so the box has to
    // grow in that direction too — the old `Math.min(0 - padding, …)` floor
    // pinned it at zero and clipped anything above or left of the origin.
    const box = viewBox(
      input({ image: { x: -300, y: -200, width: 400, height: 400 } }),
    );

    expect(box.minX).toBe(-300 - PAD);
    expect(box.minY).toBe(-200 - PAD);
  });

  it("covers nodes and image together when each overhangs a different side", () => {
    const box = viewBox(
      input({
        nodes: [{ x_position: -2, y_position: 14 }],
        image: { x: 1200, y: -400, width: 300, height: 300 },
      }),
    );

    expect(box.minX).toBe(-200 - PAD);
    expect(box.minY).toBe(-400 - PAD);
    expect(box.minX + box.width).toBe(1500 + PAD);
    expect(box.minY + box.height).toBe(1400 + PAD);
  });

  it("still produces a usable box for a map with no nodes at all", () => {
    // A freshly created map: the editor has to draw something to put the
    // first node on, so this must not collapse to zero or NaN.
    const box = viewBox(input({ nodes: [] }));

    expect(box.width).toBeGreaterThan(0);
    expect(box.height).toBeGreaterThan(0);
    expect(Number.isFinite(box.minX)).toBe(true);
    expect(Number.isFinite(box.minY)).toBe(true);
  });

  it("survives a map with no dimensions and no nodes", () => {
    const box = viewBox(input({ nodes: [], mapWidth: 0, mapHeight: 0 }));

    expect(box.width).toBeGreaterThan(0);
    expect(box.height).toBeGreaterThan(0);
  });
});
