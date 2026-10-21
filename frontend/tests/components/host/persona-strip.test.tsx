import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { PersonaStripList } from "@/components/host/persona-strip";
import { de } from "@/lib/de";

const rows = [
  { id: 1, name: "Sparfuchs", groups: 3 },
  { id: 2, name: "Sportskanone", groups: 1 },
];

describe("PersonaStripList", () => {
  it("names each type once with how many Gruppen hold it", () => {
    const html = renderToStaticMarkup(<PersonaStripList rows={rows} />);

    expect(html).toContain(de.host.personasInPlay.title);
    expect(html).toContain("Sparfuchs");
    expect(html).toContain("3 Gruppen");
    expect(html).toContain("Sportskanone");
    expect(html).toContain("1 Gruppe<");
    expect(html.indexOf("Sparfuchs")).toBeLessThan(html.indexOf("Sportskanone"));
  });

  it("says nothing when no type is in play", () => {
    expect(renderToStaticMarkup(<PersonaStripList rows={[]} />)).toBe("");
  });

  it("links to no player", () => {
    const html = renderToStaticMarkup(<PersonaStripList rows={rows} />);

    expect(html).not.toContain("<a ");
    expect(html).not.toContain("button");
  });
});
