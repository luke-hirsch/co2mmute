import { useEffect, useState } from "react";
import { CheckIcon, CopyIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { de } from "@/lib/de";

/**
 * Copies the invitation to the clipboard (F3), for the part of a class that is
 * not in the room or not looking at the projector.
 *
 * The clipboard needs a secure context and may be refused, so a failure is not
 * an error message and nothing else: it puts the text in a field to copy by
 * hand, which is what anybody would do next anyway.
 */
export function ShareInvitation({ text }: { text: string }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");

  useEffect(() => {
    if (state !== "copied") return;
    const timer = window.setTimeout(() => setState("idle"), 2000);
    return () => window.clearTimeout(timer);
  }, [state]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setState("copied");
    } catch {
      setState("failed");
    }
  }

  return (
    <div>
      <Button variant="outline" onClick={() => void copy()}>
        {state === "copied" ? <CheckIcon aria-hidden /> : <CopyIcon aria-hidden />}
        {state === "copied" ? de.host.shared : de.host.share}
      </Button>
      {state === "failed" ? (
        <div className="mt-4">
          <p className="max-w-(--measure-body) text-sm text-muted-foreground">
            {de.host.shareFailed}
          </p>
          <textarea
            readOnly
            value={text}
            rows={4}
            aria-label={de.host.share}
            onFocus={(event) => event.currentTarget.select()}
            className="mt-2 w-full rounded-md border border-input bg-transparent px-3.5 py-2 font-mono text-sm"
          />
        </div>
      ) : null}
    </div>
  );
}
