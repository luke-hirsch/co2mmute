import { useCallback, useEffect, useRef, useState } from "react";
import { MessageSquareIcon, XIcon } from "lucide-react";

import { ChatComposer } from "@/components/chat/chat-composer";
import { ChatTranscript } from "@/components/chat/chat-transcript";
import { useChat } from "@/components/chat/use-chat";
import { useGame } from "@/components/game/game-context";
import { Button } from "@/components/ui/button";
import { chatDisplayName } from "@/lib/game/chat";
import { de } from "@/lib/de";

/**
 * The chat, reachable from every screen in a game (R-13, C-05).
 *
 * `GameFrame` mounts this **once**, which is what keeps it to one socket: the
 * lobby, the round, the four between-round phases and the summary all sit
 * inside that frame, so the connection outlives every screen change and the
 * transcript does not reload when the round ends.
 *
 * **Not modal.** Radix's Dialog would give focus trapping and Escape for free,
 * but it would also put a backdrop over the game, and R-13 is specifically
 * "chat during the round" — someone reading what the class is arguing about
 * while picking a route needs both on screen. Escape is wired by hand below;
 * the rest of the page stays live on purpose.
 *
 * It is not rendered at all when the host switched the chat off (C-04), rather
 * than rendered disabled: there is nothing behind it, the server has wiped the
 * history, and a greyed-out button invites clicking.
 */
export function ChatDock() {
  const { state, identity } = useGame();
  const [open, setOpen] = useState(false);
  const chat = useChat({ gameId: state.gameId, enabled: state.chatEnabled });
  const panelRef = useRef<HTMLDivElement>(null);

  /**
   * How many lines arrived while it was shut.
   *
   * A high-water mark rather than a counter, because `chat.history` replaces
   * the transcript wholesale — a counter incremented per event would go on
   * counting across a reconnect that showed nothing new.
   *
   * It is only ever written from the close handler, and read only while the
   * panel is shut. That is what keeps it out of an effect: nothing has to be
   * kept in sync while the panel is open, because the answer is 0 either way.
   */
  const [seen, setSeen] = useState(0);
  const total = chat.lines.length;
  const unread = open ? 0 : Math.max(0, total - seen);

  const close = useCallback(() => {
    // Everything on screen has now been read, by definition.
    setSeen(total);
    setOpen(false);
  }, [total]);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") close();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, close]);

  useEffect(() => {
    if (open) panelRef.current?.focus();
  }, [open]);

  if (!state.chatEnabled) return null;

  // Not `identity.player.name` — the host chats as "<username> (Host)".
  const myName = identity ? chatDisplayName(identity) : null;

  return (
    <>
      {open ? (
        <section
          ref={panelRef}
          tabIndex={-1}
          aria-label={de.chat.title}
          className="fixed inset-x-0 bottom-0 z-50 flex max-h-[min(70dvh,32rem)] flex-col rounded-t-xl border-t border-border bg-card text-card-foreground shadow-lg outline-none sm:inset-x-auto sm:right-6 sm:bottom-6 sm:w-96 sm:rounded-xl sm:border"
        >
          <header className="flex items-center justify-between gap-3 border-b border-border px-5 py-3">
            <h2 className="font-medium">{de.chat.title}</h2>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={close}
              aria-label={de.chat.close}
            >
              <XIcon aria-hidden />
            </Button>
          </header>

          <div className="min-h-0 flex-1 overflow-y-auto px-5">
            <ChatTranscript lines={chat.lines} myName={myName} />
          </div>

          <div className="flex flex-col gap-2 border-t border-border px-5 py-3">
            {!chat.isConnected ? (
              <p className="text-xs text-muted-foreground">{de.chat.offline}</p>
            ) : null}
            <ChatComposer
              onSend={chat.send}
              disabled={!chat.isConnected}
              error={chat.error}
              onDismissError={chat.dismissError}
            />
            {/* The retention rule, where it applies rather than only on the
                cookie page: two hours, because that is what `ChatConsumer`
                actually does (CHAT_HISTORY_TTL_SECONDS). */}
            <p className="text-xs text-muted-foreground">{de.chat.retention}</p>
          </div>
        </section>
      ) : (
        <Button
          onClick={() => setOpen(true)}
          size="lg"
          className="fixed right-4 bottom-4 z-50 shadow-lg sm:right-6 sm:bottom-6"
        >
          <MessageSquareIcon aria-hidden />
          {de.chat.title}
          {unread > 0 ? (
            // Attention is the accent, and a count is numerals, so mono.
            <span className="ml-1 rounded-full bg-brandaccent px-2 py-0.5 font-mono text-xs text-darkbody">
              {unread}
            </span>
          ) : null}
        </Button>
      )}
    </>
  );
}
