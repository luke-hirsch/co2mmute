import { useState, useMemo } from "react";
import { useGameSummary } from "../../hooks/gameHooks";
import type { PlayerSummary } from "../../hooks/gameHooks";
import Loading from "../Loading";

interface GameSummaryProps {
  gameId: string;
  playerId?: string;
}

type SummaryTab = "time" | "co2" | "cost";

const TABS: { id: SummaryTab; label: string; description: string }[] = [
  { id: "time", label: "Travel Time", description: "Shortest total commute wins" },
  { id: "co2", label: "CO2 Emissions", description: "Smallest carbon footprint wins" },
  { id: "cost", label: "Cost", description: "Lowest spending wins" },
];

const RANK_COLORS = [
  "from-yellow-400 to-amber-500", // 1st - gold
  "from-gray-300 to-gray-400",    // 2nd - silver
  "from-orange-400 to-orange-600", // 3rd - bronze
];

const MODE_DISPLAY: Record<string, { emoji: string; label: string }> = {
  car: { emoji: "🚗", label: "Car" },
  public: { emoji: "🚌", label: "Transit" },
  bus: { emoji: "🚌", label: "Bus" },
  train: { emoji: "🚆", label: "Train" },
  bike: { emoji: "🚴", label: "Bike" },
  walk: { emoji: "🚶", label: "Walk" },
};

function formatTime(minutes: number): string {
  if (minutes < 60) return `${Math.round(minutes)} min`;
  const hours = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  return `${hours}h ${mins}m`;
}

function getPlayerValue(player: PlayerSummary, tab: SummaryTab): number {
  switch (tab) {
    case "time": return player.total_time_min;
    case "co2": return player.total_co2_kg;
    case "cost": return player.total_cost_eur;
  }
}

function getRoundValue(round: PlayerSummary["rounds"][0], tab: SummaryTab): number {
  switch (tab) {
    case "time": return round.time_min;
    case "co2": return round.co2_kg;
    case "cost": return round.cost_eur;
  }
}

function formatValue(value: number, tab: SummaryTab): string {
  switch (tab) {
    case "time": return formatTime(value);
    case "co2": return `${value.toFixed(1)} kg`;
    case "cost": return `${value.toFixed(2)} EUR`;
  }
}

function formatUnit(tab: SummaryTab): string {
  switch (tab) {
    case "time": return "min";
    case "co2": return "kg CO2";
    case "cost": return "EUR";
  }
}

export default function GameSummary({ gameId, playerId }: GameSummaryProps) {
  const { data: summary, isLoading, error } = useGameSummary(gameId);
  const [activeTab, setActiveTab] = useState<SummaryTab>("co2");

  // Sort players by the active tab metric (ascending = winner)
  const rankedPlayers = useMemo(() => {
    if (!summary) return [];
    return [...summary.players].sort(
      (a, b) => getPlayerValue(a, activeTab) - getPlayerValue(b, activeTab)
    );
  }, [summary, activeTab]);

  // Find the max round value across all players for bar scaling
  const maxRoundValue = useMemo(() => {
    if (!summary) return 1;
    let max = 0;
    for (const player of summary.players) {
      for (const round of player.rounds) {
        const val = getRoundValue(round, activeTab);
        if (val > max) max = val;
      }
    }
    return max || 1;
  }, [summary, activeTab]);

  if (isLoading) return <Loading />;
  if (error) {
    return (
      <div className="text-red-600 dark:text-red-400 text-center p-8">
        Failed to load game summary.
      </div>
    );
  }
  if (!summary) return null;

  const endReasonText =
    summary.end_reason === "co2_limit"
      ? "CO2 budget exceeded!"
      : `All ${summary.rounds_played} rounds completed`;

  return (
    <div className="w-full max-w-3xl">
      {/* Header */}
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold mb-2">Game Over</h1>
        <p className="text-muted dark:text-darkmutedtext text-lg">
          {endReasonText}
        </p>
        <p className="text-sm text-muted dark:text-darkmutedtext mt-1">
          {summary.rounds_played} round{summary.rounds_played !== 1 ? "s" : ""} played
          {" · "}
          {summary.players.length} player{summary.players.length !== 1 ? "s" : ""}
          {" · "}
          {summary.total_co2_kg.toFixed(1)} / {summary.max_co2_kg} kg CO2
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex rounded-lg bg-gray-100 dark:bg-gray-800 p-1 mb-6">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 py-2.5 px-3 rounded-md text-sm font-medium transition-all ${
              activeTab === tab.id
                ? "bg-white dark:bg-gray-700 shadow-sm text-main dark:text-darktext"
                : "text-muted dark:text-darkmutedtext hover:text-main dark:hover:text-darktext"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab description */}
      <p className="text-center text-sm text-muted dark:text-darkmutedtext mb-6">
        {TABS.find((t) => t.id === activeTab)?.description}
      </p>

      {/* Leaderboard */}
      <div className="space-y-3">
        {rankedPlayers.map((player, index) => {
          const rank = index + 1;
          const isMe = player.player_id === playerId;
          const value = getPlayerValue(player, activeTab);

          return (
            <div
              key={player.player_id}
              className={`bg-surface dark:bg-darksurface rounded-lg border-2 overflow-hidden transition-all ${
                isMe
                  ? "border-primary-500 ring-1 ring-primary-200 dark:ring-primary-800"
                  : "border-subtle dark:border-darksubtle"
              }`}
            >
              {/* Player row */}
              <div className="flex items-center gap-3 p-4">
                {/* Rank badge */}
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-lg shrink-0 ${
                    rank <= 3
                      ? `bg-gradient-to-br ${RANK_COLORS[rank - 1]} text-white`
                      : "bg-gray-200 dark:bg-gray-700 text-muted dark:text-darkmutedtext"
                  }`}
                >
                  {rank === 1 ? "🏆" : rank}
                </div>

                {/* Player info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold truncate">
                      {player.name}
                    </span>
                    {isMe && (
                      <span className="text-xs bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 px-1.5 py-0.5 rounded">
                        you
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    {player.modes_used.map((mode) => {
                      const display = MODE_DISPLAY[mode];
                      return display ? (
                        <span key={mode} className="text-sm" title={display.label}>
                          {display.emoji}
                        </span>
                      ) : null;
                    })}
                  </div>
                </div>

                {/* Main value */}
                <div className="text-right shrink-0">
                  <div className="text-xl font-bold">
                    {formatValue(value, activeTab)}
                  </div>
                  {rank === 1 && (
                    <div className="text-xs text-green-600 dark:text-green-400 font-medium">
                      Winner
                    </div>
                  )}
                </div>
              </div>

              {/* Per-round breakdown bars */}
              <div className="px-4 pb-3">
                <div className="flex items-end gap-1 h-12">
                  {player.rounds.map((round) => {
                    const roundVal = getRoundValue(round, activeTab);
                    const heightPct = maxRoundValue > 0 ? (roundVal / maxRoundValue) * 100 : 0;

                    return (
                      <div
                        key={round.round_number}
                        className="flex-1 flex flex-col items-center gap-0.5"
                      >
                        <div
                          className={`w-full rounded-t transition-all ${
                            isMe
                              ? "bg-primary-500"
                              : "bg-gray-300 dark:bg-gray-600"
                          }`}
                          style={{ height: `${Math.max(heightPct, 4)}%` }}
                          title={`Round ${round.round_number}: ${formatValue(roundVal, activeTab)}`}
                        />
                      </div>
                    );
                  })}
                </div>
                <div className="flex gap-1 mt-1">
                  {player.rounds.map((round) => (
                    <div
                      key={round.round_number}
                      className="flex-1 text-center text-[10px] text-muted dark:text-darkmutedtext"
                    >
                      R{round.round_number}
                    </div>
                  ))}
                </div>
              </div>

              {/* All-stats summary row */}
              <div className="px-4 pb-3 flex gap-4 text-xs text-muted dark:text-darkmutedtext">
                <span className={activeTab === "time" ? "font-semibold text-main dark:text-darktext" : ""}>
                  {formatTime(player.total_time_min)}
                </span>
                <span className={activeTab === "co2" ? "font-semibold text-main dark:text-darktext" : ""}>
                  {player.total_co2_kg.toFixed(1)} kg CO2
                </span>
                <span className={activeTab === "cost" ? "font-semibold text-main dark:text-darktext" : ""}>
                  {player.total_cost_eur.toFixed(2)} EUR
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Overall stats footer */}
      <div className="mt-8 bg-surface dark:bg-darksurface rounded-lg p-4 border border-subtle dark:border-darksubtle">
        <h3 className="font-semibold mb-3 text-center">Round Breakdown</h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-muted dark:text-darkmutedtext border-b border-subtle dark:border-darksubtle">
              <th className="text-left pb-2">Player</th>
              {Array.from({ length: summary.rounds_played }, (_, i) => (
                <th key={i + 1} className="text-right pb-2">
                  R{i + 1}
                </th>
              ))}
              <th className="text-right pb-2 font-bold">Total</th>
            </tr>
          </thead>
          <tbody>
            {rankedPlayers.map((player) => {
              const isMe = player.player_id === playerId;
              return (
                <tr
                  key={player.player_id}
                  className={isMe ? "font-semibold" : ""}
                >
                  <td className="py-1.5 pr-2 truncate max-w-[120px]">
                    {player.name}
                  </td>
                  {player.rounds.map((round) => (
                    <td key={round.round_number} className="text-right py-1.5 tabular-nums">
                      {activeTab === "time" && `${Math.round(round.time_min)}`}
                      {activeTab === "co2" && `${round.co2_kg.toFixed(1)}`}
                      {activeTab === "cost" && `${round.cost_eur.toFixed(1)}`}
                    </td>
                  ))}
                  <td className="text-right py-1.5 font-bold tabular-nums">
                    {activeTab === "time" && `${Math.round(getPlayerValue(player, activeTab))}`}
                    {activeTab === "co2" && `${getPlayerValue(player, activeTab).toFixed(1)}`}
                    {activeTab === "cost" && `${getPlayerValue(player, activeTab).toFixed(1)}`}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr className="border-t border-subtle dark:border-darksubtle text-muted dark:text-darkmutedtext">
              <td className="pt-1.5 text-xs" colSpan={summary.rounds_played + 2}>
                Values in {formatUnit(activeTab)}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
