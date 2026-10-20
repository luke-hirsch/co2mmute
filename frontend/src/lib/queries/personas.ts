/**
 * `GET api/game/personas/` — the standard Pendlertypen the create form offers.
 *
 * The rows without a game (`StandardPersonasView`). A host's own Pendlertyp is
 * a copy in the game it was written for and is not offered again. Read once:
 * they change in the admin, not while a host fills in a form.
 */

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { Persona } from "@/lib/game/personas";

export const personaKeys = {
  standard: ["personas", "standard"] as const,
};

export function useStandardPersonas(enabled: boolean) {
  return useQuery({
    queryKey: personaKeys.standard,
    queryFn: () => apiFetch<Persona[]>("/api/game/personas/"),
    enabled,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
}

/** A Pendlertyp of one game and how many Gruppen hold it (`PersonasInPlayView`). */
export type PersonaInPlay = { id: number; name: string; groups: number };

/**
 * `GET api/game/<id>/pendlertypen/` — who is in play, as counts.
 *
 * The dealing happens at join, so the answer changes when the room does: the
 * seat count is in the key, which is how it follows the roster without a poll
 * or a refetch from a socket callback.
 */
export function usePersonasInPlay(gameId: string, seatCount: number) {
  return useQuery({
    queryKey: ["game", gameId, "pendlertypen", seatCount] as const,
    queryFn: () =>
      apiFetch<PersonaInPlay[]>(`/api/game/${gameId}/pendlertypen/`),
    enabled: gameId.length > 0,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    retry: false,
  });
}

