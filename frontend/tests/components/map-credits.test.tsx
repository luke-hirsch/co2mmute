import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
  CREDITS_FOLD_MS,
  CreditsView,
  MapCredits,
} from "@/components/map/map-credits";
import { NamesToggle } from "@/components/map/names-toggle";
import { de } from "@/lib/de";
import { BIG_SCREEN_QUERY } from "@/lib/use-big-screen";

const credits = [
  {
    text: "© OpenStreetMap contributors",
    url: "https://www.openstreetmap.org/copyright",
  },
  { text: "© Statistisches Bundesamt (Destatis), Zensus 2022" },
];

describe("MapCredits", () => {
  it("prints nothing on a map without sources", () => {
    expect(renderToStaticMarkup(<MapCredits credits={undefined} />)).toBe("");
    expect(renderToStaticMarkup(<MapCredits credits={[]} />)).toBe("");
  });

  it("starts folded where there is no window to measure, behind a small Quellen", () => {
    const html = renderToStaticMarkup(<MapCredits credits={credits} />);

    expect(html).toContain("<details");
    expect(html).not.toMatch(/<details[^>]* open/);
    expect(html).toContain(`>${de.map.credits.label}</summary>`);
    expect(de.map.credits.label).toBe("Quellen");
  });

  it("keeps every source and link in the page while folded, in order", () => {
    const html = renderToStaticMarkup(
      <CreditsView credits={credits} open={false} onToggle={() => {}} />,
    );

    expect(html).toContain(
      '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer"',
    );
    expect(html.indexOf("OpenStreetMap")).toBeLessThan(html.indexOf("Zensus"));
    expect(html.match(/<a /g)).toHaveLength(1);
  });

  it("opens when told to", () => {
    const html = renderToStaticMarkup(
      <CreditsView credits={credits} open onToggle={() => {}} />,
    );
    expect(html).toMatch(/<details[^>]* open/);
  });

  it("is small, lets clicks through but on the button, and uses tokens", () => {
    const html = renderToStaticMarkup(<MapCredits credits={credits} />);

    expect(html).toContain("text-[10px]");
    expect(html).toContain("pointer-events-none");
    expect(html).toContain("pointer-events-auto");
    expect(html).toContain("text-mutedtext");
    expect(html).not.toContain("font-bold");
  });

  it("folds a big screen after five seconds, and a big screen is Tailwind's sm", () => {
    expect(CREDITS_FOLD_MS).toBe(5000);
    expect(BIG_SCREEN_QUERY).toBe("(min-width: 640px)");
  });
});

describe("NamesToggle", () => {
  it("is a switch labelled Namen anzeigen that reflects its state", () => {
    const on = renderToStaticMarkup(<NamesToggle shown onChange={() => {}} />);
    const off = renderToStaticMarkup(
      <NamesToggle shown={false} onChange={() => {}} />,
    );

    expect(on).toContain('role="switch"');
    expect(on).toContain(de.map.names);
    expect(de.map.names).toBe("Namen anzeigen");
    expect(on).toContain('checked=""');
    expect(off).not.toContain('checked=""');
  });
});
