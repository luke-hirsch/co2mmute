import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  NetworkError,
  apiErrorMessage,
  apiFetch,
  csrfToken,
  readCookie,
} from "@/lib/api";

/** A minimal Response stand-in — node has fetch, but not a server to call. */
function jsonResponse(status: number, body: unknown) {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Typed as `fetch` so `spy.mock.calls[0][1]` is a RequestInit, not `never`. */
function stubFetch(response: Response | Error) {
  const spy = vi.fn<typeof fetch>(() =>
    response instanceof Error ? Promise.reject(response) : Promise.resolve(response),
  );
  vi.stubGlobal("fetch", spy);
  return spy;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("readCookie", () => {
  it("returns null when there is no document at all", () => {
    expect(readCookie("csrftoken")).toBeNull();
  });

  it("reads a value from the middle of the cookie string", () => {
    vi.stubGlobal("document", { cookie: "a=1; csrftoken=abc123; b=2" });
    expect(readCookie("csrftoken")).toBe("abc123");
  });

  it("does not match a cookie whose name merely ends with the query", () => {
    vi.stubGlobal("document", { cookie: "xcsrftoken=wrong" });
    expect(readCookie("csrftoken")).toBeNull();
  });

  it("decodes percent-encoded values", () => {
    vi.stubGlobal("document", { cookie: "player_ABC=abc%3A1s2t3u" });
    expect(readCookie("player_ABC")).toBe("abc:1s2t3u");
  });

  it("csrfToken falls back to an empty string", () => {
    vi.stubGlobal("document", { cookie: "" });
    expect(csrfToken()).toBe("");
  });
});

describe("apiErrorMessage", () => {
  it("unwraps DRF's detail key without labelling it", () => {
    expect(apiErrorMessage({ detail: "Incorrect password." })).toBe(
      "Incorrect password.",
    );
  });

  it("labels field errors and joins the list", () => {
    expect(apiErrorMessage({ name: ["This field may not be blank.", "Too long."] })).toBe(
      "name: This field may not be blank., Too long.",
    );
  });

  it("skips the machine-readable reason key", () => {
    expect(
      apiErrorMessage({ detail: "Cannot join this session.", reason: "full" }),
    ).toBe("Cannot join this session.");
  });

  it("returns null when there is nothing human-readable", () => {
    expect(apiErrorMessage({})).toBeNull();
    expect(apiErrorMessage(null)).toBeNull();
    expect(apiErrorMessage("  ")).toBeNull();
  });
});

describe("apiFetch", () => {
  it("parses a JSON body on success", async () => {
    stubFetch(jsonResponse(200, { game_id: "ABCDE", joinable: true }));
    await expect(apiFetch("/api/game/lookup/ABCDE/")).resolves.toEqual({
      game_id: "ABCDE",
      joinable: true,
    });
  });

  it("sends cookies, so the signed player cookie rides along", async () => {
    const spy = stubFetch(jsonResponse(200, {}));
    await apiFetch("/api/game/ABCDE/lobby/");
    expect(spy.mock.calls[0][1]).toMatchObject({ credentials: "include" });
  });

  it("adds CSRF and a JSON content type on POST", async () => {
    vi.stubGlobal("document", { cookie: "csrftoken=tok" });
    const spy = stubFetch(jsonResponse(201, {}));

    await apiFetch("/api/game/join/ABCDE/", {
      method: "post",
      body: JSON.stringify({ name: "Alex" }),
    });

    const init = spy.mock.calls[0][1] as RequestInit;
    const headers = init.headers as Headers;
    expect(init.method).toBe("POST");
    expect(headers.get("X-CSRFToken")).toBe("tok");
    expect(headers.get("Content-Type")).toBe("application/json");
  });

  it("does not add CSRF on GET", async () => {
    vi.stubGlobal("document", { cookie: "csrftoken=tok" });
    const spy = stubFetch(jsonResponse(200, {}));

    await apiFetch("/api/game/lookup/ABCDE/");

    const headers = (spy.mock.calls[0][1] as RequestInit).headers as Headers;
    expect(headers.has("X-CSRFToken")).toBe(false);
  });

  it("keeps the status code, so the join screen can tell 403 from 409", async () => {
    stubFetch(jsonResponse(403, { detail: "Incorrect password." }));

    const error = await apiFetch("/api/game/join/ABCDE/", { method: "POST" }).catch(
      (e: unknown) => e,
    );

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(403);
    expect((error as ApiError).message).toBe("Incorrect password.");
  });

  it("exposes the reason a 409 carries", async () => {
    stubFetch(jsonResponse(409, { detail: "Cannot join this session.", reason: "full" }));

    const error = (await apiFetch("/api/game/join/ABCDE/", { method: "POST" }).catch(
      (e: unknown) => e,
    )) as ApiError;

    expect(error.status).toBe(409);
    expect(error.reason).toBe("full");
  });

  it("has no reason when the body does not carry one", async () => {
    stubFetch(jsonResponse(404, { detail: "No session found with that ID." }));

    const error = (await apiFetch("/api/game/lookup/ZZZZZ/").catch(
      (e: unknown) => e,
    )) as ApiError;

    expect(error.reason).toBeNull();
  });

  it("falls back to the status when the body is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response("<html>502</html>", { status: 502 }))),
    );

    const error = (await apiFetch("/api/game/ABCDE/").catch((e: unknown) => e)) as ApiError;

    expect(error.status).toBe(502);
    expect(error.body).toBe("<html>502</html>");
  });

  it("returns null for a 204 rather than blowing up on an empty body", async () => {
    stubFetch(new Response(null, { status: 204 }));
    await expect(apiFetch("/api/game/ABCDE/player/1/")).resolves.toBeNull();
  });

  it("wraps a dropped connection in NetworkError", async () => {
    stubFetch(new TypeError("Failed to fetch"));
    await expect(apiFetch("/api/game/lookup/ABCDE/")).rejects.toBeInstanceOf(NetworkError);
  });
});
