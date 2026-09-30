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
 * The mark is sized to the round capital beside it. A flat capital is `1cap`
 * tall; an O is 3.4 % taller and dips 1.2 % of an em under the baseline (SF,
 * measured in WebKit; Helvetica and Arial land within a percent), and a C drawn
 * to the flat height looks too small next to it. `0.729em` is the same height
 * for a browser without the `cap` unit — Safari before 17.2, which old school
 * iPads still run.
 */
export const LOCKUP_CLASS =
  "whitespace-nowrap text-2xl/none font-semibold tracking-[-0.02em]";
export const MARK_CLASS =
  "mr-[0.04em] inline-block aspect-[155/160] h-[0.729em] w-auto align-[-0.012em] supports-[height:1cap]:h-[1.034cap]";

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
