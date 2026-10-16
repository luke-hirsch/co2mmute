/**
 * What the editor calls what it draws, and which names it won't save.
 *
 * A click names a node or an edge after its map, with a count of the map's
 * own, so a new map starts at 1 and not at the row's id, which runs on over
 * every map in the database. The count goes on from the highest the editor
 * gave on this map, so a row keeps its number when an earlier one is deleted.
 */

import { de } from "@/lib/de";

/** A name holds 100 characters (`Node.name`, `Edge.name`); the count needs room. */
const MAP_PART = 80;

export function defaultName(
  mapName: string,
  taken: Iterable<string | null | undefined>,
  nameOf: (map: string, n: number) => string,
): string {
  const map = mapName.slice(0, MAP_PART).trim();
  let highest = 0;
  for (const name of taken) {
    const n = Number(name?.match(/\d+$/)?.[0] ?? 0);
    if (n > highest && name === nameOf(map, n)) highest = n;
  }
  return nameOf(map, highest + 1);
}

/**
 * The names for what a version's diff draws, keyed by the temp ids, counted on
 * from the map's own the way a click in the base version does.
 */
export function nameNewRows(
  mapName: string,
  nodeNames: Iterable<string | null | undefined>,
  edgeNames: Iterable<string | null | undefined>,
  newNodeIds: string[],
  newEdgeIds: string[],
): { nodes: Record<string, string>; edges: Record<string, string> } {
  const give = (
    taken: Iterable<string | null | undefined>,
    ids: string[],
    nameOf: (map: string, n: number) => string,
  ) => {
    const names = [...taken];
    const out: Record<string, string> = {};
    for (const id of ids) {
      out[id] = defaultName(mapName, names, nameOf);
      names.push(out[id]);
    }
    return out;
  };
  return {
    nodes: give(nodeNames, newNodeIds, de.editor.node.defaultName),
    edges: give(edgeNames, newEdgeIds, de.editor.edge.defaultName),
  };
}

/** "Knoten 4587", "Callenberg Kante 3": a number where a name should be. */
const NUMBERED = /(^|\s)(knoten|kante|node|edge) \d+$/i;

/** A name nobody chose: empty, the editor's own, or the id shown for a row without one. */
export function isPlaceholderName(name: string): boolean {
  const named = name.trim();
  return named === "" || NUMBERED.test(named);
}
