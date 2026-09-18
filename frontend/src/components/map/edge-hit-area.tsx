/**
 * The invisible wide stroke that makes a thin edge clickable.
 *
 * An edge is drawn 3 units wide in a view box a thousand units across, which
 * lands at one or two pixels on screen — so clicking one meant hitting a hair.
 * That is "Edges lassen sich nicht anklicken" on the old README list, and K-03.
 *
 * The editor already had this trick inline; the map detail page put its
 * `onClick` straight on the visible line and was effectively unclickable. Same
 * stroke, one component, so the target stays the same size wherever edges are
 * drawn.
 *
 * `strokeWidth` is in **map units**, not pixels: the SVG scales, so a fixed
 * pixel target is not available. 14 is what the editor used and what a mouse
 * reliably hits at the zoom levels these maps are drawn at.
 */
export function EdgeHitArea({
  x1,
  y1,
  x2,
  y2,
  onClick,
  strokeWidth = 14,
}: {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  onClick: (event: React.MouseEvent<SVGLineElement>) => void;
  strokeWidth?: number;
}) {
  return (
    <line
      x1={x1}
      y1={y1}
      x2={x2}
      y2={y2}
      stroke="transparent"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      className="cursor-pointer"
      onClick={onClick}
    />
  );
}
