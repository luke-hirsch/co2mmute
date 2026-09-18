import { useNavigate } from "@tanstack/react-router";

import { ConfirmAction } from "@/components/layout/confirm-action";
import { DepartureBoard } from "@/components/metro/departure-board";
import { GameSettings } from "@/components/lobby/game-settings";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import { SeatList } from "@/components/lobby/seat-list";
import { useGame } from "@/components/game/game-context";
import { de } from "@/lib/de";
import { playingSeats } from "@/lib/game/game-state";
import { useRemoveSeat } from "@/lib/queries/seats";

/**
 * Waiting for the host to start.
 *
 * Not a route of its own since F3: `/app/game/<ID>` renders whichever screen
 * `currentScreen()` names, so the lobby turns into the round by itself when
 * `game.started` arrives — no link to press, and no way to sit in a lobby for
 * a game that is already running.
 *
 * Since F2 this screen holds no connection and no state of its own: it reads
 * the game from the provider in the layout above it. Everything it used to do
 * about loading, revocation and a dropped socket now happens once, in
 * `GameFrame`, for every screen in the game.
 *
 * The host does not see this screen — `HostLobbyScreen` takes its place (F4).
 */
export function LobbyScreen() {
  const navigate = useNavigate();
  const { state, seatId } = useGame();
  const leave = useRemoveSeat(state.gameId);

  const players = playingSeats(state);

  /**
   * L-12. The same `DELETE` the host uses to remove somebody, only aimed at
   * one's own seat — the backend tells the two apart by the cookie and drops
   * both cookies on the way out, so there is nothing to clean up here.
   *
   * `mutateAsync` in a plain handler rather than `mutate(…, { onSettled })`:
   * React Query drops those callbacks when the component unmounts first, and
   * this one always does. Leaving revokes the seat, `player.revoked` comes back
   * over the socket, and `GameFrame` swaps this screen for the revoked notice
   * before the request has settled — so the navigation never ran and the player
   * was left reading "Du hast das Spiel verlassen" with a button to press.
   */
  async function leaveGame() {
    if (!seatId) return;
    try {
      await leave.mutateAsync(seatId);
    } finally {
      // Either way this browser has no seat any more, so the join screen is
      // the only honest place to be. A failure that leaves the row in place
      // still ends with a lobby that 403s, which says the same thing.
      await navigate({ to: "/join" });
    }
  }

  return (
    <Screen narrow>
      <ScreenHeading
        title={state.gameName || de.lobby.title}
        lead={
          state.endedAt
            ? de.lobby.ended
            : state.isActive
              ? de.lobby.started
              : de.lobby.hostStarts
        }
      />

      <DepartureBoard
        label={de.code.gameId}
        footnote={de.lobby.seatsTaken(players.length, state.maxPlayers)}
        className="mb-12"
      >
        <p className="font-mono text-3xl tracking-[0.3em] text-brandaccent uppercase">
          {state.gameId}
        </p>
      </DepartureBoard>

      <section className="mb-12">
        <h2 className="mb-4 text-2xl font-semibold">{de.lobby.players}</h2>
        <SeatList seats={state.seats} youId={seatId} />
      </section>

      <section className="mb-12">
        <h2 className="mb-4 text-2xl font-semibold">
          {de.lobby.settings.title}
        </h2>
        <GameSettings />
      </section>

      {seatId ? (
        <ConfirmAction
          label={de.lobby.leave}
          title={de.lobby.leave}
          description={de.lobby.leaveConfirm}
          confirmLabel={de.lobby.leave}
          onConfirm={() => void leaveGame()}
          variant="ghost"
          size="default"
          pending={leave.isPending}
        />
      ) : null}
    </Screen>
  );
}
