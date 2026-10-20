import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { TypeOverview } from "@/components/summary/type-overview";
import { de } from "@/lib/de";

const lines = [
  { name: "Sparfuchs", groups: 4, rounds: 12, modes: { bike: 7, public: 4, car: 1 } },
  { name: "Benzin im Blut", groups: 1, rounds: 3, modes: { car: 3 } },
];

describe("TypeOverview", () => {
  it("is folded by default, with the lines in the page", () => {
    const html = renderToStaticMarkup(<TypeOverview lines={lines} />);

    expect(html).toContain("<details");
    expect(html).not.toMatch(/<details[^>]* open/);
    expect(html).toContain(de.summary.typesTitle);
    expect(html).toContain("Sparfuchs");
    expect(html).toContain("4 Gruppen");
    expect(html).toContain(`7× ${de.modes.bike}`);
    expect(html.indexOf("7×")).toBeLessThan(html.indexOf("4×"));
    expect(html).toContain("1 Gruppe");
  });

  it("shows nothing for a game without types", () => {
    expect(renderToStaticMarkup(<TypeOverview lines={[]} />)).toBe("");
  });

  it("carries no figure of CO₂", () => {
    const html = renderToStaticMarkup(<TypeOverview lines={lines} />);

    expect(html).not.toContain("CO₂");
    expect(html).not.toMatch(/\bkg\b/);
  });
});
