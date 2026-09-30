import { describe, expect, it } from "vitest";

import {
  bundleKey,
  bundleLines,
  edgeLayers,
  editorPaint,
  nodeMark,
  offsetLine,
  PT_LINE_PAINT,
} from "@/lib/map/palette";

/**
 * The map's palette, which before S18 was two palettes and a legend that
 * restated a third.
 *
 * `MapViewer` and `EditorCanvas` each held a `getEdgeColorAndStyle` and a
 * `getNodeColor`, eleven hexes apiece, and the legend arrays sat beside them
 * under a comment claiming they could not drift. They had: the detail page drew
 * a street `#6b7280` and the editor `#475569`; its legend named the walk path
 * `#22c55e` against a drawn `#10b981` and the bike-and-walk path `#a855f7`
 * against `#8b5cf6`. Four of eleven entries were wrong, live, on a staff screen.
 *
 * So the tests below are about the two properties that made that possible:
 * **one answer per question**, and **no value that cannot follow the theme**.
 */
describe("the map palette", () => {
  /**
   * The rule that matters most, and the one no type can enforce: a hex paints
   * the same pixel in dark mode, where ink is near-white and the page is
   * `#0b1120`. Every colour here has to be a `var()` into a token.
   */
  it("never hands a renderer a literal colour", () => {
    const paints = [
      ...edgeLayers({ street_edge: {} }).map((l) => l.color),
      ...edgeLayers({ train_edge: {} }).map((l) => l.color),
      ...edgeLayers({ biking: true, walking: true }).map((l) => l.color),
      nodeMark([{ name: "home" }]).color,
      nodeMark([{ name: "station" }]).color,
      nodeMark([]).color,
      ...Object.values(editorPaint),
      PT_LINE_PAINT,
    ];

    for (const paint of paints) {
      expect(paint, paint).toMatch(/^var\(--[a-z0-9-]+\)$/);
    }
  });

  describe("an edge is the layers it carries", () => {
    it("draws a street as one solid stroke", () => {
      const layers = edgeLayers({ street_edge: {} });
      expect(layers.map((l) => l.kind)).toEqual(["street"]);
      expect(layers[0].dash).toBeUndefined();
    });

    it("draws a railway dashed, so it is not a second solid line", () => {
      const [rail] = edgeLayers({ train_edge: {} });
      expect(rail.kind).toBe("rail");
      expect(rail.dash).toBeTruthy();
    });

    /**
     * The shape that replaced the invented third colour. A corridor carrying a
     * street *and* a railway is not a third kind of link, so it gets both
     * strokes rather than an orange one that meant "both".
     */
    it("draws a street with a railway over it as both, in order", () => {
      expect(edgeLayers({ street_edge: {}, train_edge: {} }).map((l) => l.kind)).toEqual(
        ["street", "rail"],
      );
    });

    /**
     * A street is open to bikes and pedestrians too, so reading the access flags
     * on every edge would put three strokes on every street. The path layers are
     * for a link with neither a street nor a railway under it — `"type": "path"`,
     * the four on the shipped map.
     */
    it("ignores the access flags when there is a street underneath", () => {
      expect(
        edgeLayers({ street_edge: {}, biking: true, walking: true }).map(
          (l) => l.kind,
        ),
      ).toEqual(["street"]);
    });

    it("ignores them under a railway too — a way alongside is still the railway", () => {
      expect(
        edgeLayers({ train_edge: {}, biking: true }).map((l) => l.kind),
      ).toEqual(["rail"]);
    });

    it("draws a cycle track and a footpath in their own lines", () => {
      expect(edgeLayers({ biking: true }).map((l) => l.kind)).toEqual(["bikeway"]);
      expect(edgeLayers({ walking: true }).map((l) => l.kind)).toEqual(["footway"]);
      expect(edgeLayers({ biking: true, walking: true }).map((l) => l.kind)).toEqual(
        ["bikeway", "footway"],
      );
    });

    /** Pattern is what separates them, so the four cannot share one dash. */
    it("gives the four layers four different strokes", () => {
      const dashes = [
        edgeLayers({ street_edge: {} })[0].dash,
        edgeLayers({ train_edge: {} })[0].dash,
        edgeLayers({ biking: true })[0].dash,
        edgeLayers({ walking: true })[0].dash,
      ];
      expect(new Set(dashes).size).toBe(4);
    });

    /**
     * An invisible edge in a map editor is worse than a wrong one: you cannot
     * click what is not drawn, and a link with no street, no railway and neither
     * flag set is a link somebody has to be able to select and fix.
     */
    it("still draws a link that states nothing about itself", () => {
      expect(edgeLayers({}).length).toBeGreaterThan(0);
      expect(edgeLayers({ biking: false, walking: false }).length).toBeGreaterThan(0);
    });
  });

  describe("a node mark is a colour and a fill", () => {
    /**
     * Two colours for five types: primary is where people are, accent is where
     * transit is. That is what replaced green-home against red-bus-stop, which
     * a colour-blind reader could not separate at all.
     */
    it("puts home and workplace on one colour, station and stop on the other", () => {
      expect(nodeMark([{ name: "home" }]).color).toBe(
        nodeMark([{ name: "workplace" }]).color,
      );
      expect(nodeMark([{ name: "station" }]).color).toBe(
        nodeMark([{ name: "bus_stop" }]).color,
      );
      expect(nodeMark([{ name: "home" }]).color).not.toBe(
        nodeMark([{ name: "station" }]).color,
      );
    });

    it("separates the pair inside each colour by fill", () => {
      expect(nodeMark([{ name: "home" }]).filled).toBe(true);
      expect(nodeMark([{ name: "workplace" }]).filled).toBe(false);
      expect(nodeMark([{ name: "station" }]).filled).toBe(true);
      expect(nodeMark([{ name: "bus_stop" }]).filled).toBe(false);
    });

    it("draws an unremarkable node smaller, and in neither colour", () => {
      const plain = nodeMark([]);
      expect(plain.scale).toBeLessThan(1);
      expect(plain.color).not.toBe(nodeMark([{ name: "home" }]).color);
      expect(plain.color).not.toBe(nodeMark([{ name: "station" }]).color);
    });

    /** A node can carry several types; the order is the one the map has used. */
    it("reads home before workplace before station before stop", () => {
      expect(
        nodeMark([{ name: "station" }, { name: "home" }]),
      ).toEqual(nodeMark([{ name: "home" }]));
      expect(
        nodeMark([{ name: "bus_stop" }, { name: "workplace" }]),
      ).toEqual(nodeMark([{ name: "workplace" }]));
    });

    it("falls back to the plain mark for a type it does not know", () => {
      expect(nodeMark([{ name: "airport" }])).toEqual(nodeMark([]));
    });
  });

  /**
   * The eight-colour PT palette is gone, and what replaced it also fixed a bug:
   * two lines sharing a street were drawn on the same coordinates, so whichever
   * came last was the only one visible. On the shipped map, where twelve lines
   * run over 116 street edges, that is most corridors.
   */
  describe("lines are bundled, not coloured", () => {
    it("centres a single line on the link", () => {
      const at = offsetLine({ x: 0, y: 0 }, { x: 100, y: 0 }, 0, 1);
      expect(at).toEqual({ x1: 0, y1: 0, x2: 100, y2: 0 });
    });

    it("puts two lines either side of it, perpendicular to the link", () => {
      const first = offsetLine({ x: 0, y: 0 }, { x: 100, y: 0 }, 0, 2, 10);
      const second = offsetLine({ x: 0, y: 0 }, { x: 100, y: 0 }, 1, 2, 10);
      // A horizontal link shifts in y, and the two shift opposite ways.
      expect(first.y1).toBe(-5);
      expect(second.y1).toBe(5);
      expect(first.x1).toBe(0);
      expect(second.x2).toBe(100);
    });

    it("keeps the bundle centred however many lines are in it", () => {
      const spread = [0, 1, 2, 3, 4].map(
        (i) => offsetLine({ x: 0, y: 0 }, { x: 100, y: 0 }, i, 5, 10).y1,
      );
      expect(spread).toEqual([-20, -10, 0, 10, 20]);
    });

    /** A zero-length link has no perpendicular; it must not divide by it. */
    it("survives a link whose ends are the same point", () => {
      const at = offsetLine({ x: 5, y: 5 }, { x: 5, y: 5 }, 1, 3);
      expect(Number.isFinite(at.x1)).toBe(true);
      expect(Number.isFinite(at.y2)).toBe(true);
    });

    it("gives each line its place among the lines on a link", () => {
      const lines = [
        { id: 1, type: "bus", edges: [10, 11] },
        { id: 2, type: "bus", edges: [11, 12] },
        { id: 1, type: "train", edges: [11] },
      ];
      const bundles = bundleLines(lines);

      // Edge 11 carries all three; edge 10 and 12 carry one each.
      expect(bundles.get(bundleKey(lines[0], 11))).toEqual({ index: 0, count: 3 });
      expect(bundles.get(bundleKey(lines[1], 11))).toEqual({ index: 1, count: 3 });
      expect(bundles.get(bundleKey(lines[2], 11))).toEqual({ index: 2, count: 3 });
      expect(bundles.get(bundleKey(lines[0], 10))).toEqual({ index: 0, count: 1 });
    });

    /**
     * A bus line and a train line can share an id — they are separate tables —
     * so the key has to carry the type or one would hide the other.
     */
    it("does not confuse a bus line with a train line of the same id", () => {
      const bus = { id: 7, type: "bus", edges: [1] };
      const train = { id: 7, type: "train", edges: [1] };
      const bundles = bundleLines([bus, train]);
      expect(bundles.get(bundleKey(bus, 1))).toEqual({ index: 0, count: 2 });
      expect(bundles.get(bundleKey(train, 1))).toEqual({ index: 1, count: 2 });
    });
  });

  /**
   * The editor's own state, as opposed to the map's. Primary is what this
   * version adds, the accent is what it removes — and the two must not collapse
   * into one, because the whole point is that a reader can tell a proposed node
   * from a deleted one at a glance.
   */
  it("keeps 'adding' and 'removing' apart", () => {
    expect(editorPaint.proposed).not.toBe(editorPaint.removed);
    expect(editorPaint.changed).toBe(editorPaint.proposed);
  });
});
