/**
 * What a seat has been dealt.
 *
 * `GET api/game/<game_id>/<player_id>/` (`GetYourOwnGame`) is the only endpoint
 * that hands out `agent_assignments`: one home node plus a destination per
 * agent. The game row rides along, and from it we need `game_map` and
 * `active_map_version` to fetch the graph the routes are found on.
 *
 * Parameterised by the player_id in the URL, not by "me": since 1.6
 * `IsPlayerInGame` also lets the host through for a seat played at the host
 * machine. That is what makes this the same hook F4's desk will use.
 *
 * Read once and left alone (`staleTime: Infinity`). The assignment does not
 * change during a game, and everything that does change arrives over the socket.
 * The one thing that can change is the active map version, after a vote — and
 * that arrives as a new round, which remounts this screen.
 */

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";

export type AgentAssignments = {
  home_node: number;
  agents: { id: number; destination_node: number }[];
};

/** The slice of `GameSessionSerializer` the turn actually needs. */
export type SeatGame = {
  game_id: string;
  game_map: number | null;
  active_map_version: number | null;
  people_per_agent: number;
  agent_assignments: AgentAssignments | null;
};

export const seatKeys = {
  seat: (gameId: string, seatId: string) =>
    ["game", gameId, "seat", seatId] as const,
};

export function useSeatGame(gameId: string, seatId: string | null) {
  return useQuery({
    queryKey: seatKeys.seat(gameId, seatId ?? ""),
    queryFn: () => apiFetch<SeatGame>(`/api/game/${gameId}/${seatId}/`),
    enabled: gameId.length > 0 && !!seatId,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    retry: false,
  });
}
