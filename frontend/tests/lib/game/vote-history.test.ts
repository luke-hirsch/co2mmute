import { describe, expect, it } from "vitest";

import { voteHistory } from "@/lib/game/vote-history";
import type { SummaryRoundTotals, SummaryVote } from "@/lib/queries/summary";

/**
 * What the class changed between the rounds, read back off the summary.
 *
 * The end screen has always promised "Daran siehst du, was die Änderungen an
 * der Karte gebracht haben" over a list that never named a single change. The
 * ballot, the tally and the winner are now recorded on the round as they happen
 * (`GameRound.vote_result`) — never re-derived, because `_tally_if_complete`
 * counts the players still in the game and a re-tally weeks later can hand back
 * a different winner than the class saw.
 *
 * So this module does no arithmetic on the outcome. It orders the rounds, fills
 * in the options nobody voted for, and keeps the one thing the payload cannot
 * say: "so lassen" arrives as the backend's English `LEAVE_AS_IS`, so the row
 * for it carries no name at all and the screen supplies the German one.
 */

function round(
  roundNumber: number,
  vote: SummaryVote | null,
): SummaryRoundTotals {
  return {
    round_number: roundNumber,
    co2_kg: 100,
    cost_eur: 10,
    network_co2_kg: 0,
    network_cost_eur: 0,
    unridden_co2_kg: 0,
    unridden_cost_eur: 0,
    agent_count: 4,
    co2_g_per_person: 250,
    cost_eur_per_person: 1,
    simulation_used: true,
    vote,
  };
}

const busspurWon: SummaryVote = {
  options: [
    { version_id: 7, version_name: "Busspur Turmstraße" },
    { version_id: 8, version_name: "Radweg am Kanal" },
  ],
  vote_counts: [
    { version_id: 7, version_name: "Busspur Turmstraße", count: 3 },
    { version_id: 8, version_name: "Radweg am Kanal", count: 1 },
  ],
  winning_version_id: 7,
  winning_version_name: "Busspur Turmstraße",
  tie: false,
  stalemate_count: 0,
  forced: false,
};

describe("voteHistory", () => {
  it("names the round the vote followed, not the round it changed", () => {
    // "Nach Runde 2" is what makes the next row of numbers legible; a vote
    // labelled with the round it took effect in reads as its cause.
    const entries = voteHistory([round(1, null), round(2, busspurWon)]);

    expect(entries).toHaveLength(1);
    expect(entries[0].roundNumber).toBe(2);
  });

  it("skips rounds that held no vote at all", () => {
    // A single-version map, `map_updates` off, the last round of the game, and
    // every round played before the field existed. None of them is a tie.
    expect(voteHistory([round(1, null), round(2, null)])).toEqual([]);
  });

  it("carries the winner and how many votes it took", () => {
    const [entry] = voteHistory([round(1, busspurWon)]);

    expect(entry.winnerName).toBe("Busspur Turmstraße");
    expect(entry.votes).toBe(4);
    expect(entry.tie).toBe(false);
    expect(entry.forced).toBe(false);
  });

  it("orders the tally by votes, most first", () => {
    const [entry] = voteHistory([round(1, busspurWon)]);

    expect(entry.tally.map((row) => row.count)).toEqual([3, 1]);
    expect(entry.tally.map((row) => row.won)).toEqual([true, false]);
  });

  it("lists an option nobody voted for, at zero", () => {
    // The ballot is the interesting part: "niemand wollte den Radweg" is a
    // finding, and an option missing from `vote_counts` would simply vanish.
    const [entry] = voteHistory([
      round(1, {
        ...busspurWon,
        vote_counts: [
          { version_id: 7, version_name: "Busspur Turmstraße", count: 4 },
        ],
      }),
    ]);

    expect(entry.tally).toHaveLength(2);
    expect(entry.tally[1]).toMatchObject({ versionId: 8, count: 0, won: false });
  });

  it("gives the 'so lassen' row no name of its own", () => {
    // `phases.LEAVE_AS_IS` is the English string "Leave as it is". It is a
    // sentinel, not a version name, and it must never reach a German screen.
    const [entry] = voteHistory([
      round(1, {
        ...busspurWon,
        vote_counts: [
          { version_id: 7, version_name: "Busspur Turmstraße", count: 2 },
          { version_id: null, version_name: "Leave as it is", count: 3 },
        ],
        winning_version_id: 7,
      }),
    ]);

    const keep = entry.tally.find((row) => row.versionId === null);
    expect(keep).toBeDefined();
    expect(keep?.name).toBeNull();
    expect(keep?.count).toBe(3);
    // And it never wins a name either: the map simply stayed as it was.
    expect(entry.tally.every((row) => row.name !== "Leave as it is")).toBe(true);
  });

  it("reports a tie as the map staying put, with nobody having won", () => {
    const [entry] = voteHistory([
      round(1, {
        options: [
          { version_id: 7, version_name: "Busspur" },
          { version_id: 8, version_name: "Radweg" },
        ],
        vote_counts: [
          { version_id: 7, version_name: "Busspur", count: 2 },
          { version_id: 8, version_name: "Radweg", count: 2 },
        ],
        winning_version_id: null,
        winning_version_name: "Leave as it is",
        tie: true,
        stalemate_count: 1,
        forced: false,
      }),
    ]);

    expect(entry.winnerName).toBeNull();
    expect(entry.tie).toBe(true);
    expect(entry.tally.every((row) => !row.won)).toBe(true);
  });

  it("says when the host cut the tie short", () => {
    const [entry] = voteHistory([
      round(1, {
        ...busspurWon,
        winning_version_id: null,
        winning_version_name: "Leave as it is",
        tie: true,
        forced: true,
      }),
    ]);

    expect(entry.forced).toBe(true);
    expect(entry.winnerName).toBeNull();
  });

  it("orders the entries by round, whatever order the payload had", () => {
    const entries = voteHistory([round(3, busspurWon), round(1, busspurWon)]);

    expect(entries.map((entry) => entry.roundNumber)).toEqual([1, 3]);
  });

  it("has nothing to say about a game with no rounds", () => {
    expect(voteHistory([])).toEqual([]);
  });
});
