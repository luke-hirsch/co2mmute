import { useEffect, useRef } from "react";

import type { ChatLine } from "@/lib/game/chat-state";
import { de } from "@/lib/de";
import { cn } from "@/lib/utils";

/**
 * The conversation, drawn as a line with stops on it.
 *
 * The old `ChatSidebar` used chat bubbles — grey for them, primary for you,
 * amber-bordered for the host — which is three colours doing the work of one
 * and none of them in the palette any more. A transcript is a sequence, and a
 * sequence in this interface is a line with markers on it (rulebook §1), so it
 * is drawn the way the round steps and the phase machine are.
 *
 * **Whose line it is, is filled versus hollow, never a colour** (rulebook §5).
 * That cue is a nicety and is treated as one: `Player.name` is not unique in a
 * game, so two students called Max each see both lines filled. The name is on
 * every line regardless, which is what makes that harmless — a screen that hid
 * the name on "your own" messages would leave the class unable to tell them
 * apart at all.
 */
export function ChatTranscript({
  lines,
  myName,
  className,
}: {
  lines: ChatLine[];
  /** This device's screen name, from `whoami`. Null while it is in flight. */
  myName: string | null;
  className?: string;
}) {
  const endRef = useRef<HTMLDivElement>(null);
  const count = lines.length;

  useEffect(() => {
    // `block: "nearest"` scrolls the panel and not the page under it — the
    // round screen behind the dock must not jump when a message arrives.
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [count]);

  if (count === 0) {
    return (
      <p className={cn("px-1 py-8 text-sm text-muted-foreground", className)}>
        {de.chat.empty}
      </p>
    );
  }

  return (
    <ol className={cn("relative flex flex-col gap-5 py-2 pl-7", className)}>
      {/* The rail. Hairline rather than the Track's 5px stroke: this is a
          hundred stops on a phone, not five steps in a turn. */}
      <span
        aria-hidden
        className="absolute top-2 bottom-2 left-[5px] w-0 border-l border-border"
      />
      {lines.map((line, index) =>
        line.kind === "system" ? (
          <SystemLine key={index} text={line.text} />
        ) : (
          <MessageLine
            key={index}
            playerName={line.playerName}
            ts={line.ts}
            text={line.text}
            mine={myName !== null && line.playerName === myName}
          />
        ),
      )}
      <div ref={endRef} aria-hidden />
    </ol>
  );
}

function MessageLine({
  playerName,
  ts,
  text,
  mine,
}: {
  playerName: string;
  ts: number;
  text: string;
  mine: boolean;
}) {
  return (
    <li className="relative">
      <span
        aria-hidden
        className={cn(
          "absolute top-[0.5lh] left-[-1.75rem] size-[11px] -translate-y-1/2 rounded-full border-2 border-foreground",
          mine ? "bg-foreground" : "bg-background",
        )}
      />
      <p className="flex items-baseline gap-2">
        <span className="text-sm font-medium">{playerName}</span>
        {/* Mono, because a clock is numerals (rulebook §6). */}
        <time
          dateTime={new Date(ts).toISOString()}
          className="font-mono text-xs text-muted-foreground"
        >
          {clockTime(ts)}
        </time>
      </p>
      <p className="mt-0.5 max-w-(--measure-body) text-sm/6 wrap-anywhere">{text}</p>
    </li>
  );
}

/**
 * A join notice. No marker and no time: the consumer sends neither, and a
 * hollow stop on the rail would claim it is the same kind of thing as a message.
 */
function SystemLine({ text }: { text: string }) {
  return (
    <li className="relative">
      <p className="max-w-(--measure-body) text-xs text-muted-foreground">{text}</p>
    </li>
  );
}

/** `14:07`, in German 24-hour time. */
function clockTime(ts: number): string {
  return new Date(ts).toLocaleTimeString("de-DE", {
    hour: "2-digit",
    minute: "2-digit",
  });
}
