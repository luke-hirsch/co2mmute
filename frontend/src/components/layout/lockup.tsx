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
 * The C runs from the top of the O to its baseline — the O's own cap height,
 * not the whole word — so both its edges line up with the O, and the
 * subscript 2's foot is left to hang below on its own, the way it does after
 * every other letter. The icon's own bottom sits on the baseline with no
 * offset, so `align` carries none; the O's top needed 0.75 em of height to
 * reach it exactly, checked pixel-for-pixel against a WebKit render at 8x —
 * 0.71 em (the O's cap height alone) came out a pixel short at 22 px, the
 * same rounding the old shape also had to correct for. Its arrow lands on
 * the middle of the lowercase letters. Sized to a capital it read as a
 * letter among letters and too small; centred on the O at 1.7 capitals no
 * edge met anything; run down to the 2's foot it overshot the O on both
 * ends. **`h-[…]em` and `align-[…]em` are the two numbers this shape comes
 * down to** — everything else in this class list is fixed by the artwork or
 * the type.
 */
export const LOCKUP_CLASS =
  "whitespace-nowrap text-[1.375rem]/none font-semibold tracking-[-0.02em]";
export const MARK_CLASS =
  "mr-[0.08em] inline-block aspect-[155/160] h-[0.75em] w-auto align-[0em]";

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
