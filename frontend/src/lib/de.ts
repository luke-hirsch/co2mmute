/**
 * Every user-facing string in the SPA. German only, one file, no i18n library —
 * the game is played in one language and a library would only add indirection.
 *
 * Rule: nothing hardcoded in JSX. If a component renders a word, it comes from
 * here. Parameterised copy is a function, not string concatenation at the call
 * site.
 */

/** The `reason` values `GET lookup/` and `POST join/` can return. Backend contract. */
export type JoinBlockedReason = "started" | "ended" | "full";

/**
 * Typed as a Record on purpose: when the backend grows a fourth reason, adding
 * it to JoinBlockedReason breaks the build here instead of rendering nothing.
 */
const joinBlocked: Record<JoinBlockedReason, string> = {
  started: "Das Spiel läuft schon.",
  ended: "Das Spiel ist zu Ende.",
  full: "Das Spiel ist voll.",
};

export const de = {
  app: {
    name: "co2mmute",
    loading: "Lädt …",
    saving: "Wird gespeichert …",
    empty: "Nichts da.",
  },

  actions: {
    back: "Zurück",
    cancel: "Abbrechen",
    close: "Schließen",
    confirm: "Bestätigen",
    retry: "Nochmal versuchen",
    submit: "Absenden",
  },

  errors: {
    network: "Keine Verbindung zum Server.",
    unknown: "Da ist etwas schiefgelaufen.",
    notFound: "Nicht gefunden.",
    forbidden: "Dafür fehlt dir die Berechtigung.",
    server: "Der Server hat einen Fehler gemeldet.",
  },

  join: {
    title: "Spiel beitreten",
    subtitle: "Gib deinen Namen ein, dann geht es in die Lobby.",
    nameLabel: "Dein Name",
    namePlaceholder: "z. B. Alex",
    nameRequired: "Bitte gib einen Namen ein.",
    passwordLabel: "Passwort",
    passwordPlaceholder: "Passwort des Spiels",
    passwordHint: "Für dieses Spiel braucht es ein Passwort.",
    passwordWrong: "Das Passwort stimmt nicht.",
    gameNotFound: "Es gibt kein Spiel mit dieser ID.",
    submit: "Beitreten",
    submitting: "Trete bei …",
    blocked: joinBlocked,
    seats: (taken: number, max: number) => `${taken} von ${max} Plätzen belegt`,
  },

  lobby: {
    title: "Lobby",
    waiting: "Warten auf den Start …",
    players: "Mitspielende",
    noPlayers: "Noch niemand da.",
    you: "du",
    host: "Spielleitung",
    muted: "stummgeschaltet",
    leave: "Spiel verlassen",
    leaveConfirm: "Willst du das Spiel wirklich verlassen?",
    settings: {
      title: "Einstellungen",
      agentsPerPlayer: "Agenten pro Person",
      maxRounds: "Runden",
      co2Budget: "CO₂-Budget",
      chatOn: "Chat an",
      chatOff: "Chat aus",
    },
    co2Kg: (kg: number) => `${kg} kg`,
    roundsCount: (rounds: number) =>
      rounds === 1 ? "1 Runde" : `${rounds} Runden`,
  },
};
