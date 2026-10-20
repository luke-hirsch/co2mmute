import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MapBadges } from "@/components/map/map-index";
import { de } from "@/lib/de";

function badges(
  calibrated_at: string | null,
  edited_since_calibration: boolean,
  offers_map_changes = true,
) {
  return renderToStaticMarkup(
    <MapBadges
      gameMap={{ calibrated_at, edited_since_calibration, offers_map_changes }}
    />,
  );
}

describe("MapBadges", () => {
  it("says a measured map is calibrated, next to the ballot badge", () => {
    const html = badges("2026-10-16T12:00:00+00:00", false);

    expect(html).toContain(`>${de.map.index.calibrated}<`);
    expect(html).not.toContain(de.map.index.notCalibrated);
    expect(html).not.toContain(de.map.index.calibrationStale);
    expect(html.indexOf(de.map.index.votable)).toBeLessThan(
      html.indexOf(`>${de.map.index.calibrated}<`),
    );
  });

  it("says a map edited after its measurement has a stale calibration", () => {
    const html = badges("2026-10-16T12:00:00+00:00", true);

    expect(html).toContain(`>${de.map.index.calibrationStale}<`);
    expect(html).not.toContain(`>${de.map.index.calibrated}<`);
    expect(html).not.toContain(de.map.index.notCalibrated);
  });

  it("says an unmeasured map is not, and both are outline badges", () => {
    const html = badges(null, false, false);

    expect(html).toContain(de.map.index.notCalibrated);
    expect(html).toContain(de.map.index.noVote);
    expect(html.match(/data-variant="outline"/g)).toHaveLength(2);
  });

  it("names the three states exactly", () => {
    expect(de.map.index.calibrated).toBe("kalibriert");
    expect(de.map.index.notCalibrated).toBe("nicht kalibriert");
    expect(de.map.index.calibrationStale).toBe("Kalibrierung veraltet");
  });
});
