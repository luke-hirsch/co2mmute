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
