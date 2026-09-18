import { useNavigate } from "@tanstack/react-router";

import { Button } from "@/components/ui/button";
import { DepartureBoard } from "@/components/metro/departure-board";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import { SeatList } from "@/components/lobby/seat-list";
import { useGame } from "@/components/game/game-context";
import { de } from "@/lib/de";
import { playingSeats } from "@/lib/game/game-state";

/**
 * `/app/game/<ID>/lobby` — waiting for the host to start.
 *
 * Since F2 this screen holds no connection and no state of its own: it reads
 * the game from the provider in the layout above it. Everything it used to do
 * about loading, revocation and a dropped socket now happens once, in
 * `GameFrame`, for every screen in the game.
 */
export function LobbyScreen() {
  const navigate = useNavigate();
  const { state, seatId } = useGame();

  const players = playingSeats(state);

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

      {/* The game started while this screen was open. F3 folds this into one
          route driven by `currentScreen()`; until the round screen exists it is
          an honest link rather than a silent redirect onto the legacy screen. */}
      {state.isActive && !state.endedAt ? (
        <Button
          className="mb-8 w-full sm:w-auto"
          onClick={() =>
            void navigate({
              to: "/game/$gameId",
              params: { gameId: state.gameId },
            })
          }
        >
          {de.lobby.toGame}
        </Button>
      ) : null}

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

      <section>
        <h2 className="mb-4 text-2xl font-semibold">
          {de.lobby.settings.title}
        </h2>
        <dl className="grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2">
          <Setting
            label={de.lobby.settings.agentsPerPlayer}
            value={state.agentPerPlayer}
          />
          <Setting
            label={de.lobby.settings.maxRounds}
            value={de.lobby.roundsCount(state.maxRounds)}
          />
          <Setting
            label={de.lobby.settings.co2Budget}
            value={de.lobby.co2Kg(state.maxCo2LevelKg)}
          />
          <Setting
            label={de.lobby.settings.chat}
            mono={false}
            value={
              state.chatEnabled
                ? de.lobby.settings.chatOn
                : de.lobby.settings.chatOff
            }
          />
        </dl>
      </section>
    </Screen>
  );
}

/**
 * `mono` defaults to true because most of these are numbers, and mono is what
 * the rulebook reserves for ids, codes and numerals. A word like "an" is none
 * of those, so it opts out rather than pretending to be a figure.
 */
function Setting({
  label,
  value,
  mono = true,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="border-t border-border pt-3">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className={mono ? "mt-1 font-mono" : "mt-1"}>{value}</dd>
    </div>
  );
}
