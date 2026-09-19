import { useGame } from "@/components/game/game-context";
import { de } from "@/lib/de";

/**
 * What this game was set up as: agents, rounds and the CO2 budget.
 *
 * Shared by the player's lobby and the host's, because it is the same three
 * numbers and they are read off the same snapshot. The host sees them for the
 * same reason the players do — it is the last chance to notice that the CO₂
 * budget is wrong before a round is played on it.
 */
export function GameSettings() {
  const { state } = useGame();

  return (
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
      {/*
        No chat row. The chat died with the legacy screen in F5 and does not
        come back until R-13 / C-05, but `chat_enabled` is still shipped in the
        lobby snapshot — so this row went on promising "Chat — an" for a
        feature with no way to reach it. The setting itself stays in the state
        and in the backend; it is only the promise that goes.
      */}
    </dl>
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
