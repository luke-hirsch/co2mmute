export function csrf(): string {
  return (
    document.cookie.match("(^|;)\\s*csrftoken\\s*=\\s*([^;]+)")?.pop() ?? ""
  );
}

/**
 * Extract a human-readable message from a DRF error response body.
 * Handles objects like { field: ["msg"] }, arrays ["msg"], or plain strings.
 */
export function formatApiError(body: unknown): string {
  if (typeof body === "string") return body;

  if (Array.isArray(body)) {
    return body.join(", ");
  }

  if (body && typeof body === "object") {
    const parts: string[] = [];
    for (const [key, val] of Object.entries(body)) {
      const msg = Array.isArray(val) ? val.join(", ") : String(val);
      parts.push(key === "non_field_errors" || key === "detail" ? msg : `${key}: ${msg}`);
    }
    return parts.join(". ");
  }

  return "Unknown error";
}

// A fetch wrapper that adds credentials and CSRF on unsafe methods
export async function apiFetch(url: string, options: RequestInit = {}) {
  const opts: RequestInit = {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  };

  if (opts.method && opts.method.toUpperCase() !== "GET") {
    (opts.headers as Record<string, string>)["X-CSRFToken"] = csrf();
  }

  const res = await fetch(url, opts);

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const message = formatApiError(body);
    throw new Error(message);
  }

  return res.json().catch(() => ({}));
}
