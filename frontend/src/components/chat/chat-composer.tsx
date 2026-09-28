import { useState, type FormEvent } from "react";
import { SendHorizontalIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { de } from "@/lib/de";

/** `ChatConsumer.CHAT_MESSAGE_MAX_LENGTH`. */
const MAX_LENGTH = 500;

/**
 * The line being written.
 *
 * Two rules it keeps, both learned from what the old sidebar did wrong:
 *
 * - **The text survives a failed send.** `send` returns false when the socket
 *   is not open, and on a school wifi that is a normal few seconds. Clearing
 *   the field regardless — which is what a naive `setInputText("")` after the
 *   call does — loses the sentence.
 * - **The length limit is enforced here as well as on the server.** 500
 *   characters is `CHAT_MESSAGE_MAX_LENGTH`; letting someone type 900 and then
 *   telling them it was too long wastes the typing.
 */
export function ChatComposer({
  onSend,
  disabled,
  error,
  onDismissError,
}: {
  onSend: (text: string) => boolean;
  disabled: boolean;
  /** Already German. Null when there is nothing to say. */
  error: string | null;
  onDismissError: () => void;
}) {
  const [text, setText] = useState("");
  const trimmed = text.trim();
  const remaining = MAX_LENGTH - text.length;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!trimmed || disabled) return;
    if (onSend(trimmed)) setText("");
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      {error ? (
        // The accent is what attention looks like here — there is no red in
        // this interface (rulebook §5). Clicking it away rather than a timeout:
        // a rate-limit notice that vanishes on its own is one nobody read.
        <button
          type="button"
          onClick={onDismissError}
          className="rounded-md bg-brandaccent px-3 py-2 text-left text-sm text-darkbody"
        >
          {error}
        </button>
      ) : null}

      <div className="flex items-end gap-2">
        <Input
          value={text}
          onChange={(event) => setText(event.target.value.slice(0, MAX_LENGTH))}
          placeholder={de.chat.placeholder}
          aria-label={de.chat.placeholder}
          maxLength={MAX_LENGTH}
          autoComplete="off"
          className="h-10"
        />
        <Button
          type="submit"
          size="icon"
          disabled={disabled || trimmed.length === 0}
          aria-label={de.chat.send}
        >
          <SendHorizontalIcon aria-hidden />
        </Button>
      </div>

      {/* Only once it is close enough to matter. A counter that sits at 500/500
          from the first keystroke is noise on a phone. */}
      {remaining <= 50 ? (
        <p className="font-mono text-xs text-muted-foreground">{remaining}</p>
      ) : null}
    </form>
  );
}
