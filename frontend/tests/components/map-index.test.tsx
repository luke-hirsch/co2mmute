import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MapBadges } from "@/components/map/map-index";
import { de } from "@/lib/de";

describe("MapBadges", () => {
  it("says when a measured map was calibrated, next to the ballot badge", () => {
    const html = renderToStaticMarkup(
      <MapBadges
        gameMap={{
          calibrated_at: "2026-10-16T12:00:00+00:00",
          offers_map_changes: true,
        }}
      />,
    );

    expect(html).toContain("kalibriert am 16.10.2026");
    expect(html).not.toContain(de.map.index.notCalibrated);
    expect(html.indexOf(de.map.index.votable)).toBeLessThan(
      html.indexOf("kalibriert am"),
    );
  });

  it("says an unmeasured map is not, and both are outline badges", () => {
    const html = renderToStaticMarkup(
      <MapBadges gameMap={{ calibrated_at: null, offers_map_changes: false }} />,
    );

    expect(html).toContain(de.map.index.notCalibrated);
    expect(html).toContain(de.map.index.noVote);
    expect(html.match(/data-variant="outline"/g)).toHaveLength(2);
  });
});
