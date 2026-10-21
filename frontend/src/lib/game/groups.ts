/**
 * "Meine Gruppen" on the end screen: a seat's own Gruppen, each with its
 * Pendlertyp and how it commuted over the game (`SummaryGroup`).
 */

import { modeOrder } from "@/components/metro/mode";
import type { TransportMode } from "@/lib/de";
import type { GameSummary, SummaryGroup } from "@/lib/queries/summary";

/**
 * The viewer's own Gruppen, or none.
 *
 * None before the summary lands, for a game that dealt no Pendlertypen (the
 * payload's `groups` are empty then), and for the host, whose own row is not
 * in `players` — so the switch offers the view only where there is one.
 */
export function ownGroups(
  summary: GameSummary | undefined,
  seatId: string | null,
): SummaryGroup[] {
  if (!summary || !seatId) return [];
  return summary.players.find((player) => player.player_id === seatId)?.groups ?? [];
}

/**
 * How often a Gruppe took each mode, most often first. A tie keeps the order
 * the four lines always run in, so two Gruppen with the same tally read alike.
 */
export function modeTally(
  modes: Partial<Record<TransportMode, number>>,
): { mode: TransportMode; count: number }[] {
  return modeOrder
    .filter((mode) => (modes[mode] ?? 0) > 0)
    .map((mode) => ({ mode, count: modes[mode] ?? 0 }))
    .sort((a, b) => b.count - a.count);
}

/** One Pendlertyp over the whole class: its Gruppen, and what they did. */
export type TypeLine = {
  name: string;
  /** How many Gruppen were dealt it, whatever their seat. */
  groups: number;
  /** Trips the Gruppen made in all (a Gruppe's rounds, added up). */
  rounds: number;
  /** How often those trips took each mode; a mode never taken is not a key. */
  modes: Partial<Record<TransportMode, number>>;
};

/**
 * "Pendlertypen": every type once, over every seat that
 * holds it, in the order they first turn up.
 *
 * The same `groups` the seat's own view reads, added up by type. It carries no
 * seat and no figure of CO₂ — a hidden game's budget is the summary's to show,
 * and this line is about what a type *did*, not what it emitted.
 */
export function typeOverview(
  players: readonly { groups: readonly SummaryGroup[] }[],
): TypeLine[] {
  const lines = new Map<string, TypeLine>();
  for (const player of players) {
    for (const group of player.groups) {
      if (!group.persona) continue;
      const name = group.persona.name;
      const line = lines.get(name) ?? { name, groups: 0, rounds: 0, modes: {} };
      line.groups += 1;
      line.rounds += group.rounds;
      for (const [mode, count] of Object.entries(group.modes) as [
        TransportMode,
        number,
      ][]) {
        line.modes[mode] = (line.modes[mode] ?? 0) + count;
      }
      lines.set(name, line);
    }
  }
  return [...lines.values()];
}

