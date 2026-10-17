import { useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { CodeDisplay, DepartureBoard } from "@/components/metro/departure-board";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import { ApiError, NetworkError } from "@/lib/api";
import { de, type RedeemRefusal } from "@/lib/de";
import type { SeatLook } from "@/lib/queries/join";
import { useRedeemSeatCode } from "@/lib/queries/seats";

/**
 * A seat code opened: the device that takes a seat over.
 *
 * `CodeScreen` has already asked (`GET code/<CODE>/`: who and which game, the
 * code **not** used up). This is the second call, and the order is the point:
 *
 *   POST code/<CODE>/   single use: new player_id, both cookies, old device out
 *
 * Asking first is what makes a QR safe to scan. A code is a bearer token, so
 * opening the link must not be enough to take a seat — somebody who scans the
 * projector out of curiosity would otherwise throw a classmate off their game
 * before reading a word.
 *
 * The ways the take can fail all say different things, which is why
 * `lib/api.ts` keeps status and `reason`:
 *
 *   404          the code is gone — expired, or already used
 *   409 seated   this browser already holds a seat in that game
 *   409 host     this browser runs the game
 *   409 ended    the game is over
 */
export function SeatTakeover({ code, seat }: { code: string; seat: SeatLook }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const redeem = useRedeemSeatCode();

  async function take() {
    const taken = await redeem.mutateAsync(code).catch(() => null);
    if (!taken) return;
    // Both cookies came back on that response, and `whoami` is what every
    // screen asks who it is — the cached answer is now a different person.
    await queryClient.invalidateQueries({ queryKey: ["identity"] });
    await navigate({ to: "/game/$gameId", params: { gameId: taken.game_id } });
  }

  if (redeem.error) {
    return (
      <Screen narrow>
        <ScreenHeading title={de.resumeSeat.title} />
        <Alert variant="destructive">
          <AlertDescription>{redeemFailure(redeem.error)}</AlertDescription>
        </Alert>
        <Button
          variant="outline"
          className="mt-8"
          onClick={() => void navigate({ to: "/join" })}
        >
          {de.actions.back}
        </Button>
      </Screen>
    );
  }

  return (
    <Screen narrow>
      <ScreenHeading title={de.resumeSeat.title} />

      <DepartureBoard label={de.code.seatCode} className="mb-10">
        <CodeDisplay code={code} />
      </DepartureBoard>

      <p className="max-w-(--measure-body)">
        {de.resumeSeat.confirm(seat.player_name, seat.game_name)}
      </p>

      <div className="mt-8 flex flex-wrap items-center gap-4">
        <Button size="lg" onClick={() => void take()} disabled={redeem.isPending}>
          {redeem.isPending ? de.resumeSeat.taking : de.resumeSeat.take}
        </Button>
        <Button variant="ghost" onClick={() => void navigate({ to: "/join" })}>
          {de.actions.cancel}
        </Button>
      </div>
    </Screen>
  );
}

function redeemFailure(error: unknown): string {
  if (error instanceof NetworkError) return de.errors.network;
  if (!(error instanceof ApiError)) return de.errors.unknown;
  if (error.status === 404) return de.resumeSeat.gone;
  if (error.status === 429) return de.join.codeThrottled;
  if (error.status === 409 && error.reason) {
    const known = de.resumeSeat.refused[error.reason as RedeemRefusal];
    if (known) return known;
  }
  return de.errors.unknown;
}
