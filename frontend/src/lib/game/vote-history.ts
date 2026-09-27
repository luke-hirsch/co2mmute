/**
 * What the class changed between the rounds.
 *
 * The end screen has always promised _"Daran siehst du, was die Änderungen an
 * der Karte gebracht haben"_ over a list that never named a single change. The
 * ballot, the tally and the winner are recorded on the round as the vote
 * resolves (`GameRound.vote_result`) and never recomputed, because
 * `_tally_if_complete` counts the players still in the game — a re-tally weeks
 * later counts a smaller room than voted and can name a different winner than
 * the class actually saw.
 *
 * So nothing here recounts anything. It orders the rounds, fills in the options
 * nobody voted for — "niemand wollte den Radweg" is a finding, and an option
 * missing from `vote_counts` would simply vanish — and drops the one string the
 * payload cannot be trusted with.
 *
 * **A vote list is history, not a ballot.** The rule that explanation never goes
 * next to the vote (Lukas, 2026-09-22) does not bind here: the class has already
 * decided, and what they are reading is the consequence.
 */

import type { SummaryRoundTotals } from "@/lib/queries/summary";

export type VoteTallyRow = {
  /**
   * Null is the vote to leave the map as it is — and then `name` is null too.
   * The payload calls it `phases.LEAVE_AS_IS`, the English sentinel "Leave as
   * it is", which is not a version name and must never reach a German screen.
   */
  versionId: number | null;
  name: string | null;
  count: number;
  /** Only ever one row, and never any when the map stayed as it was. */
  won: boolean;
};

export type VoteEntry = {
  /** The round the vote came **after**, which is what makes the next one legible. */
  roundNumber: number;
  /** Null when the map stayed as it was: a tie, or the host ending one. */
  winnerName: string | null;
  winnerId: number | null;
  tie: boolean;
  /** The host cut a tie short rather than letting it resolve. */
  forced: boolean;
  /** How many seats voted at all. */
  votes: number;
  /** Every option on the ballot, most votes first. */
  tally: VoteTallyRow[];
};

export function voteHistory(
  rounds: readonly SummaryRoundTotals[],
): VoteEntry[] {
  const entries: VoteEntry[] = [];

  for (const round of rounds) {
    const vote = round.vote;
    if (!vote) continue;

    const counts = new Map<number | null, number>();
    for (const row of vote.vote_counts) {
      counts.set(row.version_id, (counts.get(row.version_id) ?? 0) + row.count);
    }

    const tally: VoteTallyRow[] = vote.options.map((option) => ({
      versionId: option.version_id,
      name: option.version_name,
      count: counts.get(option.version_id) ?? 0,
      won: vote.winning_version_id === option.version_id,
    }));

    // "So lassen" is not on the ballot as an option — it is what a seat picks
    // instead of one — so it only appears here if somebody chose it. It can
    // never win a name: a tie leaves the map alone without anything winning.
    const keepCount = counts.get(null);
    if (keepCount !== undefined) {
      tally.push({ versionId: null, name: null, count: keepCount, won: false });
    }

    tally.sort(
      (a, b) => b.count - a.count || (a.name ?? "").localeCompare(b.name ?? ""),
    );

    entries.push({
      roundNumber: round.round_number,
      winnerId: vote.winning_version_id,
      winnerName:
        vote.winning_version_id === null ? null : vote.winning_version_name,
      tie: vote.tie,
      forced: vote.forced,
      votes: tally.reduce((sum, row) => sum + row.count, 0),
      tally,
    });
  }

  return entries.sort((a, b) => a.roundNumber - b.roundNumber);
}
