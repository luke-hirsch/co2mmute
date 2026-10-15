/**
 * Pendlertypen: who a Gruppe is played as ("Sparfuchs — jeder Euro zählt").
 *
 * The host picks a game's at creation, from the standard ones
 * (`GET api/game/personas/`) and their own; the game keeps copies of them
 * (`game.models.Persona`), and each seat is dealt one per Gruppe at join, as the
 * `persona` id of its entry in `agent_assignments`. The round screen names it
 * beside the Gruppe, and the end screen's "Meine Gruppen" lays out how each
 * Gruppe commuted, so a player can hold what it did against what it was meant
 * to be.
 */

/** A Pendlertyp as the endpoints send it: a standard one, or a game's copy. */
export type Persona = { id: number; name: string; description: string };

/** One as the create form sends it. No id: the game gets a copy, not the row. */
export type PersonaDraft = { name: string; description: string };

/**
 * What the create form sends as `personas`.
 *
 * Off, nothing — the key is left out and the game plays free. On, the standard
 * ones still ticked, in their order, then the host's own; with every box
 * unticked that is an empty list, and the server refuses it rather than make a
 * game without the Pendlertypen the host switched on.
 *
 * `unticked` rather than "ticked" so that every standard one is ticked by
 * default, including when the list arrives after the host flipped the switch.
 */
export function pickedPersonas(
  on: boolean,
  standard: readonly Persona[],
  unticked: ReadonlySet<number>,
  own: readonly PersonaDraft[],
): PersonaDraft[] | undefined {
  if (!on) return undefined;
  return [
    ...standard
      .filter((persona) => !unticked.has(persona.id))
      .map(({ name, description }) => ({ name, description })),
    ...own,
  ];
}

/** Each Gruppe's dealt Pendlertyp, by agent id. A Gruppe dealt none is not in it. */
export function personasByAgent(
  agents: readonly { id: number; persona?: number }[],
  personas: readonly Persona[],
): Map<number, Persona> {
  const byId = new Map(personas.map((persona) => [persona.id, persona]));
  const out = new Map<number, Persona>();
  for (const agent of agents) {
    const persona =
      agent.persona === undefined ? undefined : byId.get(agent.persona);
    if (persona) out.set(agent.id, persona);
  }
  return out;
}
