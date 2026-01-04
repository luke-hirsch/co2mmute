import { useGameState } from "../../hooks/useGameState";
import ConnectionSignal from "../ConnectionSignal";

interface GameStatSidebarProps {
  gameId: string;
}

export default function GameStatSidebar({ gameId }: GameStatSidebarProps) {
  const { gameStats, connectionQuality } = useGameState({
    gameId,
  });

  if (!gameStats) {
    return (
      <div className="flex flex-col justify-between max-h-screen overflow-y-auto rounded border border-subtle bg-surface p-4 text-main shadow-sm transition-colors duration-300 dark:border-darksubtle dark:bg-darksurface dark:text-darktext">
        <div className="text-muted dark:text-darkmutedtext">
          Loading stats...
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col justify-between max-h-screen overflow-y-auto rounded border border-subtle bg-surface p-4 text-main shadow-sm transition-colors duration-300 dark:border-darksubtle dark:bg-darksurface dark:text-darktext">
      <div>
        {/* Connection Status */}
        <div className="mb-6 pb-4 border-b border-subtle dark:border-darksubtle">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold">Connection</h3>
            {connectionQuality && (
              <ConnectionSignal
                quality={connectionQuality}
                showTooltip={true}
              />
            )}
          </div>
          <p className="text-xs text-muted dark:text-darkmutedtext">
            Latency: {connectionQuality?.latency.current}ms
          </p>
        </div>

        {/* Game Stats */}
        <div className="mb-6">
          <h3 className="text-sm font-semibold mb-3">Game Stats</h3>

          {/* CO2 Summary */}
          <div className="mb-4 p-3 rounded bg-elevated dark:bg-darkelevated">
            <div className="flex justify-between mb-2">
              <span className="text-xs text-muted dark:text-darkmutedtext">
                Total CO₂
              </span>
              <span className="font-semibold text-sm">
                {gameStats.totalCo2.toFixed(1)} kg
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-xs text-muted dark:text-darkmutedtext">
                Limit
              </span>
              <span className="text-xs">{gameStats.maxCo2} kg</span>
            </div>
            <div className="mt-2 w-full bg-gray-300 dark:bg-gray-600 rounded-full h-2">
              <div
                className={`h-2 rounded-full transition-all duration-300 ${
                  gameStats.co2Percentage > 75
                    ? "bg-red-500"
                    : gameStats.co2Percentage > 50
                      ? "bg-yellow-500"
                      : "bg-green-500"
                }`}
                style={{
                  width: `${Math.min(gameStats.co2Percentage, 100)}%`,
                }}
              />
            </div>
            <div className="mt-1 text-right text-xs text-muted dark:text-darkmutedtext">
              {gameStats.co2Percentage.toFixed(1)}%
            </div>
          </div>
        </div>

        {/* Player Rankings */}
        <div>
          <h3 className="text-sm font-semibold mb-3">Player Rankings</h3>
          <ul className="space-y-2">
            {gameStats.players.map((player, index) => (
              <li
                key={player.playerId}
                className="flex items-start gap-2 p-2 rounded hover:bg-elevated dark:hover:bg-darkelevated transition-colors"
              >
                <span className="text-xs font-bold text-primary-600 dark:text-primary-400 min-w-6">
                  #{index + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-semibold truncate text-main dark:text-darktext">
                    {player.name}
                  </p>
                  <p className="text-xs text-muted dark:text-darkmutedtext">
                    {player.co2.toFixed(1)} kg CO₂
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Footer Info */}
      <div className="mt-auto pt-4 border-t border-subtle dark:border-darksubtle text-xs text-muted dark:text-darkmutedtext">
        <p>Round progress and CO₂ tracking</p>
      </div>
    </div>
  );
}
