import { de } from "@/lib/de";
import { cn } from "@/lib/utils";

/**
 * The file both halves draw the lockup from. It lives with Django's static
 * files because the Django pages render first and the SPA can reach them on
 * the same origin — its favicon already comes from there.
 */
export const LOCKUP_HREF = "/static/img/lockup.svg#lockup";

/** The file's own viewBox; `tests/design/lockup.test.ts` keeps them equal. */
export const LOCKUP_VIEWBOX = "20 16 1114 184";

/**
 * The mark as the C of the name, followed by the rest of it.
 *
 * By reference rather than as an `<img>`, so the letters take `currentColor`
 * and follow the theme; an image cannot see the page's `dark` class.
 */
export function Lockup({ className }: { className?: string }) {
  return (
    <svg
      viewBox={LOCKUP_VIEWBOX}
      role="img"
      aria-label={de.app.name}
      className={cn("aspect-[1114/184] h-7 w-auto", className)}
    >
      <use href={LOCKUP_HREF} />
    </svg>
  );
}
