/**
 * Watch the round happen, then read what it cost.
 *
 * This is the **front half of the stats phase**, not a phase of its own. Making it
 * a `between_round_phase` would cost an enum value, a migration, new `_claim`
 * transitions and new ack logic for a screen that changes nothing about what the
 * class is waiting for — while as the first act of `stats` it costs no backend
 * phase work at all, because `StatsAck` already exists and already means "I have
 * seen it".
 *
 * Synchronisation is free for the same reason: every client enters the phase on
 * the same `round.completed` broadcast, so the room is within network jitter of
 * itself with no new mechanism. Everybody sees the same traffic; there is nothing
 * per-device in here.
 *
 * **Skippable and replayable, never blocking.** The ack is the gate, not the
 * animation — so a round with no recording, or a fetch that fails, hands the
 * numbers over immediately rather than stranding the class on a spinner.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  ReplayCanvas,
  type ReplayCanvasHandle,
} from "@/components/replay/replay-canvas";
import { activityProfile } from "@/lib/replay/activity";
import { dotScale, replayEndings } from "@/lib/replay/counts";
import { buildStreetFill } from "@/lib/replay/street-fill";
import { buildWarp } from "@/lib/replay/time-warp";
import { cn } from "@/lib/utils";
import { de } from "@/lib/de";
import { modeOrder, modeStyle } from "@/components/metro/mode";
import { useGame } from "@/components/game/game-context";
import { useHostGame } from "@/lib/queries/session";
import { useMapGraph } from "@/lib/queries/map-graph";
import { useReplayClock } from "@/components/replay/use-replay-clock";
import { useRoundReplay } from "@/lib/queries/replay";
import { useSeatGame } from "@/lib/queries/seat";
import { REPLAY_FORMAT_VERSION, type Replay } from "@/lib/replay/types";
import type { ExtendedMapGraph } from "@/types/routeTypes";

export function ReplayPlayer({
  roundNumber,
  onWatched,
}: {
  roundNumber: number;
  /** Fired once, when the numbers may appear: played through, skipped, or nothing to play. */
  onWatched: () => void;
}) {
  const { state, seatId, isHost, isLoading } = useGame();
  const payload = useRoundReplay(state.gameId, roundNumber);

  // Two ways to the map id, because the two screens have different rights: a
  // player's seat row carries it, and the host's game row does. Both are already
  // in the cache by the time a round ends, so this costs no request.
  const seat = useSeatGame(state.gameId, seatId);
  const hostGame = useHostGame(state.gameId, isHost && !seatId);
  const mapId = seat.data?.game_map ?? hostGame.data?.game_map ?? null;

  // The version the round was *played* on. During the stats phase that is still
  // the active one — the vote comes after — so nothing has to remember it.
  const graph = useMapGraph(mapId, state.activeMapVersionId);

  const replay: Replay | null =
    payload.data?.replay && payload.data.replay.version === REPLAY_FORMAT_VERSION
      ? payload.data.replay
      : null;

  /**
   * `isHost` is false while `whoami` is in flight, so on the host's first render
   * there is no seat AND no host game row, and therefore no map id. That is a
   * loading state, not a missing recording — but once identity has settled and
   * there is still no map, it IS missing, and the numbers have to come out
   * rather than the screen sitting on a message for ever.
   */
  const noMap = !isLoading && mapId === null;
  const failed = payload.isError || graph.isError;
  const blocked = failed || noMap || (payload.isSuccess && !replay);
  const loading =
    !blocked && (payload.isPending || isLoading || graph.isPending);

  // Fires once. The numbers are never gated on a recording that is missing or
  // broken, and a second call would re-reveal a screen the class has moved past.
  const announced = useRef(false);
  const announce = () => {
    if (announced.current) return;
    announced.current = true;
    onWatched();
  };
  useEffect(() => {
    if (blocked) announce();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [blocked]);

  if (loading) return <Shell>{de.replay.loading}</Shell>;
  if (blocked || !replay || !graph.data) {
    return <Shell>{failed ? de.replay.failed : de.replay.missing}</Shell>;
  }

  return (
    <Stage
      // A new round is a new component: the clock, the cursors and the scratch
      // space all belong to one recording, and remounting is cheaper to reason
      // about than resetting seven things in an effect.
      key={roundNumber}
      replay={replay}
      graph={graph.data}
      ticks={payload.data!.ticks}
      tickDurationMin={payload.data!.tick_duration_min}
      onWatched={announce}
    />
  );
}

/** One line where the animation would be. Never a spinner the class waits on. */
function Shell({ children }: { children: React.ReactNode }) {
  return (
    <section aria-label={de.replay.title} className="mb-10">
      <p className="max-w-(--measure-body) text-muted-foreground">{children}</p>
    </section>
  );
}

function Stage({
  replay,
  graph,
  ticks,
  tickDurationMin,
  onWatched,
}: {
  replay: Replay;
  graph: ExtendedMapGraph;
  ticks: NonNullable<ReturnType<typeof useRoundReplay>["data"]>["ticks"];
  tickDurationMin: number;
  onWatched: () => void;
}) {
  const canvas = useRef<ReplayCanvasHandle>(null);

  const fill = useMemo(
    () => buildStreetFill(ticks, tickDurationMin),
    [ticks, tickDurationMin],
  );

  // The budget is fixed and the simulated span is normalised into it, so a round
  // that drained for four hours does not take twice as long to watch. The profile
  // is what makes the peak slow and the drain quick.
  const warp = useMemo(
    () =>
      buildWarp(activityProfile(replay), {
        endMin: Math.max(replay.end_min, 1),
      }),
    [replay],
  );

  const clock = useReplayClock(warp, (minute, _second, jumped) =>
    canvas.current?.draw(minute, jumped),
  );

  /**
   * Whether the numbers are out yet.
   *
   * The animation stays on screen afterwards — it is replayable, and the class
   * is about to argue about what it just watched — so this is not "am I still
   * mounted" but "is there still anything to skip".
   */
  const [handed, setHanded] = useState(false);
  const hand = () => {
    setHanded(true);
    onWatched();
  };

  useEffect(() => {
    if (clock.finished) hand();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clock.finished]);

  const endings = useMemo(() => replayEndings(replay), [replay]);

  return (
    <section aria-label={de.replay.title} className="mb-12">
      <p className="max-w-(--measure-body) text-muted-foreground">
        {de.replay.lead}
      </p>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
        <p className="font-mono text-sm tabular-nums text-muted-foreground">
          <span className="sr-only">{de.replay.clockLabel} </span>
          {de.replay.clock(clock.minute)}
        </p>
        <div className="flex flex-wrap gap-3">
          <Button variant="outline" size="sm" onClick={clock.toggle}>
            {clock.playing ? de.replay.pause : de.replay.play}
          </Button>
          <Button variant="ghost" size="sm" onClick={clock.restart}>
            {de.replay.again}
          </Button>
          {handed ? null : (
            <Button variant="ghost" size="sm" onClick={hand}>
              {de.replay.skip}
            </Button>
          )}
        </div>
      </div>

      <div className="mt-4">
        <ReplayCanvas ref={canvas} graph={graph} replay={replay} fill={fill} />
      </div>

      <Legend />

      <p className="mt-4 max-w-(--measure-body) text-sm text-muted-foreground">
        {de.replay.scale(de.replay.crowd(dotScale(replay)))} {de.replay.hint}
      </p>

      {/* The beat: the morning has landed, and the card may only say everybody
          made it when everybody did — counted by the simulator, not the sample
          (`lib/replay/counts.ts`). `stranded` and `unfinished` are two different
          sentences — never travelled at all versus not there yet when the clock
          stopped. */}
      {clock.beat ? (
        <div className="mt-8 max-w-(--measure-body) border-l-[3px] border-brandaccent pl-4">
          {endings.unfinished === 0 && endings.stranded === 0 ? (
            <p className="font-medium">{de.replay.beatArrived}</p>
          ) : (
            <>
              {endings.unfinished > 0 ? (
                <p>{de.replay.beatUnfinished(de.replay.crowd(endings.unfinished))}</p>
              ) : null}
              {endings.stranded > 0 ? (
                <p className={endings.unfinished > 0 ? "mt-2" : undefined}>
                  {de.replay.beatStranded(de.replay.crowd(endings.stranded))}
                </p>
              ) : null}
            </>
          )}
        </div>
      ) : null}
    </section>
  );
}

/**
 * What the marks mean.
 *
 * Purpose-built rather than `components/map/map-legend.tsx`: that one's groups are
 * "Kanten" and "Knoten", which is the map editor's vocabulary and the wrong
 * register for a student's screen. There is also no entry for "your own dots" —
 * there are none.
 */
function Legend() {
  return (
    <ul className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-muted-foreground">
      <li className="text-xs">{de.replay.legend.people}</li>
      {modeOrder.map((mode) => (
        <li key={mode} className="flex items-center gap-2">
          <span
            aria-hidden
            className={cn("size-2.5 shrink-0 rounded-full", modeStyle[mode].bg)}
          />
          {de.modes[mode]}
        </li>
      ))}
      <li className="flex items-center gap-2">
        <span aria-hidden className="h-2.5 w-4 shrink-0 rounded-sm bg-mode-pt" />
        {de.replay.legend.vehicle}
      </li>
      <li className="flex items-center gap-2">
        <span
          aria-hidden
          className="size-4 shrink-0 rounded-full border border-foreground/45 bg-foreground/15"
        />
        {de.replay.legend.crowd}
      </li>
      <li className="flex items-center gap-2">
        <span
          aria-hidden
          className="h-1.5 w-5 shrink-0 rounded-full bg-mode-car/40"
        />
        {de.replay.legend.fill}
      </li>
    </ul>
  );
}
