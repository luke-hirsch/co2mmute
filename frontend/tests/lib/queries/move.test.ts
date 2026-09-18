import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";
import { submitMove, type MovePayload } from "@/lib/queries/move";

/**
 * Submitting a turn.
 *
 * The hook around this is untestable here — vitest runs in node with no jsdom,
 * so `useMutation` has nowhere to render. What matters is testable without it:
 * the URL is built from the **seat**, not from "me", and the statuses the
 * backend answers with survive as an `ApiError` instead of being flattened into
 * a message. A paused game (409 `paused`, `game/pause.py`) is the case that
 * broke on the old screen, which showed "Netzwerkfehler" for it.
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

const payload: MovePayload = {
  agents: [
    {
      id: 1,
      transport_mode: "car",
      optimization: "time",
      route: {
        total_distance_m: 4200,
        estimated_time_min: 11.5,
        segments: [
          { edge_id: 101, start_node: 10, end_node: 20, mode: "car", pt_line_id: undefined },
        ],
      },
    },
  ],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("submitMove", () => {
  it("posts to the seat's move endpoint", async () => {
    const fetchSpy = stubFetch(jsonResponse(200, { success: true }));

    await submitMove("ABC123", "P-7", payload);

    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe("/api/game/ABC123/player/P-7/move/");
    expect(init?.method).toBe("POST");
    // The seat in the URL is what IsPlayerInGame checks against the cookie —
    // and, since 1.6, what lets the host play a seat at their own machine.
    expect(url).not.toContain("undefined");
  });

  it("wraps the routes in the action the backend switches on", async () => {
    const fetchSpy = stubFetch(jsonResponse(200, { success: true }));

    await submitMove("ABC123", "P-7", payload);

    const body = JSON.parse(String(fetchSpy.mock.calls[0][1]?.body));
    expect(body.action).toBe("route_submission");
    expect(body.payload).toEqual(payload);
  });

  it("keeps the reason on a paused game so the screen can say why", async () => {
    // game/views_rest.py: 409 + {"error": ..., "reason": "paused"}. P-03.
    stubFetch(jsonResponse(409, { error: "Game is paused", reason: "paused" }));

    const error = await submitMove("ABC123", "P-7", payload).catch((e) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(409);
    expect((error as ApiError).reason).toBe("paused");
  });

  it("keeps a validation failure readable", async () => {
    stubFetch(
      jsonResponse(400, {
        error: ["Agent 1 route must start from home node 10"],
      }),
    );

    const error = await submitMove("ABC123", "P-7", payload).catch((e) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(400);
    expect((error as ApiError).message).toContain("home node 10");
  });

  it("carries a 403 through rather than turning it into a generic failure", async () => {
    // Someone else's seat without a host session. The screen has to send them
    // to the join, not tell them the network is down.
    stubFetch(jsonResponse(403, { detail: "Not allowed." }));

    const error = await submitMove("ABC123", "P-9", payload).catch((e) => e);

    expect((error as ApiError).status).toBe(403);
  });
});
