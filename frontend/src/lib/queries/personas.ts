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
