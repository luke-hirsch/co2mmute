import type { VoteOption } from "@/lib/game/events";

/**
 * Voting by keyboard (S24): `1`, `2`, … for the options in the order they are
 * printed, `0` for "so lassen".
 *
 * The reason is not convenience. A mouse crossing a projected screen towards one
 * card tells the room how you are about to vote; a key press does not.
 *
 * Answers `undefined` for a key that is not a vote — which is not the same as
 * `null`, the vote for leaving the map as it is.
 */
export function voteForKey(
  key: string,
  options: readonly VoteOption[],
): number | null | undefined {
  if (key === "0") return null;
  if (!/^[1-9]$/.test(key)) return undefined;
  return options[Number(key) - 1]?.id;
}

/**
 * Whether a key press belongs to something else: a field being typed into (the
 * chat dock is on every game screen), or a dialog that is open over the ballot.
 */
export function keyBelongsElsewhere(target: EventTarget | null): boolean {
  // Duck-typed: the tests run in node, where there is no `Element` to test for.
  const element = target as Partial<Element> | null;
  if (typeof element?.closest !== "function") return false;
  if (element.closest("input, textarea, select, [contenteditable='true']")) {
    return true;
  }
  return element.closest("[role='dialog']") !== null;
}
