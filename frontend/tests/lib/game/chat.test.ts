import { describe, expect, it } from "vitest";

import {
  CHAT_TRANSCRIPT_LIMIT,
  asChatEvent,
  chatDisplayName,
  chatErrorText,
  chatSocketUrl,
  type ChatEvent,
} from "@/lib/game/chat";
import { de } from "@/lib/de";

describe("asChatEvent", () => {
  it("passes the four frames the consumer can send", () => {
    // game/consumers.py:ChatConsumer — connect() sends chat.history,
    // chat_broadcast sends chat.message, chat_system sends chat.system, and
    // _handle_chat_message answers a refusal with chat.error.
    const frames: unknown[] = [
      { type: "chat.history", game_id: "ABC123", messages: [] },
      {
        type: "chat.message",
        game_id: "ABC123",
        message: { ts: 1, playerName: "Alex", message: "hallo" },
      },
      { type: "chat.system", game_id: "ABC123", message: "Alex joined the game" },
      { type: "chat.error", error: "Slow down" },
    ];

    for (const frame of frames) {
      expect(asChatEvent(frame)).toBe(frame);
    }
  });

  it("refuses a frame that is not an object or has no type", () => {
    expect(asChatEvent(null)).toBeNull();
    expect(asChatEvent("chat.message")).toBeNull();
    expect(asChatEvent(42)).toBeNull();
    expect(asChatEvent({ message: "no type" })).toBeNull();
    expect(asChatEvent({ type: 7 })).toBeNull();
  });

  it("refuses a game event, so one socket's frames cannot land in the other", () => {
    // Both sockets are open at once on every screen in a game. A frame from
    // ws/game/ reaching the chat reducer would be silently appended as an
    // unknown line rather than ignored.
    expect(asChatEvent({ type: "roster.update", players: [] })).toBeNull();
    expect(asChatEvent({ type: "round.started", game_id: "A", data: {} })).toBeNull();
  });
});

describe("chatSocketUrl", () => {
  it("is same-origin, because the player cookies only ride along there", () => {
    expect(chatSocketUrl("ABC123", "https:", "co2mmute.stsds.tu-berlin.de")).toBe(
      "wss://co2mmute.stsds.tu-berlin.de/ws/chat/ABC123/",
    );
  });

  it("drops to ws: on a plain-http page", () => {
    expect(chatSocketUrl("ABC123", "http:", "localhost:5173")).toBe(
      "ws://localhost:5173/ws/chat/ABC123/",
    );
  });
});

describe("chatErrorText", () => {
  it("translates every refusal ChatConsumer can send", () => {
    // The three literals in game/consumers.py: _validate_message_content
    // returns "Message too long", _check_rate_limits returns "Slow down" or
    // "Chat is moving too fast". They reach the player as they are, so the
    // German has to happen here.
    const raw = [
      "Message too long",
      "Slow down",
      "Chat is moving too fast",
      // S9: `is_muted` finally means something, and a muted player has to be
      // told *why* nothing they send arrives — silence reads as a broken chat.
      "You are muted",
      // S21: the host switched the chat off while this socket was open.
      "Chat is off",
    ];
    const texts = raw.map(chatErrorText);

    // Each says something of its own — one shared "es hat nicht geklappt" for
    // all five would tell a rate-limited class nothing about what to do.
    expect(new Set(texts).size).toBe(5);
    // And none of them is the backend's own wording handed straight through.
    for (const sentence of raw) {
      expect(texts).not.toContain(sentence);
    }
  });

  it("does not fall back on the mute refusal", () => {
    // The fallback is deliberately vague ("nicht angekommen"), which for a
    // muted player is exactly the wrong answer: it invites them to try again
    // all lesson. Pinned separately because the set-size check above would
    // still pass if two of the four collapsed onto the fallback.
    expect(chatErrorText("You are muted")).not.toBe(chatErrorText("Invalid JSON"));
  });

  it("says the chat is off in the words the dock already uses for it", () => {
    // One sentence for one fact: a socket opened before the switch hears it
    // from the server, a fresh load hears it from the snapshot, and both
    // should read the same.
    expect(chatErrorText("Chat is off")).toBe(de.chat.disabled);
  });

  it("falls back rather than showing the player an English sentence", () => {
    const text = chatErrorText("Invalid JSON");
    expect(text).not.toBe("Invalid JSON");
    expect(text.length).toBeGreaterThan(0);
  });
});

describe("chatDisplayName", () => {
  it("gives the host the name the backend chats under", () => {
    // `HostPlayer.name` in game/ws_auth.py is f"{username} (Host)". Comparing
    // against the host's *seat* name instead would mean the host never
    // recognises a single one of their own lines.
    expect(chatDisplayName({ kind: "host", username: "sarah" })).toBe("sarah (Host)");
  });

  it("gives a player their screen name", () => {
    expect(
      chatDisplayName({ kind: "player", player: { name: "Alex" } }),
    ).toBe("Alex");
  });

  it("is null when there is nothing to compare against", () => {
    // `whoami` in flight, or an anonymous browser. Null means no line is
    // marked as this reader's, which is the right answer rather than marking
    // every nameless line.
    expect(chatDisplayName({ kind: "anonymous" })).toBeNull();
    expect(chatDisplayName({ kind: "host" })).toBeNull();
  });
});

describe("CHAT_TRANSCRIPT_LIMIT", () => {
  it("is the server's own history window", () => {
    // ChatConsumer.CHAT_MESSAGE_HISTORY_LIMIT. Keeping the client bound equal
    // means a reconnect restores the same window the screen already showed,
    // instead of suddenly holding more or less than before.
    expect(CHAT_TRANSCRIPT_LIMIT).toBe(100);
  });
});

/** The union is exhaustive — this fails to compile if a member goes missing. */
describe("ChatEvent", () => {
  it("covers exactly the four frame types", () => {
    const types = (
      [
        { type: "chat.history", game_id: "A", messages: [] },
        {
          type: "chat.message",
          game_id: "A",
          message: { ts: 0, playerName: "A", message: "m" },
        },
        { type: "chat.system", game_id: "A", message: "m" },
        { type: "chat.error", error: "e" },
      ] satisfies ChatEvent[]
    ).map((event) => event.type);

    expect(types.sort()).toEqual([
      "chat.error",
      "chat.history",
      "chat.message",
      "chat.system",
    ]);
  });
});
