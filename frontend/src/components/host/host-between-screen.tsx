import { useMemo } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Ballot } from "@/components/between/ballot";
import { Button } from "@/components/ui/button";
import { ConfirmAction } from "@/components/layout/confirm-action";
import { Curtain } from "@/components/host/curtain";
import { HostControls } from "@/components/host/host-controls";
import { MapChangeCard } from "@/components/between/map-change-card";
import { Screen, ScreenHeading } from "@/components/layout/screen";
import { StatsPanel } from "@/components/between/stats-panel";
import { de } from "@/lib/de";
import { hostControlledSeats } from "@/lib/game/game-state";
import { useDesk } from "@/hooks/use-desk";
import { useGame } from "@/components/game/game-context";
import { usePhase } from "@/hooks/use-phase";

/**
 * Between two rounds, at the desk.
 *
 * The host is not in the game, so they have no ack and no vote of their own —
 * what they have is everyone else's. Two different shapes, because the backend
 * treats them differently and for a good reason:
 *
 * - **the stats ack goes out once for every seat at this machine.**
 *   `phases.ack_host_seats` acks the lot, because they are all looking at this
 *   one screen and there is nothing per-seat about having read a table;
 * - **the vote goes round the desk, one seat at a time, behind the curtain.**
 *   A vote *is* per seat — it is what a tie is made of — and the machine is on
 *   a projector, so the same rule as H-04 applies: the room must not see the
 *   switch, and must not see the last person's ballot while the next one sits
 *   down.
 *
 * That carousel is F4's, not a second one: `use-desk.ts` takes the set of seats
 * that are finished, and here that set is "has voted" instead of "has moved".
 *
 * **What the host cannot see is who is still missing.** No event names the seats
 * that have acked or voted, only how many — so when a phase hangs on one
 * forgotten phone, the screen says so and points at the one thing that does
 * work: removing the seat runs `phases.recheck` and the phase completes without
 * it.
 */
export function HostBetweenScreen() {
  const { state } = useGame();

  switch (state.phase) {
    case "stats":
      return <HostStats />;
    case "discussion":
      return <HostDiscussion />;
    case "voting":
      return <HostVote />;
    case "stalemate":
      return <HostTie />;
    case "none":
      return null;
  }
}

/** The table, and one "Weiter" for every seat at this machine. */
function HostStats() {
  const { state } = useGame();
  const phase = usePhase();
  const seats = hostControlledSeats(state);

  return (
    <Screen>
      <ScreenHeading
        title={de.between.statsTitle(
          state.lastRound?.roundNumber ?? state.currentRound,
        )}
        lead={de.between.statsLead}
      />

      {state.lastRound ? (
        <StatsPanel
          round={state.lastRound}
          seatId={null}
          totalEmissionsG={state.totalEmissionsG}
          maxCo2LevelG={state.maxCo2LevelG}
        />
      ) : null}

      <div className="mt-12">
        {seats.length === 0 ? (
          // Nothing to ack: every seat is on a phone and acks for itself.
          <p className="max-w-(--measure-body) text-muted-foreground">
            {de.host.waitingForPhones}
          </p>
        ) : phase.acked ? (
          <p className="font-medium">{de.host.ackedAll}</p>
        ) : (
          <Button size="lg" onClick={phase.ackStats} disabled={!!state.pausedAt}>
            {de.host.ackAll}
          </Button>
        )}
        <p className="mt-6 max-w-(--measure-body) text-sm text-muted-foreground">
          {de.host.stuckHint}
        </p>
      </div>

      <div className="mt-12">
        <HostControls />
      </div>
    </Screen>
  );
}

/** The options, and the one button that ends the discussion (Z-04). */
function HostDiscussion() {
  const { state } = useGame();
  const phase = usePhase();

  return (
    <Screen>
      <ScreenHeading
        title={de.between.discussionTitle}
        lead={de.between.discussionLead}
      />

      {state.voteOptions.length === 0 ? (
        <p className="max-w-(--measure-body) text-muted-foreground">
          {de.between.noOptions}
        </p>
      ) : (
        <div className="grid gap-10 sm:grid-cols-2">
          {state.voteOptions.map((option) => (
            <MapChangeCard key={option.id} option={option} />
          ))}
        </div>
      )}

      <div className="mt-12">
        <Button
          size="lg"
          onClick={phase.openVote}
          disabled={state.voteOptions.length === 0 || !!state.pausedAt}
        >
          {de.vote.open}
        </Button>
        {phase.refused ? (
          <Alert className="mt-6">
            <AlertDescription>{phase.refused}</AlertDescription>
          </Alert>
        ) : null}
      </div>

      <div className="mt-12">
        <HostControls />
      </div>
    </Screen>
  );
}

/**
 * The vote, seat by seat (Z-05, H-09).
 *
 * `useDesk` is handed "has voted" as the done-set, so a seat that has cast its
 * vote drops out of the carousel exactly the way a seat that has submitted its
 * move does during a round — and the curtain comes back for the next one
 * without anybody pressing anything.
 */
function HostVote() {
  const { state } = useGame();
  const phase = usePhase();
  const desk = useDesk({ done: phase.voted, epoch: phase.epoch });

  if (desk.mode === "curtain" && desk.openSeat) {
    return (
      <Curtain
        name={desk.openSeat.name}
        onReady={desk.ready}
        onCancel={desk.leave}
      />
    );
  }

  if (desk.mode === "playing" && desk.openSeat && desk.openSeatId) {
    const seatId = desk.openSeatId;
    return (
      <Screen>
        <ScreenHeading
          title={de.vote.title}
          lead={de.host.playingSeat(desk.openSeat.name)}
        />
        <Ballot
          options={state.voteOptions}
          onPick={(versionId) => {
            phase.vote(seatId, versionId);
            desk.leave();
          }}
          disabled={!!state.pausedAt}
        />
        <div className="mt-10">
          <Button variant="ghost" onClick={desk.leave}>
            {de.host.back}
          </Button>
        </div>
      </Screen>
    );
  }

  return (
    <Screen>
      <ScreenHeading title={de.vote.title} lead={de.host.voteLead} />

      {phase.refused ? (
        <Alert className="mb-10">
          <AlertDescription>{phase.refused}</AlertDescription>
        </Alert>
      ) : null}

      <SeatQueue
        label={de.host.voteSeat}
        seats={desk.seats.map((seat) => ({
          id: seat.player_id,
          name: seat.name,
          done: phase.voted.has(seat.player_id),
        }))}
        onPick={desk.pick}
        disabled={!!state.pausedAt}
        emptyLine={de.host.waitingForPhones}
        doneLine={de.host.votedSeats}
      />

      {state.votes ? (
        <p className="mt-10 font-mono text-sm tabular-nums text-muted-foreground">
          {de.vote.progress(state.votes.cast, state.votes.needed)}
        </p>
      ) : null}

      <p className="mt-6 max-w-(--measure-body) text-sm text-muted-foreground">
        {de.host.stuckHint}
      </p>

      <div className="mt-12">
        <HostControls />
      </div>
    </Screen>
  );
}

/**
 * The tie, seat by seat, plus the way to end it (Z-09).
 *
 * No curtain here: the answer is one of two buttons and carries no route, no
 * map and nothing anyone could copy off the projector — the curtain exists to
 * hide a *choice being made*, and this one is a show of hands.
 */
function HostTie() {
  const { state } = useGame();
  const phase = usePhase();
  const seats = hostControlledSeats(state);

  const outstanding = useMemo(
    () => seats.filter((seat) => !phase.answered.has(seat.player_id)),
    [seats, phase.answered],
  );

  return (
    <Screen>
      <ScreenHeading
        title={de.vote.tieTitle}
        lead={
          <>
            {de.vote.tieLead} {de.vote.tieLast}
          </>
        }
      />

      {phase.refused ? (
        <Alert className="mb-10">
          <AlertDescription>{phase.refused}</AlertDescription>
        </Alert>
      ) : null}

      {seats.length === 0 ? (
        <p className="max-w-(--measure-body) text-muted-foreground">
          {de.host.waitingForPhones}
        </p>
      ) : outstanding.length === 0 ? (
        <p className="font-medium">{de.vote.tieAnswered}</p>
      ) : (
        <ul className="divide-y divide-border border-y border-border">
          {outstanding.map((seat) => (
            <li
              key={seat.player_id}
              className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 py-4"
            >
              <span className="font-medium">{seat.name}</span>
              <span className="flex flex-wrap gap-3">
                <Button
                  size="sm"
                  onClick={() => phase.answerTie(seat.player_id, true)}
                  disabled={!!state.pausedAt}
                >
                  {de.vote.revote}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => phase.answerTie(seat.player_id, false)}
                  disabled={!!state.pausedAt}
                >
                  {de.vote.leaveAsIs}
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}

      {state.stalemate ? (
        <p className="mt-10 font-mono text-sm tabular-nums text-muted-foreground">
          {de.vote.tieProgress(state.stalemate.cast, state.stalemate.needed)}
        </p>
      ) : null}

      <div className="mt-12 flex flex-wrap items-center gap-4">
        <ConfirmAction
          label={de.vote.forceLeave}
          title={de.vote.forceLeave}
          description={de.vote.forceLeaveConfirm}
          confirmLabel={de.vote.forceLeave}
          onConfirm={phase.forceLeaveAsIs}
          variant="outline"
          size="default"
        />
      </div>

      <div className="mt-12">
        <HostControls />
      </div>
    </Screen>
  );
}

/**
 * The seats at this machine, as a queue of things still to do.
 *
 * Deliberately not `SeatAdminList` (F4): that one is about a seat's
 * administration — take over, remove, hand on a code — and between rounds the
 * only question is whether this seat has answered yet.
 */
function SeatQueue({
  seats,
  label,
  onPick,
  disabled,
  emptyLine,
  doneLine,
}: {
  seats: { id: string; name: string; done: boolean }[];
  label: string;
  onPick: (seatId: string) => void;
  disabled: boolean;
  emptyLine: string;
  doneLine: string;
}) {
  if (seats.length === 0) {
    return (
      <p className="max-w-(--measure-body) text-muted-foreground">{emptyLine}</p>
    );
  }

  const outstanding = seats.filter((seat) => !seat.done);
  if (outstanding.length === 0) {
    return <p className="font-medium">{doneLine}</p>;
  }

  return (
    <ul className="divide-y divide-border border-y border-border">
      {outstanding.map((seat) => (
        <li
          key={seat.id}
          className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 py-4"
        >
          <span className="font-medium">{seat.name}</span>
          <Button size="sm" onClick={() => onPick(seat.id)} disabled={disabled}>
            {label}
          </Button>
        </li>
      ))}
    </ul>
  );
}
