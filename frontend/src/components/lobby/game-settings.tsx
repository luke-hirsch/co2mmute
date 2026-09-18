import { useGame } from "@/components/game/game-context";
import { de } from "@/lib/de";

/**
 * What this game was set up as: agents, rounds, budget, chat.
 *
 * Shared by the player's lobby and the host's, because it is the same four
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
      <Setting
        label={de.lobby.settings.chat}
        mono={false}
        value={
          state.chatEnabled ? de.lobby.settings.chatOn : de.lobby.settings.chatOff
        }
      />
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
