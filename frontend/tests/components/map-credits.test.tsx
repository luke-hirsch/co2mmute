import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MapCredits } from "@/components/map/map-credits";
import { de } from "@/lib/de";

describe("MapCredits", () => {
  it("prints nothing on a map without sources", () => {
    expect(renderToStaticMarkup(<MapCredits credits={undefined} />)).toBe("");
    expect(renderToStaticMarkup(<MapCredits credits={[]} />)).toBe("");
  });

  it("names every source, in order, and links the ones with an address", () => {
    const html = renderToStaticMarkup(
      <MapCredits
        credits={[
          {
            text: "© OpenStreetMap contributors",
            url: "https://www.openstreetmap.org/copyright",
          },
          { text: "© Statistisches Bundesamt (Destatis), Zensus 2022" },
        ]}
      />,
    );

    expect(html).toContain(de.map.credits.label);
    expect(html).toContain(
      '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer"',
    );
    expect(html.indexOf("OpenStreetMap")).toBeLessThan(html.indexOf("Zensus"));
    expect(html.match(/<a /g)).toHaveLength(1);
  });

  it("is small, lets clicks through, and takes its colour from a token", () => {
    const html = renderToStaticMarkup(
      <MapCredits credits={[{ text: "© A" }]} />,
    );

    expect(html).toContain("text-[10px]");
    expect(html).toContain("pointer-events-none");
    expect(html).toContain("text-mutedtext");
    expect(html).not.toContain("font-bold");
  });
});
