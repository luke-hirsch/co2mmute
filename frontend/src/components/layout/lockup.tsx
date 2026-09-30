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
 * The C runs from the top of the O to the foot of the subscript 2 — the whole
 * height of the word — so both its edges line up with a letter. Measured from
 * the rendered ink in WebKit at 200 px: the O's top is 0.71 em above the
 * baseline and the 2's foot 0.19 em below it, so 0.9 em; on the page at 22 px
 * the top then came out a quarter pixel short, hence 0.91. Both edges meet to
 * the device pixel at 4x, on both halves. Its arrow lands on the middle of the
 * lowercase letters. Sized to a capital it read as a letter among letters and
 * too small; centred on the O at 1.7 capitals no edge met anything.
 */
export const LOCKUP_CLASS =
  "whitespace-nowrap text-[1.375rem]/none font-semibold tracking-[-0.02em]";
export const MARK_CLASS =
  "mr-[0.08em] inline-block aspect-[155/160] h-[0.91em] w-auto align-[-0.19em]";

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
