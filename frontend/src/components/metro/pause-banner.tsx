import { PauseIcon } from "lucide-react";
import { de } from "@/lib/de";
import { cn } from "@/lib/utils";

/**
 * Shown on every screen while `paused_at` is set (1.6 — the bell rang).
 *
 * Styled as a platform notice rather than an error: nothing has gone wrong, the
 * game is simply standing at a platform. Same amber as the landing page's
 * service notice, and the same reason — it is the one colour that reads as
 * "information you must not miss" without reading as a fault.
 */
export function PauseBanner({ className }: { className?: string }) {
  return (
    <div
      role="status"
      className={cn(
        "flex items-start gap-3 rounded-md bg-brandaccent px-5 py-4 text-darkbody",
        className,
      )}
    >
      <PauseIcon aria-hidden className="mt-0.5 size-5 shrink-0" />
      <div className="flex flex-col gap-1">
        <p className="font-medium">{de.pause.title}</p>
        <p className="max-w-(--measure-body) text-sm/6">{de.pause.body}</p>
      </div>
    </div>
  );
}
