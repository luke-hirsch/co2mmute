import { useNavigate } from "@tanstack/react-router";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { JoinForm } from "@/components/join/join-form";
import { ParticipantJoin } from "@/components/join/participant-join";
import { SeatTakeover } from "@/components/join/seat-takeover";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import { ApiError, NetworkError } from "@/lib/api";
import { de, type RedeemRefusal } from "@/lib/de";
import { useCodeLook } from "@/lib/queries/join";

/**
 * `/app/join/<CODE>` — the one screen every code lands on: a scanned QR (the
 * projector's, the Leitstelle's seat QR), a typed game id, a typed seat code.
 *
 * It asks the code first (`GET code/<CODE>/`) and renders by what it opens: a
 * game id → name and password; a seat code → "Du übernimmst den Platz von …";
 * a participant code → the card's waiting game(s), then the name.
 * One screen knows what a code can be wrong about, so the other doors only
 * route here.
 */
export function CodeScreen({ code }: { code: string }) {
  const navigate = useNavigate();
  const look = useCodeLook(code);

  if (look.isLoading) {
    return (
      <Screen narrow>
        <p className="text-muted-foreground">{de.join.checking}</p>
      </Screen>
    );
  }

  // 404: nothing is behind the code. Anything else that goes wrong here is a
  // connection problem, and saying "no such code" to someone whose wifi dropped
  // would send them hunting for a typo that is not there.
  if (look.isError || !look.data) {
    return (
      <Screen narrow>
        <ScreenHeading title={de.join.title} />
        <Alert variant="destructive">
          <AlertDescription>{codeFailure(look.error)}</AlertDescription>
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

  if (look.data.kind === "game") return <JoinForm session={look.data} />;
  if (look.data.kind === "participant") {
    return <ParticipantJoin code={code} look={look.data} />;
  }
  return <SeatTakeover code={code} seat={look.data} />;
}

function codeFailure(error: unknown): string {
  if (error instanceof NetworkError) return de.errors.network;
  if (!(error instanceof ApiError)) return de.errors.unknown;
  if (error.status === 404) return de.join.codeNotFound;
  if (error.status === 429) return de.join.codeThrottled;
  if (error.status === 409 && error.reason) {
    const known = de.resumeSeat.refused[error.reason as RedeemRefusal];
    if (known) return known;
  }
  return de.errors.unknown;
}
