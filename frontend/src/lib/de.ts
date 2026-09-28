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

/**
 * Why the game is over. `game/signals.py` sends one of these.
 *
 * `host` and `idle` are here ahead of the backend that sends them
 * (`.claude/plans/to-do/[backend]-game-ending.md`): the reason used to be
 * recomputed at read time from "over budget or not", so every ending that was
 * neither reported `max_rounds` — a game stopped by hand in round 1 said "Alle
 * Runden sind gefahren" above "0 Runden gefahren". Adding the words first lets
 * that guide land on its own and be visible the day it does.
 */
export type GameEndReason = "co2_limit" | "max_rounds" | "host" | "idle";

const endReason: Record<GameEndReason, string> = {
  co2_limit: "Das CO₂-Budget ist aufgebraucht.",
  max_rounds: "Alle Runden sind gefahren.",
  host: "Die Spielleitung hat das Spiel beendet.",
  idle: "Das Spiel lag zu lange still und hat sich selbst beendet.",
};

export const de = {
  app: {
    name: "co2mmute",
    loading: "Lädt …",
    saving: "Wird gespeichert …",
    empty: "Nichts da.",

    /**
     * The header on the screens under `/app/` that are not a game. Both links
     * leave the SPA — the landing page and the profile are Django pages — so
     * they are plain `<a href>` and not router links.
     */
    header: {
      home: "Startseite",
      profile: "Mein Profil",
    },
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
    co2Kg: (kg: number) => `${kg.toLocaleString("de-DE")} kg`,
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

  /** S8: the chat, rebuilt against `ChatConsumer` after F5 deleted the old one. */
  chat: {
    title: "Chat",
    /** On the button that opens the panel, and as the panel's own heading. */
    open: "Chat öffnen",
    close: "Chat schließen",
    empty: "Noch nichts geschrieben.",
    /** The host switched it off; there is nothing to open. */
    disabled: "Die Spielleitung hat den Chat ausgeschaltet.",
    placeholder: "Schreib etwas …",
    send: "Senden",
    /** While the socket is down the composer stays, the send does not. */
    offline: "Keine Verbindung zum Chat. Wird neu aufgebaut …",
    /** Beside the transcript, so nobody expects it back tomorrow. */
    retention: "Nachrichten verschwinden nach zwei Stunden.",
    unread: (count: number) => (count === 1 ? "1 neue" : `${count} neue`),
    errors: {
      /** `ChatConsumer.CHAT_MESSAGE_MAX_LENGTH` is 500. */
      tooLong: "Das ist zu lang. Höchstens 500 Zeichen.",
      /** This device sent two messages inside 0,35 s. */
      tooFast: "Nicht so schnell — kurz warten.",
      /** The whole game is over 10 messages a second. */
      roomTooFast: "Gerade schreiben alle gleichzeitig. Versuch es gleich noch mal.",
      /**
       * The host muted this seat (S9). Says so outright rather than falling
       * back on `unknown`: silence, or a vague "nicht angekommen", reads as a
       * broken chat and invites trying again all lesson.
       */
      muted: "Die Spielleitung hat dich im Chat stummgeschaltet.",
      unknown: "Die Nachricht ist nicht angekommen.",
    },
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
    /**
     * Grouped, like every other figure in the game. It used to print raw
     * integers — "10349 von 500000 kg" — which is the one number on the screen
     * a reader has to count digits on.
     */
    used: (usedKg: number, maxKg: number) =>
      `${Math.round(usedKg).toLocaleString("de-DE")} von ${Math.round(
        maxKg,
      ).toLocaleString("de-DE")} kg`,
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
    /**
     * Too far is not the same answer as no connection, so it does not get the
     * same sentence: one says take another line, this one says stop trying this
     * mode. Naming the limit makes it a rule the class can argue with rather
     * than the app being difficult.
     */
    tooFar: {
      walk: (limit: string) =>
        `Weiter als ${limit} — so weit geht niemand zu Fuß zur Arbeit.`,
      bike: (limit: string) =>
        `Weiter als ${limit} — so weit fährt niemand mit dem Rad zur Arbeit.`,
    },
    tooFarShort: "zu weit",
    routeAgain: "nochmal versuchen",

    /**
     * What you know before you choose anything: roughly how far away the place
     * is. Until S6 the distance only appeared once a route had been found, so
     * the number that should inform the decision was a consequence of it.
     */
    airDistance: (distance: string) => `Luftlinie ${distance}`,
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
    /** The overlay drawn from the last round's measured speeds. */
    jamHint:
      "Je dicker die Straße, desto langsamer war sie in der letzten Runde. „Schnellste“ rechnet damit.",
    noAssignment:
      "Für diesen Platz sind keine Fahrgäste hinterlegt. Die Spielleitung muss das Spiel neu anlegen.",
  },

  /**
   * The animation, which is the first act of the stats phase rather than a phase
   * of its own: submit → loading → animation → numbers → Weiter.
   *
   * The vocabulary is the player's, not the researcher's. "Knoten" and "Kante"
   * belong to the map editor; here it is zu Hause and die Haltestelle.
   */
  replay: {
    title: "Der Morgen",
    lead:
      "Zwei Stunden Berufsverkehr in zwei Minuten — so verhält sich die Karte " +
      "mit dem, was ihr gewählt habt.",
    mapLabel: "Karte mit den Fahrten dieser Runde",

    /**
     * Simulated time, not a time of day. The model has no wall clock — the
     * departure window simply starts at zero — so claiming "7:48 Uhr" would put
     * a number on screen that nothing in the simulation stands behind.
     */
    clockLabel: "Simulationszeit",
    clock: (minute: number) =>
      `${Math.floor(minute / 60)}:${String(Math.floor(minute % 60)).padStart(2, "0")}`,

    play: "Abspielen",
    pause: "Anhalten",
    again: "Nochmal ansehen",
    skip: "Überspringen",

    /**
     * One dot is fifty people, and the screen says so. Every other figure on
     * these screens is class-scale and nothing names it; a dot is the one place
     * where the scale is attached to something you can point at.
     */
    scale: (people: string) => `Ein Punkt steht für ${people} Menschen.`,
    crowd: (people: number) => people.toLocaleString("de-DE"),

    /**
     * The four lines plus the two marks that are not a person. No entry for "your
     * own dots": everybody watches the same traffic and no dot belongs to anybody
     * on screen (Lukas, 2026-09-27).
     */
    legend: {
      title: "Was du siehst",
      /** Reads as a label in front of the four mode dots, which are people. */
      people: "unterwegs mit",
      vehicle: "ein Bus oder eine Bahn",
      crowd: "Menschen, die warten",
      fill: "wie voll die Straße ist",
    },
    hint:
      "Punkte, die stehen bleiben, stecken im Stau. Wer noch nicht losfahren " +
      "konnte, wartet als Gruppe zu Hause oder an der Haltestelle.",

    /**
     * The beat at the end. Three sentences, because the three endings mean
     * different things and the first one may only appear when it is true:
     * `arrived` got there, `unfinished` was still moving when the clock stopped,
     * and `stranded` never travelled at all because the line's edges do not
     * reach a stop its route asks for — a defect in the map, not a bad choice.
     */
    beatArrived: "Alle sind angekommen.",
    beatUnfinished: (people: string) =>
      `${people} Menschen waren noch unterwegs, als der Morgen vorbei war.`,
    beatStranded: (people: string) =>
      `${people} Menschen kamen gar nicht los: die Linie fährt ihre Haltestelle ` +
      `nicht an. Das liegt an der Karte, nicht an der Wahl.`,

    loading: "Die Aufzeichnung wird geladen …",
    /** An old round, simulated before the recorder existed. Its numbers are intact. */
    missing: "Von dieser Runde gibt es keine Aufzeichnung.",
    failed: "Die Aufzeichnung ließ sich nicht laden.",
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
    /**
     * The same figure in a unit the caller picked, for a whole column at once.
     * `grams` above switches at a kilo per figure, which is right for a single
     * number and wrong for a list — see `lib/game/scale.ts:co2Unit`.
     */
    co2Figure: (g: number, unit: "g" | "kg") =>
      unit === "kg"
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

    /** The two class-scale rows under the table, and the switch above it. */
    unridden: "Linien ohne Fahrgäste",
    unriddenHint:
      "Bus und Bahn fahren ihren Takt, auch wenn niemand einsteigt. Dieses CO₂ steht in der Rundensumme, aber in keiner Zeile.",
    /** The class's own commutes, not the round — the timetable nobody rode is
     *  already on its own line above and would make the gap look like subsidy. */
    paidSelf: (paid: string, cost: string) =>
      `Für die Wege der Klasse wurden ${paid} bezahlt. Gekostet haben sie ${cost}.`,
    /** The footer is the class's whatever the switch says. */
    wholeClass: "ganze Klasse",
    paidYou: (paid: string, cost: string) =>
      `Du hast ${paid} bezahlt. Gekostet hat dein Weg ${cost}.`,
  },

  /**
   * How the numbers on screen are to be read.
   *
   * Every figure in this game has two scales: what the class did, and what one
   * commuter did once. The class scale is what the CO₂ budget is spent out of;
   * the per-person one is the only figure a student can hold against their own
   * morning. Both are in the payload, and the reader switches between them.
   *
   * **The explanation never goes next to the ballot** (Lukas, 2026-09-22). The
   * class needs to know that one Fahrgast is a hundred people and that a line
   * runs empty or not — but that sentence beside the vote hands them an argument
   * they should arrive at themselves. So it lives in an overlay of its own and
   * on the screens where there is nothing to do but wait.
   */
  numbers: {
    /** The switch. The table above it is the subject, so the legend is for screen readers. */
    scaleLegend: "Zahlen anzeigen",
    person: "pro Person",
    class: "ganze Klasse",

    /** One line above the table, so the column headings do not have to carry it. */
    perPersonNote: (people: string) =>
      `Eine Zeile ist ein Weg, einmal gefahren. Ein Fahrgast steht für ${people} Menschen — die Summe unten ist die ganze Klasse.`,
    classNote: (people: string) =>
      `Jede Zeile ist schon mit ${people} Menschen pro Fahrgast gerechnet.`,
    /** Without the factor: the host desk in round 1 has no seat to read it off. */
    perPersonNotePlain:
      "Eine Zeile ist ein Weg, einmal gefahren. Die Summe unten ist die ganze Klasse.",
    classNotePlain:
      "Jede Zeile ist mit allen Menschen gerechnet, für die ein Fahrgast steht.",

    /** The overlay. */
    explain: "Wie wird gerechnet?",
    explainTitle: "Wie diese Zahlen zustande kommen",
    explainLead: "Was hinter den Zahlen auf dem Schirm steht.",
    close: "Verstanden",

    scaleTitle: "Ein Fahrgast ist nicht eine Person",
    scaleBody: (people: string) =>
      `Die Karte zeigt einen echten Stadtteil, und dort pendeln jeden Morgen ` +
      `tausende Menschen. Die verteilen sich auf die Fahrgäste im Spiel: einer ` +
      `steht für ${people} Menschen. Deshalb kostet eine Runde Tonnen und nicht ` +
      `Gramm. Wenn mehr Plätze mitspielen, steht ein Fahrgast für weniger ` +
      `Menschen — der Stadtteil bleibt gleich groß.`,
    scaleBodyPlain:
      "Die Karte zeigt einen echten Stadtteil, und dort pendeln jeden Morgen " +
      "tausende Menschen. Die verteilen sich auf die Fahrgäste im Spiel: einer " +
      "steht für viele. Deshalb kostet eine Runde Tonnen und nicht Gramm.",

    timeTitle: "Zeit wird nicht zusammengezählt",
    timeBody:
      "CO₂ und Kosten kann man addieren: zwei Wege kosten doppelt. Zeit nicht — " +
      "wenn zwei Fahrgäste je 30 Minuten brauchen, dauert der Morgen 30 Minuten " +
      "und nicht 60. In der Zeitspalte steht deshalb immer der Schnitt über die " +
      "Wege, auf beiden Skalen.",

    paidTitle: "Was es kostet und was du zahlst",
    paidBody:
      "In der Kostenspalte steht, was ein Weg wirklich kostet: beim Auto Sprit, " +
      "Verschleiß, Versicherung und Wertverlust, bei Bus und Bahn der Betrieb " +
      "der Linie. Was du selbst zahlst, ist weniger — ein Ticket, oder was an " +
      "der Tankstelle liegen bleibt. Den Rest zahlen alle zusammen.",

    networkTitle: "Der Fahrplan fährt auch leer",
    networkBody:
      "Eine Buslinie fährt ihren Takt, ob jemand einsteigt oder nicht, und " +
      "stößt dabei CO₂ aus. Benutzt niemand aus der Klasse eine Linie, steht " +
      "ihr CO₂ trotzdem in der Rundensumme — aber in keiner Zeile. Genau diese " +
      "Differenz steht unter der Tabelle.",

    jamTitle: "Im Stau wird es mehr",
    jamBody:
      "Ein Auto im Stau verbraucht pro Kilometer mehr als eines, das fährt. " +
      "Dieselbe Strecke kann in zwei Runden also unterschiedlich viel CO₂ " +
      "kosten, auch wenn niemand seine Route geändert hat.",
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
    /**
     * They left before the end and their rounds still count. Marked because the
     * list is ordered per commute for exactly this reason: on the sums, whoever
     * played least comes out cleanest, cheapest and fastest.
     */
    leftEarly: "vorzeitig raus",
    /** In the cost list only, where the contrast is the point. */
    paid: "davon selbst bezahlt",

    /** The class's own figures, under the arc. Always class scale. */
    societyTitle: "Was der Fahrplan gekostet hat",
    societyLead:
      "Bus und Bahn fahren ihren Takt, ob jemand einsteigt oder nicht. Dieses CO₂ zählt gegen das Budget wie jedes andere.",
    societyTimetable: "Fahrplan insgesamt",
    societyUnridden: "davon auf Linien, die niemand genutzt hat",
    /** Nothing to say: a map without bus or train lines. */
    societyNone: "Auf dieser Karte fahren keine Linien.",

    /** The vote list. History, not a ballot — so it may explain itself. */
    votesTitle: "Was die Klasse geändert hat",
    votesLead:
      "Nach jeder Runde stand eine Änderung zur Wahl. Daran siehst du, warum die nächste Zeile anders aussieht.",
    votesNone: "In diesem Spiel wurde nichts abgestimmt.",
    afterRound: (n: number) => `Nach Runde ${n}`,
    voteWon: (name: string) => `„${name}" ist angenommen.`,
    voteKept: "Die Karte ist geblieben, wie sie war.",
    voteTie: "Gleichstand.",
    voteForced: "Die Spielleitung hat die Abstimmung beendet.",
    voteKeepRow: "So lassen",
    voteCount: (n: number) => (n === 1 ? "1 Stimme" : `${n} Stimmen`),

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

    mute: "Stummschalten",
    unmute: "Stummschaltung aufheben",
    muteConfirm: (name: string) =>
      `${name} kann dann nichts mehr in den Chat schreiben. Mitlesen geht weiter, und du kannst es jederzeit wieder aufheben.`,

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

    /** The map detail page (`/app/maps/<id>`), which is not the editor. */
    loading: "Karte wird geladen …",
    loadFailed: "Die Karte ließ sich nicht laden.",
    noGraph: "Für diese Karte gibt es keinen Graphen.",
    dimensions: "Maße",
    author: "Angelegt von",
    created: "Angelegt am",
    nodes: "Knoten",
    edges: "Kanten",
    version: "Version",
    details: "Details",
    clearSelection: "Auswahl aufheben",
    pickHint: "Klick einen Knoten oder eine Kante an, um Details zu sehen.",
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
    notFound: "Die Karte gibt es nicht.",
    unsaved: "Nicht gespeichert",

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
      /** What to do next, per tool. The editor used to say all of this in English. */
      addNodeHint: "Klick auf die Fläche, um einen Knoten zu setzen.",
      addEdgeHint: "Klick zwei Knoten an, um sie zu verbinden.",
      selectHint: "Klick Kanten an, um sie zu ändern.",
      proposeNodeHint: "Klick auf die Fläche, um einen Knoten vorzuschlagen.",
      proposeEdgeHint: "Klick zwei Knoten an, um eine Kante vorzuschlagen.",
      editingPtLine: "Linie wird bearbeitet — klick Kanten auf der Karte an.",
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
    modify: "Ändern",
    remove: "Entfernen",
    manage: "Verwalten",
    editMap: "Karte bearbeiten",
    deleteMap: "Karte löschen",
    /**
     * The backup button. It writes the *whole* map — every version, the
     * ballot between them and both poll texts — since S14, and it is the only
     * way a map moves between boxes.
     */
    exportMap: "Karte sichern (JSON)",
    emptyMap: "Leere Karte — leg im Graph-Modus Knoten und Kanten an.",
    pickHint: "Klick einen Knoten oder eine Kante an, um sie zu bearbeiten.",
    versionStep1: "Schritt 1: Angaben zur Version",
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
      noTypes: "Es sind keine Knotenarten angelegt.",
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
      name: "Name",
      type: "Art",
      direction: "Richtung",
      makeOneWay: "Zur Einbahn machen …",
      whichDirection: "Welche Richtung soll bleiben?",
      maxLanes: "Spuren (höchstens)",
      accessibleBy: "Nutzbar für",
      distance: "Länge",
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
      extendHint:
        "Klick Kanten auf der Karte an, um die Linie zu verlängern. Klick die Enden an, um sie zu kürzen.",
      flipDirection: "Richtung umdrehen",
      createFailed: "Die Linie ließ sich nicht anlegen.",
      none: "Noch keine Linien.",
      countTitle: (n: number) => `Linien (${n})`,
      addBus: "+ Buslinie",
      addTrain: "+ Bahnlinie",
      summary: (edges: number, interval: number) =>
        `${edges} Kanten, alle ${interval} min`,
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
      changeImage: "Bild ändern",
      replaceImage: "Bild austauschen",
      uploadImage: "Bild hochladen",
      loading: "Versionen werden geladen …",
      none: "Noch keine Versionen.",
      manage: "Versionen verwalten",
      description: "Beschreibung",
      pollForward: "Abstimmungstext (dafür)",
      pollRevert: "Abstimmungstext (zurück)",
      /** Creating an alternate version out of the current changes. */
      createTitle: "Andere Version anlegen",
      createLead:
        "Leg die Version fest, über die die Klasse abstimmen kann. Trag unten die Angaben ein und änder dann die Kanten.",
      versionName: "Name der Version",
      current: (name: string) => `Aktuell (${name})`,
      baseSuffix: "(Grundversion)",
      pollText: "Abstimmungstext",
      namePlaceholder: "z. B. Busspur auf der Hauptstraße",
      pollPlaceholder: "z. B. Soll die Hauptstraße eine Busspur bekommen?",
      revertPlaceholder: "z. B. Soll die Busspur wieder weg?",
      sourceVersion: "Ausgangsversion",
      pollQuestion: "Worüber wird abgestimmt?",
      startEditing: "Bearbeiten",
      ptLines: "Linien",
      savePtLine: "Änderung an der Linie speichern",
      noPtLines: "In dieser Version gibt es keine Linien.",
      finishPtLineFirst:
        "Speicher oder verwirf erst die Änderung an der Linie.",
      createFailed: "Die Version ließ sich nicht anlegen. Versuch es nochmal.",
      created: "Die Version ist angelegt.",
      diffHint:
        "Änder die Karte mit den Werkzeugen oben: Kanten anklicken, um ihre Eigenschaften zu ändern, Knoten und Kanten anlegen oder löschen, oder unten eine Linie ändern.",
    },

    /** The map's own settings. */
    settings: {
      title: "Einstellungen",
      name: "Name der Karte",
      xDim: "Breite (Rasterfelder)",
      yDim: "Höhe (Rasterfelder)",
      scale: "Maßstab (Meter pro Feld)",
      maxPlayer: "Plätze",
      walkSpeed: "Tempo zu Fuß (km/h)",
      bikeSpeed: "Tempo mit dem Rad (km/h)",
      carSpeed: "Tempo mit dem Auto (km/h)",
    },
  },

  /**
   * Spiel anlegen. S13 — the last funnel screen that wanted JavaScript.
   *
   * It was a Django ModelForm, which derived the two calibrated numbers once
   * per page load: a host who changed the Platzzahl had to pull both across by
   * hand. Here they follow the class size, the round count and the chosen map
   * as it is typed.
   *
   * The help texts are the form's, kept almost word for word — they are the
   * only place the game explains what a Fahrgast stands for before a round has
   * been played, and the explain-the-numbers overlay is not this screen.
   */
  create: {
    title: "Spiel anlegen",
    lead: "Stell das Spiel ein. Die beiden gerechneten Zahlen passen sich an, du kannst sie aber überschreiben.",

    name: "Name des Spiels",
    namePlaceholder: "z. B. Klasse 8b, Dienstag",
    password: "Passwort für die Lobby",
    passwordHelp: "Optional – ohne Passwort kommt jeder in die Lobby.",
    passwordPlaceholder: "z. B. ECO-42",

    map: "Karte",
    mapLoading: "Karten werden geladen …",
    mapNone: "Es gibt noch keine Karte. Ohne Karte lässt sich kein Spiel anlegen.",
    mapFailed: "Die Karten ließen sich nicht laden. Lad die Seite neu.",
    /**
     * A map with one version removes the discussion and the vote from the whole
     * game — `_advance_from_stats` is "discussion if there is a ballot, else the
     * next round". This select is the last place a host can change their mind.
     */
    mapNoChanges:
      "Diese Karte hat nur eine Version. Es gibt also nichts abzustimmen, und die Diskussion zwischen den Runden fällt weg.",

    mapUpdates: "Kartenänderungen zulassen",
    mapUpdatesHelp:
      "Nach jeder Runde stimmt die Klasse über eine Änderung an der Karte ab.",

    classSize: "Klasse",
    maxPlayers: "Plätze insgesamt",
    maxPlayersHelp: "So viele Plätze hat das Spiel insgesamt.",
    agentPerPlayer: "Fahrgäste pro Person",
    agentPerPlayerHelp: "So viele Fahrgäste bekommt jede Person zu Beginn.",

    game: "Spielverlauf",
    maxRounds: "Runden",
    maxRoundsHelp: "So viele Runden werden gefahren, wenn das Budget reicht.",
    idleEndDays: "Ende nach Tagen ohne Spiel",
    idleEndDaysHelp:
      "Ein Spiel, das so lange niemand spielt, endet von selbst – angehalten oder nicht. Einen Tag später werden die Spielernamen entfernt.",

    derived: "Gerechnet",
    derivedLead:
      "Beide Zahlen kommen aus der Karte und der Klassengröße. Du kannst sie überschreiben.",
    co2Budget: "CO₂-Budget (kg)",
    peoplePerAgent: "Menschen pro Fahrgast",
    /** Parameterised, because the sentence has to name the map's own figures. */
    co2BudgetHelp: (perRound: number, rounds: number) =>
      `${perRound.toLocaleString("de-DE")} kg pro Runde × ${rounds} ${
        rounds === 1 ? "Runde" : "Runden"
      }. Ist das Budget aufgebraucht, ist das Spiel vorbei – genug, wenn die Klasse umsteigt, zu wenig, wenn alle fahren.`,
    peoplePerAgentHelp: (commuters: number, agents: number) =>
      `${commuters.toLocaleString("de-DE")} Pendler auf ${agents} ${
        agents === 1 ? "Fahrgast" : "Fahrgäste"
      } verteilt. Bei weniger Plätzen steht ein Fahrgast für mehr Menschen, damit auf der Karte gleich viel Verkehr ist.`,
    /** Shown once either number no longer matches what the map would suggest. */
    overridden: "Von dir überschrieben.",
    reset: "Vorschlag übernehmen",

    submit: "Spiel anlegen",
    submitting: "Wird angelegt …",
    failed: "Das Spiel ließ sich nicht anlegen. Versuch es nochmal.",
  },

  /**
   * `/app/host` — the host's own page. S13.
   *
   * It replaces `/accounts/profile/`, which was a Django template: the game
   * list, the account form, and links to the two credential flows that stayed
   * server-rendered (password, account deletion).
   */
  hostHome: {
    /** Parameterised so the page greets by name when the account has one. */
    greeting: (name: string) => `Hallo ${name},`,
    lead: "Hier verwaltest du deine Spiele und deine Kontodaten.",

    games: "Deine Spiele",
    newGame: "Neues Spiel anlegen",
    noGames:
      "Du hast noch kein Spiel angelegt. Fang mit „Neues Spiel anlegen“ an.",
    gamesFailed: "Deine Spiele ließen sich nicht laden. Lad die Seite neu.",
    gameId: "Spiel-ID",
    createdAt: (date: string) => `angelegt am ${date}`,
    open: "Zum Spiel",
    delete: "Löschen",

    /** What state a game is in. The list says it, so the delete dialog can. */
    running: "läuft",
    paused: "angehalten",
    over: "zu Ende",
    notStarted: "noch nicht gestartet",
    noMap: "ohne Karte",
    rounds: (count: number) => (count === 1 ? "1 Runde" : `${count} Runden`),
    players: (count: number) => (count === 1 ? "1 Platz" : `${count} Plätze`),

    deleteTitle: "Spiel löschen",
    deleteBody: (name: string) =>
      `„${name}“ und alles, was darauf gespielt wurde. Das lässt sich nicht rückgängig machen.`,
    /** Named rather than described: "alle Daten" is nothing anybody can weigh. */
    deleteTakes: (rounds: number, players: number) =>
      `${rounds === 1 ? "1 gefahrene Runde" : `${rounds} gefahrene Runden`} mit allen Wegen, Ergebnissen und Abstimmungen, ${
        players === 1 ? "1 Platz" : `${players} Plätze`
      } und der QR-Code zum Beitreten.`,
    deleteWarning:
      "Gespielte Spiele sind die Forschungsdaten dieses Projekts – wirf eines nur weg, wenn es nie gespielt wurde.",
    deleteConfirm: "Endgültig löschen",
    deleting: "Wird gelöscht …",
    deleteCancel: "Doch nicht",
    /**
     * The 409 the endpoint answers for a game in progress. Ending it is what
     * writes `end_reason`, and that cannot be worked out afterwards.
     */
    deleteRunning:
      "Das Spiel läuft gerade. Beende es erst im Spielbildschirm – dann wird auch festgehalten, warum es zu Ende ging.",
    deleteFailed: "Das Spiel ließ sich nicht löschen. Versuch es nochmal.",

    account: "Dein Konto",
    accountLead:
      "Hier änderst du deine persönlichen Daten. Dein Passwort änderst du auf einer eigenen Seite.",
    accountFailed: "Deine Kontodaten ließen sich nicht laden. Lad die Seite neu.",
    firstName: "Anzeigename",
    firstNameHelp: "So begrüßt dich die Seite. Darf leer bleiben.",
    username: "Benutzername",
    email: "E-Mail-Adresse",
    save: "Speichern",
    saving: "Wird gespeichert …",
    saved: "Gespeichert.",
    saveFailed: "Das ließ sich nicht speichern. Versuch es nochmal.",

    changePassword: "Passwort ändern",
    deleteAccount: "Konto löschen",
    deleteAccountBody:
      "Dein Name und dein Zugang werden entfernt, laufende Spiele beendet. Die Spielergebnisse bleiben anonym erhalten.",
  },
};
