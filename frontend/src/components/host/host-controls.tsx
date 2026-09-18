import { PauseIcon, PlayIcon } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ConfirmAction } from "@/components/layout/confirm-action";
import { useGame } from "@/components/game/game-context";
import { ApiError } from "@/lib/api";
import { de, type HostRefusal } from "@/lib/de";
import { useEndGame, usePauseGame, useResumeGame } from "@/lib/queries/session";

/**
 * The bell and the emergency brake (H-10, E-04).
 *
 * Neither reports success: `game.paused`, `game.resumed` and `game.ended` come
 * back over the socket and the reducer applies them, which is also how every
 * other screen in the room finds out. The button only has to say when the
 * server refused — 409 `paused` / `not_running` / `not_paused`, which in
 * practice means two people pressed at once.
 *
 * Pausing is one click with no question: it is the most reversible thing on the
 * screen and the reason for it is usually that a bell just rang. Ending is not,
 * so it asks.
 */
export function HostControls() {
  const { state } = useGame();
  const pause = usePauseGame(state.gameId);
  const resume = useResumeGame(state.gameId);
  const end = useEndGame(state.gameId);

  const paused = !!state.pausedAt;
  const failure = pause.error ?? resume.error ?? end.error;

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3">
        {paused ? (
          <Button
            variant="default"
            onClick={() => resume.mutate()}
            disabled={resume.isPending}
          >
            <PlayIcon aria-hidden />
            {resume.isPending ? de.host.resuming : de.host.resume}
          </Button>
        ) : (
          <Button
            variant="outline"
            onClick={() => pause.mutate()}
            disabled={pause.isPending}
          >
            <PauseIcon aria-hidden />
            {pause.isPending ? de.host.pausing : de.host.pause}
          </Button>
        )}

        <ConfirmAction
          label={de.host.end}
          title={de.host.end}
          description={de.host.endConfirm}
          confirmLabel={de.host.end}
          onConfirm={() => end.mutate()}
          variant="ghost"
          size="default"
          pending={end.isPending}
        />
      </div>

      {failure ? (
        <Alert variant="destructive" className="mt-4">
          <AlertDescription>{controlFailure(failure)}</AlertDescription>
        </Alert>
      ) : null}
    </div>
  );
}

function controlFailure(error: unknown): string {
  if (error instanceof ApiError && error.status === 409 && error.reason) {
    const known = de.host.failed[error.reason as HostRefusal];
    if (known) return known;
  }
  return de.host.failedUnknown;
}
