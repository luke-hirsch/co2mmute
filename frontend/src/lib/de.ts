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
 * Same trick for the two below.
 */
const joinBlocked: Record<JoinBlockedReason, string> = {
  started: "Das Spiel läuft schon.",
  ended: "Das Spiel ist zu Ende.",
  full: "Das Spiel ist voll.",
};

/** `AgentRoute.transport_mode`. The four lines the whole design is built on. */
export type TransportMode = "car" | "public" | "bike" | "walk";

const modeLabels: Record<TransportMode, string> = {
  car: "Auto",
  public: "Bus & Bahn",
  bike: "Fahrrad",
  walk: "zu Fuß",
};

/** `status` on a roster row, from `roster.update`. Backend contract. */
export type SeatStatus = "ready" | "making_move" | "waiting" | "not_connected";

const seatStatus: Record<SeatStatus, string> = {
  ready: "bereit",
  making_move: "wählt noch",
  waiting: "abgeschickt",
  not_connected: "nicht verbunden",
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

  modes: modeLabels,

  seat: {
    status: seatStatus,
    /** 1.6: the seat is played at the host machine, not on the student's phone. */
    atHostMachine: "am Lehrerrechner",
    offline: "nicht verbunden",
  },

  /** 1.6: the bell rang, the host stopped the clock. */
  pause: {
    title: "Pause",
    body: "Die Spielleitung hat das Spiel angehalten. Lass die Seite offen, es geht gleich weiter.",
    resumed: "Weiter geht's.",
  },

  /** Game ids and the 1.7 seat-handover code. Both are read off a projector. */
  code: {
    boarding: "Einsteigen",
    gameId: "Spiel-ID",
    seatCode: "Platz-Code",
    placeholder: "4F2A9C",
    scanHint: "Oder den QR-Code am Beamer scannen.",
    expiresIn: (seconds: number) =>
      seconds <= 60
        ? "läuft gleich ab"
        : `noch ${Math.ceil(seconds / 60)} Minuten gültig`,
  },

  co2: {
    label: "CO₂-Budget",
    used: (usedKg: number, maxKg: number) => `${usedKg} von ${maxKg} kg`,
    exceeded: "Budget überschritten",
  },

  round: {
    label: (n: number) => `Runde ${n}`,
    of: (n: number, total: number) => `Runde ${n} von ${total}`,
  },
};
