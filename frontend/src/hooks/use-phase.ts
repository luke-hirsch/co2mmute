/**
 * The between-round phases, from this device's side.
 *
 * Four messages go up the socket (`game/consumers.py`): `player.stats_ack`,
 * `vote.open`, `vote.submit` and `stalemate.vote`, plus the host's
 * `stalemate.force_leave`. Everything that comes back — the phase itself, the
 * counts, the outcome — is already in the reducer, so this hook holds only the
 * one thing the protocol does not carry.
 *
 * ### What this device has already sent
 *
 * Nothing tells a client whether it has acked or voted. `stats.all_acked` says
 * only that *everyone* is through, `vote.recorded` is a one-shot broadcast, and
 * `game.state` on reconnect says neither. So a `votedSeatIds` in the game state
 * would be a field that is right until the socket drops and quietly wrong after
 * — worse than not having it. It lives here instead: per phase, cleared when
 * the phase or the round turns over, and gone on a reload.
 *
 * That leaves one honest gap, and the server closes it. A second ack is a
 * `get_or_create` no-op. A second vote is refused, and a refusal for a seat is
 * taken at its word: the seat is marked as having voted and the screen says so,
 * because that is what a refusal in this phase means and the screen must not go
 * on offering a ballot the server will not take.
 *
 * All of that is one state object keyed by the phase, and it is read *through*
 * the key rather than reset in an effect — an effect would leave one render
 * showing the previous phase's record, which on this screen is a ballot that
 * looks as though it has already been used.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useGame } from "@/components/game/game-context";
import { de } from "@/lib/de";

type PhaseRecord = {
  /** The round and phase this record belongs to. */
  epoch: string;
  /** This device has acked the stats. For the host that covers all its seats. */
  acked: boolean;
  /** Seats this device has voted for, and seats it has answered the tie for. */
  voted: string[];
  answered: string[];
  /** The last refusal, in German. */
  refused: string | null;
};

function emptyRecord(epoch: string): PhaseRecord {
  return { epoch, acked: false, voted: [], answered: [], refused: null };
}

export function usePhase() {
  const { state, send, lastError, clearError } = useGame();

  // The round *and* the phase: a revote after a tie re-opens `voting`, and
  // everyone owes a vote again.
  const epoch = `${state.currentRound}:${state.phase}`;
  const [record, setRecord] = useState<PhaseRecord>(() => emptyRecord(epoch));

  // Memoised as well as derived: the sets built from it are a `useEffect`
  // dependency in `useDesk`, and a fresh empty record per render would re-sync
  // the vote carousel on every render for nothing.
  const current = useMemo(
    () => (record.epoch === epoch ? record : emptyRecord(epoch)),
    [record, epoch],
  );

  /** The seat whose message is in flight, so a refusal can be attributed. */
  const pending = useRef<string | null>(null);

  /** Apply a change to the record for the phase that is current *now*. */
  const amend = useCallback(
    (change: (previous: PhaseRecord) => PhaseRecord) => {
      setRecord((previous) =>
        change(previous.epoch === epoch ? previous : emptyRecord(epoch)),
      );
    },
    [epoch],
  );

  useEffect(() => {
    if (!lastError) return;
    const seat = pending.current;
    pending.current = null;
    // An effect, because this *is* an external system reporting back: the
    // socket refused something this device sent, and the message reaches the
    // hook as a context value rather than as a callback.
    amend((previous) => {
      // A refusal for a named seat is "already voted" in every case a player
      // can produce; the others (wrong phase, a version not on the ballot) are
      // bugs, and the screen would have moved on for the first of them anyway.
      const refused = seat ? de.vote.already : de.vote.failed;
      if (!seat) return { ...previous, refused };
      const key = state.phase === "stalemate" ? "answered" : "voted";
      if (previous[key].includes(seat)) return { ...previous, refused };
      return { ...previous, refused, [key]: [...previous[key], seat] };
    });
    clearError();
  }, [lastError, clearError, amend, state.phase]);

  const dispatch = useCallback(
    (message: object, seatId: string | null): boolean => {
      pending.current = seatId;
      const sent = send(message);
      if (!sent) {
        pending.current = null;
        amend((previous) => ({ ...previous, refused: de.errors.network }));
      }
      return sent;
    },
    [send, amend],
  );

  const ackStats = useCallback(() => {
    if (!dispatch({ type: "player.stats_ack" }, null)) return;
    amend((previous) => ({ ...previous, acked: true, refused: null }));
  }, [dispatch, amend]);

  const openVote = useCallback(() => {
    dispatch({ type: "vote.open" }, null);
  }, [dispatch]);

  /** `versionId` null is "so lassen" — the backend's own "leave as it is". */
  const vote = useCallback(
    (seatId: string, versionId: number | null) => {
      const message = {
        type: "vote.submit",
        player_id: seatId,
        version_id: versionId,
      };
      if (!dispatch(message, seatId)) return;
      amend((previous) => ({
        ...previous,
        refused: null,
        voted: [...previous.voted, seatId],
      }));
    },
    [dispatch, amend],
  );

  const answerTie = useCallback(
    (seatId: string, wantRevote: boolean) => {
      const message = {
        type: "stalemate.vote",
        player_id: seatId,
        want_revote: wantRevote,
      };
      if (!dispatch(message, seatId)) return;
      amend((previous) => ({
        ...previous,
        refused: null,
        answered: [...previous.answered, seatId],
      }));
    },
    [dispatch, amend],
  );

  const forceLeaveAsIs = useCallback(() => {
    dispatch({ type: "stalemate.force_leave" }, null);
  }, [dispatch]);

  const voted = useMemo(() => new Set(current.voted), [current.voted]);
  const answered = useMemo(() => new Set(current.answered), [current.answered]);

  return {
    epoch,
    acked: current.acked,
    voted,
    answered,
    hasVoted: (seatId: string | null) => !!seatId && voted.has(seatId),
    hasAnswered: (seatId: string | null) => !!seatId && answered.has(seatId),
    refused: current.refused,
    ackStats,
    openVote,
    vote,
    answerTie,
    forceLeaveAsIs,
  };
}
