import { de } from "@/lib/de";
import { cn } from "@/lib/utils";

/**
 * The file both halves draw the mark from. It lives with Django's static files
 * because the Django pages render first and the SPA can reach them on the same
 * origin — its favicon already comes from there.
 */
export const MARK_HREF = "/static/img/mark.svg#mark";

/** The file's own viewBox, cropped to the C's outer edges. */
export const MARK_VIEWBOX = "22 20 155 160";

/**
 * Django's `template/partials/lockup.html` carries these same two class lists,
 * and `tests/design/lockup.test.ts` compares them.
 *
 * The mark is 1.7 capital heights tall and centred on the O, so its arrow
 * points at the O's middle: a capital is 0.705 em in SF (0.714 Helvetica,
 * 0.716 Arial), so 1.2 em tall with its foot 0.25 em under the baseline. At
 * exactly a capital's height, as a letter among letters, the C read as too
 * small and the name as too big (Lukas, 2026-09-30); 1.6, 1.7 and 1.8 were
 * compared in the header and 1.7 is the one that matches the drawn version's
 * C at 20 px type.
 */
export const LOCKUP_CLASS =
  "whitespace-nowrap text-xl/none font-semibold tracking-[-0.02em]";
export const MARK_CLASS =
  "mr-[0.08em] inline-block aspect-[155/160] h-[1.2em] w-auto align-[-0.25em]";

/**
 * The mark as the C of the name, followed by the rest of it as text.
 *
 * The rest is set in the page's own font on purpose. Drawn as paths it was a
 * geometric sans nobody else on the site uses, and it looked it; as text it is
 * the same face as every heading, on every system. The mark goes by reference
 * rather than as an `<img>`: an image cannot see the page's `dark` class.
 * Screen readers get the name once, whole, rather than "O 2 mmute".
 */
export function Lockup({ className }: { className?: string }) {
  const { before, sub, after } = de.app.wordmark;

  return (
    <span className={cn(LOCKUP_CLASS, className)}>
      <span aria-hidden="true">
        <svg viewBox={MARK_VIEWBOX} className={MARK_CLASS}>
          <use href={MARK_HREF} />
        </svg>
        {before}
        <sub>{sub}</sub>
        {after}
      </span>
      <span className="sr-only">{de.app.name}</span>
    </span>
  );
}
