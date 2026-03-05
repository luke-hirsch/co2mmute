import { useState } from "react";
import { type WSRosterPlayer, type PlayerStatus } from "../../types/wsTypes";
import { useGameSocket } from "../../hooks/useGameSocket";
import { useAuth } from "../../context/AuthContext";
import { API_BASE_URL } from "../../config";
import { apiFetch } from "../../utils/api";
import ConnectionSignal from "../ConnectionSignal";
import ConfirmDialog from "../ConfirmDialog";

interface StatusBarProps {
  gameId: string;
  selectedPlayerId?: string;
  onPlayerSelect?: (player: WSRosterPlayer | null) => void;
}

// Status display configuration
const STATUS_CONFIG: Record<PlayerStatus, { label: string; color: string; icon: string }> = {
  ready: {
    label: "Ready",
    color: "bg-green-500",
    icon: "✓",
  },
  making_move: {
    label: "Choosing...",
    color: "bg-yellow-500 animate-pulse",
    icon: "⏳",
  },
  waiting: {
    label: "Waiting",
    color: "bg-blue-500",
    icon: "✓",
  },
  not_connected: {
    label: "Offline",
    color: "bg-gray-400",
    icon: "✗",
  },
};

const StatusBar = ({
  gameId,
  selectedPlayerId,
  onPlayerSelect,
}: StatusBarProps) => {
  const { auth } = useAuth();
  const { error, isConnected, connectionQuality, gameState } = useGameSocket({
    gameId,
  });
  const [showLeaveConfirm, setShowLeaveConfirm] = useState(false);
  const [isLeaving, setIsLeaving] = useState(false);

  // Get players from roster, filter out hosts
  const roster = gameState?.roster || [];
  const players = roster.filter((p) => !p.is_host);

  const co2Percentage = gameState
    ? (gameState.totalEmissionsG / gameState.maxCo2LevelG) * 100
    : 0;

  const handleLeaveLobby = async () => {
    if (!auth) {
      window.location.href = "/";
      return;
    }

    if (auth.kind === "host") {
      window.location.href = "/accounts/profile/";
      return;
    }

    if (auth.kind === "player" && auth.player?.playerId) {
      setIsLeaving(true);
      try {
        const response = await apiFetch(
          `${API_BASE_URL}/api/game/${gameId}/player/${auth.player.playerId}/`,
          {
            method: "DELETE",
          },
        );

        if (response.status === 204 && response.redirect_url) {
          window.location.href = response.redirect_url;
        } else {
          window.location.href = "/";
        }
      } catch (err) {
        console.error("Error leaving lobby:", err);
        alert("An error occurred while leaving the lobby. Please try again.");
        setIsLeaving(false);
        setShowLeaveConfirm(false);
      }
    }
  };

  const handleLeaveClick = () => {
    if (auth?.kind === "host") {
      window.location.href = "/accounts/profile/";
    } else {
      setShowLeaveConfirm(true);
    }
  };

  const handlePlayerClick = (player: WSRosterPlayer) => {
    if (!onPlayerSelect) return;

    // Host can click any player; players can only click themselves
    const canClick =
      auth?.kind === "host" ||
      (auth?.kind === "player" && auth.player?.playerId === player.player_id);

    if (canClick) {
      if (selectedPlayerId === player.player_id) {
        onPlayerSelect(null);
      } else {
        onPlayerSelect(player);
      }
    }
  };

  const getStatusDisplay = (status: PlayerStatus, online: boolean) => {
    if (!online) {
      return STATUS_CONFIG.not_connected;
    }
    return STATUS_CONFIG[status] || STATUS_CONFIG.ready;
  };

  return (
    <div className="flex flex-col justify-between max-h-screen overflow-y-auto rounded border border-subtle bg-surface p-4 text-main shadow-sm transition-colors duration-300 dark:border-darksubtle dark:bg-darksurface dark:text-darktext">
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">
            Players ({players.length})
          </h2>
          {connectionQuality ? (
            <ConnectionSignal quality={connectionQuality} showTooltip={true} />
          ) : (
            <div
              className={`h-2 w-2 rounded-full ${
                isConnected ? "bg-green-500" : "bg-red-500"
              }`}
            />
          )}
        </div>

        {error && (
          <div className="mb-3 rounded bg-red-100 p-2 text-sm text-red-700 dark:bg-red-900 dark:text-red-200">
            {error}
          </div>
        )}

        {/* Player List */}
        <ul className="space-y-2 mb-6">
          {players.length === 0 ? (
            <li className="text-xs text-muted dark:text-darkmutedtext p-2">
              No players yet...
            </li>
          ) : (
            players.map((player) => {
              const statusDisplay = getStatusDisplay(player.status, player.online);
              return (
                <li key={player.player_id}>
                  <button
                    onClick={() => handlePlayerClick(player)}
                    className={`w-full flex items-center justify-between rounded p-2 text-left text-main transition-colors duration-200 dark:text-darktext ${
                      selectedPlayerId === player.player_id
                        ? "bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-200"
                        : "hover:bg-elevated hover:text-primary-600 dark:hover:bg-darkelevated dark:hover:text-darktext"
                    } ${auth?.kind === "host" || (auth?.kind === "player" && auth.player?.playerId === player.player_id) ? "cursor-pointer" : "cursor-default"}`}
                  >
                    <div className="flex flex-col min-w-0 flex-1">
                      <span className="truncate font-medium">{player.name}</span>
                      <span className={`text-xs ${player.online ? 'text-muted dark:text-darkmutedtext' : 'text-red-500'}`}>
                        {statusDisplay.label}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 ml-2">
                      {player.controlled_by_host && (
                        <span className="text-xs text-primary-500" title="Controlled by host">
                          🎮
                        </span>
                      )}
                      <div
                        className={`h-2 w-2 rounded-full ${statusDisplay.color}`}
                        title={statusDisplay.label}
                      />
                    </div>
                  </button>
                </li>
              );
            })
          )}
        </ul>

        {/* Game Stats */}
        <div className="mb-6">
          <h3 className="text-sm font-semibold mb-3">Game Stats</h3>

          {gameState && gameState.isActive ? (
            <>
              {/* Round Info */}
              <div className="mb-4 p-3 rounded bg-elevated dark:bg-darkelevated">
                <div className="flex justify-between mb-2">
                  <span className="text-xs text-muted dark:text-darkmutedtext">
                    Round
                  </span>
                  <span className="font-semibold text-sm">
                    {gameState.currentRound} / {gameState.maxRounds}
                  </span>
                </div>
              </div>

              {/* CO2 Summary */}
              <div className="mb-4 p-3 rounded bg-elevated dark:bg-darkelevated">
                <div className="flex justify-between mb-2">
                  <span className="text-xs text-muted dark:text-darkmutedtext">
                    Total CO₂
                  </span>
                  <span className="font-semibold text-sm">
                    {(gameState.totalEmissionsG / 1000).toFixed(1)} kg
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-muted dark:text-darkmutedtext">
                    Limit
                  </span>
                  <span className="text-xs">
                    {(gameState.maxCo2LevelG / 1000).toFixed(0)} kg
                  </span>
                </div>
                <div className="mt-2 w-full bg-gray-300 dark:bg-gray-600 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full transition-all duration-300 ${
                      co2Percentage > 75
                        ? "bg-red-500"
                        : co2Percentage > 50
                          ? "bg-yellow-500"
                          : "bg-green-500"
                    }`}
                    style={{
                      width: `${Math.min(co2Percentage, 100)}%`,
                    }}
                  />
                </div>
                <div className="mt-1 text-right text-xs text-muted dark:text-darkmutedtext">
                  {co2Percentage.toFixed(1)}%
                </div>
              </div>

              {/* Last Round Results */}
              {gameState.lastRoundStats &&
                gameState.lastRoundStats.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold mb-2 text-muted dark:text-darkmutedtext">
                      Last Round
                    </h4>
                    <ul className="space-y-2">
                      {gameState.lastRoundStats.map((stat, index) => (
                        <li
                          key={stat.player_id}
                          className="flex items-start gap-2 p-2 rounded hover:bg-elevated dark:hover:bg-darkelevated transition-colors"
                        >
                          <span className="text-xs font-bold text-primary-600 dark:text-primary-400 min-w-6">
                            #{index + 1}
                          </span>
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-semibold truncate text-main dark:text-darktext">
                              {stat.player_name}
                            </p>
                            <p className="text-xs text-muted dark:text-darkmutedtext">
                              {stat.action} · {stat.emissions_g}g CO₂
                            </p>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
            </>
          ) : (
            <div className="p-3 rounded bg-elevated dark:bg-darkelevated">
              <p className="text-xs text-muted dark:text-darkmutedtext">
                {gameState?.isActive === false && !gameState?.endedAt
                  ? "Waiting for game to start..."
                  : "Connecting..."}
              </p>
            </div>
          )}
        </div>
      </div>

      <div className="mt-auto">
        <button
          onClick={handleLeaveClick}
          className="w-full rounded bg-red-600 p-2 text-left font-semibold text-white transition-colors duration-200 hover:bg-red-700 focus-visible:outline focus-visible:outline-offset-2 focus-visible:outline-red-600 dark:bg-red-600 dark:hover:bg-red-700"
        >
          Leave Game
        </button>
      </div>

      {/* Leave Confirmation Dialog */}
      <ConfirmDialog
        isOpen={showLeaveConfirm}
        title="Leave Game?"
        message="Are you sure you want to leave? If the game starts or is already running, you won't be able to rejoin."
        confirmLabel={isLeaving ? "Leaving..." : "Leave"}
        cancelLabel="Cancel"
        variant="danger"
        onConfirm={handleLeaveLobby}
        onCancel={() => setShowLeaveConfirm(false)}
      />
    </div>
  );
};

export default StatusBar;
