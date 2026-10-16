import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { BudgetNote } from "@/components/host/budget-note";

const TABLE = { "100": 3.62, "75": 2.65, "50": 1.86, "25": 1.28, "0": 0.73 };

describe("BudgetNote", () => {
  it("says up to which share of cars the budget reaches", () => {
    const html = renderToStaticMarkup(
      <BudgetNote table={TABLE} kgPerPerson="2.4" />,
    );

    expect(html).toContain(
      "Auf dieser Karte reichen 2,4 kg, wenn bis zu 67 % der Gruppen Auto fahren.",
    );
    expect(html).not.toContain("Nicht spielbar");
  });

  it("follows the dial", () => {
    const html = renderToStaticMarkup(
      <BudgetNote table={TABLE} kgPerPerson="1.4" />,
    );

    expect(html).toContain("reichen 1,4 kg, wenn bis zu 30 % der Gruppen");
  });

  it("says a budget that cannot be lost is not playable", () => {
    const html = renderToStaticMarkup(
      <BudgetNote table={TABLE} kgPerPerson="5.0" />,
    );

    expect(html).toContain(
      "Nicht spielbar: 5,0 kg reichen auf dieser Karte auch, wenn alle Auto fahren – das Budget ist nicht zu verlieren.",
    );
    expect(html).toContain("Stell weniger kg ein.");
    expect(html).toContain("border-brandaccent");
  });

  it("says a budget that cannot be made is not playable, and what to do", () => {
    const html = renderToStaticMarkup(
      <BudgetNote table={TABLE} kgPerPerson="0.6" />,
    );

    expect(html).toContain(
      "Nicht spielbar: 0,6 kg reichen auf dieser Karte nicht einmal, wenn niemand Auto fährt – das Budget ist nicht zu schaffen.",
    );
    expect(html).toContain(
      "Stell mehr kg ein, oder dünn im Karteneditor den Fahrplan aus: weniger Linien, ein längerer Takt. Bus und Bahn fahren, ob jemand mitfährt oder nicht.",
    );
  });

  it("prints nothing on a map without a table", () => {
    expect(
      renderToStaticMarkup(<BudgetNote table={null} kgPerPerson="2.4" />),
    ).toBe("");
    expect(
      renderToStaticMarkup(<BudgetNote table={undefined} kgPerPerson="2.4" />),
    ).toBe("");
  });
});
