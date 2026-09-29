import { useGame } from "@/components/game/game-context";
import { useHostGame } from "@/lib/queries/session";
import { useSeatGame } from "@/lib/queries/seat";

/**
 * How many real people one Gruppe stands for, wherever this device can read it.
 *
 * It is derived from the class size — `GameMap.district_commuters / (seats x
 * Gruppen)` — so it is a property of the game, not a constant, and only the
 * server knows it. Three endpoints carry it and **no single one of them serves
 * both halves of the room**, which is why the preference order lives here in one
 * place rather than in each screen:
 *
 * 1. `round.completed`, once a round has finished. Everybody gets this one, and
 *    it is the figure the numbers on screen were actually computed with.
 * 2. the seat (`GET api/game/<id>/<player_id>/`), for a player before round 1.
 *    The host has no seat.
 * 3. the game row (`GET api/game/<id>/`), for the host before round 1. It needs
 *    a logged-in user, so a player cannot call it.
 *
 * Both queries are `staleTime: Infinity` and are already in the cache wherever a
 * screen uses them, so this costs no extra request. Null until one of the three
 * answers, which happens on the host desk in round 1 — the screens then leave the
 * factor out of the sentence rather than guessing at it.
 */
export function usePeoplePerAgent(): number | null {
  const { state, seatId, isHost } = useGame();
  const seat = useSeatGame(state.gameId, seatId);
  const host = useHostGame(state.gameId, isHost);

  return (
    state.lastRound?.peoplePerAgent ??
    seat.data?.people_per_agent ??
    host.data?.people_per_agent ??
    null
  );
}
