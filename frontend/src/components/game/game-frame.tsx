import { useNavigate } from "@tanstack/react-router";
import type { ReactNode } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { PauseBanner } from "@/components/metro/pause-banner";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import { useGame } from "@/components/game/game-context";
import { ApiError } from "@/lib/api";
import { de } from "@/lib/de";

/**
 * What every screen in a game has in common, in one place.
 *
 * Three of these used to be nobody's job. A revoked seat kept rendering a game
 * it no longer had; a paused game looked exactly like a running one; a dropped
 * socket looked like a game where nothing was happening. Putting them in the
 * frame means they hold for the legacy screen too, which still sits under this
 * layout until F3 replaces it.
 *
 * The order matters: revoked beats everything, because once the seat is gone
 * nothing below it is true any more.
 */
export function GameFrame({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const { state, connection, isLoading, error } = useGame();

  // The seat is not ours. The socket has already been closed with 4403, so this
  // is a full stop rather than a banner over a game we cannot act in.
  if (state.revoked) {
    return (
      <Screen narrow>
        <ScreenHeading
          title={de.revoked.title}
          lead={de.revoked.reason[state.revoked]}
        />
        <Button variant="outline" onClick={() => void navigate({ to: "/join" })}>
          {de.revoked.back}
        </Button>
      </Screen>
    );
  }

  // 403 from the snapshot: no valid game cookie for this game. The join screen
  // is the only useful place to send them.
  if (error) {
    const forbidden = error instanceof ApiError && error.status === 403;
    return (
      <Screen narrow>
        <ScreenHeading title={de.lobby.title} />
        <Alert variant="destructive">
          <AlertDescription>
            {forbidden ? de.lobby.noAccess : de.errors.unknown}
          </AlertDescription>
        </Alert>
        <Button
          variant="outline"
          className="mt-8"
          onClick={() =>
            void navigate({
              to: "/join/$gameId",
              params: { gameId: state.gameId },
            })
          }
        >
          {de.lobby.joinAgain}
        </Button>
      </Screen>
    );
  }

  if (isLoading) {
    return (
      <Screen narrow>
        <p className="text-muted-foreground">{de.app.loading}</p>
      </Screen>
    );
  }

  return (
    <>
      {state.pausedAt ? (
        // Fixed rather than in the flow: the bell can ring while someone is
        // halfway down a long screen, and a banner they have to scroll up to
        // find is not a banner.
        <div className="sticky top-0 z-40 px-4 pt-4 sm:px-6">
          <PauseBanner />
        </div>
      ) : null}

      {children}

      {/* Reconnecting is normal on a school wifi and not worth an alert. It is
          worth saying, because everything on screen stops moving while it
          happens and the alternative is looking at a game that seems frozen.

          Never once the game is over, though: `ws_auth.resolve_player` refuses
          a socket for a game with an `ended_at` (4403, "game-ended"), so on the
          summary there is nothing to reconnect to and the line would sit under
          a finished game for ever promising otherwise. Nothing on that screen
          needs a socket — it reads the reducer and one query. */}
      {connection !== "open" && !state.endedAt ? (
        <p className="px-4 pb-8 text-center text-sm text-muted-foreground sm:px-6">
          {de.lobby.connectionLost}
        </p>
      ) : null}
    </>
  );
}
