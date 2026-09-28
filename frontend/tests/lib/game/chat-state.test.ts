import { describe, expect, it } from "vitest";

import type { ChatEvent, ChatMessage } from "@/lib/game/chat";
import {
  chatReducer,
  initialChatState,
  type ChatState,
} from "@/lib/game/chat-state";

function message(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return { ts: 1_700_000_000_000, playerName: "Alex", message: "hallo", ...overrides };
}

function apply(state: ChatState, ...events: ChatEvent[]): ChatState {
  return events.reduce((acc, event) => chatReducer(acc, { kind: "event", event }), state);
}

describe("initialChatState", () => {
  it("starts empty and without an error", () => {
    expect(initialChatState()).toEqual({ lines: [], error: null });
  });
});

describe("chat.history", () => {
  it("replaces the transcript rather than appending to it", () => {
    // This is the whole reason history is not an append. ChatConsumer sends
    // the full stored history on *every* connect, and a school wifi reconnects
    // often — appending would show the lesson twice, then three times.
    const first = apply(initialChatState(), {
      type: "chat.history",
      game_id: "ABC123",
      messages: [message({ message: "eins" }), message({ message: "zwei" })],
    });
    expect(first.lines).toHaveLength(2);

    const second = apply(first, {
      type: "chat.history",
      game_id: "ABC123",
      messages: [message({ message: "eins" }), message({ message: "zwei" })],
    });

    expect(second.lines).toHaveLength(2);
    expect(second.lines.map((line) => line.text)).toEqual(["eins", "zwei"]);
  });

  it("keeps the server's order", () => {
    const state = apply(initialChatState(), {
      type: "chat.history",
      game_id: "ABC123",
      messages: [
        message({ ts: 3, message: "spaet" }),
        message({ ts: 1, message: "frueh" }),
      ],
    });

    // lrange returns oldest first; the screen prints them in that order and
    // does not re-sort. Re-sorting by `ts` would put the clock in charge of a
    // transcript whose order the server already fixed.
    expect(state.lines.map((line) => line.text)).toEqual(["spaet", "frueh"]);
  });

  it("drops a system line that was only ever local", () => {
    // System lines are not stored in Redis, so a reconnect cannot bring them
    // back. Replacing is therefore also the honest thing: what is on screen
    // afterwards is exactly what the server can vouch for.
    const withSystem = apply(initialChatState(), {
      type: "chat.system",
      game_id: "ABC123",
      message: "Alex joined the game",
    });
    expect(withSystem.lines).toHaveLength(1);

    const reconnected = apply(withSystem, {
      type: "chat.history",
      game_id: "ABC123",
      messages: [message()],
    });

    expect(reconnected.lines).toEqual([
      { kind: "message", ts: 1_700_000_000_000, playerName: "Alex", text: "hallo" },
    ]);
  });
});

describe("chat.message", () => {
  it("appends", () => {
    const state = apply(
      initialChatState(),
      { type: "chat.message", game_id: "A", message: message({ message: "eins" }) },
      { type: "chat.message", game_id: "A", message: message({ message: "zwei" }) },
    );

    expect(state.lines.map((line) => line.text)).toEqual(["eins", "zwei"]);
  });

  it("carries the name on every line, collisions included", () => {
    // `Player.name` has no uniqueness constraint (only `player_id` does), so
    // two students can both be "Max". The name therefore prints on every line
    // — a screen that hides it on "your own" messages would leave the class
    // unable to tell two Maxes apart.
    const state = apply(
      initialChatState(),
      { type: "chat.message", game_id: "A", message: message({ playerName: "Max" }) },
      { type: "chat.message", game_id: "A", message: message({ playerName: "Max" }) },
    );

    for (const line of state.lines) {
      expect(line.kind === "message" && line.playerName).toBe("Max");
    }
  });
});

describe("chat.system", () => {
  it("appends a line of its own kind, with no name and no timestamp", () => {
    // `chat_system` sends `{type, game_id, message}` — message is a plain
    // string here, where `chat.message` carries an object. The asymmetry is
    // the backend's; it is kept rather than smoothed over.
    const state = apply(initialChatState(), {
      type: "chat.system",
      game_id: "A",
      message: "Alex joined the game",
    });

    expect(state.lines).toEqual([{ kind: "system", text: "Alex joined the game" }]);
  });
});

describe("chat.error", () => {
  it("is shown beside the composer and never joins the transcript", () => {
    // A refusal is this client's own problem. Putting it in the transcript
    // would show one student's rate limit to the whole class.
    const state = apply(initialChatState(), {
      type: "chat.error",
      error: "Slow down",
    });

    expect(state.lines).toEqual([]);
    expect(state.error).toBe("Slow down");
  });

  it("is cleared by dismissing it", () => {
    const withError = apply(initialChatState(), {
      type: "chat.error",
      error: "Slow down",
    });

    expect(chatReducer(withError, { kind: "dismiss-error" }).error).toBeNull();
  });

  it("is cleared by the next message that does land", () => {
    const withError = apply(initialChatState(), {
      type: "chat.error",
      error: "Slow down",
    });

    const recovered = apply(withError, {
      type: "chat.message",
      game_id: "A",
      message: message(),
    });

    expect(recovered.error).toBeNull();
  });
});

describe("the transcript is bounded", () => {
  it("keeps the last 100 lines and drops the oldest", () => {
    // Same window as ChatConsumer.CHAT_MESSAGE_HISTORY_LIMIT, so a two-hour
    // lesson cannot grow the array without end and a reconnect shows about
    // what was already there.
    let state = initialChatState();
    for (let i = 0; i < 130; i += 1) {
      state = apply(state, {
        type: "chat.message",
        game_id: "A",
        message: message({ message: `nachricht ${i}` }),
      });
    }

    expect(state.lines).toHaveLength(100);
    expect(state.lines[0].text).toBe("nachricht 30");
    expect(state.lines[99].text).toBe("nachricht 129");
  });

  it("bounds a history longer than the window too", () => {
    const messages = Array.from({ length: 130 }, (_, i) =>
      message({ message: `alt ${i}` }),
    );
    const state = apply(initialChatState(), {
      type: "chat.history",
      game_id: "A",
      messages,
    });

    expect(state.lines).toHaveLength(100);
    expect(state.lines[0].text).toBe("alt 30");
  });
});

describe("reset", () => {
  it("empties the transcript when the chat is switched off", () => {
    // `clear_chat_on_toggle` in game/signals.py wipes the Redis list the
    // moment the host flips `chat_enabled`. The screen has to follow, or the
    // class keeps reading a conversation the server has already deleted.
    const state = apply(initialChatState(), {
      type: "chat.message",
      game_id: "A",
      message: message(),
    });

    expect(chatReducer(state, { kind: "reset" })).toEqual(initialChatState());
  });
});
