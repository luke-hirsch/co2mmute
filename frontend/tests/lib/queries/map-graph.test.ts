import { describe, expect, it } from "vitest";

import { mapKeys, trafficAfter } from "@/lib/queries/map-graph";

/**
 * The graph's cache key.
 *
 * The graph is identical for every game on a map version and is cached for ever
 * on the client and for an hour on the server. Last round's observed speeds ride
 * along with it and are neither: they belong to one game and change every round.
 *
 * So the key has to carry both, and the round is the subtle one — it is in the
 * key but not in the URL, because the backend always serves the *last completed*
 * round for the game. Leave it out and `staleTime: Infinity` hands round 3 the
 * jams round 1 drove on, which looks exactly like the feature working.
 */

describe("the graph cache key", () => {
  it("separates two versions of one map", () => {
    expect(mapKeys.graph(1, 7)).not.toEqual(mapKeys.graph(1, 8));
  });

  it("separates two games on the same map version", () => {
    const a = mapKeys.graph(1, 7, { gameId: "aaa", roundNumber: 2 });
    const b = mapKeys.graph(1, 7, { gameId: "bbb", roundNumber: 2 });
    expect(a).not.toEqual(b);
  });

  it("separates two rounds of one game, so the traffic is refetched", () => {
    const first = mapKeys.graph(1, 7, { gameId: "aaa", roundNumber: 1 });
    const second = mapKeys.graph(1, 7, { gameId: "aaa", roundNumber: 2 });
    expect(first).not.toEqual(second);
  });

  it("is stable for the same version, game and round", () => {
    const traffic = { gameId: "aaa", roundNumber: 2 };
    expect(mapKeys.graph(1, 7, traffic)).toEqual(mapKeys.graph(1, 7, traffic));
  });

  it("keeps a trafficless read — the editor and the detail page — out of the way", () => {
    // They pass no game, so they share one cached graph per version however many
    // games are running on it.
    expect(mapKeys.graph(1, 7)).toEqual(mapKeys.graph(1, 7, null));
  });
});

describe("the traffic for the screens between two rounds", () => {
  it("is what the next round's screen asks for", () => {
    expect(mapKeys.graph(1, 7, trafficAfter("aaa", 1))).toEqual(
      mapKeys.graph(1, 7, { gameId: "aaa", roundNumber: 2 }),
    );
  });

  it("is not what the round just played asked for while it ran", () => {
    // That entry was filled before the round finished: it holds the round
    // before's speeds, and after round 1 none at all.
    expect(mapKeys.graph(1, 7, trafficAfter("aaa", 1))).not.toEqual(
      mapKeys.graph(1, 7, { gameId: "aaa", roundNumber: 1 }),
    );
  });
});
