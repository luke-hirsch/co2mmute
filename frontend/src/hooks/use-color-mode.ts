import { useSyncExternalStore } from "react";

import { DARK_CLASS, type ResolvedColorMode } from "@/lib/color-mode";

/**
 * Watch the `dark` class on <html> rather than re-deriving the mode from
 * localStorage. The inline script in index.html is the single writer — reading
 * the class means we agree with it by construction, whoever flipped it and
 * whenever.
 */
function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class"],
  });
  return () => observer.disconnect();
}

function getSnapshot(): ResolvedColorMode {
  return document.documentElement.classList.contains(DARK_CLASS) ? "dark" : "light";
}

export function useResolvedColorMode(): ResolvedColorMode {
  return useSyncExternalStore(subscribe, getSnapshot, () => "light");
}
