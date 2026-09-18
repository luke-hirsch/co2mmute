import { Co2Bar } from "@/components/metro/co2-bar";
import { useGame } from "@/components/game/game-context";
import { de } from "@/lib/de";
import { moveProgress } from "@/lib/game/game-state";

/**
 * Where the game stands, above every turn: which round, how much of the CO₂
 * budget is gone, and how many seats have already submitted.
 *
 * The counts come from `moveProgress`, which is the frontend's copy of the one
 * counting rule: seats that play, host row excluded, seats played at the host
 * machine included — on both sides of the comparison. Spelling it out here
 * again is how the backend ended up with the rule in nine places.
 *
 * The round number comes from the reducer, so it is whatever `round.started`
 * last said. That event never arrived before split part 1, which is the "runden
 * counter" bug (2.4 / R-09); there is nothing to fix here beyond reading the
 * right field.
 */
export function RoundHeader() {
  const { state } = useGame();
  const { done, total } = moveProgress(state);

  return (
    <header className="mb-10">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
        <h1 className="text-3xl font-medium sm:text-4xl">
          {state.maxRounds > 0
            ? de.round.of(state.currentRound, state.maxRounds)
            : de.round.label(state.currentRound)}
        </h1>
        <p className="font-mono text-sm tabular-nums text-muted-foreground">
          {de.round.submittedOf(done, total)}
        </p>
      </div>

      <Co2Bar
        usedG={state.totalEmissionsG}
        maxG={state.maxCo2LevelG}
        className="mt-6"
      />
    </header>
  );
}
