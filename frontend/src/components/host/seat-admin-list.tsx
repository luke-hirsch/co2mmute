import { useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ConfirmAction } from "@/components/layout/confirm-action";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { SeatCodePanel } from "@/components/host/seat-code-panel";
import { SeatRow } from "@/components/metro/seat-row";
import { ApiError } from "@/lib/api";
import { de, type HostRefusal } from "@/lib/de";
import { useRemoveSeat, useTakeOverSeat } from "@/lib/queries/seats";
import type { RosterSeat } from "@/lib/game/events";

/**
 * The roster as the host works with it — the same list in the lobby and at the
 * desk, because the things it can do are the same before and during a game.
 * The backend allows adding and removing until the game ends, and the pause is
 * exactly when a teacher rearranges seats (P-06).
 *
 * Which controls a row gets follows from one flag:
 *
 * - **on a phone** (`controlled_by_host: false`) — take it over, or remove it.
 *   Taking over is the one-way half of 1.7: the host decides, the student's
 *   device is out (`taken_over`).
 * - **at this machine** (`controlled_by_host: true`) — play it, hand it to a
 *   device by code, or remove it. Handing over is the other half, and it is
 *   not a button but a code, because a host cannot conjure up a phone: some
 *   device has to redeem it.
 *
 * The host's own row is not here at all. It is not a seat — the round does not
 * wait for it, it cannot be played, handed over or removed, and the backend
 * refuses all three with `host`. Showing it would only offer clicks that 409.
 */
export function SeatAdminList({
  gameId,
  seats,
  canPlay = false,
  onPlay,
}: {
  gameId: string;
  seats: RosterSeat[];
  /** A round is open, so a seat at this machine has something to do. */
  canPlay?: boolean;
  onPlay?: (seatId: string) => void;
}) {
  const takeOver = useTakeOverSeat(gameId);
  const remove = useRemoveSeat(gameId);
  const [handOver, setHandOver] = useState<RosterSeat | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  const players = seats.filter((seat) => !seat.is_host);

  function run(action: { mutateAsync: (id: string) => Promise<unknown> }, id: string) {
    setFailure(null);
    action.mutateAsync(id).catch((error: unknown) => setFailure(seatFailure(error)));
  }

  if (players.length === 0) {
    return <p className="text-muted-foreground">{de.host.noSeats}</p>;
  }

  return (
    <>
      {failure ? (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>{failure}</AlertDescription>
        </Alert>
      ) : null}

      <ul className="border-t border-border">
        {players.map((seat) => (
          <SeatRow
            key={seat.player_id}
            name={seat.name}
            status={seat.status}
            online={seat.online}
            controlledByHost={seat.controlled_by_host}
            action={
              /* On a phone the controls take a line of their own. Left to
                 compete for the row, the name column shrinks instead of
                 wrapping and the buttons land on top of the "am Lehrerrechner"
                 badge — which is exactly what happened at 390px. */
              <div className="flex w-full flex-wrap items-center gap-2 sm:ml-auto sm:w-auto">
                {seat.controlled_by_host ? (
                  <>
                    {canPlay && onPlay ? (
                      <Button
                        size="xs"
                        onClick={() => onPlay(seat.player_id)}
                        disabled={seat.status === "waiting"}
                      >
                        {de.host.play}
                      </Button>
                    ) : null}
                    <Button
                      variant="outline"
                      size="xs"
                      onClick={() => setHandOver(seat)}
                    >
                      {de.handover.toOtherDevice}
                    </Button>
                  </>
                ) : (
                  <ConfirmAction
                    label={de.host.takeOver}
                    title={de.host.takeOver}
                    description={de.host.takeOverConfirm(seat.name)}
                    confirmLabel={de.host.takeOver}
                    onConfirm={() => run(takeOver, seat.player_id)}
                    pending={takeOver.isPending}
                  />
                )}
                <ConfirmAction
                  label={de.host.remove}
                  title={de.host.remove}
                  description={de.host.removeConfirm(seat.name)}
                  confirmLabel={de.host.remove}
                  onConfirm={() => run(remove, seat.player_id)}
                  variant="ghost"
                  pending={remove.isPending}
                />
              </div>
            }
          />
        ))}
      </ul>

      <Dialog
        open={!!handOver}
        onOpenChange={(open) => !open && setHandOver(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {handOver ? de.host.playingSeat(handOver.name) : de.handover.title}
            </DialogTitle>
          </DialogHeader>
          {handOver ? (
            <SeatCodePanel
              gameId={gameId}
              seatId={handOver.player_id}
              body={de.handover.hostBody}
            />
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}

function seatFailure(error: unknown): string {
  if (error instanceof ApiError && error.status === 409 && error.reason) {
    const known = de.host.failed[error.reason as HostRefusal];
    if (known) return known;
  }
  return de.host.failedUnknown;
}
