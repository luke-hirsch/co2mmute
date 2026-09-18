/**
 * The SVG view box a map is drawn in — nodes, the map box and the background
 * image, in one rectangle.
 *
 * ### Why this is its own module
 *
 * Three renderers draw this graph: `GameMapViewer` (in the game),
 * `MapViewer` (the map detail page) and `EditorCanvas` (the editor). Each one
 * computed its own view box, and each got it wrong the same way — the box was
 * sized from the node extent and the map's nominal `x_dim`/`y_dim`, while the
 * background image is drawn at `image_offset_* × 100` and scaled by
 * `image_scale`. An image pushed right, or scaled past 1, therefore hangs
 * outside the box and is simply cut off. That is "Karte über Bildrand" on the
 * old README list, and K-02.
 *
 * It matters more than a display bug looks: the editor is where the image is
 * placed against the graph, and the game is where that placement is read. If
 * the two disagree about what is visible, a map is calibrated by eye against a
 * picture the players never see the same way.
 *
 * So the arithmetic lives here once, pure and tested, and all three renderers
 * take their box from it.
 *
 * ### Units
 *
 * Everything is **map units × 100**, which is what the renderers already use:
 * `x_position * 100` for nodes, `x_dim * 100` for the map box. The offsets are
 * in map units and the crops are percentages. Nothing here converts to pixels —
 * that is the SVG's job.
 */

/** Just enough of a node to be placed. */
export type PlacedNode = { x_position: number; y_position: number };

/** A rectangle in map units × 100. */
export type Rect = { x: number; y: number; width: number; height: number };

/** The background fields as the graph payload carries them, all optional. */
export type ImageFields = {
  background_image_url?: string | null;
  x_dim?: number | null;
  y_dim?: number | null;
  image_scale?: number | null;
  image_offset_x?: number | null;
  image_offset_y?: number | null;
};

export type ViewBoxInput = {
  nodes: readonly PlacedNode[];
  /** The map's nominal size, `x_dim × 100`. */
  mapWidth: number;
  mapHeight: number;
  /** Where the background is actually drawn, from `imageRect`. */
  image: Rect | null;
  padding: number;
};

export type ViewBox = {
  minX: number;
  minY: number;
  width: number;
  height: number;
};

/** The default map box for a map that has no dimensions yet, in map units. */
const FALLBACK_DIM = 10;

/**
 * Where the background image is actually drawn.
 *
 * Mirrors what the renderers pass to `<image>`: origin from the offsets, size
 * from the map's dimensions times the scale. The crops are deliberately **not**
 * applied — they clip what is *shown*, and a clipped image still occupies its
 * full rectangle in the coordinate space, so the box has to cover the whole of
 * it or the clip path itself would be cut.
 */
export function imageRect(fields: ImageFields): Rect | null {
  if (!fields.background_image_url) return null;

  const scale = fields.image_scale ?? 1;
  return {
    x: (fields.image_offset_x ?? 0) * 100,
    y: (fields.image_offset_y ?? 0) * 100,
    width: (fields.x_dim ?? FALLBACK_DIM) * 100 * scale,
    height: (fields.y_dim ?? FALLBACK_DIM) * 100 * scale,
  };
}

/**
 * The box that contains everything, plus padding on every side.
 *
 * Note what is *not* here: the old code floored the box at the origin
 * (`Math.min(0 - padding, …)`), which pinned it to the top-left corner of the
 * map. The editor lets you drag the image up and to the left, so anything
 * placed at a negative offset was clipped. The box now starts wherever the
 * leftmost, topmost thing actually is.
 */
export function viewBox({
  nodes,
  mapWidth,
  mapHeight,
  image,
  padding,
}: ViewBoxInput): ViewBox {
  // The map box is always in, so a map with no nodes and no image still has
  // something to draw the first node onto.
  const width = mapWidth > 0 ? mapWidth : FALLBACK_DIM * 100;
  const height = mapHeight > 0 ? mapHeight : FALLBACK_DIM * 100;

  const xs = [0, width];
  const ys = [0, height];

  for (const node of nodes) {
    xs.push(node.x_position * 100);
    ys.push(node.y_position * 100);
  }

  if (image) {
    xs.push(image.x, image.x + image.width);
    ys.push(image.y, image.y + image.height);
  }

  const minX = Math.min(...xs) - padding;
  const minY = Math.min(...ys) - padding;

  return {
    minX,
    minY,
    width: Math.max(...xs) + padding - minX,
    height: Math.max(...ys) + padding - minY,
  };
}
