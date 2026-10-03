import type { NavItem } from "@/lib/queries/navigation";

/**
 * Links the SPA can follow without a reload.
 *
 * The header's items come from the server as plain hrefs, some into Django
 * (`/docs/hintergrund/`, the legal pages, the repository) and some into this app
 * (`/app/maps`, `/app/join`). The router is mounted at `/app` and wants the path
 * *inside* it, so an href under `/app/` becomes that path and everything else
 * is `null` — a document navigation, which is exactly right for a Django page.
 *
 * Deliberately not a prefix test on `/app`: `/apple-touch-icon.png` starts with
 * it too.
 */
export function routerPath(href: string): string | null {
  if (href === "/app" || href === "/app/") return "/";
  if (href.startsWith("/app/")) return href.slice("/app".length);
  return null;
}

/**
 * Where to put a popover so it hangs under its button: centred on it, but kept
 * `edge` pixels inside the viewport. `base.html`'s flyouts do the same sum in
 * `static/js/script.js` — CSS anchor positioning would make both unnecessary,
 * but it is Safari 26+ and the school iPads are older.
 */
export function placeBelow(
  anchor: { left: number; width: number; bottom: number },
  panelWidth: number,
  viewportWidth: number,
  { gap = 12, edge = 16 } = {},
): { top: number; left: number } {
  const centred = anchor.left + anchor.width / 2 - panelWidth / 2;
  const left = Math.max(edge, Math.min(centred, viewportWidth - panelWidth - edge));
  return { top: anchor.bottom + gap, left };
}

/**
 * Whether a menu draws a rule above this item: where the language of its links
 * changes. The docs menu lists three pages in German and the same three in
 * English (F13); `base.html` does the same with `{% ifchanged %}`.
 */
export function startsLanguageGroup(items: readonly NavItem[], index: number): boolean {
  return index > 0 && items[index].lang !== items[index - 1].lang;
}
