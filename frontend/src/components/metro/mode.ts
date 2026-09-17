import type { TransportMode } from "@/lib/de";

/**
 * How each transport mode is drawn. One place, because a mode keeps its look
 * everywhere it appears — legend, agent card, route on the map, stats bar. If
 * you find yourself picking a colour for a mode at a call site, use this.
 *
 * Colour alone does not identify a mode here. The palette is two colours, so
 * the car and the bike are both blue, and two blues of similar luminance read
 * as one line at stroke width. **The stroke pattern is what separates them** —
 * solid, dashed, dotted — which is how a transit map does it and which keeps
 * working for a colour-blind reader.
 *
 * The class names are written out in full rather than built from a template,
 * because Tailwind scans source text and never sees a string it has to compute.
 *
 * Bike and walk swap value between light and dark; that is handled by
 * --line-bike / --line-walk in main.css, not here.
 */
export type ModeStyle = {
  /** Tailwind class painting text in the mode's colour. */
  text: string;
  /** Tailwind class painting a background in the mode's colour. */
  bg: string;
  /** Tailwind class painting a border in the mode's colour. */
  border: string;
  /** Border-style class for the line, empty for a solid one. */
  stroke: "" | "border-dashed" | "border-dotted";
};

export const modeStyle: Record<TransportMode, ModeStyle> = {
  car: {
    text: "text-mode-car",
    bg: "bg-mode-car",
    border: "border-mode-car",
    stroke: "",
  },
  public: {
    text: "text-mode-pt",
    bg: "bg-mode-pt",
    border: "border-mode-pt",
    stroke: "",
  },
  bike: {
    text: "text-mode-bike",
    bg: "bg-mode-bike",
    border: "border-mode-bike",
    stroke: "border-dashed",
  },
  walk: {
    text: "text-mode-walk",
    bg: "bg-mode-walk",
    border: "border-mode-walk",
    stroke: "border-dotted",
  },
};

/** The order the four lines run in, on the landing page and everywhere since. */
export const modeOrder: readonly TransportMode[] = [
  "car",
  "public",
  "bike",
  "walk",
] as const;
