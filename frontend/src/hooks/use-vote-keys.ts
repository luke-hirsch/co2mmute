import { useEffect } from "react";

import { keyBelongsElsewhere, voteForKey } from "@/lib/game/vote-keys";
import type { VoteOption } from "@/lib/game/events";

/**
 * Calls `onKey` for a plain key press that is not meant for something else. A
 * held key counts once, and any modifier means the press is a browser shortcut.
 */
function useKeyDown(onKey: (key: string) => boolean, disabled: boolean) {
  useEffect(() => {
    if (disabled) return;

    function onKeyDown(event: KeyboardEvent) {
      if (event.repeat || event.defaultPrevented) return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (keyBelongsElsewhere(event.target)) return;
      if (onKey(event.key)) event.preventDefault();
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onKey, disabled]);
}

/**
 * Listens for the vote keys while a ballot is on screen. See `vote-keys.ts` for
 * why they exist.
 */
export function useVoteKeys(
  options: readonly VoteOption[],
  onPick: (versionId: number | null) => void,
  disabled: boolean,
) {
  useKeyDown((key) => {
    const pick = voteForKey(key, options);
    if (pick === undefined) return false;
    onPick(pick);
    return true;
  }, disabled);
}

/** The tie vote, same reasoning: `1` votes again, `0` leaves the map as it is. */
export function useTieKeys(onAnswer: (revote: boolean) => void, disabled: boolean) {
  useKeyDown((key) => {
    if (key !== "1" && key !== "0") return false;
    onAnswer(key === "1");
    return true;
  }, disabled);
}
