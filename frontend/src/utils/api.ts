export function csrf(): string {
  return (
    document.cookie.match("(^|;)\\s*csrftoken\\s*=\\s*([^;]+)")?.pop() ?? ""
  );
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
    (opts.headers as any)["X-CSRFToken"] = csrf();
  }

  const res = await fetch(url, opts);

  if (res.status === 401) {
    throw new Error("unauthenticated");
  }

  return res.json().catch(() => ({}));
}
