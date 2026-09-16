/**
 * The one way the SPA talks to Django.
 *
 * The difference to the old `src/utils/api.ts` it replaces: a failed request
 * throws an `ApiError` that still carries the status code and the parsed body.
 * The old wrapper collapsed everything into `new Error(message)`, which is
 * unusable for the join flow — that endpoint answers 400, 403, 404 and 409 with
 * four different meanings and deliberately identical prose.
 *
 * No toasts, no React. Callers in `lib/queries/` decide what a failure looks
 * like.
 */

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/** Read a browser cookie by name. Returns null when it is not set. */
export function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = document.cookie.match(
    new RegExp(`(?:^|;)\\s*${escaped}\\s*=\\s*([^;]*)`),
  );
  return match ? decodeURIComponent(match[1]) : null;
}

export function csrfToken(): string {
  return readCookie("csrftoken") ?? "";
}

/**
 * Flatten a DRF error body into one line.
 *
 * DRF answers with `{"detail": "..."}`, `{"field": ["...", "..."]}`, a bare
 * array, or a bare string depending on where the error came from.
 */
export function apiErrorMessage(body: unknown): string | null {
  if (typeof body === "string") return body.trim() || null;
  if (Array.isArray(body)) return body.map(String).join(", ") || null;

  if (body && typeof body === "object") {
    const parts: string[] = [];
    for (const [key, value] of Object.entries(body)) {
      // `reason` is machine-readable state, not prose — see JoinBlockedReason.
      if (key === "reason") continue;
      const text = Array.isArray(value) ? value.map(String).join(", ") : String(value);
      if (!text) continue;
      parts.push(key === "detail" || key === "non_field_errors" ? text : `${key}: ${text}`);
    }
    return parts.join(" ") || null;
  }

  return null;
}

/** A non-2xx response. `status` and `body` survive, so callers can branch. */
export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, body: unknown, fallbackMessage: string) {
    super(apiErrorMessage(body) ?? fallbackMessage);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }

  /** The machine-readable `reason` some endpoints add next to `detail`. */
  get reason(): string | null {
    if (this.body && typeof this.body === "object" && "reason" in this.body) {
      const value = (this.body as { reason: unknown }).reason;
      return typeof value === "string" ? value : null;
    }
    return null;
  }
}

/** The request never reached the server, or the connection dropped. */
export class NetworkError extends Error {
  constructor(cause: unknown) {
    super("Network request failed");
    this.name = "NetworkError";
    this.cause = cause;
  }
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const method = (options.method ?? "GET").toUpperCase();
  const headers = new Headers(options.headers);

  if (options.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (UNSAFE_METHODS.has(method)) {
    headers.set("X-CSRFToken", csrfToken());
  }

  let response: Response;
  try {
    response = await fetch(path, {
      // Both player cookies and the host session ride on this.
      credentials: "include",
      ...options,
      method,
      headers,
    });
  } catch (cause) {
    throw new NetworkError(cause);
  }

  // 204 and friends have no body to parse.
  const raw = response.status === 204 ? "" : await response.text();
  let body: unknown = null;
  if (raw) {
    try {
      body = JSON.parse(raw);
    } catch {
      body = raw;
    }
  }

  if (!response.ok) {
    throw new ApiError(response.status, body, `HTTP ${response.status}`);
  }

  return body as T;
}
