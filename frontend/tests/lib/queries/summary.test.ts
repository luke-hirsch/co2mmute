import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";
import { fetchSummary } from "@/lib/queries/summary";

/**
 * `GET api/game/<game_id>/summary/` — the only request the end screen makes.
 *
 * The path is worth a test of its own: `game/urls.py` ordering is load-bearing,
 * and `<str:game_id>/<str:player_id>/` sits at the bottom of it swallowing any
 * two-segment path. A summary URL typed one segment wrong therefore does not
 * 404 — it lands in `GetYourOwnGame` and comes back as a plausible 403.
 *
 * And the failure has to survive as an `ApiError`: the screen distinguishes
 * "the game had no completed rounds" (an empty list, which is a real answer)
 * from "the request failed" (which is not), and it can only do that if the
 * status is still there when it arrives.
 */

function jsonResponse(status: number, body: unknown) {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubFetch(response: Response) {
  const spy = vi.fn<typeof fetch>(() => Promise.resolve(response));
  vi.stubGlobal("fetch", spy);
  return spy;
}

const payload = {
  game_id: "ABC123",
  game_name: "5b",
  end_reason: "co2_limit",
  rounds_played: 2,
  max_rounds: 3,
  total_co2_kg: 1240,
  max_co2_kg: 1000,
  players: [
    {
      player_id: "P-1",
      name: "Mira",
      total_co2_kg: 180,
      total_cost_eur: 4.2,
      total_time_min: 96,
      modes_used: ["bike", "walk"],
      rounds: [{ round_number: 1, co2_kg: 100, cost_eur: 2.2, time_min: 50 }],
    },
  ],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchSummary", () => {
  it("gets the game's summary", async () => {
    const fetchSpy = stubFetch(jsonResponse(200, payload));

    const summary = await fetchSummary("ABC123");

    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe("/api/game/ABC123/summary/");
    expect(init?.method ?? "GET").toBe("GET");
    expect(summary.players[0].name).toBe("Mira");
    expect(summary.total_co2_kg).toBe(1240);
  });

  it("keeps the status on a failure", async () => {
    // A player whose game cookie has expired gets a 403 here, and that is a
    // different screen from a 404. `apiFetch` is what makes the difference
    // survive; the old utils/api.ts flattened both into one Error.
    stubFetch(jsonResponse(403, { detail: "You do not have access." }));

    // One assertion, because a Response body can only be read once and the
    // stub hands back the same object every call.
    const error = await fetchSummary("ABC123").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(403);
  });

  it("reads a game that ended before anybody completed a round", async () => {
    // `rounds_played: 0` with an empty player list is a real answer, not an
    // error: the host ended the game during round 1. The screen has to be
    // able to tell it apart from a failed request.
    stubFetch(
      jsonResponse(200, { ...payload, rounds_played: 0, players: [] }),
    );

    const summary = await fetchSummary("ABC123");

    expect(summary.players).toEqual([]);
    expect(summary.rounds_played).toBe(0);
  });
});
