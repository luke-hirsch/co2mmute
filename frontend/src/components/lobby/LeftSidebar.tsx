import { useState } from "react";
import { type WSPlayer } from "../../types/wsTypes";
import { useGameSocket } from "../../hooks/useGameSocket";
import { useAuth } from "../../context/AuthContext";
import { API_BASE_URL } from "../../config";
import { apiFetch } from "../../utils/api";
import ConnectionSignal from "../ConnectionSignal";
import ConfirmDialog from "../ConfirmDialog";

interface LeftSidebarProps {
  gameId: string;
  selectedPlayerId?: string;
  onPlayerSelect?: (player: WSPlayer | null) => void;
}

const LeftSidebar = ({
  gameId,
  selectedPlayerId,
  onPlayerSelect,
}: LeftSidebarProps) => {
  const { auth } = useAuth();
  const { error, isConnected, connectionQuality } = useGameSocket({
    gameId,
  });
  const [showLeaveConfirm, setShowLeaveConfirm] = useState(false);
  const [isLeaving, setIsLeaving] = useState(false);

  // TODO: Players will be populated when GameConsumer sends roster updates
  const [players] = useState<WSPlayer[]>([]);

  // Filter out the host (identified by playerId starting with "host_" or name ending with "(Host)")
  // but keep players controlled by the host
  const regularPlayers = players
    .filter((player) => !player.name.endsWith("(Host)"))
    .filter((player) => player.name.toLowerCase() !== "host");

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
          }
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
      // Hosts go directly to profile, no confirmation needed
      window.location.href = "/accounts/profile/";
    } else {
      // Players see confirmation dialog
      setShowLeaveConfirm(true);
    }
  };

  const handlePlayerClick = (player: WSPlayer) => {
    if (auth?.kind === "host" && onPlayerSelect) {
      // Toggle selection if clicking the same player
      if (selectedPlayerId === player.playerId) {
        onPlayerSelect(null);
      } else {
        onPlayerSelect(player);
      }
    }
  };

  return (
    <div className="flex flex-col justify-between max-h-screen overflow-y-auto rounded border border-subtle bg-surface p-4 text-main shadow-sm transition-colors duration-300 dark:border-darksubtle dark:bg-darksurface dark:text-darktext">
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">
            Spieler ({regularPlayers.length})
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

        <ul className="space-y-2">
          {regularPlayers.map((player: WSPlayer) => (
            <li key={player.playerId}>
              <button
                onClick={() => handlePlayerClick(player)}
                className={`w-full flex items-center justify-between rounded p-2 text-left text-main transition-colors duration-200 dark:text-darktext ${
                  selectedPlayerId === player.playerId
                    ? "bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-200"
                    : "hover:bg-elevated hover:text-primary-600 dark:hover:bg-darkelevated dark:hover:text-darktext"
                } ${auth?.kind === "host" ? "cursor-pointer" : "cursor-default"}`}
              >
                <span className="truncate">{player.name}</span>
                <div className="flex items-center gap-2">
                  {player.isMuted && (
                    <span className="text-xs text-red-500" title="Muted">
                      🔇
                    </span>
                  )}
                  <div
                    className={`h-2 w-2 rounded-full ${player.online ? "bg-green-500" : "bg-gray-400"}`}
                  />
                </div>
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-auto">
        <button
          onClick={handleLeaveClick}
          className="w-full rounded bg-red-600 p-2 text-left font-semibold text-white transition-colors duration-200 hover:bg-red-700 focus-visible:outline focus-visible:outline-offset-2 focus-visible:outline-red-600 dark:bg-red-600 dark:hover:bg-red-700"
        >
          Lobby verlassen
        </button>
      </div>

      {/* Leave Confirmation Dialog */}
      <ConfirmDialog
        isOpen={showLeaveConfirm}
        title="Lobby verlassen?"
        message="Bist du sicher, dass du die Lobby verlassen willst? Wenn das Spiel startet oder bereits läuft, kannst du nicht mehr beitreten."
        confirmLabel={isLeaving ? "Verlassen..." : "Verlassen"}
        cancelLabel="Abbrechen"
        variant="danger"
        onConfirm={handleLeaveLobby}
        onCancel={() => setShowLeaveConfirm(false)}
      />
    </div>
  );
};

export default LeftSidebar;
