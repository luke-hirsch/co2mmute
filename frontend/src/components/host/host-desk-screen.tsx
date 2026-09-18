import { AddSeatDialog } from "@/components/host/add-seat-dialog";
import { Button } from "@/components/ui/button";
import { Curtain } from "@/components/host/curtain";
import { HostControls } from "@/components/host/host-controls";
import { RoundHeader } from "@/components/round/round-header";
import { RoundScreen } from "@/components/round/round-screen";
import { Screen } from "@/components/layout/screen";
import { SeatAdminList } from "@/components/host/seat-admin-list";
import { useDesk } from "@/hooks/use-desk";
import { useGame } from "@/components/game/game-context";
import { de } from "@/lib/de";

/**
 * The desk, while a round is running (H-03, H-09).
 *
 * Three states, and `use-desk.ts` owns which one is on:
 *
 *   **desk**     the list — who still owes a move, and everything the host does
 *   **curtain**  one name and one button, nothing of the game
 *   **playing**  the ordinary round screen, with somebody else's seat in it
 *
 * The turn is not reimplemented here. `RoundScreen` was built seat-parameterised
 * in F3 for exactly this, so the host plays a student's seat through the same
 * screen the student would have used — same map, same pickers, same validation,
 * and one place to fix anything wrong with any of it.
 *
 * Coming back is not a button either. A seat that submits turns `waiting` in
 * the roster, and the desk reducer takes that as the turn being over — so does
 * a seat that is removed, handed to a phone, or overtaken by a new round. The
 * machine lands back on the list without anybody pressing anything, which is
 * what you want when the person at the keyboard is thirteen and has already
 * stood up.
 */
export function HostDeskScreen() {
  const { state } = useGame();
  const desk = useDesk();

  if (desk.mode === "curtain" && desk.openSeat) {
    return (
      <Curtain
        name={desk.openSeat.name}
        onReady={desk.ready}
        onCancel={desk.leave}
      />
    );
  }

  if (desk.mode === "playing" && desk.openSeat) {
    return (
      <RoundScreen
        seatId={desk.openSeatId}
        desk={{ name: desk.openSeat.name, onLeave: desk.leave }}
      />
    );
  }

  return (
    <Screen>
      <RoundHeader />

      <section className="mb-12">
        <div className="mb-4 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-3">
          <h2 className="text-2xl font-semibold">{de.host.seats}</h2>
          <div className="flex flex-wrap items-center gap-3">
            {desk.hasNext ? (
              <Button onClick={desk.playNext}>{de.host.next}</Button>
            ) : null}
            <AddSeatDialog gameId={state.gameId} />
          </div>
        </div>

        <p className="mb-6 max-w-(--measure-body) text-muted-foreground">
          {desk.seats.length === 0
            ? de.host.noDeskSeats
            : desk.done
              ? de.host.allDone
              : de.host.deskLead}
        </p>

        <SeatAdminList
          gameId={state.gameId}
          seats={state.seats}
          canPlay={!state.pausedAt}
          onPlay={desk.pick}
        />
      </section>

      <HostControls />
    </Screen>
  );
}
