import { useState } from "react";
import { API_BASE_URL } from "../config";

import TextInput from "./TextInput";
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
      const response = await fetch(`${API_BASE_URL}/api/mv/?search=${search}`);
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
      <nav className="mt-5 text-main dark:text-darktext">
        <ul className="space-y-2 ">
          <li>
            <a
              href="/neue-anmeldungen"
              className="block rounded p-2 transition-colors duration-200 hover:bg-elevated hover:text-primary-600 dark:hover:bg-darkelevated dark:hover:text-darktext"
            >
              Anmeldungen
            </a>
          </li>
          <li>
            <a
              href="/teilnehmer"
              className="block rounded p-2 transition-colors duration-200 hover:bg-elevated hover:text-primary-600 dark:hover:bg-darkelevated dark:hover:text-darktext"
            >
              Teilnehmer*innen
            </a>
          </li>
          <li>
            <a
              href="/wahlvorbereitung"
              className="block rounded p-2 transition-colors duration-200 hover:bg-elevated hover:text-primary-600 dark:hover:bg-darkelevated dark:hover:text-darktext"
            >
              Wähler
            </a>
          </li>
          <li>
            <a
              href="/authentifizierung"
              className="block rounded p-2 transition-colors duration-200 hover:bg-elevated hover:text-primary-600 dark:hover:bg-darkelevated dark:hover:text-darktext"
            >
              Authentifizierung
            </a>
          </li>
          <li>
            <a
              href="/wahlregister"
              className="block rounded p-2 transition-colors duration-200 hover:bg-elevated hover:text-primary-600 dark:hover:bg-darkelevated dark:hover:text-darktext"
            >
              Wahlregister
            </a>
          </li>
          <li>
            <a
              href="/anwesenheit"
              className="block rounded p-2 transition-colors duration-200 hover:bg-elevated hover:text-primary-600 dark:hover:bg-darkelevated dark:hover:text-darktext"
            >
              Anwesenheit
            </a>
          </li>
        </ul>
        <div className="mb-2 border-b border-subtle dark:border-darksubtle">
          <h3 className="mt-5 p-2 text-muted dark:text-darkmutedtext">
            Verwaltung
          </h3>
        </div>
        <ul className="space-y-2">
          <li>
            <a
              href="/staff"
              className="block rounded p-2 transition-colors duration-200 hover:bg-elevated hover:text-primary-600 dark:hover:bg-darkelevated dark:hover:text-darktext"
            >
              Staff
            </a>
          </li>
          <li>
            <a
              href="/event"
              className="block rounded p-2 transition-colors duration-200 hover:bg-elevated hover:text-primary-600 dark:hover:bg-darkelevated dark:hover:text-darktext"
            >
              Veranstaltungen
            </a>
          </li>
          <li>
            <a
              href="/mail"
              className="block rounded p-2 transition-colors duration-200 hover:bg-elevated hover:text-primary-600 dark:hover:bg-darkelevated dark:hover:text-darktext"
            >
              Mail
            </a>
          </li>
          <li>
            <a
              href="/org"
              className="block rounded p-2 transition-colors duration-200 hover:bg-elevated hover:text-primary-600 dark:hover:bg-darkelevated dark:hover:text-darktext"
            >
              Organsiationen
            </a>
          </li>
          <li>
            <a
              href="/person"
              className="block rounded p-2 transition-colors duration-200 hover:bg-elevated hover:text-primary-600 dark:hover:bg-darkelevated dark:hover:text-darktext"
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
          className="w-full rounded bg-primary-600 p-2 text-left font-semibold text-white transition-colors duration-200 hover:bg-primary-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600 dark:bg-primary-600 dark:hover:bg-primary-500"
        >
          Logout
        </button>
      </div>
    </div>
  );
};

export default Sidebar;
