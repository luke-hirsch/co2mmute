/**
 * Who this browser is, for one game.
 *
 * `GET api/whoami/?game_id=<id>` is the only identity call the SPA has, and it
 * answers for both auth systems at once: a host is a Django user with a
 * session, a player is two signed cookies and no account at all. The screens
 * never ask "am I logged in" — they ask this.
 *
 * Calling it also **renews both player cookies** (`WhoAmIView._renew_cookies`,
 * 1.6). That is why the lobby calls it on mount rather than reading the cookie
 * itself: a phone left lying around over a lesson break stays in the game
 * because someone asked this question.
 *
 * Replaces `hooks/useSession.ts` for new screens. The old hook keeps the legacy
 * ones alive until they go.
 */

import { useQuery } from "@tanstack/react-query";

import { ApiError, apiFetch } from "@/lib/api";

export type IdentityKind = "host" | "player" | "user" | "anonymous";

export type Identity = {
  kind: IdentityKind;
  authenticated: boolean;
  gameId?: string;
  player?: { playerId: string; name: string };
  username?: string;
  firstName?: string;
  lastName?: string;
};

const ANONYMOUS: Identity = { kind: "anonymous", authenticated: false };

async function fetchIdentity(gameId?: string): Promise<Identity> {
  const path = gameId
    ? `/api/whoami/?game_id=${encodeURIComponent(gameId)}`
    : "/api/whoami/";
  try {
    return await apiFetch<Identity>(path);
  } catch (error) {
    // Anonymous is a state, not a failure: the endpoint answers 401 for a
    // browser with no session and no player cookie, which is exactly what a
    // player looks like one moment before they join.
    if (error instanceof ApiError && error.status === 401) return ANONYMOUS;
    throw error;
  }
}

export function useIdentity(gameId?: string) {
  return useQuery({
    queryKey: ["identity", gameId ?? null],
    queryFn: () => fetchIdentity(gameId),
    staleTime: 60_000,
    retry: false,
  });
}

/** The host leads the game; a player holds a seat in it. */
export function isHost(identity: Identity | undefined): boolean {
  return identity?.kind === "host";
}

/** The `player_id` of the seat this browser holds, if it holds one. */
export function seatId(identity: Identity | undefined): string | null {
  return identity?.player?.playerId ?? null;
}
