import { de } from "@/lib/de";
import { cn } from "@/lib/utils";

/**
 * What the colours on a map mean.
 *
 * "Legende fehlt" is on the old README list, and the editor is where it was
 * missing outright — you draw a map in five colours with nothing saying which
 * is a tram track and which is a footpath.
 *
 * **The items come from the caller, not from here.** Each renderer has its own
 * colour function (`EditorCanvas` and `MapViewer` agree; `GameMapViewer` uses a
 * blue/slate scheme so its edges do not collide with the traffic heatmap), and
 * recolouring any of them is redesign — 2.6's explicit exclusion, and a
 * decision about what node types *mean* that the UX pass has to make. So this
 * component is the layout and the wording; the colours stay the renderer's own
 * and the legend cannot drift from what is actually drawn.
 *
 * Dashes matter as much as hue here: a train track is dashed, and on a map with
 * five similar colours the pattern is often what you actually read.
 */

export type LegendItem = {
  /** The colour as the renderer draws it. */
  color: string;
  label: string;
  /** SVG `stroke-dasharray`, for edge entries that are drawn dashed. */
  dash?: string;
  /** Nodes are dots, edges are strokes. */
  shape?: "line" | "dot";
};

export function MapLegend({
  edges,
  nodes,
  className,
}: {
  edges: LegendItem[];
  nodes: LegendItem[];
  className?: string;
}) {
  return (
    <section className={cn("text-sm", className)}>
      <h3 className="font-medium">{de.map.legend.title}</h3>

      <div className="mt-3 grid gap-x-8 gap-y-4 sm:grid-cols-2">
        <Group title={de.map.legend.edges} items={edges} fallbackShape="line" />
        <Group title={de.map.legend.nodes} items={nodes} fallbackShape="dot" />
      </div>
    </section>
  );
}

function Group({
  title,
  items,
  fallbackShape,
}: {
  title: string;
  items: LegendItem[];
  fallbackShape: "line" | "dot";
}) {
  if (items.length === 0) return null;

  return (
    <div>
      <p className="text-xs text-muted-foreground">{title}</p>
      <ul className="mt-2 space-y-1.5">
        {items.map((item) => (
          <li key={item.label} className="flex items-center gap-2.5">
            <Swatch item={item} shape={item.shape ?? fallbackShape} />
            <span>{item.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Swatch({ item, shape }: { item: LegendItem; shape: "line" | "dot" }) {
  if (shape === "dot") {
    return (
      <span
        aria-hidden
        className="size-3 shrink-0 rounded-full"
        style={{ backgroundColor: item.color }}
      />
    );
  }

  // An SVG rather than a bordered span, so a dashed entry actually reads as
  // the dash it is drawn with on the map.
  return (
    <svg aria-hidden width="24" height="6" className="shrink-0 overflow-visible">
      <line
        x1="0"
        y1="3"
        x2="24"
        y2="3"
        stroke={item.color}
        strokeWidth="3"
        strokeDasharray={item.dash}
        strokeLinecap="round"
      />
    </svg>
  );
}
