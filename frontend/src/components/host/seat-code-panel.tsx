import { useEffect, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { CodeDisplay, DepartureBoard } from "@/components/metro/departure-board";
import { ApiError } from "@/lib/api";
import { de } from "@/lib/de";
import { useIssueSeatCode } from "@/lib/queries/seats";
import type { HostRefusal } from "@/lib/de";

/** A code this panel is showing, and the seat it was made for. */
type HeldCode = {
  seatId: string;
  code: string;
  qrUrl?: string;
  expiresAt: number;
};

/**
 * A seat's transfer code, made on request (1.7).
 *
 * The same panel serves both directions, because it is the same code: the host
 * hands a seat back to a student who turned up with a phone, and a student
 * moves their own seat to another device. Only the explaining sentence differs,
 * so that is the prop.
 *
 * **The countdown is local.** `expires_in` comes with the code (300 s) and runs
 * down here — no polling, and no second opinion about whether a code is still
 * alive. If it really is dead, that shows when somebody tries to redeem it; a
 * client-side clock that disagrees with the server by a second is harmless,
 * whereas a request every second to ask is not.
 *
 * The QR is optional on purpose. `qr_url` only appears once the backend renders
 * one (`[backend]-seat-code-qr.md`); without it the six characters stand alone,
 * which is what an alphabet with no 0/O and no 1/I/L was chosen for.
 */
export function SeatCodePanel({
  gameId,
  seatId,
  body,
}: {
  gameId: string;
  seatId: string;
  body: string;
}) {
  const issue = useIssueSeatCode(gameId);
  const [held, setHeld] = useState<HeldCode | null>(null);
  const [now, setNow] = useState(() => Date.now());

  // The clock ticks, the deadline does not: seconds left are computed from the
  // timestamp rather than counted down in state, so a phone that sleeps or a
  // tab the browser throttles comes back with the right number instead of a
  // stale one.
  useEffect(() => {
    if (!held) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [held]);

  // Derived, not reset in an effect: a code belongs to the seat it was made
  // for, and showing one seat's code under another's name is the one way this
  // panel could hand a stranger a place.
  const issued = held?.seatId === seatId ? held : null;
  const secondsLeft = issued
    ? Math.max(0, Math.ceil((issued.expiresAt - now) / 1000))
    : 0;

  const request = () => {
    issue.mutate(seatId, {
      onSuccess: (code) => {
        setNow(Date.now());
        setHeld({
          seatId,
          code: code.code,
          qrUrl: code.qr_url,
          expiresAt: Date.now() + code.expires_in * 1000,
        });
      },
    });
  };

  const expired = !!issued && secondsLeft <= 0;

  return (
    <div>
      <p className="max-w-(--measure-body) text-muted-foreground">{body}</p>

      {issued ? (
        <DepartureBoard
          label={de.code.seatCode}
          footnote={expired ? de.handover.expired : de.code.expiresIn(secondsLeft)}
          className="mt-6"
        >
          <CodeDisplay code={issued.code} />
          {issued.qrUrl ? (
            <div className="mt-5">
              {/* White plate behind it: a QR has to stay black on white to
                  scan, whatever the board around it is doing. */}
              <img
                src={issued.qrUrl}
                alt={de.handover.scan}
                className="size-40 rounded-md bg-white p-2"
              />
              <p className="mt-3 text-xs text-white/50">{de.handover.scan}</p>
            </div>
          ) : null}
        </DepartureBoard>
      ) : null}

      {issue.error ? (
        <Alert variant="destructive" className="mt-6">
          <AlertDescription>{codeFailure(issue.error)}</AlertDescription>
        </Alert>
      ) : null}

      <div className="mt-6 flex flex-wrap items-center gap-4">
        <Button
          variant={issued ? "outline" : "default"}
          onClick={request}
          disabled={issue.isPending}
        >
          {issue.isPending
            ? de.handover.issuing
            : issued
              ? de.handover.again
              : de.handover.issue}
        </Button>
        {issued && !expired ? (
          <p className="text-sm text-muted-foreground">{de.handover.againHint}</p>
        ) : null}
      </div>
    </div>
  );
}

/** 409 carries a `reason`; anything else is not worth guessing about. */
function codeFailure(error: unknown): string {
  if (error instanceof ApiError && error.status === 409 && error.reason) {
    const known = de.host.failed[error.reason as HostRefusal];
    if (known) return known;
  }
  return de.handover.failed;
}
