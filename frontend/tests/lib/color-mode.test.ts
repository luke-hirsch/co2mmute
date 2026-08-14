import { describe, expect, it } from "vitest";

import {
  COLOR_MODE_STORAGE_KEY,
  isColorMode,
  readStoredColorMode,
  resolveColorMode,
} from "@/lib/color-mode";

/** Just enough of Storage to read from; optionally one that throws. */
function storage(value: string | null, throws = false): Pick<Storage, "getItem"> {
  return {
    getItem: () => {
      if (throws) throw new Error("SecurityError");
      return value;
    },
  };
}

describe("isColorMode", () => {
  it("accepts the three the bootstrap script writes", () => {
    expect(["light", "dark", "system"].every(isColorMode)).toBe(true);
  });

  it("rejects anything else", () => {
    expect(isColorMode("Dark")).toBe(false);
    expect(isColorMode(null)).toBe(false);
    expect(isColorMode(1)).toBe(false);
  });
});

describe("readStoredColorMode", () => {
  it("reads the key the inline script uses", () => {
    expect(COLOR_MODE_STORAGE_KEY).toBe("colorMode");
  });

  it("returns a stored mode", () => {
    expect(readStoredColorMode(storage("dark"))).toBe("dark");
  });

  it("falls back to system when unset or junk", () => {
    expect(readStoredColorMode(storage(null))).toBe("system");
    expect(readStoredColorMode(storage("purple"))).toBe("system");
  });

  it("falls back to system when localStorage throws", () => {
    expect(readStoredColorMode(storage(null, true))).toBe("system");
  });
});

describe("resolveColorMode", () => {
  it("passes an explicit choice through, whatever the OS says", () => {
    expect(resolveColorMode("light", true)).toBe("light");
    expect(resolveColorMode("dark", false)).toBe("dark");
  });

  it("defers to the OS on system", () => {
    expect(resolveColorMode("system", true)).toBe("dark");
    expect(resolveColorMode("system", false)).toBe("light");
  });
});
