import { useEffect, useRef, useState } from "react";

import { de } from "@/lib/de";
import { useBigScreen } from "@/lib/use-big-screen";
import type { MapCredit } from "@/types/mapTypes";

/** How long the sources stay open on a big screen before they fold. */
export const CREDITS_FOLD_MS = 5000;

/**
 * Whose data a generated map is drawn from. The licences ask for it
 * (OpenStreetMap's, the Zensus', the EU's), and a hand-drawn map has none, so
 * it prints nothing then.
 *
 * Folded it is a small "Quellen" in the corner; opened, the full list lies over
 * the map. OpenStreetMap's attribution rule allows that: behind one tap on a
 * phone, and on a bigger screen once it has been shown. So a phone starts
 * folded, and a big screen starts open and folds after `CREDITS_FOLD_MS` or on
 * the first touch of the map. The text and links stay in the page while it is
 * folded.
 *
 * Put it inside a `relative` box that holds the map. It lets clicks through to
 * the map, except on the "Quellen" button and a link.
 */
export function MapCredits({ credits }: { credits?: MapCredit[] | null }) {
  const big = useBigScreen();
  const [open, setOpen] = useState(big);
  const root = useRef<HTMLDivElement>(null);

  // A phone that turns into a big screen (or back) takes that screen's start.
  useEffect(() => setOpen(big), [big]);

  // On a big screen the list folds by itself: after a few seconds, or when the
  // map is touched. A hand on "Quellen" has the last word.
  useEffect(() => {
    if (!big || !open) return;
    const fold = () => setOpen(false);
    const timer = window.setTimeout(fold, CREDITS_FOLD_MS);
    const map = root.current?.parentElement;
    map?.addEventListener("pointerdown", fold, { once: true });
    return () => {
      window.clearTimeout(timer);
      map?.removeEventListener("pointerdown", fold);
    };
  }, [big, open]);

  if (!credits || credits.length === 0) return null;
  return (
    <div
      ref={root}
      data-testid="map-credits"
      className="pointer-events-none absolute right-1.5 bottom-1"
    >
      <CreditsView credits={credits} open={open} onToggle={setOpen} />
    </div>
  );
}

export function CreditsView({
  credits,
  open,
  onToggle,
}: {
  credits: MapCredit[];
  open: boolean;
  onToggle: (open: boolean) => void;
}) {
  return (
    <details
      open={open}
      onToggle={(event) => onToggle(event.currentTarget.open)}
      className="pointer-events-auto relative text-right text-[10px] leading-tight text-mutedtext"
    >
      <summary className="cursor-pointer list-none rounded-sm bg-card/80 px-1 py-0.5 underline">
        {de.map.credits.label}
      </summary>
      <ul className="absolute right-0 bottom-full mb-1 w-[min(22rem,calc(100vw-3rem))] rounded-sm bg-card/95 px-2 py-1.5 text-left">
        {credits.map((credit) => (
          <li key={credit.text}>
            {credit.url ? (
              <a
                href={credit.url}
                target="_blank"
                rel="noreferrer"
                className="underline"
              >
                {credit.text}
              </a>
            ) : (
              credit.text
            )}
          </li>
        ))}
      </ul>
    </details>
  );
}
