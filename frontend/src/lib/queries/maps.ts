/**
 * The maps a host can start a game on.
 *
 * `GET api/maps/` is `GameMapListView`, which is `IsStaffOrReadOnly` — reading
 * it needs no account at all. The create screen is behind a login anyway; the
 * point here is that a host who is not staff can still see the list, which is
 * the common case (uploading a map needs `is_staff`, playing on one does not).
 *
 * Four fields on a row matter to the create screen and to nothing else in the
 * SPA:
 *
 * - `district_commuters` and `co2_budget_kg_per_round` are the calibration, and
 *   they are per map because they are properties of a *graph* — how much
 *   traffic its corridors carry, and what a playable round costs on its
 *   distances and its timetable. `lib/calibration.ts` derives the two offered
 *   numbers from them.
 * - `calibrated` says whether that pair was measured on this map (S21). Every
 *   map starts at Berlin Mitte-West's, and the pair alone cannot tell the one
 *   map it was measured on from a small one that inherited it — so the screen
 *   warns on the flag, never on the numbers.
 * - `offers_map_changes` is whether a game on this map can ever reach a ballot.
 *   A single-version map removes the discussion and the vote from the whole
 *   game silently, and the select is the last place a host can change their
 *   mind — so it says so. The Django form put the same fact inside the option
 *   label; a flag lets the screen put the sentence where it belongs.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";

export type GameMapRow = {
  id: number;
  name: string;
  district_commuters: number;
  co2_budget_kg_per_round: number;
  calibrated: boolean;
  offers_map_changes: boolean;
};

export const mapKeys = {
  list: () => ["maps", "list"] as const,
};

export function useGameMaps() {
  return useQuery({
    queryKey: mapKeys.list(),
    queryFn: () => apiFetch<GameMapRow[]>("/api/maps/"),
    // Maps are uploaded by hand, minutes apart at the fastest. Refetching this
    // while a host fills in a form would only move the select under them.
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
}

/**
 * `POST api/maps/import/` — a map file in, a new map out (S19).
 *
 * Always a *new* map: the importer never overwrites one, because
 * `GameSession.game_map` would take the games with it. Invalidates `["maps"]`,
 * which covers this module's list key and `map-graph.ts`'s alike.
 */
export function useImportMap() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: FormData) =>
      apiFetch<{ id: number }>("/api/maps/import/", { method: "POST", body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["maps"] }),
  });
}
