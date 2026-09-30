/**
 * How the map graph itself is drawn — one place, for all three renderers.
 *
 * ### Why this file exists
 *
 * `MapViewer` and `EditorCanvas` each carried a `getEdgeColorAndStyle` and a
 * `getNodeColor` of their own, eleven hardcoded hexes apiece, and then wrote
 * the legend out a third time beside them. The two had already drifted: the
 * detail page drew a street `#6b7280` and the editor `#475569`, and its legend
 * called the walk path `#22c55e` while the renderer drew `#10b981`. A comment
 * in `MapViewer` claimed both "come off `getEdgeColorAndStyle`". They did not.
 *
 * So the graph's palette came from nowhere central — F7's open item, and the
 * reason S10 counted 118 off-palette hits in `map/` and 102 in `map/editor/`
 * against **zero** everywhere else in the SPA.
 *
 * ### What the colours are now
 *
 * The rulebook's palette is two colours and ink: primary blue, accent amber,
 * no green and no red. Nothing here is a hue that is not already in the design
 * system, and nothing is a literal — every value is a `var()` into a token that
 * resolves per theme, the way `GameMapViewer` already did it. A hex would paint
 * the same pixel in dark mode, where ink is near-white.
 *
 * ### An edge is its layers, not a colour
 *
 * The old function answered "street, rail, or both?" with three colours, the
 * third of which (`#f97316`, orange) existed only to name the combination. That
 * is the wrong shape: an edge that carries a street *and* a railway is not a
 * third kind of link, it is two pieces of infrastructure in the same corridor.
 * So an edge draws **one stroke per layer it carries**, and the combination
 * needs no colour of its own — you see both lines, which is also what a transit
 * diagram does with a road under a viaduct.
 *
 * The same mechanism covers the path cases, so `bikeAndWalk` stops being a
 * fourth invented hue (`#8b5cf6`, violet) too.
 *
 * Pattern separates them where colour cannot, exactly as `metro/mode.ts` does
 * for the four lines: street solid, rail long-dashed, bike short-dashed, foot
 * dotted.
 *
 * ### The path layers only apply to a path
 *
 * A street is open to bikes and pedestrians too, so reading `biking`/`walking`
 * on every edge would draw three strokes on every street. The path layers are
 * for a link with neither a street nor a railway under it — `"type": "path"` in
 * the map file, the four on the shipped map. Rail wins over them for the same
 * reason: a rail alignment with a way alongside is drawn as the railway it is.
 */

/** A colour that resolves per theme. Never a literal. */
type Paint = string;

/** One stroke of an edge. Several make a corridor that carries several things. */
export type EdgeLayer = {
  /** Which piece of infrastructure this stroke is. */
  kind: "street" | "rail" | "bikeway" | "footway";
  color: Paint;
  /** SVG `stroke-dasharray`, absent for a solid line. */
  dash?: string;
};

/**
 * The four layers.
 *
 * Ink for the street because the road network is the ground everything else is
 * drawn on — the same call `GameMapViewer` makes, where the network is neutral
 * and colour is spent only on the route. The railway is the accent because
 * public transport *is* the accent line. Bike and foot take the bike and walk
 * lines, which is not a mode colour used as decoration: a cycle track is the
 * bike line's infrastructure, and `metro/mode.ts` is where that colour lives.
 */
const LAYER: Record<EdgeLayer["kind"], EdgeLayer> = {
  street: { kind: "street", color: "var(--color-foreground)" },
  rail: { kind: "rail", color: "var(--color-mode-pt)", dash: "10,6" },
  bikeway: { kind: "bikeway", color: "var(--color-mode-bike)", dash: "6,4" },
  footway: { kind: "footway", color: "var(--color-mode-walk)", dash: "1,5" },
};

/** Only the fields the drawing cares about, so a test needs no whole graph. */
type DrawableEdge = {
  street_edge?: unknown | null;
  train_edge?: unknown | null;
  biking?: boolean;
  walking?: boolean;
};

/**
 * What an edge is made of, bottom stroke first.
 *
 * Never empty: a link with no street, no railway and neither flag set is still
 * a link, and an invisible edge in a map editor is worse than a wrong one.
 */
export function edgeLayers(edge: DrawableEdge): EdgeLayer[] {
  const layers: EdgeLayer[] = [];
  if (edge.street_edge) layers.push(LAYER.street);
  if (edge.train_edge) layers.push(LAYER.rail);
  if (layers.length > 0) return layers;

  if (edge.biking) layers.push(LAYER.bikeway);
  if (edge.walking) layers.push(LAYER.footway);
  return layers.length > 0 ? layers : [LAYER.street];
}

/**
 * How a node is marked.
 *
 * Five node types, two colours: **primary is where people are** (home, work)
 * and **accent is where transit is** (station, stop). Fill separates the two
 * inside each pair, which is the language the rest of the app already speaks
 * for presence — and it survives a colour-blind reader, where green-home
 * against red-bus-stop did not.
 *
 * A node can carry several types, so the first match wins, in the order the
 * old `getNodeColor` used.
 */
export type NodeMark = {
  color: Paint;
  /** Hollow marks get the page colour inside and their colour as the ring. */
  filled: boolean;
  /** Fraction of the ordinary node radius. An unremarkable node is smaller. */
  scale: number;
};

const MARK: Record<string, NodeMark> = {
  home: { color: "var(--color-primary)", filled: true, scale: 1 },
  workplace: { color: "var(--color-primary)", filled: false, scale: 1 },
  station: { color: "var(--color-mode-pt)", filled: true, scale: 1 },
  bus_stop: { color: "var(--color-mode-pt)", filled: false, scale: 1 },
};

const PLAIN_NODE: NodeMark = {
  color: "var(--color-muted-foreground)",
  filled: true,
  scale: 0.7,
};

/** The order a node's types are read in — the first one it carries decides. */
const MARK_ORDER = ["home", "workplace", "station", "bus_stop"] as const;

export function nodeMark(nodeTypes: { name: string }[]): NodeMark {
  const names = new Set(nodeTypes.map((t) => t.name));
  for (const key of MARK_ORDER) {
    if (names.has(key)) return MARK[key];
  }
  return PLAIN_NODE;
}

/**
 * The paint the editor uses for its own state, as opposed to the map's.
 *
 * Two words carry it, and they are the rulebook's: **primary is what you are
 * adding** — a proposed node, a proposed edge, an edge whose properties this
 * version changes — and **accent is what needs attention**, which for an editor
 * means what is being removed and what it is waiting for you to click.
 *
 * That is the pair the old code spent six hues on: green for proposed, red for
 * deleted, amber for selected-for-a-line, a second amber for changed, and a
 * third for the edge source ring.
 */
export const editorPaint = {
  /** A node or edge this version adds, not yet saved. */
  proposed: "var(--color-primary)",
  /** An edge whose properties this version changes. */
  changed: "var(--color-primary)",
  /** A node or edge this version removes. */
  removed: "var(--destructive)",
  /** An edge picked into the route of the line being drawn. */
  routed: "var(--color-mode-pt)",
  /** The node an edge is being drawn from. */
  pending: "var(--destructive)",
  /** The ring around a selected element, and the page colour inside a mark. */
  ink: "var(--color-foreground)",
  surface: "var(--color-card)",
  grid: "var(--color-border)",
  muted: "var(--color-muted-foreground)",
} as const;

/**
 * Every line on the map is the accent, and they are told apart by where they
 * run, not by hue.
 *
 * The editor used to hold eight colours for this — violet, cyan, amber, pink,
 * teal, orange, indigo, lime — which is a second palette, and it still could
 * not show two lines sharing a street: they were drawn on the same coordinates,
 * so whichever came last was the only one you saw. On the shipped map, where
 * twelve lines run over 116 street edges, that is most corridors.
 *
 * Offsetting them perpendicular to the link is what a transit diagram does, it
 * needs no colour, and it shows the overlap rather than hiding it.
 */
export const PT_LINE_PAINT = "var(--color-mode-pt)";

/** How far apart parallel lines on one link sit, in map units (×100). */
export const PT_LINE_SPACING = 9;

/**
 * Shift a link sideways so several lines on it sit beside each other.
 *
 * `index` is the line's place among the `count` lines using this link, so the
 * bundle stays centred on the street whether one line runs on it or five.
 */
export function offsetLine(
  p1: { x: number; y: number },
  p2: { x: number; y: number },
  index: number,
  count: number,
  spacing: number = PT_LINE_SPACING,
): { x1: number; y1: number; x2: number; y2: number } {
  const dx = p2.x - p1.x;
  const dy = p2.y - p1.y;
  const len = Math.hypot(dx, dy);
  const shift = (index - (count - 1) / 2) * spacing;
  if (len === 0 || shift === 0) {
    return { x1: p1.x, y1: p1.y, x2: p2.x, y2: p2.y };
  }
  // The perpendicular unit vector, times the shift.
  const ox = (-dy / len) * shift;
  const oy = (dx / len) * shift;
  return { x1: p1.x + ox, y1: p1.y + oy, x2: p2.x + ox, y2: p2.y + oy };
}

/**
 * Which lines run on which link, and in what order, so `offsetLine` can place
 * them. Built once per render from the graph's own lists.
 */
export function bundleLines(
  lines: { id: number; type: string; edges: number[] }[],
): Map<string, { index: number; count: number }> {
  const perEdge = new Map<number, string[]>();
  for (const line of lines) {
    for (const edgeId of line.edges) {
      const key = `${line.type}-${line.id}`;
      const bundle = perEdge.get(edgeId);
      if (bundle) bundle.push(key);
      else perEdge.set(edgeId, [key]);
    }
  }

  const placed = new Map<string, { index: number; count: number }>();
  for (const [edgeId, keys] of perEdge) {
    keys.forEach((key, index) => {
      placed.set(`${key}@${edgeId}`, { index, count: keys.length });
    });
  }
  return placed;
}

/** The key `bundleLines` files a line's use of one link under. */
export function bundleKey(
  line: { id: number; type: string },
  edgeId: number,
): string {
  return `${line.type}-${line.id}@${edgeId}`;
}
