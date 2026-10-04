import { de } from "@/lib/de";
import { cn } from "@/lib/utils";
import { PT_LINE_PAINT } from "@/lib/map/palette";
import type { Network, Point, VersionDiff } from "@/lib/map/version-diff";

/**
 * What a version changes, drawn over a map — the editor's canvas and the vote's
 * map draw the same thing from the same `VersionDiff`.
 *
 * **Colour says which network, fill says which way.** Primary is the street
 * network (car, bike, foot), the accent is public transport — the game's two
 * colours, as everywhere. What arrives or changes is a full stroke; what goes is
 * hollow, the "presence" language the roster and the track already speak. A
 * dash would have been the obvious "gone", and on this map a dash means a bike.
 *
 * Every stroke sits on a halo in the card's colour, so it reads over the
 * background image and over the network under it. Sizes come from the caller:
 * `GameMapViewer` sizes everything as a fraction of its view box, the editor in
 * fixed units, and neither should have to learn the other's way.
 */

export type DiffSizes = {
  /** The stroke of a changed link or line segment. */
  line: number;
  /** The halo under it. */
  halo: number;
  /** The radius of a node that comes or goes. */
  node: number;
};

const PAINT: Record<Network, string> = {
  street: "var(--color-primary)",
  pt: PT_LINE_PAINT,
};

/** The SVG is in map units × 100, as in every renderer. */
const svg = (p: Point) => ({ x: p.x * 100, y: p.y * 100 });

type Stroke = {
  key: string;
  a: Point;
  b: Point;
  network: Network;
  hollow: boolean;
  /** Drawn as a stripe down the middle: a PT change on a link whose street changed too. */
  stripe: boolean;
};

export function VersionDiffLayer({
  diff,
  sizes,
}: {
  diff: VersionDiff;
  sizes: DiffSizes;
}) {
  const streetChanged = new Set(
    diff.links.filter((l) => l.network === "street").map((l) => `${l.start}-${l.end}`),
  );

  const strokes: Stroke[] = [
    ...diff.links.map((link, i) => ({
      key: `link-${i}`,
      a: link.a,
      b: link.b,
      network: link.network,
      hollow: link.sense === "removed",
      stripe: link.network === "pt" && streetChanged.has(`${link.start}-${link.end}`),
    })),
    ...diff.lines.flatMap((line) =>
      line.segments.map((segment, i) => ({
        key: `line-${line.type}-${line.id}-${i}`,
        a: segment.a,
        b: segment.b,
        network: "pt" as const,
        hollow: segment.sense === "removed",
        stripe: streetChanged.has(`${segment.start}-${segment.end}`),
      })),
    ),
  ];

  // Hollow first, so a link that goes never covers one that arrives, and the
  // street network under public transport, so a stripe lands on its street.
  const order = (s: Stroke) => (s.hollow ? 0 : 2) + (s.network === "pt" ? 1 : 0);
  const sorted = [...strokes].sort((x, y) => order(x) - order(y));

  return (
    <g
      data-layer="version-diff"
      fill="none"
      strokeLinecap="round"
      pointerEvents="none"
      aria-hidden="true"
    >
      {strokes.map((s) => {
        const a = svg(s.a);
        const b = svg(s.b);
        return (
          <line
            key={`halo-${s.key}`}
            x1={a.x}
            y1={a.y}
            x2={b.x}
            y2={b.y}
            stroke="var(--color-card)"
            strokeWidth={sizes.halo}
            opacity={0.9}
          />
        );
      })}

      {sorted.map((s) => {
        const a = svg(s.a);
        const b = svg(s.b);
        const width = s.stripe ? sizes.line * 0.5 : sizes.line;
        return (
          <g key={s.key} data-network={s.network} data-hollow={s.hollow || undefined}>
            <line
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke={PAINT[s.network]}
              strokeWidth={width}
            />
            {s.hollow ? (
              <line
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke="var(--color-card)"
                strokeWidth={width * 0.45}
              />
            ) : null}
          </g>
        );
      })}

      {diff.nodes.map((node) => {
        const p = svg(node.at);
        return (
          <circle
            key={`node-${node.id}`}
            cx={p.x}
            cy={p.y}
            r={sizes.node}
            fill={node.sense === "added" ? PAINT.street : "var(--color-card)"}
            stroke={PAINT.street}
            strokeWidth={sizes.node * 0.5}
          />
        );
      })}
    </g>
  );
}

/**
 * What the strokes on the map mean, drawn with the same paint — only the kinds
 * this diff actually has, so "fällt weg" is not explained beside a change that
 * takes nothing away.
 */
export function VersionDiffLegend({
  diff,
  className,
}: {
  diff: VersionDiff;
  className?: string;
}) {
  const networks = new Set<Network>([
    ...diff.links.map((l) => l.network),
    ...(diff.lines.length ? (["pt"] as const) : []),
    ...(diff.nodes.length ? (["street"] as const) : []),
  ]);
  const gone =
    diff.links.some((l) => l.sense === "removed") ||
    diff.lines.some((l) => l.segments.some((s) => s.sense === "removed")) ||
    diff.nodes.some((n) => n.sense === "removed");
  const entries: { label: string; network: Network; hollow?: boolean }[] = [
    ...(networks.has("street")
      ? [{ label: de.map.diff.legendStreet, network: "street" as const }]
      : []),
    ...(networks.has("pt") ? [{ label: de.map.diff.legendPt, network: "pt" as const }] : []),
    ...(gone
      ? [{ label: de.map.diff.legendGone, network: "street" as const, hollow: true }]
      : []),
  ];
  return (
    <ul
      className={cn(
        "flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted-foreground",
        className,
      )}
    >
      {entries.map((entry) => (
        <li key={entry.label} className="flex items-center gap-2">
          <svg width="28" height="10" viewBox="0 0 28 10" aria-hidden="true">
            <line
              x1="3"
              y1="5"
              x2="25"
              y2="5"
              // "Fällt weg" is hollow in either colour, so its swatch is ink.
              stroke={entry.hollow ? "var(--color-foreground)" : PAINT[entry.network]}
              strokeWidth="6"
              strokeLinecap="round"
            />
            {entry.hollow ? (
              <line
                x1="3"
                y1="5"
                x2="25"
                y2="5"
                stroke="var(--color-card)"
                strokeWidth="2.7"
                strokeLinecap="round"
              />
            ) : null}
          </svg>
          {entry.label}
        </li>
      ))}
    </ul>
  );
}
