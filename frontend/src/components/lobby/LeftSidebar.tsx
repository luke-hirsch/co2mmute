import { type WSPlayer } from "../../types/wsTypes";
import { useLobbySocket } from "../../hooks/useLobbySocket";
import { useAuth } from "../../context/AuthContext";
import { API_BASE_URL } from "../../config";
import { apiFetch } from "../../utils/api";
import ConnectionSignal from "../ConnectionSignal";

interface LeftSidebarProps {
  gameId: string;
}

const LeftSidebar = ({ gameId }: LeftSidebarProps) => {
  const { auth } = useAuth();
  const { players, error, isConnected, connectionQuality } = useLobbySocket({
    gameId,
  });

  // Filter out the host (identified by playerId starting with "host_" or name ending with "(Host)")
  // but keep players controlled by the host
  const regularPlayers = players
    .filter((player) => !player.name.endsWith("(Host)"))
    .filter((player) => player.name.toLowerCase() !== "host");

  const handleLeaveLobby = async () => {
    if (!auth) {
      window.location.href = "/";
    } else if (auth.kind === "host") {
      // Redirect to profile
      window.location.href = "/accounts/profile/";
    } else if (auth.kind === "player" && auth.player?.playerId) {
      // Delete the player - backend will clear cookies and return redirect URL
      try {
        const response = await apiFetch(
          `${API_BASE_URL}/api/game/${gameId}/player/${auth.player.playerId}/`,
          {
            method: "DELETE",
          }
        );

        // Backend clears cookies in response and provides redirect URL
        if (response.status === 204 && response.redirect_url) {
          window.location.href = response.redirect_url;
        } else {
          // Fallback to home if no redirect URL provided
          window.location.href = "/";
        }
      } catch (error) {
        console.error("Error leaving lobby:", error);
        alert("An error occurred while leaving the lobby. Please try again.");
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
              <a
                className="flex items-center justify-between rounded p-2 text-main transition-colors duration-200 hover:bg-elevated hover:text-primary-600 dark:text-darktext dark:hover:bg-darkelevated dark:hover:text-darktext"
                href="#"
              >
                {player.name}
              </a>
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-auto">
        <button
          onClick={handleLeaveLobby}
          className="w-full rounded bg-red-600 p-2 text-left font-semibold text-white transition-colors duration-200 hover:bg-red-700 focus-visible:outline focus-visible:outline-offset-2 focus-visible:outline-red-600 dark:bg-red-600 dark:hover:bg-red-700"
        >
          Lobby verlassen
        </button>
      </div>
    </div>
  );
};

export default LeftSidebar;
