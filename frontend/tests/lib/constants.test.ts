import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import * as constants from "@/lib/constants";

/**
 * `lib/constants.ts` copies numbers the backend owns. This reads
 * `backend/sim/constants.py` as text and names the copy that drifted, the way
 * `tokens.test.ts` does for the design tokens. A name is checked when the
 * Python file has a plain `NAME = number` line for it; the names in
 * `ONLY_HERE` have no twin.
 */
const PY = fileURLToPath(
  new URL("../../../backend/sim/constants.py", import.meta.url),
);

/** Copies whose value is knowingly not the Python one: `name: reason`. */
const KNOWN_DIFFERENCES: Record<string, string> = {};

const ONLY_HERE = ["MAX_WALK_M", "MAX_BIKE_M", "PT_MAX_WALK_DISTANCE_M"];

function pythonNumbers(): Map<string, number> {
  const found = new Map<string, number>();
  const line = /^([A-Z][A-Z0-9_]*)\s*=\s*(-?[0-9][0-9_]*(?:\.[0-9]+)?)\s*(?:#.*)?$/gm;
  for (const m of readFileSync(PY, "utf8").matchAll(line)) {
    found.set(m[1], Number(m[2].replaceAll("_", "")));
  }
  return found;
}

describe("lib/constants.ts against backend/sim/constants.py", () => {
  const python = pythonNumbers();
  const names = Object.keys(constants).filter(
    (name) => !ONLY_HERE.includes(name) && !(name in KNOWN_DIFFERENCES),
  );

  it("finds the numbers it compares", () => {
    expect(python.size).toBeGreaterThan(20);
    expect(names.length).toBeGreaterThan(10);
  });

  it.each(names)("%s is the backend's number", (name) => {
    expect(python.has(name), `${name} is not a plain number in sim/constants.py`).toBe(
      true,
    );
    expect((constants as Record<string, number>)[name]).toBe(python.get(name));
  });
});
