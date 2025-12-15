import { useState } from "react";
import { API_BASE_URL } from "../../config";
import { type Player } from "../../types";

import TextInput from "./../TextInput";
import type { XMarkIcon } from "@heroicons/react/24/solid";
const LeftSidebar = () => {
  const [results, setResults] = useState({
    results: [],
    data: {},
    show: false,
  });
  const [players, setPlayers] = useState<Player[]>([]);
  const search = async (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    const search = e.target.value;
    if (search.length > 3) {
      const response = await fetch(`${API_BASE_URL}/mv/?search=${search}`);
      const data = await response.json();
      setResults({ ...results, ...data, show: true });
    }
  };

  return (
    <div className="flex flex-col justify-between max-h-screen overflow-y-auto rounded border border-subtle bg-surface p-4 text-main shadow-sm transition-colors duration-300 dark:border-darksubtle dark:bg-darksurface dark:text-darktext">
      <TextInput
        additionalClasses="relative"
        margin="my-2"
        name="search"
        placeholder="Suche"
        onChange={search}
      />
      {results.show && (
        <div className="border border-subtle bg-elevated dark:border-darksubtle dark:bg-darkelevated rounded p-3 text-start relative transition-colors duration-300">
          <button
            onClick={() => {
              setResults({ ...results, show: false });
            }}
            className="absolute top-2 right-2 text-muted transition-colors duration-200 hover:text-primary-600 dark:text-darkmutedtext dark:hover:text-darktext"
          >
            &times;
          </button>
          {results.results.length > 0 && (
            <div>
              <h6 className="text-sm text-muted dark:text-darkmutedtext">
                Teilnehmer
              </h6>
              <ul>
                {results.results.map((id: number) => (
                  <li>
                    <a
                      className="block p-2 rounded text-main transition-colors duration-200 hover:bg-elevated hover:text-primary-600 dark:text-darktext dark:hover:bg-darkelevated dark:hover:text-darktext"
                      href={`#`}
                      key={id}
                    >
                      {results.results.toString()}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
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
          Logout
        </button>
      </div>
    </div>
  );
};

export default LeftSidebar;
