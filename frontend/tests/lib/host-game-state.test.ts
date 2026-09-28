import { describe, expect, it } from "vitest";

import { de } from "@/lib/de";
import { hostGameState } from "@/lib/host-game-state";
import type { HostGameRow } from "@/lib/queries/host-games";

/**
 * What the host's game list says a game is doing.
 *
 * The order of the branches is the rule, and it is not the obvious one:
 * `GameSession.save()` forces `is_active` back to False for an **ended** game
 * and for one with **no map**, so the flag alone cannot tell a finished game
 * from a broken one — and the broken one is the case the list exists to get rid
 * of, because it can never be started, never be ended, and before the per-game
 * delete it had no way out of the page at all.
 *
 * Two of these states are ones no e2e run reaches, which is why they are
 * asserted here.
 */
function game(overrides: Partial<HostGameRow> = {}): HostGameRow {
  return {
    game_id: "ABC123",
    game_name: "Klasse 8b",
    game_map: 1,
    created_at: "2026-09-28T09:00:00Z",
    started_at: null,
    ended_at: null,
    end_reason: null,
    paused_at: null,
    is_active: false,
    round_count: 0,
    player_count: 0,
    ...overrides,
  };
}

describe("what the list says a game is doing", () => {
  it("a fresh game has not started", () => {
    expect(hostGameState(game())).toBe(de.hostHome.notStarted);
  });

  it("a started game is running", () => {
    expect(
      hostGameState(
        game({ is_active: true, started_at: "2026-09-28T10:00:00Z" }),
      ),
    ).toBe(de.hostHome.running);
  });

  it("a paused game says so rather than 'running'", () => {
    expect(
      hostGameState(
        game({
          is_active: true,
          started_at: "2026-09-28T10:00:00Z",
          paused_at: "2026-09-28T10:20:00Z",
        }),
      ),
    ).toBe(de.hostHome.paused);
  });

  /** `is_active` is False on an ended game, so it must be read after ended_at. */
  it("an ended game is over, not 'not started'", () => {
    expect(
      hostGameState(
        game({
          is_active: false,
          started_at: "2026-09-28T10:00:00Z",
          ended_at: "2026-09-28T11:00:00Z",
          end_reason: "host",
        }),
      ),
    ).toBe(de.hostHome.over);
  });

  /**
   * The case the delete button exists for: a game made over the REST API or in
   * the admin without a map can never be started and never be ended.
   */
  it("a mapless game says it has no map", () => {
    expect(hostGameState(game({ game_map: null }))).toBe(de.hostHome.noMap);
  });

  it("an ended game that lost its map is still over", () => {
    expect(
      hostGameState(
        game({ game_map: null, ended_at: "2026-09-28T11:00:00Z" }),
      ),
    ).toBe(de.hostHome.over);
  });
});
