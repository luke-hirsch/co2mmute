/**
 * The requestAnimationFrame loop behind the animation.
 *
 * **Nothing here calls `setState` per frame.** 160–500 dots at 60 fps through
 * React state is where WebKit falls over, and every iOS browser is WebKit. So the
 * loop hands each frame to a callback that writes SVG attributes directly, and
 * React re-renders only when something a human reads has changed: the clock, and
 * whether the animation is playing, holding on the beat, or over.
 *
 * The clock display is throttled on top of that. Playback runs at one constant
 * rate since F2b, several simulated minutes to a screen second, and re-rendering
 * at frame rate to advance a number nobody can read that fast is the same mistake
 * by a smaller margin.
 *
 * Measured in WebKit (F3, 2026-10-02): a full round trip, 6 400 people, plays in
 * 120.0 s of wall time against the 120 s budget at 60 fps, 99th-percentile frame
 * about 30 ms — so the 0.25 s frame cap never bites and the clock does not fall
 * behind on a desktop. A real phone is not measured.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import type { Warp } from "@/lib/replay/time-warp";

/** Called once per frame. `jumped` means playback moved backwards — reset cursors. */
export type ReplayFrame = (
  minute: number,
  second: number,
  jumped: boolean,
) => void;

export type ReplayClock = {
  playing: boolean;
  /** Playback has reached the end and stopped. */
  finished: boolean;
  /** Playback is holding on the last moment — the beat. */
  beat: boolean;
  /** Playback is jumping over the middle of the day. */
  midday: boolean;
  /** Simulated minute, coarse. For the clock display, never for drawing. */
  minute: number;
  toggle: () => void;
  restart: () => void;
};

/** At most this many clock re-renders a second. */
const DISPLAY_HZ = 4;

/**
 * A backgrounded tab hands back one enormous delta on its first frame. Capping it
 * makes the animation pause rather than skip half the morning.
 */
const MAX_FRAME_SEC = 0.25;

export function useReplayClock(warp: Warp, onFrame: ReplayFrame): ReplayClock {
  const secondRef = useRef(0);
  const [playing, setPlaying] = useState(true);
  const [display, setDisplay] = useState({
    minute: 0,
    beat: false,
    midday: false,
    finished: false,
  });

  // The callback changes identity on every render of the component that owns the
  // canvas; keeping it in a ref is what stops that from restarting the loop. Synced
  // in an effect rather than assigned during render — writing a ref while rendering
  // is the thing React asks you not to do, and this hook is the one place where it
  // would be tempting.
  const frameRef = useRef(onFrame);
  useEffect(() => {
    frameRef.current = onFrame;
  }, [onFrame]);

  // The first paint has to place everybody, or the animation opens on an empty map
  // for as long as it takes the first frame to arrive. The canvas's imperative
  // handle is attached during commit, so it is already there when this runs.
  //
  // There is deliberately no "reset when the warp changes" effect: the caller keys
  // the stage on the round, so a new recording is a new component rather than an
  // old one being talked out of its state.
  useEffect(() => {
    frameRef.current(0, 0, true);
  }, []);

  useEffect(() => {
    if (!playing) return;

    let frame = 0;
    let last = performance.now();
    let lastDisplay = 0;
    let lastMinute = -1;

    const step = (now: number) => {
      const delta = Math.min((now - last) / 1000, MAX_FRAME_SEC);
      last = now;

      const second = Math.min(secondRef.current + delta, warp.durationSec);
      secondRef.current = second;
      const minute = warp.simMinuteAt(second);
      frameRef.current(minute, second, false);

      const beat = warp.isBeat(second);
      const midday = warp.isMidday(second);
      const done = second >= warp.durationSec;
      const whole = Math.floor(minute);
      if (
        done ||
        ((now - lastDisplay > 1000 / DISPLAY_HZ) && whole !== lastMinute)
      ) {
        lastDisplay = now;
        lastMinute = whole;
        setDisplay({ minute, beat, midday, finished: done });
      }

      if (done) {
        setPlaying(false);
        return;
      }
      frame = requestAnimationFrame(step);
    };

    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [playing, warp]);

  const toggle = useCallback(() => {
    // Pressing play on a finished replay starts it again; there is nowhere else
    // for it to go, and two buttons for one obvious intent is worse.
    if (secondRef.current >= warp.durationSec) {
      secondRef.current = 0;
      setDisplay({ minute: 0, beat: false, midday: false, finished: false });
      frameRef.current(0, 0, true);
    }
    setPlaying((value) => !value);
  }, [warp.durationSec]);

  const restart = useCallback(() => {
    secondRef.current = 0;
    setDisplay({ minute: 0, beat: false, midday: false, finished: false });
    frameRef.current(0, 0, true);
    setPlaying(true);
  }, []);

  return {
    playing,
    finished: display.finished,
    beat: display.beat,
    midday: display.midday,
    minute: display.minute,
    toggle,
    restart,
  };
}
