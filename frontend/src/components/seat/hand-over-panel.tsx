import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { SeatCodePanel } from "@/components/host/seat-code-panel";
import { de } from "@/lib/de";

/**
 * "Auf anderes Gerät" on a player's own screen (1.7, 2.7).
 *
 * The case is a phone that is about to die, or a student moving to the
 * classroom machine. They ask for a code here and type it on the other device;
 * the seat keeps its row, its moves and its votes, and only its `player_id`
 * changes — which is precisely what makes every cookie naming the old one
 * worthless, this one included.
 *
 * So this device *loses* the seat by using it, and the copy says so before the
 * code appears rather than after. The revocation arrives as `player.revoked`
 * with reason `handed_over`, and `GameFrame` turns that into a full stop.
 */
export function HandOverPanel({
  gameId,
  seatId,
}: {
  gameId: string;
  seatId: string;
}) {
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button variant="ghost" size="sm" onClick={() => setOpen(true)}>
        {de.handover.toOtherDevice}
      </Button>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{de.handover.title}</DialogTitle>
        </DialogHeader>
        <SeatCodePanel
          gameId={gameId}
          seatId={seatId}
          body={de.handover.playerBody}
        />
      </DialogContent>
    </Dialog>
  );
}
