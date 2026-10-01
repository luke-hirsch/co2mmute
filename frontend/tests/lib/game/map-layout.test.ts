import { describe, expect, it } from "vitest";

import {
  MAP_LAYOUT_KEY,
  readMapLayout,
  writeMapLayout,
} from "@/lib/game/map-layout";

function memory(initial: Record<string, string> = {}): Storage {
  const data = new Map(Object.entries(initial));
  return {
    get length() {
      return data.size;
    },
    clear: () => data.clear(),
    getItem: (key) => data.get(key) ?? null,
    key: (index) => [...data.keys()][index] ?? null,
    removeItem: (key) => void data.delete(key),
    setItem: (key, value) => void data.set(key, String(value)),
  };
}

describe("map layout", () => {
  it("is below the map until somebody says otherwise", () => {
    // A projector is a large screen to Tailwind and the one place beside is
    // wrong, so the default is the layout that works everywhere.
    expect(readMapLayout(memory())).toBe("below");
  });

  it("remembers beside", () => {
    const storage = memory();
    writeMapLayout(storage, "beside");
    expect(readMapLayout(storage)).toBe("beside");
  });

  it("goes back to below by removing the entry, not by storing it", () => {
    const storage = memory();
    writeMapLayout(storage, "beside");
    writeMapLayout(storage, "below");
    expect(storage.getItem(MAP_LAYOUT_KEY)).toBeNull();
  });

  it("reads anything it does not know as below", () => {
    expect(readMapLayout(memory({ [MAP_LAYOUT_KEY]: "left" }))).toBe("below");
  });

  it("takes no storage at all", () => {
    expect(readMapLayout(null)).toBe("below");
    expect(() => writeMapLayout(null, "beside")).not.toThrow();
  });

  it("survives a storage that throws", () => {
    const broken = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
      removeItem: () => {
        throw new Error("blocked");
      },
    } as unknown as Storage;
    expect(readMapLayout(broken)).toBe("below");
    expect(() => writeMapLayout(broken, "beside")).not.toThrow();
  });
});
