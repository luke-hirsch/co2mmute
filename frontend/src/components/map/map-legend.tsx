import { de } from "@/lib/de";
import { cn } from "@/lib/utils";
import { edgeLayers, nodeMark, type EdgeLayer, type NodeMark } from "@/lib/map/palette";

/**
 * What the marks on a map mean.
 *
 * "Legende fehlt" is on the old README list, and the editor is where it was
 * missing outright — you draw a map in six colours with nothing saying which is
 * a tram track and which is a footpath.
 *
 * **It takes no items any more.** They used to come from the caller, because
 * each renderer carried a colour function of its own and handing the legend its
 * own copy of the colours was the only way to keep it honest. It did not work:
 * `MapViewer` passed `#22c55e` for the walk path while its renderer drew
 * `#10b981`, and `#a855f7` against a drawn `#8b5cf6`. The legend and the map
 * disagreed on four of eleven entries, live, with a comment above them claiming
 * they could not.
 *
 * Now there is one palette (`lib/map/palette.ts`) and the entries below are
 * built by running the *same functions the renderers run*, on an edge or a node
 * that is an example of the case. So the swatch is not a copy of the colour —
 * it is the colour, and the drift has nowhere to happen.
 */

type EdgeEntry = { label: string; layers: EdgeLayer[] };
type NodeEntry = { label: string; mark: NodeMark };

/** One example of each case, drawn by `edgeLayers` exactly as the map draws it. */
const EDGE_ENTRIES: EdgeEntry[] = [
  { label: de.map.legend.street, layers: edgeLayers({ street_edge: {} }) },
  { label: de.map.legend.train, layers: edgeLayers({ train_edge: {} }) },
  {
    label: de.map.legend.streetAndTrain,
    layers: edgeLayers({ street_edge: {}, train_edge: {} }),
  },
  { label: de.map.legend.bike, layers: edgeLayers({ biking: true }) },
  { label: de.map.legend.walk, layers: edgeLayers({ walking: true }) },
  {
    label: de.map.legend.bikeAndWalk,
    layers: edgeLayers({ biking: true, walking: true }),
  },
];

const NODE_ENTRIES: NodeEntry[] = [
  { label: de.map.legend.home, mark: nodeMark([{ name: "home" }]) },
  { label: de.map.legend.workplace, mark: nodeMark([{ name: "workplace" }]) },
  { label: de.map.legend.station, mark: nodeMark([{ name: "station" }]) },
  { label: de.map.legend.busStop, mark: nodeMark([{ name: "bus_stop" }]) },
  { label: de.map.legend.other, mark: nodeMark([]) },
];

export function MapLegend({ className }: { className?: string }) {
  return (
    <section className={cn("text-sm", className)}>
      <h3 className="font-medium">{de.map.legend.title}</h3>

      <div className="mt-3 grid gap-x-8 gap-y-4 sm:grid-cols-2">
        <div>
          <p className="text-xs text-muted-foreground">{de.map.legend.edges}</p>
          <ul className="mt-2 space-y-1.5">
            {EDGE_ENTRIES.map((entry) => (
              <li key={entry.label} className="flex items-center gap-2.5">
                <EdgeSwatch layers={entry.layers} />
                <span>{entry.label}</span>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <p className="text-xs text-muted-foreground">{de.map.legend.nodes}</p>
          <ul className="mt-2 space-y-1.5">
            {NODE_ENTRIES.map((entry) => (
              <li key={entry.label} className="flex items-center gap-2.5">
                <NodeSwatch mark={entry.mark} />
                <span>{entry.label}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

/**
 * An SVG rather than a bordered span, so a dashed entry reads as the dash it is
 * drawn with on the map — and so a corridor carrying two things can show both
 * strokes, stacked the way the renderer stacks them.
 */
function EdgeSwatch({ layers }: { layers: EdgeLayer[] }) {
  const stacked = layers.length > 1;
  return (
    <svg aria-hidden width="24" height="10" className="shrink-0 overflow-visible">
      {layers.map((layer, index) => {
        // Two layers sit either side of the middle, one sits on it.
        const y = stacked ? 3 + index * 4 : 5;
        return (
          <line
            key={layer.kind}
            x1="0"
            y1={y}
            x2="24"
            y2={y}
            stroke={layer.color}
            strokeWidth={stacked ? "2.5" : "3"}
            strokeDasharray={layer.dash}
            strokeLinecap="round"
          />
        );
      })}
    </svg>
  );
}

/** Filled or hollow, the same way the map draws the mark. */
function NodeSwatch({ mark }: { mark: NodeMark }) {
  const r = 5 * mark.scale;
  return (
    <svg aria-hidden width="12" height="12" viewBox="0 0 12 12" className="shrink-0">
      <circle
        cx="6"
        cy="6"
        r={r}
        fill={mark.filled ? mark.color : "var(--color-card)"}
        stroke={mark.color}
        strokeWidth="2"
      />
    </svg>
  );
}
