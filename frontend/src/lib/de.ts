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

/** Why the game is over. `game/signals.py` sends one of the two. */
export type GameEndReason = "co2_limit" | "max_rounds";

const endReason: Record<GameEndReason, string> = {
  co2_limit: "Das CO₂-Budget ist aufgebraucht.",
  max_rounds: "Alle Runden sind gefahren.",
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
   * Between two rounds: what the last one cost, and what the class does about
   * it. The phases are the backend's (`game/phases.py`), and each one is a
   * screen: stats → discussion → voting → stalemate → next round.
   */
  between: {
    /** Stats. The round is named, because the number is the point. */
    statsTitle: (n: number) => `Runde ${n} ist gefahren`,
    statsLead:
      "So ist die Klasse gependelt. Schau dir an, was deine Wahl gekostet hat.",
    /** The table. "Zeit" is the average trip, not the sum. */
    player: "Wer",
    co2: "CO₂",
    cost: "Kosten",
    time: "Zeit",
    you: "du",
    roundTotal: "Runde gesamt",
    /**
     * Figures, formatted once. Grams below a kilo, kilos above — a round costs
     * anything from a few hundred grams to tonnes, and "0,4 kg" reads worse
     * than "400 g" on the low end.
     */
    grams: (g: number) =>
      g >= 1000
        ? `${(g / 1000).toLocaleString("de-DE", {
            maximumFractionDigits: 1,
          })} kg`
        : `${Math.round(g).toLocaleString("de-DE")} g`,
    eur: (value: number) =>
      `${value.toLocaleString("de-DE", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })} €`,
    /**
     * The fallback figures, when no routes reached the simulation. It has never
     * happened since 1.1 fixed the ordering, but the flag is in the payload and
     * silently showing made-up numbers as real ones would be the worse bug.
     */
    noSimulation: "Für diese Runde konnte die Simulation nicht rechnen.",

    ack: "Weiter",
    acked: "Du bist durch.",
    ackedBody: "Sobald alle gelesen haben, geht es weiter.",
    /**
     * Nothing tells us *who* is missing — no event carries the acks. Naming a
     * number is honest; naming a name would be made up.
     */
    ackWaiting: "Es fehlen noch ein paar.",

    /** Discussion. */
    discussionTitle: "Was soll sich ändern?",
    discussionLead:
      "Redet darüber, bevor abgestimmt wird. Die Spielleitung öffnet die Abstimmung.",
    discussionWaiting: "Die Abstimmung wird gleich geöffnet.",
    noOptions: "Diesmal steht keine Änderung zur Wahl. Es geht direkt weiter.",
  },

  /** The map vote and the tie-break that can follow it. */
  vote: {
    title: "Abstimmen",
    lead: "Eine Stimme pro Platz. Was die Mehrheit will, steht ab der nächsten Runde auf der Karte.",
    /** A version that takes an earlier change back out. */
    rollback: "nimmt eine Änderung zurück",
    pick: "Dafür stimmen",
    keep: "So lassen",
    keepHint: "Die Karte bleibt, wie sie ist.",
    progress: (cast: number, needed: number) =>
      `${cast} von ${needed} haben abgestimmt`,
    cast: "Deine Stimme ist da.",
    castBody: "Sobald alle abgestimmt haben, geht es weiter.",
    already: "Für diesen Platz ist schon abgestimmt.",
    failed: "Die Stimme ist nicht durchgegangen. Versuch es nochmal.",
    open: "Abstimmung öffnen",
    opening: "Wird geöffnet …",

    /** The tie. */
    tieTitle: "Unentschieden",
    tieLead:
      "Die Stimmen stehen gleich. Wollt ihr nochmal abstimmen, oder bleibt die Karte, wie sie ist?",
    /** Second tie: there is no third round of this. Say it before they answer. */
    tieLast:
      "Das ist die letzte Abstimmung. Bleibt es unentschieden, bleibt die Karte, wie sie ist.",
    revote: "Nochmal abstimmen",
    leaveAsIs: "So lassen",
    tieProgress: (cast: number, needed: number) =>
      `${cast} von ${needed} haben geantwortet`,
    tieAnswered: "Deine Antwort ist da.",
    forceLeave: "Abstimmung beenden",
    forceLeaveConfirm:
      "Die Karte bleibt, wie sie ist, und die nächste Runde startet.",

    /** The outcome, carried into the next round's header. */
    appliedTitle: "Neu auf der Karte",
    applied: (name: string) => `„${name}“ ist angenommen.`,
    unchanged: "Die Karte bleibt, wie sie ist.",
  },

  /** The end of the game (F6). */
  summary: {
    title: "Spiel zu Ende",
    reason: endReason,
    roundsPlayed: (n: number) =>
      n === 1 ? "1 Runde gefahren" : `${n} Runden gefahren`,
    lastRound: (n: number) => `Die letzte Runde (${n})`,
    total: "CO₂ insgesamt",
    budget: "Budget",

    /** The class's arc: one stop per round, the round's CO₂ on it. */
    arcTitle: "Runde für Runde",
    arcLead:
      "So viel hat die Klasse in jeder Runde ausgestoßen. Daran siehst du, was die Änderungen an der Karte gebracht haben.",
    arcRound: (n: number) => `Runde ${n}`,

    /**
     * The three lists. Each heading is a superlative rather than a metric
     * name, because the order is the only thing that says what being at the
     * top of one means — the entries are deliberately not numbered.
     */
    listsTitle: "Wer wie gependelt ist",
    cleanest: "Am wenigsten CO₂",
    cheapest: "Am günstigsten",
    fastest: "Am schnellsten",
    /**
     * The closing line, and the point of the whole screen. There is no winner
     * — or rather, who won is what the class argues about now (the research
     * group's position, via Lukas 2026-09-18). A plain string on purpose:
     * nothing can be interpolated into it, so nobody can be named in it.
     */
    noWinner:
      "Drei Listen, drei Reihenfolgen. Wenig CO₂, wenig Geld und wenig Zeit sind selten dasselbe. Wer also hat am besten gespielt? Das entscheidet ihr.",
    perRound: "Pro Runde",
    modes: "Womit",

    /** A game that ended before anybody completed a round. */
    empty:
      "Es ist keine Runde zu Ende gefahren, also gibt es auch nichts auszuwerten.",
    failed: "Die Auswertung lässt sich gerade nicht laden.",
    hostHome: "Neues Spiel anlegen",
    /**
     * Both headline figures in kilos, whatever their size. `between.grams`
     * switches to grams below a kilo, which is right in a round's table and
     * wrong next to a budget in the tonnes — two numbers meant to be compared
     * must carry the same unit.
     */
    kg: (kg: number) => `${kg.toLocaleString("de-DE")} kg`,
    /**
     * Kilos with one decimal, for every figure that sits in a column with
     * another one. Same argument as `kg` above, one level down: `between.grams`
     * switches to grams below a kilo, which is right in a round's table and
     * wrong in an ordered list — "0 g" above "4.794 kg" makes the reader do a
     * unit conversion to see which is bigger, and these lists are nothing but
     * a comparison.
     */
    kgExact: (kg: number) =>
      `${kg.toLocaleString("de-DE", { maximumFractionDigits: 1 })} kg`,
    /** Names stay until anonymisation runs, 24 h after the end (1.3). */
    lead: "Das war's. Hier steht, was am Ende zusammengekommen ist.",
    home: "Zurück zum Start",
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

    /**
     * Between the rounds (F5). The stats ack goes out for every seat at this
     * machine at once — they are all looking at the same screen — but a vote is
     * one per seat, so that one goes round the desk like a turn does.
     */
    ackAll: "Weiter für alle hier",
    ackedAll: "Für die Plätze hier ist gelesen.",
    voteLead: "Jeder Platz an diesem Rechner stimmt einmal ab. Gib den Rechner reihum weiter.",
    voteSeat: "Abstimmen",
    votedSeats: "Alle Plätze an diesem Rechner haben abgestimmt.",
    /** The phase waits for phones, and nothing here can hurry them along. */
    waitingForPhones: "Es fehlen noch Plätze auf den Handys.",
    /**
     * The one escape hatch when a phase hangs: removing a seat runs
     * `phases.recheck` and the phase completes without it.
     */
    stuckHint:
      "Wenn jemand nicht mehr da ist: entferne den Platz, dann geht es ohne ihn weiter.",

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
  /**
   * The map itself — what its colours mean. Shared by the editor, the map
   * detail page and the in-game view; each one supplies its own colours, so
   * these are only the words (F7).
   */
  map: {
    legend: {
      title: "Legende",
      edges: "Kanten",
      nodes: "Knoten",
      street: "Straße",
      train: "Bahn",
      streetAndTrain: "Straße und Bahn",
      bike: "Radweg",
      walk: "Fußweg",
      bikeAndWalk: "Rad- und Fußweg",
      home: "Zuhause",
      workplace: "Arbeit",
      station: "Bahnhof",
      busStop: "Bushaltestelle",
      other: "sonstiger Knoten",
    },
  },

  /**
   * The map editor (F7).
   *
   * The one part of the dictionary whose reader is a researcher rather than a
   * player, so it names things precisely instead of gently: Knoten, Kante,
   * Version. It still says "du" — the rule holds everywhere.
   */
  editor: {
    title: (name: string) => `Karte bearbeiten: ${name}`,
    back: "Zurück zur Karte",
    loading: "Karte wird geladen …",
    failed: "Die Karte ließ sich nicht laden.",

    /** The tools in the graph tab. */
    tools: {
      select: "Auswählen",
      addNode: "Knoten",
      addEdge: "Kante",
      delete: "Löschen",
      bidirectional: "beide Richtungen",
      oneWay: "Einbahn",
      bidirectionalHint: "Neue Kanten gelten in beide Richtungen (A↔B).",
      oneWayHint: "Neue Kanten gelten nur in eine Richtung (A→B).",
      deleteHint: "Klick Knoten oder Kanten an, um sie zum Löschen zu markieren.",
    },

    /** The toolbar's tabs. */
    tabs: {
      settings: "Einstellungen",
      image: "Hintergrundbild",
      graph: "Graph",
      ptLines: "Linien",
      versions: "Versionen",
    },

    /** Actions that appear on more than one panel. */
    save: "Speichern",
    saving: "Wird gespeichert …",
    saved: "Gespeichert.",
    cancel: "Abbrechen",
    delete: "Löschen",
    deleting: "Wird gelöscht …",
    create: "Anlegen",
    creating: "Wird angelegt …",
    nothingSelected: "Nichts ausgewählt.",
    edit: "Bearbeiten",
    saveSettings: "Einstellungen speichern",
    saveChanges: "Änderungen speichern",
    newBusLine: "Neue Buslinie",
    newTrainLine: "Neue Bahnlinie",
    saveLine: "Linie speichern",
    add: "Hinzufügen",
    imageLoaded: "Bild geladen.",
    selectForCombination: "Für Kombinationen auswählen",
    deleteEdgeConfirm: "Diese Kante löschen?",
    saveFailed: "Das Speichern hat nicht geklappt.",

    /** The background image and where it sits against the graph. */
    image: {
      title: "Hintergrundbild",
      none: "Noch kein Hintergrundbild. Lad eins über die Leiste oben hoch.",
      upload: "Bild hochladen",
      uploading: "Wird hochgeladen …",
      remove: "Bild entfernen",
      offsetX: "Verschiebung X",
      offsetY: "Verschiebung Y",
      scale: "Größe",
      cropTop: "Beschnitt oben",
      cropRight: "Beschnitt rechts",
      cropBottom: "Beschnitt unten",
      cropLeft: "Beschnitt links",
      hint: "Schieb das Bild so, dass die Knoten auf den richtigen Stellen liegen.",
    },

    /** A node. */
    node: {
      title: "Knoten",
      name: "Name",
      types: "Art",
      position: "Position",
      add: "Knoten anlegen",
      removeConfirm: "Der Knoten und alle Kanten daran werden gelöscht.",
    },

    /** An edge, and the two kinds that hang off it. */
    edge: {
      title: "Kante",
      street: "Straße",
      train: "Bahn",
      biking: "für Räder",
      walking: "für Fußgänger",
      lanes: "Spuren",
      speedLimit: "Tempolimit",
      busLane: "eigene Busspur",
      bidirectional: "in beide Richtungen",
      oneWay: "Einbahn",
      add: "Kante ziehen",
      removeConfirm: "Die Kante wird gelöscht.",
    },

    /** Bus and train lines. */
    ptLine: {
      title: "Linien",
      bus: "Buslinie",
      train: "Bahnlinie",
      name: "Name",
      interval: "Takt in Minuten",
      capacity: "Plätze",
      speed: "Geschwindigkeit",
      edges: "Kanten der Linie",
      pickEdges: "Kanten auf der Karte anklicken.",
      add: "Linie anlegen",
      removeConfirm: "Die Linie wird gelöscht. Die Kanten bleiben.",
    },

    /** Versions: what the class votes on. */
    version: {
      title: "Versionen",
      base: "Grundversion",
      active: "aktiv",
      name: "Name",
      create: "Version anlegen",
      fromDiff: "Aus den Änderungen eine Version machen",
      changes: "Änderungen",
      noChanges: "Keine Änderungen gegenüber der Grundversion.",
      compatible: "Verträglich mit",
      generate: "Kombinationen erzeugen",
      hint: "Eine Version ist ein Filter über einen Graphen, keine Kopie.",
    },

    /** The map's own settings. */
    settings: {
      title: "Einstellungen",
      name: "Name der Karte",
      xDim: "Breite",
      yDim: "Höhe",
      maxPlayer: "Plätze",
      walkSpeed: "Tempo zu Fuß",
      bikeSpeed: "Tempo mit dem Rad",
      carSpeed: "Tempo mit dem Auto",
    },
  },
};
