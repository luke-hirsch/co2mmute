import { describe, expect, it } from "vitest";

import { personasByAgent, pickedPersonas } from "@/lib/game/personas";
import type { Persona } from "@/lib/game/personas";

/**
 * Pendlertypen, without React: what the create form sends, and which Gruppe
 * the round screen labels with which.
 *
 * The send is worth pinning for its two empties. Switched off, the key is left
 * out and the game plays free; switched on with every box unticked, an empty
 * list goes and the server refuses it — a host who switched them on and gets a
 * game without them has been ignored.
 */

const standard: Persona[] = [
  { id: 1, name: "Sparfuchs", description: "Jeder Euro zählt." },
  { id: 2, name: "Sportskanone", description: "Rad und Füße sind Training." },
  { id: 3, name: "Einfach du", description: "Keine Mission." },
];

describe("pickedPersonas", () => {
  it("sends nothing while the switch is off", () => {
    expect(pickedPersonas(false, standard, new Set(), [])).toBeUndefined();
  });

  it("sends the ticked standard ones in their order, then the host's own", () => {
    const own = [{ name: "Nachteule", description: "" }];

    expect(pickedPersonas(true, standard, new Set([2]), own)).toEqual([
      { name: "Sparfuchs", description: "Jeder Euro zählt." },
      { name: "Einfach du", description: "Keine Mission." },
      { name: "Nachteule", description: "" },
    ]);
  });

  it("sends an empty list when every box is unticked, for the server to refuse", () => {
    expect(pickedPersonas(true, standard, new Set([1, 2, 3]), [])).toEqual([]);
  });

  it("sends no ids: the game gets copies, not the standard rows", () => {
    const sent = pickedPersonas(true, standard, new Set(), []) ?? [];

    expect(sent.every((p) => !("id" in p))).toBe(true);
  });
});

describe("personasByAgent", () => {
  it("names each Gruppe's dealt Pendlertyp", () => {
    const byAgent = personasByAgent(
      [
        { id: 1, persona: 3 },
        { id: 2, persona: 1 },
      ],
      standard,
    );

    expect(byAgent.get(1)?.name).toBe("Einfach du");
    expect(byAgent.get(2)?.name).toBe("Sparfuchs");
  });

  it("leaves a Gruppe out when the game dealt none", () => {
    expect(personasByAgent([{ id: 1 }], standard).size).toBe(0);
  });

  it("leaves a Gruppe out whose id the game does not have", () => {
    expect(personasByAgent([{ id: 1, persona: 99 }], standard).size).toBe(0);
  });
});
