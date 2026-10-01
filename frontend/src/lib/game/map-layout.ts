/**
 * Where the map sits on a large screen: beside the controls, or above them.
 *
 * The research group asked for beside (S24). A projector is a large screen as far
 * as Tailwind is concerned and beside is wrong there — a map half the width of a
 * beamer with a list the size of a book next to it — so it is a choice the person
 * at the screen makes, and the default is the layout that works everywhere. Below
 * `lg` the choice does not exist and the toggle is not drawn; the map is above.
 *
 * One device preference, shared by the round screen and the vote, and nothing
 * else: no name, no game, no seat. `template/legal/cookies.html` §3.4 says so.
 * Same shape as `draft-storage.ts` — the storage is an argument, so null and a
 * throwing one are ordinary inputs.
 */

export type MapLayout = "below" | "beside";

export const MAP_LAYOUT_KEY = "mapLayout";

export function readMapLayout(storage: Storage | null): MapLayout {
  try {
    return storage?.getItem(MAP_LAYOUT_KEY) === "beside" ? "beside" : "below";
  } catch {
    return "below";
  }
}

/** "below" is the default, so it is stored as nothing rather than as itself. */
export function writeMapLayout(storage: Storage | null, layout: MapLayout) {
  try {
    if (layout === "beside") storage?.setItem(MAP_LAYOUT_KEY, "beside");
    else storage?.removeItem(MAP_LAYOUT_KEY);
  } catch {
    // Blocked storage: the choice lasts until the page does.
  }
}
