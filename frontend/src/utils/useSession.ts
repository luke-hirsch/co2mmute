import { useQuery } from "@tanstack/react-query";
import { API_BASE_URL } from "../config";
export type SessionKind = "host" | "anonymous" | "player" | "user";

import type { Auth } from "../types/types";

const ANONYMOUS_AUTH: Auth = {
  kind: "anonymous",
  authenticated: false,
};

async function fetchSession(gameId?: string): Promise<Auth> {
  const url = new URL(`${API_BASE_URL}/api/whoami/`);
  if (gameId) {
    url.searchParams.append("game_id", gameId);
  }

  const res = await fetch(url.toString(), {
    credentials: "include",
    headers: {
      Accept: "application/json",
    },
  });

  // Anonymous is a *state*, not an error
  if (res.status === 401) {
    return ANONYMOUS_AUTH;
  }

  if (!res.ok) {
    throw new Error(`whoami failed with ${res.status}`);
  }

  return res.json();
}

export function useSession(gameId?: string) {
  return useQuery<Auth>({
    queryKey: ["session", gameId],
    queryFn: () => fetchSession(gameId),
    staleTime: 60_000,
    refetchOnWindowFocus: true,
    retry: false,
  });
}
