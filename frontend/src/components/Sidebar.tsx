import { useState } from "react";
import { API_BASE_URL } from "../config";

import TextInput from "../components/TextInput";
const Sidebar = () => {
  const [results, setResults] = useState({
    results: [],
    data: {},
    show: false,
  });
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
    <div className="flex flex-col justify-between max-h-screen overflow-y-auto rounded m-2 bg-black dark:bg-white p-4 text-black dark:text-black">
      <TextInput
        additionalClasses="relative"
        margin="my-2"
        name="search"
        placeholder="Suche"
        onChange={search}
      />
      {results.show && (
        <div className="border rounded border-zinc-500 p-3 text-start relative">
          <button
            onClick={() => {
              setResults({ ...results, show: false });
            }}
            className="absolute top-2 right-2 text-gray-400 hover:text-gray-600"
          >
            &times;
          </button>
          {results.results.length > 0 && (
            <div>
              <h6 className="text-zinc-500 text-sm">Teilnehmer</h6>
              <ul>
                {results.results.map((id: number) => (
                  <li>
                    <a
                      className="block p-2 rounded bg-white hover:bg-zinc-200 dark:hover:bg-zinc-700"
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
      <nav className="mt-5 text-white dark:text-black">
        <ul className="space-y-2 ">
          <li>
            <a
              href="/neue-anmeldungen"
              className="block p-2 rounded bg-transparent hover:text-black hover:bg-zinc-200 dark:hover:bg-zinc-700"
            >
              Anmeldungen
            </a>
          </li>
          <li>
            <a
              href="/teilnehmer"
              className="block p-2 rounded bg-transparent hover:text-black hover:bg-zinc-200 dark:hover:bg-zinc-700"
            >
              Teilnehmer*innen
            </a>
          </li>
          <li>
            <a
              href="/wahlvorbereitung"
              className="block p-2 rounded bg-transparent hover:text-black hover:bg-zinc-200 dark:hover:bg-zinc-700"
            >
              Wähler
            </a>
          </li>
          <li>
            <a
              href="/authentifizierung"
              className="block p-2 rounded bg-transparent hover:text-black hover:bg-zinc-200 dark:hover:bg-zinc-700"
            >
              Authentifizierung
            </a>
          </li>
          <li>
            <a
              href="/wahlregister"
              className="block p-2 rounded bg-transparent hover:text-black hover:bg-zinc-200 dark:hover:bg-zinc-700"
            >
              Wahlregister
            </a>
          </li>
          <li>
            <a
              href="/anwesenheit"
              className="block p-2 rounded bg-transparent hover:text-black hover:bg-zinc-200 dark:hover:bg-zinc-700"
            >
              Anwesenheit
            </a>
          </li>
        </ul>
        <div className="border-b mb-2 border-zinc-500">
          <h3 className="mt-5 p-2 text-zinc-500">Verwaltung</h3>
        </div>
        <ul className="space-y-2">
          <li>
            <a
              href="/staff"
              className="block p-2 rounded bg-transparent hover:text-black hover:bg-zinc-200 dark:hover:bg-zinc-700"
            >
              Staff
            </a>
          </li>
          <li>
            <a
              href="/event"
              className="block p-2 rounded bg-transparent hover:text-black hover:bg-zinc-200 dark:hover:bg-zinc-700"
            >
              Veranstaltungen
            </a>
          </li>
          <li>
            <a
              href="/mail"
              className="block p-2 rounded bg-transparent hover:text-black hover:bg-zinc-200 dark:hover:bg-zinc-700"
            >
              Mail
            </a>
          </li>
          <li>
            <a
              href="/org"
              className="block p-2 rounded bg-transparent hover:text-black hover:bg-zinc-200 dark:hover:bg-zinc-700"
            >
              Organsiationen
            </a>
          </li>
          <li>
            <a
              href="/person"
              className="block p-2 rounded bg-transparent hover:text-black hover:bg-zinc-200 dark:hover:bg-zinc-700"
            >
              Personen
            </a>
          </li>
        </ul>
      </nav>

      {/* Logout link */}
      <div className="mt-auto">
        <button
          onClick={() => {}}
          className="w-full p-2 text-left rounded bg-white text-black dark:bg-black dark:text-white hover:bg-zinc-900 dark:hover:bg-zinc-200"
        >
          Logout
        </button>
      </div>
    </div>
  );
};

export default Sidebar;
