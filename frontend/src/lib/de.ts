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

/**
 * Why a device lost its seat. `game/roster.py:revoke` sends one of these, and
 * the screen has to say which — "du bist raus" reads very differently when the
 * teacher took the seat over on purpose than when someone else scanned your
 * code.
 */
export type RevokedReason =
  | "removed"
  | "left"
  | "taken_over"
  | "handed_over";

const revoked: Record<RevokedReason, string> = {
  removed: "Die Spielleitung hat dich aus dem Spiel genommen.",
  left: "Du hast das Spiel verlassen.",
  taken_over: "Die Spielleitung spielt deinen Platz jetzt am Lehrerrechner.",
  handed_over: "Dein Platz läuft jetzt auf einem anderen Gerät.",
};

/** `AgentRoute.Optimization` in the backend. The serializer rejects anything else. */
export type CarOptimization = "time" | "distance" | "co2";

const carOptimization: Record<CarOptimization, string> = {
  time: "schnellste",
  distance: "kürzeste",
  co2: "sparsamste",
};

/** Client-side only (`src/utils/ptRouting.ts`), but the picker names each one. */
export type PTOptimization = "fastest" | "fewest_transfers" | "no_bus";

const ptOptimization: Record<PTOptimization, string> = {
  fastest: "schnellste",
  fewest_transfers: "wenig umsteigen",
  no_bus: "ohne Bus",
};

const seatStatus: Record<SeatStatus, string> = {
  ready: "bereit",
  making_move: "wählt noch",
  waiting: "abgeschickt",
  not_connected: "nicht verbunden",
};

/**
 * Every `reason` the host's own endpoints answer 409 with. From
 * `game/seats.py:SeatRefused` (full, ended, host, controlled) and
 * `game/pause.py:PauseRefused` (paused, not_running, not_paused).
 */
export type HostRefusal =
  | "full"
  | "ended"
  | "host"
  | "controlled"
  | "paused"
  | "not_running"
  | "not_paused";

const hostRefusal: Record<HostRefusal, string> = {
  full: "Alle Plätze sind belegt. Entferne erst einen.",
  ended: "Das Spiel ist vorbei.",
  host: "Dein eigener Platz lässt sich nicht weitergeben.",
  controlled: "Dieser Platz läuft schon hier am Rechner.",
  paused: "Das Spiel ist schon angehalten.",
  not_running: "Gerade läuft keine Runde.",
  not_paused: "Das Spiel läuft schon.",
};

/** The `reason` values `POST api/game/seat/<code>/` refuses with (1.7). */
export type RedeemRefusal = "host" | "seated" | "ended";

const redeemRefusal: Record<RedeemRefusal, string> = {
  host: "Du leitest dieses Spiel. Der Platz gehört auf ein anderes Gerät.",
  seated: "Dieses Gerät hat in dem Spiel schon einen Platz.",
  ended: "Das Spiel ist vorbei.",
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
    /** The first screen: no game id yet, typed or scanned. */
    idTitle: "Mitspielen",
    idSubtitle:
      "Scanne den QR-Code oder tippe die Spiel-ID ein, die vorne steht.",
    idLabel: "Spiel-ID",
    idRequired: "Bitte gib eine Spiel-ID ein.",
    idSubmit: "Weiter",
    checking: "Wird geprüft …",

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
      chat: "Chat",
      chatOn: "an",
      chatOff: "aus",
    },
    co2Kg: (kg: number) => `${kg} kg`,
    roundsCount: (rounds: number) =>
      rounds === 1 ? "1 Runde" : `${rounds} Runden`,
    seatsTaken: (taken: number, max: number) =>
      `${taken} von ${max} Plätzen belegt`,
    /** The host has not started yet; this is what everyone stares at. */
    hostStarts: "Die Spielleitung startet das Spiel.",
    started: "Das Spiel läuft.",
    toGame: "Zum Spiel",
    ended: "Das Spiel ist zu Ende.",
    toSummary: "Zur Auswertung",
    connectionLost: "Verbindung unterbrochen. Wird neu aufgebaut …",
    /** The snapshot came back 403 — no valid game cookie for this game. */
    noAccess: "Für dieses Spiel fehlt dir der Zugang.",
    joinAgain: "Neu beitreten",
  },

  /** 1.6 + 1.7: this device does not hold the seat any more. */
  revoked: {
    title: "Dein Platz ist weg",
    reason: revoked,
    back: "Zurück zum Start",
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

    /**
     * An agent is a *Fahrgast* to the player — transit vocabulary like the rest
     * of the interface (Platz, Linie, Einsteigen), and it avoids the gendered
     * "Pendler". "Agent" stays in the code, the backend and the thesis.
     */
    agent: (n: number) => `Fahrgast ${n}`,
    destination: "Ziel",
    home: "zu Hause",

    /** The list heading. The question below is what one picker asks. */
    agents: "Deine Fahrgäste",
    pickMode: "Womit fährt dieser Fahrgast?",
    carOptimization,
    ptOptimization,
    otherRoute: "andere Route",
    change: "ändern",

    routing: "Route wird gesucht …",
    noRoute: "Auf diesem Weg kommt der Fahrgast nicht ans Ziel. Nimm eine andere Linie.",
    routeAgain: "nochmal versuchen",
    duration: (minutes: number) =>
      minutes < 60
        ? `${Math.round(minutes)} min`
        : `${Math.floor(minutes / 60)} h ${Math.round(minutes % 60)} min`,
    distance: (meters: number) =>
      meters < 1000
        ? `${Math.round(meters)} m`
        : `${(meters / 1000).toFixed(1)} km`,
    transfers: (n: number) => (n === 1 ? "1 Umstieg" : `${n} Umstiege`),

    /** How far this seat has got, and how far the game has. Two different counts. */
    chosenOf: (done: number, total: number) => `${done} von ${total} gewählt`,
    submittedOf: (done: number, total: number) =>
      `${done} von ${total} abgeschickt`,

    submit: "Losfahren",
    submitting: "Wird abgeschickt …",
    submitBlocked: "Erst wenn jeder Fahrgast eine Route hat.",
    submitted: "Abgeschickt",
    submittedBody: "Deine Wahl steht. Sobald alle durch sind, wird die Runde gefahren.",
    waitingFor: "Es fehlen noch",
    /** The move was refused. Each one names what to do next, never a player. */
    failedPaused: "Das Spiel ist angehalten. Sobald es weitergeht, kannst du abschicken.",
    failedRoundOver: "Diese Runde ist schon durch.",
    failedSeat: "Dieser Platz gehört dir nicht mehr.",
    failedUnknown: "Das Abschicken hat nicht geklappt. Versuch es nochmal.",
    retry: "Nochmal abschicken",

    simulation: "Die Runde wird gefahren …",
    simulationFailed: "Die Simulation ist steckengeblieben. Die Spielleitung weiß Bescheid.",

    mapTitle: "Karte",
    mapHint: "Tippe einen Fahrgast an, um seine Route zu sehen.",
    noAssignment:
      "Für diesen Platz sind keine Fahrgäste hinterlegt. Die Spielleitung muss das Spiel neu anlegen.",
  },

  /**
   * 1.6 + 1.7: the host machine runs the game and the host does not play.
   * "Leitpult" rather than "Host-Screen" — it is the desk at the front of the
   * room, and everything on it is something you do for somebody else.
   */
  host: {
    title: "Leitpult",
    lobbyLead:
      "Die Klasse scannt den Code. Wer kein Handy hat, bekommt von dir einen Platz am Rechner.",
    deskLead: "Gib den Rechner reihum weiter. Jeder Platz fährt einmal.",

    seats: "Plätze",
    noSeats: "Noch niemand da.",
    /** Nothing to play here: everyone is on their own phone. */
    noDeskSeats: "Kein Platz wird gerade an diesem Rechner gespielt.",
    allDone: "Alle Plätze an diesem Rechner sind durch.",

    add: "Platz anlegen",
    addTitle: "Platz am Rechner",
    addBody:
      "Für alle ohne eigenes Gerät. Der Platz wird hier am Rechner gespielt und zählt wie jeder andere.",
    addName: "Name",
    addSubmit: "Anlegen",
    adding: "Wird angelegt …",

    start: "Spiel starten",
    starting: "Startet …",
    startBlocked: "Es muss mindestens ein Platz besetzt sein.",
    /**
     * A game without a map cannot be started at all: `GameSession.save()` forces
     * `is_active` back to False when `game_map` is None, so the request comes
     * back 200 and nothing happens. Say it here rather than let someone press a
     * button eighteen times.
     */
    startNoMap:
      "Diesem Spiel fehlt die Karte, damit kann es nicht starten. Leg ein neues Spiel an und wähl beim Anlegen eine Karte aus.",
    startFailed:
      "Der Start ist nicht durchgegangen — das Spiel steht weiter in der Lobby. Meistens fehlt dem Spiel die Karte.",
    end: "Spiel beenden",
    endConfirm:
      "Danach ist das Spiel vorbei und niemand kann mehr fahren. Die Auswertung bleibt.",
    pause: "Pause",
    pausing: "Wird angehalten …",
    resume: "Weiter",
    resuming: "Geht weiter …",

    play: "Spielen",
    next: "Nächster Platz",
    back: "Zurück zum Pult",
    playingSeat: (name: string) => `Platz von ${name}`,

    takeOver: "Übernehmen",
    takeOverConfirm: (name: string) =>
      `${name} wird ab jetzt hier am Rechner gespielt. Das Gerät von ${name} fliegt dabei aus dem Spiel.`,
    remove: "Entfernen",
    removeConfirm: (name: string) =>
      `${name} ist danach raus. Schon gefahrene Runden bleiben gespeichert.`,

    curtainTitle: (name: string) => `${name} ist dran`,
    curtainBody: "Gib den Rechner weiter. Erst dann weiter — vorher sieht der Raum alles mit.",
    curtainGo: "Los",

    failed: hostRefusal,
    failedUnknown: "Das hat nicht geklappt. Versuch es nochmal.",
  },

  /** 1.7: a seat moves to another device, by a six-character code. */
  handover: {
    title: "Platz auf ein Gerät geben",
    /** On the host machine, for a student who turns up with a phone. */
    hostBody:
      "Der Code gilt fünf Minuten und nur einmal. Wer ihn einlöst, spielt den Platz weiter.",
    /** On a phone, for somebody moving to another one. */
    playerBody:
      "Am anderen Gerät co2mmute öffnen, „Sitzung fortsetzen“ wählen und diesen Code eintippen. Dein jetziges Gerät verlässt den Platz dabei.",
    issue: "Code erzeugen",
    issuing: "Code wird erzeugt …",
    again: "Neuen Code",
    /** A new code kills the old one — worth saying before someone makes two. */
    againHint: "Ein neuer Code macht den alten ungültig.",
    expired: "Der Code ist abgelaufen. Mach einen neuen.",
    scan: "Oder diesen QR-Code scannen.",
    failed: "Der Code ließ sich nicht erzeugen.",
    /** The button on the player's own round screen. */
    toOtherDevice: "Auf anderes Gerät",
  },

  /** `/app/seat/<code>`: the device that takes the seat over. */
  resumeSeat: {
    title: "Sitzung fortsetzen",
    lead: "Tippe den Platz-Code ein, der auf dem anderen Gerät steht.",
    codeRequired: "Bitte gib den Code ein.",
    submit: "Weiter",
    checking: "Wird geprüft …",
    confirm: (player: string, game: string) =>
      `Du übernimmst den Platz von ${player} in „${game}“.`,
    take: "Platz übernehmen",
    taking: "Wird übernommen …",
    gone: "Diesen Code gibt es nicht mehr. Lass dir einen neuen geben.",
    refused: redeemRefusal,
    /** The way in from the join screen. */
    link: "Du warst schon dabei? Sitzung fortsetzen",
  },
};
