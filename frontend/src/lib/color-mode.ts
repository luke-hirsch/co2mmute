/**
 * The app's colour mode, as the inline bootstrap script in index.html already
 * implements it: a `colorMode` entry in localStorage, resolved against the OS
 * preference, applied as a `dark` class on <html>.
 *
 * This module is the typed reader for that. It does not own the toggle — the
 * script runs before React mounts, which is what stops the page flashing white.
 * `next-themes` would be a second writer for the same class and is deliberately
 * not used.
 */

export type ColorMode = "light" | "dark" | "system";
export type ResolvedColorMode = "light" | "dark";

export const COLOR_MODE_STORAGE_KEY = "colorMode";
export const DARK_CLASS = "dark";

const MODES: readonly string[] = ["light", "dark", "system"];

export function isColorMode(value: unknown): value is ColorMode {
  return typeof value === "string" && MODES.includes(value);
}

/** Falls back to "system" for a missing, malformed or unreadable entry. */
export function readStoredColorMode(storage: Pick<Storage, "getItem">): ColorMode {
  let stored: string | null;
  try {
    stored = storage.getItem(COLOR_MODE_STORAGE_KEY);
  } catch {
    // Safari in private mode throws rather than returning null.
    return "system";
  }
  return isColorMode(stored) ? stored : "system";
}

export function resolveColorMode(
  mode: ColorMode,
  prefersDark: boolean,
): ResolvedColorMode {
  if (mode === "system") return prefersDark ? "dark" : "light";
  return mode;
}
