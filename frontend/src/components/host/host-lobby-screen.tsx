import { AddSeatDialog } from "@/components/host/add-seat-dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DepartureBoard } from "@/components/metro/departure-board";
import { GameSettings } from "@/components/lobby/game-settings";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import { SeatAdminList } from "@/components/host/seat-admin-list";
import { useGame } from "@/components/game/game-context";
import { de } from "@/lib/de";
import { playingSeats } from "@/lib/game/game-state";
import { useHostGame, useStartGame } from "@/lib/queries/session";

/**
 * The host's lobby: get the room in, then start.
 *
 * **This carries the start button, which nothing has had since F3.**
 * `currentScreen()` sends a host who has not started to `lobby`, and `lobby`
 * became the player's screen — which has no start, because players do not
 * start games. For one chunk a game could only be started by hand
 * (`PATCH api/game/<ID>/ {"is_active": true}`). Whatever else F4 is, it is
 * first of all that hole closing.
 *
 * The join QR is the other half of the screen, and it is why this one is not
 * `narrow`: it goes on a projector and the class scans it. It comes from
 * `GameSession.generate_qr_code()` — the image Django rendered when the game
 * was created — and needs a host session to read, which is exactly who is
 * looking.
 */
export function HostLobbyScreen() {
  const { state } = useGame();
  const game = useHostGame(state.gameId, true);
  const start = useStartGame(state.gameId);

  const players = playingSeats(state);
  const canStart = players.length > 0 && !state.endedAt;

  return (
    <Screen>
      <ScreenHeading
        title={state.gameName || de.host.title}
        lead={de.host.lobbyLead}
      />

      <div className="mb-12 grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] lg:items-start">
        <DepartureBoard
          label={de.code.gameId}
          footnote={de.lobby.seatsTaken(players.length, state.maxPlayers)}
        >
          <p className="font-mono text-5xl tracking-[0.3em] text-brandaccent uppercase sm:text-6xl">
            {state.gameId}
          </p>
          {game.data?.game_qr_code ? (
            <div className="mt-6">
              {/* A QR has to stay black on white to scan, whatever the board
                  around it is doing. */}
              <img
                src={game.data.game_qr_code}
                alt={de.join.idSubtitle}
                className="size-48 rounded-md bg-white p-2 sm:size-56"
              />
            </div>
          ) : null}
        </DepartureBoard>

        <section>
          <div className="mb-4 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-3">
            <h2 className="text-2xl font-semibold">{de.host.seats}</h2>
            <AddSeatDialog gameId={state.gameId} />
          </div>
          <SeatAdminList gameId={state.gameId} seats={state.seats} />
        </section>
      </div>

      <section className="mb-12">
        <h2 className="mb-4 text-2xl font-semibold">{de.lobby.settings.title}</h2>
        <GameSettings />
      </section>

      {start.error ? (
        <Alert variant="destructive" className="mb-6">
          <AlertDescription>{de.host.failedUnknown}</AlertDescription>
        </Alert>
      ) : null}

      <div className="flex flex-wrap items-center gap-4">
        <Button
          size="lg"
          onClick={() => start.mutate()}
          disabled={!canStart || start.isPending}
        >
          {start.isPending ? de.host.starting : de.host.start}
        </Button>
        {!canStart ? (
          <p className="text-sm text-muted-foreground">{de.host.startBlocked}</p>
        ) : null}
      </div>
    </Screen>
  );
}
