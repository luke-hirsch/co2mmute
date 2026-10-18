/**
 * `/app/game/create?study=<pk>`: "Neues Spiel" on a study page. The form puts
 * the new game into that study; anything that is not a pk is dropped, and the
 * form ignores it for a host who is not staff or with the study app off.
 */
export function createSearch(search: Record<string, unknown>): {
  study?: number;
} {
  const study = Number(search.study);
  return Number.isInteger(study) && study > 0 ? { study } : {};
}
