import { describe, expect, it } from "vitest";

import { NumbersExplainerPanel } from "@/components/numbers/numbers-explainer";
import { de } from "@/lib/de";

import { renderInGame } from "../in-game";

describe("NumbersExplainerPanel", () => {
  it("explains the CO₂ alongside the cost", () => {
    const html = renderInGame(<NumbersExplainerPanel />);

    expect(html).toContain("CO₂");
    expect(html).toContain(de.numbers.jamTitle);
  });

  it("says nothing about CO₂ in a game that hides it", () => {
    const html = renderInGame(<NumbersExplainerPanel />, { hideCo2: true });

    expect(html).not.toContain("CO₂");
    // Every topic is still there, told by the cost.
    for (const title of [
      de.numbers.scaleTitle,
      de.numbers.timeTitle,
      de.numbers.paidTitle,
      de.numbers.networkTitle,
      de.numbers.jamTitle,
    ]) {
      expect(html).toContain(title);
    }
  });

  it("explains the CO₂ again once the hidden game is over", () => {
    const html = renderInGame(<NumbersExplainerPanel />, {
      hideCo2: true,
      endedAt: "2026-10-17T10:00:00Z",
    });

    expect(html).toContain("CO₂");
  });
});
