import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";
import {
  addSeat,
  issueSeatCode,
  lookUpSeatCode,
  redeemSeatCode,
  removeSeat,
  takeOverSeat,
} from "@/lib/queries/seats";

/**
 * The seat endpoints from 1.6 and 1.7, without React.
 *
 * Two things are worth pinning here. The URLs: `game/urls.py` ordering is
 * load-bearing on the backend, and a path typed one segment wrong does not 404
 * — it lands in `GetYourOwnGame` and comes back as a plausible 403. And the
 * refusals: every one of these endpoints answers 409 with a machine-readable
 * `reason`, and the screens branch on it, so it has to survive the throw.
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

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("addSeat", () => {
  it("posts the name to the game's player list", async () => {
    const fetchSpy = stubFetch(jsonResponse(201, { player_id: "P-9", name: "Ben" }));

    await addSeat("ABC123", "Ben");

    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe("/api/game/ABC123/player/");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual({ name: "Ben" });
  });

  it("keeps the reason when the game is full", async () => {
    stubFetch(jsonResponse(409, { detail: "Cannot add a seat.", reason: "full" }));

    const error = await addSeat("ABC123", "Ben").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(409);
    expect((error as ApiError).reason).toBe("full");
  });
});

describe("removeSeat", () => {
  it("deletes the seat", async () => {
    const fetchSpy = stubFetch(new Response(null, { status: 204 }));

    await removeSeat("ABC123", "P-9");

    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe("/api/game/ABC123/player/P-9/");
    expect(init?.method).toBe("DELETE");
  });
});

describe("takeOverSeat", () => {
  it("posts to the seat's takeover endpoint", async () => {
    const fetchSpy = stubFetch(jsonResponse(200, { player_id: "P-NEW" }));

    await takeOverSeat("ABC123", "P-9");

    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe("/api/game/ABC123/player/P-9/takeover/");
    expect(init?.method).toBe("POST");
  });

  it("keeps the reason when the host already plays the seat", async () => {
    stubFetch(jsonResponse(409, { detail: "…", reason: "controlled" }));

    const error = await takeOverSeat("ABC123", "P-9").catch((e: unknown) => e);

    expect((error as ApiError).reason).toBe("controlled");
  });
});

describe("issueSeatCode", () => {
  it("posts to the seat's code endpoint", async () => {
    const fetchSpy = stubFetch(jsonResponse(201, { code: "4F2A9C", expires_in: 300 }));

    const issued = await issueSeatCode("ABC123", "P-9");

    expect(fetchSpy.mock.calls[0][0]).toBe("/api/game/ABC123/player/P-9/code/");
    expect(issued.code).toBe("4F2A9C");
    expect(issued.expires_in).toBe(300);
  });

  it("carries a qr_url when the backend renders one", async () => {
    // Optional on purpose: the QR is a small backend guide of its own
    // (`[backend]-seat-code-qr.md`), and this screen ships before it.
    stubFetch(
      jsonResponse(201, {
        code: "4F2A9C",
        expires_in: 300,
        qr_url: "/media/seat_codes/4F2A9C.png",
      }),
    );

    const issued = await issueSeatCode("ABC123", "P-9");

    expect(issued.qr_url).toBe("/media/seat_codes/4F2A9C.png");
  });

  it("has no qr_url when the backend does not send one", async () => {
    stubFetch(jsonResponse(201, { code: "4F2A9C", expires_in: 300 }));

    const issued = await issueSeatCode("ABC123", "P-9");

    expect(issued.qr_url).toBeUndefined();
  });
});

describe("lookUpSeatCode", () => {
  it("asks before using the code up", async () => {
    const fetchSpy = stubFetch(
      jsonResponse(200, { game_id: "ABC123", game_name: "Spiel", player_name: "Ana" }),
    );

    const seat = await lookUpSeatCode("4f2a9c");

    const [url, init] = fetchSpy.mock.calls[0];
    // Lower case off a phone keyboard, and a stray space off a projector.
    expect(url).toBe("/api/game/seat/4F2A9C/");
    expect(init?.method ?? "GET").toBe("GET");
    expect(seat.player_name).toBe("Ana");
  });

  it("trims what was typed", async () => {
    const fetchSpy = stubFetch(jsonResponse(200, {}));

    await lookUpSeatCode("  4F2A9C ");

    expect(fetchSpy.mock.calls[0][0]).toBe("/api/game/seat/4F2A9C/");
  });
});

describe("redeemSeatCode", () => {
  it("posts to the same path", async () => {
    const fetchSpy = stubFetch(
      jsonResponse(200, { game_id: "ABC123", player_id: "P-NEW", name: "Ana" }),
    );

    const seat = await redeemSeatCode("4F2A9C");

    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe("/api/game/seat/4F2A9C/");
    expect(init?.method).toBe("POST");
    expect(seat.player_id).toBe("P-NEW");
  });

  it("keeps 404 apart from 409", async () => {
    // 404 is "this code is gone" (expired, or already used). 409 is "not from
    // here" — the host's own browser, or one that already holds a seat. The
    // screen says something different for each.
    stubFetch(jsonResponse(404, { detail: "This code is not valid (any more)." }));
    const gone = await redeemSeatCode("4F2A9C").catch((e: unknown) => e);
    expect((gone as ApiError).status).toBe(404);
    expect((gone as ApiError).reason).toBeNull();

    stubFetch(jsonResponse(409, { detail: "…", reason: "seated" }));
    const refused = await redeemSeatCode("4F2A9C").catch((e: unknown) => e);
    expect((refused as ApiError).status).toBe(409);
    expect((refused as ApiError).reason).toBe("seated");
  });
});
