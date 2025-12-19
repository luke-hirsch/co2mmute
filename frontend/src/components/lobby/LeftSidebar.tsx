import { type WSPlayer } from "../../types/wsTypes";
import { useLobbySocket } from "../../hooks/useLobbySocket";

interface LeftSidebarProps {
  gameId: string;
}

const LeftSidebar = ({ gameId }: LeftSidebarProps) => {
  const { players, error, isConnected } = useLobbySocket({
    gameId,
  });

  // Filter out the host (identified by playerId starting with "host_" or name ending with "(Host)")
  // but keep players controlled by the host
  const regularPlayers = players.filter(
    (player) =>
      !player.playerId.startsWith("host_") && !player.name.endsWith("(Host)")
  );

  return (
    <div className="flex flex-col justify-between max-h-screen overflow-y-auto rounded border border-subtle bg-surface p-4 text-main shadow-sm transition-colors duration-300 dark:border-darksubtle dark:bg-darksurface dark:text-darktext">
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">
            Spieler ({regularPlayers.length})
          </h2>
          <div
            className={`h-2 w-2 rounded-full ${
              isConnected ? "bg-green-500" : "bg-red-500"
            }`}
          />
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
          onClick={() => {}}
          className="w-full rounded bg-primary-600 p-2 text-left font-semibold text-white transition-colors duration-200 hover:bg-primary-500 focus-visible:outline focus-visible:outline-offset-2 focus-visible:outline-primary-600 dark:bg-primary-600 dark:hover:bg-primary-500"
        >
          Lobby verlassen
        </button>
      </div>
    </div>
  );
};

export default LeftSidebar;
