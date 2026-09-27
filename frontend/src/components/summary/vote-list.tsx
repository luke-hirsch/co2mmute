import { Track, TrackStop } from "@/components/metro/track";
import { de } from "@/lib/de";
import type { VoteEntry } from "@/lib/game/vote-history";

/**
 * What the class changed between the rounds (E-10).
 *
 * The screen above it has always promised _"Daran siehst du, was die Änderungen
 * an der Karte gebracht haben"_ over a list that never named a single change, so
 * a round getting cheaper was a mystery whatever caused it. With the votes listed,
 * "Nach Runde 2: Busspur Turmstraße — 3 von 4 Stimmen" explains the next row by
 * itself.
 *
 * Drawn as a line with stops, like every other sequence in this interface and
 * like the arc directly above it — the two are the same rounds read twice, once
 * for what they cost and once for what the class decided about them.
 *
 * **A vote list is history, not a ballot.** The rule that explanation never goes
 * beside the vote does not bind here: the class has already decided, and what
 * they are reading now is the consequence.
 *
 * Nothing is recounted. `GameRound.vote_result` was written as the vote resolved,
 * because `_tally_if_complete` counts the players still in the game — re-tallying
 * at the summary counts a smaller room than voted and can name a different winner
 * than the class saw.
 */
export function VoteList({ entries }: { entries: VoteEntry[] }) {
  return (
    <section>
      <h2 className="text-2xl font-semibold">{de.summary.votesTitle}</h2>
      <p className="mt-4 max-w-(--measure-body) text-muted-foreground">
        {de.summary.votesLead}
      </p>

      {entries.length === 0 ? (
        // A single-version map, or `map_updates` off. Both are normal, and the
        // shipped map has exactly one version.
        <p className="mt-8 max-w-(--measure-body) text-muted-foreground">
          {de.summary.votesNone}
        </p>
      ) : (
        <Track className="mt-10">
          {entries.map((entry) => (
            <TrackStop
              key={entry.roundNumber}
              // A vote that changed the map is a filled stop: something happened
              // here. A tie is hollow — the same language the round screens speak.
              state={entry.winnerName ? "current" : "done"}
              title={
                <span className="flex flex-wrap items-baseline gap-x-3">
                  <span>{de.summary.afterRound(entry.roundNumber)}</span>
                  <span className="font-normal text-muted-foreground">
                    {entry.winnerName
                      ? de.summary.voteWon(entry.winnerName)
                      : de.summary.voteKept}
                  </span>
                </span>
              }
            >
              <dl className="text-sm text-muted-foreground">
                {entry.tally.map((row) => (
                  <div
                    key={row.versionId ?? "keep"}
                    className="flex items-baseline justify-between gap-3 py-0.5"
                  >
                    <dt className={row.won ? "text-foreground" : undefined}>
                      {/* A null name is the vote to leave the map alone. The
                          payload's own string for it is the backend's English
                          sentinel, so the German comes from here. */}
                      {row.name ?? de.summary.voteKeepRow}
                    </dt>
                    <dd className="font-mono tabular-nums">
                      {de.summary.voteCount(row.count)}
                    </dd>
                  </div>
                ))}
              </dl>

              {/* Why the map stayed put, when it did. Both can be true at once:
                  the host ends a tie. */}
              {entry.tie || entry.forced ? (
                <p className="mt-2 text-sm text-muted-foreground">
                  {entry.forced ? de.summary.voteForced : de.summary.voteTie}
                </p>
              ) : null}
            </TrackStop>
          ))}
        </Track>
      )}
    </section>
  );
}
