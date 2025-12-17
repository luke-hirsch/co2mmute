import { useState, useEffect } from "react";
import { API_BASE_URL } from "../../config";
import { type Player } from "../../types";
import { XMarkIcon } from "@heroicons/react/24/solid";
import { apiFetch } from "../../utils/api";

const LeftSidebar = () => {
  const [players, setPlayers] = useState<Player[]>([]);

  return (
    <div className="flex flex-col justify-between max-h-screen overflow-y-auto rounded border border-subtle bg-surface p-4 text-main shadow-sm transition-colors duration-300 dark:border-darksubtle dark:bg-darksurface dark:text-darktext">
      <div className="mt-5 text-main dark:text-darktext">
        <ul className="space-y-2 ">
          {players.map((player) => (
            <li key={player.id}>
              <a
                className="flex p-2 rounded text-main transition-colors duration-200 hover:bg-elevated hover:text-primary-600 dark:text-darktext dark:hover:bg-darkelevated dark:hover:text-darktext justify-between items-center"
                href={`#`}
              >
                {player.name}{" "}
                {player.isMuted && <XMarkIcon className="h-6 w-auto" />}
              </a>
            </li>
          ))}
        </ul>
      </div>

      {/* Logout link */}
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
