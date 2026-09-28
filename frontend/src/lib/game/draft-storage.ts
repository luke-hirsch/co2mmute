/**
 * The unfinished turn, across a reload.
 *
 * A locked phone discards the page, and in a classroom that is the ordinary
 * case rather than the edge case (Roadmap.md S7). What survives is the **taps**
 * — which passenger travels how, and which of the two optimisations was picked
 * — and deliberately not the route.
 *
 * That distinction is the whole design, and it is what keeps this from being
 * the second source of truth `round-draft.ts`'s header argues against. A route
 * belongs to a graph: store one and it can come back naming an edge a vote has
 * since removed, and it would sit on screen without the pathfinder ever having
 * agreed to it. A mode is just a choice. Put the mode back with the route still
 * empty and `use-round-draft.ts`'s routing effect — "anyone with a mode but no
 * route gets one" — searches again against the map the game is on now. So the
 * pathfinder remains the only thing that ever produces a route, and re-picking
 * still costs the four taps it always did; they just come back on their own.
 *
 * Every function takes its storage as an argument, the way
 * `readStoredColorMode` does, so the logic is testable without a stubbed global
 * and `null` (no storage at all) is an ordinary input rather than a special
 * case. `browserStorage()` at the bottom is the only part that touches the
 * environment.
 *
 * **Retention**, which is a real question here and not a formality: one entry
 * per seat per game, holding no name and no free text — four transport modes.
 * It is overwritten when the round advances, removed when the turn is
 * submitted, and every entry belonging to another game is dropped on the next
 * write. `template/legal/cookies.html` §3.3 describes it.
 */

import {
  DEFAULT_CAR_OPTIMIZATION,
  DEFAULT_PT_OPTIMIZATION,
  type AgentChoice,
  type RoundDraft,
} from "@/lib/game/round-draft";
import type {
  CarOptimization,
  PTOptimization,
  TransportMode,
} from "@/types/routeTypes";

const PREFIX = "co2mmute.draft.";

const MODES: readonly string[] = ["car", "public", "bike", "walk"];
const CAR_OPTIMIZATIONS: readonly string[] = ["time", "distance", "co2"];
const PT_OPTIMIZATIONS: readonly string[] = ["fastest", "fewest_transfers", "no_bus"];

/**
 * One entry per seat per game.
 *
 * Per seat because the host desk plays several behind a curtain and a single
 * key would let one student's half-made turn overwrite the next one's. Per game
 * because that is the unit the entry is pruned by.
 *
 * The parts are escaped so the separator cannot be forged: a `player_id` that
 * happened to contain a dot would otherwise make two different seats share a
 * key.
 */
export function draftStorageKey(gameId: string, seatId: string): string {
  return `${PREFIX}${encodeURIComponent(gameId)}.${encodeURIComponent(seatId)}`;
}

/** What one agent's stored choice must look like before it is believed. */
function parseChoice(value: unknown): AgentChoice | null {
  if (typeof value !== "object" || value === null) return null;
  const raw = value as Record<string, unknown>;

  if (typeof raw.agentId !== "number") return null;
  // A mode is the entry's whole point, so an unrecognised one drops that agent
  // rather than being defaulted to something nobody picked. The optimisations
  // are a preference within a mode and can fall back.
  if (typeof raw.mode !== "string" || !MODES.includes(raw.mode)) return null;

  const car = raw.carOptimization;
  const pt = raw.ptOptimization;

  return {
    agentId: raw.agentId,
    mode: raw.mode as TransportMode,
    carOptimization:
      typeof car === "string" && CAR_OPTIMIZATIONS.includes(car)
        ? (car as CarOptimization)
        : DEFAULT_CAR_OPTIMIZATION,
    ptOptimization:
      typeof pt === "string" && PT_OPTIMIZATIONS.includes(pt)
        ? (pt as PTOptimization)
        : DEFAULT_PT_OPTIMIZATION,
  };
}

/**
 * The taps this seat had made in this round, or null.
 *
 * The round has to match. Round 2 may run on a map round 1 voted in, and
 * "the choices I made last round" is not what the screen is asking for anyway.
 * A rotated seat needs no check of its own: a handover or a takeover gives the
 * row a new `player_id` (`game/seats.py:_rotate`), so the key moves with it and
 * the old device's entry is unreachable.
 */
export function readStoredChoices(
  storage: Pick<Storage, "getItem"> | null,
  gameId: string,
  seatId: string,
  roundNumber: number,
): AgentChoice[] | null {
  if (!storage) return null;

  let raw: string | null;
  try {
    raw = storage.getItem(draftStorageKey(gameId, seatId));
  } catch {
    // Safari with site data blocked throws rather than returning null.
    return null;
  }
  if (!raw) return null;

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }

  if (typeof parsed !== "object" || parsed === null) return null;
  const record = parsed as Record<string, unknown>;
  if (record.round !== roundNumber) return null;
  if (!Array.isArray(record.agents)) return null;

  const choices = record.agents
    .map(parseChoice)
    .filter((choice): choice is AgentChoice => choice !== null);

  return choices.length ? choices : null;
}

/**
 * Keep this seat's taps, or drop the entry when there are none.
 *
 * Nothing chosen is nothing to keep: writing an empty record would leave a key
 * lying around for a turn that was never begun, and clearing the last agent
 * would otherwise not clear the storage.
 *
 * **`currentRound` is what the screen knows, and it is a guard, not a label.**
 * The draft may only be recorded for the round the screen is actually on. Two
 * ways it can disagree, both of which delete a perfectly good turn:
 *
 *  - `currentRound` is **0**, the reducer's "no round yet". On a reload the
 *    seat query can resolve before `game.state` arrives over the socket, so the
 *    draft is briefly assigned for round 0 with nothing chosen — and an empty
 *    draft removes the entry. The turn was then gone before the real round
 *    number ever got to read it. This cost an intermittent e2e failure, and it
 *    failed *more* under load, which is precisely when a socket loses a race.
 *  - the draft still describes the **previous** round, in the moment between a
 *    new round starting and the assignment for it arriving.
 *
 * So: no round, or a draft from another round, writes nothing at all. Refusing
 * is always safe — the entry is rewritten on the next change — where writing
 * the wrong thing is not.
 */
export function writeStoredChoices(
  storage: Pick<Storage, "setItem" | "removeItem"> | null,
  gameId: string,
  draft: RoundDraft,
  choices: AgentChoice[],
  currentRound: number,
): void {
  if (!storage || !draft.seatId) return;
  if (currentRound < 1 || draft.roundNumber !== currentRound) return;

  const key = draftStorageKey(gameId, draft.seatId);
  try {
    if (!choices.length) {
      storage.removeItem(key);
      return;
    }
    storage.setItem(key, JSON.stringify({ round: draft.roundNumber, agents: choices }));
  } catch {
    // A full quota or blocked site data costs the convenience, not the turn.
  }
}

/** The turn is submitted; the draft has done its job. */
export function clearStoredDraft(
  storage: Pick<Storage, "removeItem"> | null,
  gameId: string,
  seatId: string,
): void {
  if (!storage) return;
  try {
    storage.removeItem(draftStorageKey(gameId, seatId));
  } catch {
    // As above.
  }
}

/**
 * Drop every draft belonging to another game — the retention rule, in code.
 *
 * A device keeps unfinished turns for the game it is playing and for no other,
 * so a phone that joins a new game sheds the last one's on the first write.
 * Keys are collected before anything is removed: removing while iterating over
 * `key(i)` skips entries, because the indices shift underneath.
 */
export function pruneOtherGames(storage: Storage | null, gameId: string): void {
  if (!storage) return;

  const mine = `${PREFIX}${encodeURIComponent(gameId)}.`;
  const doomed: string[] = [];

  try {
    for (let i = 0; i < storage.length; i += 1) {
      const key = storage.key(i);
      if (key && key.startsWith(PREFIX) && !key.startsWith(mine)) doomed.push(key);
    }
    for (const key of doomed) storage.removeItem(key);
  } catch {
    // As above.
  }
}

/**
 * The real thing, or null where there isn't one.
 *
 * Private mode, blocked site data and a server-side render all answer null, and
 * every function above takes null, so no caller needs a branch of its own.
 */
export function browserStorage(): Storage | null {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}
