import { useSyncExternalStore } from "react";

/** Tailwind's `sm`: below it a screen counts as a phone. */
export const BIG_SCREEN_QUERY = "(min-width: 640px)";

function subscribe(onChange: () => void) {
  if (typeof window.matchMedia !== "function") return () => {};
  const query = window.matchMedia(BIG_SCREEN_QUERY);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

function read() {
  return (
    typeof window.matchMedia === "function" &&
    window.matchMedia(BIG_SCREEN_QUERY).matches
  );
}

/** Whether the screen is at least `sm` wide; false where there is no window. */
export function useBigScreen(): boolean {
  return useSyncExternalStore(subscribe, read, () => false);
}
