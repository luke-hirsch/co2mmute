import type { TransportMode } from "@/lib/de";

/**
 * How each transport mode is drawn. One place, because a mode keeps its colour
 * everywhere it appears — legend, agent card, route on the map, stats bar. If
 * you find yourself picking a colour for a mode at a call site, use this.
 *
 * The class names are written out in full rather than built from a template,
 * because Tailwind scans source text and never sees a string it has to compute.
 *
 * Walking is dotted and flips between ink and near-white with the theme; that
 * is handled by --line-walk in main.css, not here.
 */
export type ModeStyle = {
  /** Tailwind class painting text in the mode's colour. */
  text: string;
  /** Tailwind class painting a background in the mode's colour. */
  bg: string;
  /** Tailwind class painting a border in the mode's colour. */
  border: string;
  /** Walking is drawn as a dotted line, the other three solid. */
  dotted: boolean;
};

export const modeStyle: Record<TransportMode, ModeStyle> = {
  car: {
    text: "text-mode-car",
    bg: "bg-mode-car",
    border: "border-mode-car",
    dotted: false,
  },
  public: {
    text: "text-mode-pt",
    bg: "bg-mode-pt",
    border: "border-mode-pt",
    dotted: false,
  },
  bike: {
    text: "text-mode-bike",
    bg: "bg-mode-bike",
    border: "border-mode-bike",
    dotted: false,
  },
  walk: {
    text: "text-mode-walk",
    bg: "bg-mode-walk",
    border: "border-mode-walk",
    dotted: true,
  },
};

/** The order the four lines run in, on the landing page and everywhere since. */
export const modeOrder: readonly TransportMode[] = [
  "car",
  "public",
  "bike",
  "walk",
] as const;
