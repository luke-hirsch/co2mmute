import { beforeEach, describe, expect, it } from "vitest";

import {
  clearStoredDraft,
  draftStorageKey,
  pruneOtherGames,
  readStoredChoices,
  writeStoredChoices,
} from "@/lib/game/draft-storage";
import {
  DEFAULT_CAR_OPTIMIZATION,
  DEFAULT_PT_OPTIMIZATION,
  type AgentChoice,
  type RoundDraft,
} from "@/lib/game/round-draft";

/**
 * The half-made turn, across a reload.
 *
 * What is stored is the taps and nothing else — mode and the two optimisations.
 * Never a route: the routes come back out of the pathfinder against the graph
 * the game is on *now*, which is the whole reason this can exist without
 * becoming the second source of truth `round-draft.ts` was built to avoid.
 *
 * Every function here takes its storage as an argument, the way
 * `readStoredColorMode` does, so none of this needs a stubbed global.
 */

/** A `Storage` that lives in a Map. Enough for every function under test. */
function fakeStorage(seed: Record<string, string> = {}) {
  const map = new Map(Object.entries(seed));
  return {
    get length() {
      return map.size;
    },
    key: (i: number) => [...map.keys()][i] ?? null,
    getItem: (k: string) => map.get(k) ?? null,
    setItem: (k: string, v: string) => void map.set(k, v),
    removeItem: (k: string) => void map.delete(k),
    clear: () => map.clear(),
    /** For assertions, not part of `Storage`. */
    _map: map,
  };
}

/** A storage that throws on everything — Safari with site data blocked. */
function hostileStorage() {
  const boom = () => {
    throw new Error("QuotaExceededError");
  };
  return {
    get length(): number {
      throw new Error("SecurityError");
    },
    key: boom,
    getItem: boom,
    setItem: boom,
    removeItem: boom,
    clear: boom,
  } as unknown as Storage;
}

const CHOICES: AgentChoice[] = [
  {
    agentId: 1,
    mode: "car",
    carOptimization: "co2",
    ptOptimization: DEFAULT_PT_OPTIMIZATION,
  },
  {
    agentId: 2,
    mode: "public",
    carOptimization: DEFAULT_CAR_OPTIMIZATION,
    ptOptimization: "fewest_transfers",
  },
];

function draft(overrides: Partial<RoundDraft> = {}): RoundDraft {
  return {
    seatId: "P-1",
    roundNumber: 2,
    homeNode: 10,
    agents: [],
    ...overrides,
  };
}

describe("draftStorageKey", () => {
  it("is one entry per seat per game, so the desk keeps every seat apart", () => {
    expect(draftStorageKey("G-1", "P-1")).not.toEqual(draftStorageKey("G-1", "P-2"));
    expect(draftStorageKey("G-1", "P-1")).not.toEqual(draftStorageKey("G-2", "P-1"));
  });
});

describe("writeStoredChoices / readStoredChoices", () => {
  let storage: ReturnType<typeof fakeStorage>;

  beforeEach(() => {
    storage = fakeStorage();
  });

  it("brings the taps back for the same seat in the same round", () => {
    writeStoredChoices(storage, "G-1", draft(), CHOICES, 2);
    expect(readStoredChoices(storage, "G-1", "P-1", 2)).toEqual(CHOICES);
  });

  it("stores the mode and both optimisations, and nothing else", () => {
    writeStoredChoices(storage, "G-1", draft(), CHOICES, 2);
    const raw = JSON.parse(storage.getItem(draftStorageKey("G-1", "P-1"))!);
    expect(Object.keys(raw).sort()).toEqual(["agents", "round"]);
    expect(Object.keys(raw.agents[0]).sort()).toEqual([
      "agentId",
      "carOptimization",
      "mode",
      "ptOptimization",
    ]);
  });

  /**
   * The round is the guard that matters. Round 2 runs on a map round 1 may have
   * voted away, so a route from round 1 could name an edge that is gone — and
   * "the choices I made last round" is not what the screen is asking for anyway.
   */
  it("refuses a draft from another round", () => {
    writeStoredChoices(storage, "G-1", draft({ roundNumber: 1 }), CHOICES, 1);
    expect(readStoredChoices(storage, "G-1", "P-1", 2)).toBeNull();
  });

  it("refuses another seat's draft", () => {
    writeStoredChoices(storage, "G-1", draft(), CHOICES, 2);
    expect(readStoredChoices(storage, "G-1", "P-2", 2)).toBeNull();
  });

  /**
   * A seat that is handed on or taken over keeps its row but gets a new
   * `player_id` (`game/seats.py:_rotate`), so the key moves with it and the old
   * device's draft is unreachable by construction.
   */
  it("refuses the draft of a seat whose player_id has rotated", () => {
    writeStoredChoices(storage, "G-1", draft({ seatId: "P-old" }), CHOICES, 2);
    expect(readStoredChoices(storage, "G-1", "P-new", 2)).toBeNull();
  });

  it("reads nothing when nothing was ever written", () => {
    expect(readStoredChoices(storage, "G-1", "P-1", 2)).toBeNull();
  });

  it("ignores an entry that is not JSON", () => {
    storage.setItem(draftStorageKey("G-1", "P-1"), "{not json");
    expect(readStoredChoices(storage, "G-1", "P-1", 2)).toBeNull();
  });

  it("ignores an entry whose shape is wrong", () => {
    storage.setItem(draftStorageKey("G-1", "P-1"), JSON.stringify({ round: 2 }));
    expect(readStoredChoices(storage, "G-1", "P-1", 2)).toBeNull();
  });

  it("drops an agent with an unknown mode rather than the whole draft", () => {
    storage.setItem(
      draftStorageKey("G-1", "P-1"),
      JSON.stringify({
        round: 2,
        agents: [
          { agentId: 1, mode: "teleport", carOptimization: "co2", ptOptimization: "fastest" },
          CHOICES[1],
        ],
      }),
    );
    expect(readStoredChoices(storage, "G-1", "P-1", 2)).toEqual([CHOICES[1]]);
  });

  it("falls back to the defaults when an optimisation is unknown", () => {
    storage.setItem(
      draftStorageKey("G-1", "P-1"),
      JSON.stringify({
        round: 2,
        agents: [{ agentId: 1, mode: "car", carOptimization: "vibes", ptOptimization: 7 }],
      }),
    );
    expect(readStoredChoices(storage, "G-1", "P-1", 2)).toEqual([
      {
        agentId: 1,
        mode: "car",
        carOptimization: DEFAULT_CAR_OPTIMIZATION,
        ptOptimization: DEFAULT_PT_OPTIMIZATION,
      },
    ]);
  });

  /**
   * Nothing chosen is nothing to keep. Writing an empty record would leave a
   * seat's key lying around for a turn that was never begun.
   */
  it("removes the entry instead of storing an empty turn", () => {
    writeStoredChoices(storage, "G-1", draft(), CHOICES, 2);
    writeStoredChoices(storage, "G-1", draft(), [], 2);
    expect(storage.getItem(draftStorageKey("G-1", "P-1"))).toBeNull();
  });

  /**
   * The bug this guard exists for, and it was found by an e2e run that failed
   * once in four: on a reload the seat query can resolve before `game.state`
   * arrives, so the screen is briefly on round 0 — the reducer's "no round
   * yet". The draft assigned for it has nothing chosen, and an empty draft
   * removes the entry, so the half-made turn was deleted a moment before the
   * real round number got to read it.
   */
  it("writes nothing while the screen does not yet know its round", () => {
    writeStoredChoices(storage, "G-1", draft(), CHOICES, 2);
    writeStoredChoices(storage, "G-1", draft({ roundNumber: 0 }), [], 0);

    expect(readStoredChoices(storage, "G-1", "P-1", 2)).toEqual(CHOICES);
  });

  /** The same, between a new round starting and its assignment arriving. */
  it("writes nothing while the draft is still the previous round's", () => {
    writeStoredChoices(storage, "G-1", draft(), CHOICES, 2);
    writeStoredChoices(storage, "G-1", draft({ roundNumber: 2 }), [], 3);

    expect(readStoredChoices(storage, "G-1", "P-1", 2)).toEqual(CHOICES);
  });

  it("does nothing at all without a seat", () => {
    writeStoredChoices(storage, "G-1", draft({ seatId: null }), CHOICES, 2);
    expect(storage._map.size).toBe(0);
  });
});

describe("clearStoredDraft", () => {
  it("takes the turn out of storage once it is submitted", () => {
    const storage = fakeStorage();
    writeStoredChoices(storage, "G-1", draft(), CHOICES, 2);
    clearStoredDraft(storage, "G-1", "P-1");
    expect(storage.getItem(draftStorageKey("G-1", "P-1"))).toBeNull();
  });
});

describe("pruneOtherGames", () => {
  /**
   * The retention answer: a device keeps unfinished turns for the game it is
   * playing and for no other. A phone that joins a new game drops the last
   * one's on the first write.
   */
  it("keeps every seat of this game and drops every other game's", () => {
    const storage = fakeStorage();
    writeStoredChoices(storage, "G-1", draft({ seatId: "P-1" }), CHOICES, 2);
    writeStoredChoices(storage, "G-1", draft({ seatId: "P-2" }), CHOICES, 2);
    writeStoredChoices(storage, "G-2", draft({ seatId: "P-9" }), CHOICES, 2);

    pruneOtherGames(storage, "G-1");

    expect([...storage._map.keys()].sort()).toEqual(
      [draftStorageKey("G-1", "P-1"), draftStorageKey("G-1", "P-2")].sort(),
    );
  });

  it("leaves keys that are not ours alone", () => {
    const storage = fakeStorage({ colorMode: "dark" });
    pruneOtherGames(storage, "G-1");
    expect(storage.getItem("colorMode")).toBe("dark");
  });
});

/**
 * Private mode, blocked site data, a full quota: the turn still has to be
 * playable. Every one of these throws inside, and none of it reaches the screen.
 */
describe("a storage that throws", () => {
  const storage = hostileStorage();

  it("reads as nothing", () => {
    expect(readStoredChoices(storage, "G-1", "P-1", 2)).toBeNull();
  });

  it("writes without throwing", () => {
    expect(() => writeStoredChoices(storage, "G-1", draft(), CHOICES, 2)).not.toThrow();
  });

  it("clears without throwing", () => {
    expect(() => clearStoredDraft(storage, "G-1", "P-1")).not.toThrow();
  });

  it("prunes without throwing", () => {
    expect(() => pruneOtherGames(storage, "G-1")).not.toThrow();
  });
});

/** No storage at all is the same as a storage that refuses. */
describe("no storage", () => {
  it("reads as nothing and writes nowhere", () => {
    expect(readStoredChoices(null, "G-1", "P-1", 2)).toBeNull();
    expect(() => writeStoredChoices(null, "G-1", draft(), CHOICES, 2)).not.toThrow();
    expect(() => clearStoredDraft(null, "G-1", "P-1")).not.toThrow();
    expect(() => pruneOtherGames(null, "G-1")).not.toThrow();
  });
});
