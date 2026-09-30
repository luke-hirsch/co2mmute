import { useEffect, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { de } from "@/lib/de";

/**
 * The editor asks for a big screen, and says so.
 *
 * **The editor stays a desktop tool** — Lukas, 2026-09-29: it gets a UI pass,
 * not a UX pass, and deliberately no mobile layout. That decision leaves one
 * gap, which is what this closes: on a phone the toolbar, the canvas and the
 * sidebar stack into a single column and the canvas gets a third of the width,
 * so the editor does not look like the wrong tool for the screen — it looks
 * broken. A sentence costs nothing and is the difference.
 *
 * **There is a way through**, because somebody on a tablet in landscape may know
 * exactly what they are doing, and a wall with no door is worse than a warning.
 * It is not remembered across reloads on purpose: the answer depends on the
 * screen you are on now, and a stored "yes" from a laptop would silence the
 * warning on the phone next to it.
 *
 * 1024px is `lg`, which is where the editor's own grid goes from one column to
 * four (`lg:grid-cols-4`) — so the threshold is the layout's, not a guess.
 */
const MIN_WIDTH = 1024;

export function EditorViewportGate({ children }: { children: ReactNode }) {
  const [wide, setWide] = useState<boolean | null>(null);
  const [anyway, setAnyway] = useState(false);

  useEffect(() => {
    const query = window.matchMedia(`(min-width: ${MIN_WIDTH}px)`);
    const read = () => setWide(query.matches);
    read();
    query.addEventListener("change", read);
    return () => query.removeEventListener("change", read);
  }, []);

  // Until the first measurement, render nothing rather than guessing: a warning
  // that flashes on a desktop reads as a bug, and so does an editor that
  // appears and is then replaced by a warning.
  if (wide === null) return null;
  if (wide || anyway) return <>{children}</>;

  return (
    <main className="flex min-h-dvh items-center bg-background px-4 py-20 text-foreground sm:px-6">
      <div className="mx-auto max-w-(--measure-body)">
        <h1 className="text-2xl font-semibold hyphens-auto">
          {de.editor.tooSmall.title}
        </h1>
        <p className="mt-4 text-muted-foreground">{de.editor.tooSmall.body}</p>
        <Button variant="outline" className="mt-8" onClick={() => setAnyway(true)}>
          {de.editor.tooSmall.anyway}
        </Button>
      </div>
    </main>
  );
}
