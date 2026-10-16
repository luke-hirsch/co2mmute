import { de } from "@/lib/de";
import type { MapCredit } from "@/types/mapTypes";

/**
 * Whose data a generated map is drawn from, very small in the corner of the
 * map. The licences ask for it (OpenStreetMap's, the Zensus', the EU's), and a
 * hand-drawn map has none, so it prints nothing then.
 *
 * Put it inside a `relative` box that holds the map. It lets clicks through to
 * the map, except on a link.
 */
export function MapCredits({ credits }: { credits?: MapCredit[] | null }) {
  if (!credits || credits.length === 0) return null;
  return (
    <p
      data-testid="map-credits"
      className="pointer-events-none absolute right-1.5 bottom-1 left-1.5 text-right text-[10px] leading-tight text-mutedtext"
    >
      <span className="rounded-sm bg-card/80 px-1">
        {de.map.credits.label}{" "}
        {credits.map((credit, i) => (
          <span key={credit.text}>
            {i > 0 && " · "}
            {credit.url ? (
              <a
                href={credit.url}
                target="_blank"
                rel="noreferrer"
                className="pointer-events-auto underline"
              >
                {credit.text}
              </a>
            ) : (
              credit.text
            )}
          </span>
        ))}
      </span>
    </p>
  );
}
