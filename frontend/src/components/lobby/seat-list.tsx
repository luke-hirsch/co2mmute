import { SeatRow } from "@/components/metro/seat-row";
import { de } from "@/lib/de";
import type { RosterSeat } from "@/lib/game/events";

/**
 * The roster, as the game sees it.
 *
 * The host's own row is filtered out here rather than in the reducer, because
 * it is a display decision and F4's host desk wants that row back — it is how
 * the desk knows it is looking at itself. `playingSeats()` in `lobby-state.ts`
 * is the same filter for the places that need to *count*.
 *
 * Rows are keyed by `player_id`, which changes when a seat moves to another
 * device (1.7 mints a new one on every handover). That is the right key
 * anyway: a remount is exactly what should happen when the seat in front of you
 * is now somebody else's device.
 */
export function SeatList({
  seats,
  youId,
}: {
  seats: RosterSeat[];
  youId: string | null;
}) {
  const players = seats.filter((seat) => !seat.is_host);

  if (players.length === 0) {
    return <p className="text-muted-foreground">{de.lobby.noPlayers}</p>;
  }

  return (
    <ul className="border-t border-border">
      {players.map((seat) => (
        <SeatRow
          key={seat.player_id}
          name={seat.name}
          status={seat.status}
          online={seat.online}
          controlledByHost={seat.controlled_by_host}
          isYou={seat.player_id === youId}
        />
      ))}
    </ul>
  );
}
