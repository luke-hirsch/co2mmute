import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MapBadges } from "@/components/map/map-index";
import { de } from "@/lib/de";

describe("MapBadges", () => {
  it("says a measured map is calibrated, next to the ballot badge", () => {
    const html = renderToStaticMarkup(
      <MapBadges gameMap={{ calibrated: true, offers_map_changes: true }} />,
    );

    expect(html).toContain(de.map.index.calibrated);
    expect(html).not.toContain(de.map.index.notCalibrated);
    expect(html.indexOf(de.map.index.votable)).toBeLessThan(
      html.indexOf(de.map.index.calibrated),
    );
  });

  it("says an unmeasured map is not, and both are outline badges", () => {
    const html = renderToStaticMarkup(
      <MapBadges gameMap={{ calibrated: false, offers_map_changes: false }} />,
    );

    expect(html).toContain(de.map.index.notCalibrated);
    expect(html).toContain(de.map.index.noVote);
    expect(html.match(/data-variant="outline"/g)).toHaveLength(2);
  });
});
