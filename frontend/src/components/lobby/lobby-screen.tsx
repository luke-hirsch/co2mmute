import { useNavigate } from "@tanstack/react-router";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DepartureBoard } from "@/components/metro/departure-board";
import { PauseBanner } from "@/components/metro/pause-banner";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import { SeatList } from "@/components/lobby/seat-list";
import { useLobbyChannel } from "@/hooks/use-lobby-channel";
import { ApiError } from "@/lib/api";
import { de } from "@/lib/de";
import { playingSeats } from "@/lib/game/lobby-state";
import { seatId, useIdentity } from "@/lib/queries/identity";

/**
 * `/app/game/<ID>/lobby` — waiting for the host to start.
 *
 * The screen itself is thin on purpose. Everything that could go wrong about
 * *state* was decided in `use-lobby-channel` and `lobby-state`; what is left
 * here is which of four situations to render: revoked, ended, started, waiting.
 *
 * The identity call does double duty. It says which row is "du", and asking it
 * at all re-issues both player cookies (`WhoAmIView._renew_cookies`), which is
 * what lets a phone that sat locked through a lesson break come back to its
 * seat instead of to the join screen.
 */
export function LobbyScreen({ gameId }: { gameId: string }) {
  const navigate = useNavigate();
  const { state, connection, isLoading, error } = useLobbyChannel(gameId);
  const identity = useIdentity(gameId);
  const youId = seatId(identity.data);

  // This device's seat is gone. Nothing below is true any more, and the socket
  // has already been closed with 4403 — so this is a full stop, not a banner.
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

  // 403 from the snapshot: this browser has no valid game cookie. Sending them
  // to the join screen is the only useful answer.
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
            void navigate({ to: "/join/$gameId", params: { gameId } })
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

      {state.pausedAt ? <PauseBanner className="mb-8" /> : null}

      {/* The game started while this screen was open. F2 turns this into a
          phase of one route; until then it is an honest link rather than a
          silent redirect, so nobody loses a half-typed anything. */}
      {state.isActive && !state.endedAt ? (
        <Button
          className="mb-8 w-full sm:w-auto"
          onClick={() => void navigate({ to: "/game/$gameId", params: { gameId } })}
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
        <SeatList seats={state.seats} youId={youId} />
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

      {/* Reconnecting is normal on a school wifi and not worth an alert; it is
          worth saying, because the roster stops moving while it happens. */}
      {connection !== "open" && !isLoading ? (
        <p className="mt-12 text-sm text-muted-foreground">
          {de.lobby.connectionLost}
        </p>
      ) : null}
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
