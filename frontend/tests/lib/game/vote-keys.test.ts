import { describe, expect, it } from "vitest";

import { keyBelongsElsewhere, voteForKey } from "@/lib/game/vote-keys";
import type { VoteOption } from "@/lib/game/events";

const options = [{ id: 11 }, { id: 42 }] as VoteOption[];

describe("voteForKey", () => {
  it("maps 1 and 2 to the options in the order they are printed", () => {
    expect(voteForKey("1", options)).toBe(11);
    expect(voteForKey("2", options)).toBe(42);
  });

  it("maps 0 to leaving the map as it is, which is null and not nothing", () => {
    expect(voteForKey("0", options)).toBeNull();
  });

  it("ignores a number with no option behind it", () => {
    expect(voteForKey("3", options)).toBeUndefined();
    expect(voteForKey("9", [])).toBeUndefined();
  });

  it("ignores everything that is not a single digit", () => {
    for (const key of ["a", "Enter", "10", " ", "-", "٣"]) {
      expect(voteForKey(key, options), key).toBeUndefined();
    }
  });
});

describe("keyBelongsElsewhere", () => {
  /** Answers `closest` the way the DOM would, for one selector fragment. */
  const within = (...inside: string[]) =>
    ({
      closest: (selector: string) =>
        inside.some((part) => selector.includes(part)) ? {} : null,
    }) as unknown as EventTarget;

  it("is false without an element to ask", () => {
    expect(keyBelongsElsewhere(null)).toBe(false);
    expect(keyBelongsElsewhere(within())).toBe(false);
  });

  it("is true inside a field, so the chat can take a digit", () => {
    expect(keyBelongsElsewhere(within("textarea"))).toBe(true);
  });

  it("is true inside a dialog, so the explainer is not voted through", () => {
    expect(keyBelongsElsewhere(within("[role='dialog']"))).toBe(true);
  });
});
