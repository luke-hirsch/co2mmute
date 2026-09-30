import { useEffect, useMemo, useState } from "react";

import { de } from "@/lib/de";

/**
 * The waiting state, for the screens that fetch a whole map before they can
 * draw anything.
 *
 * ### What S18 changed
 *
 * Three things, none of them the animation:
 *
 * - **It was English.** `label = "Loading…"` and a subtitle reading "Adapting
 *   to the network. Modal shift, but make it latency." — live on the map detail
 *   page and in the editor, through two German passes. `german.test.ts` saw
 *   neither: a one-word literal is skipped on purpose (`type === "street"` must
 *   not read as a sentence) and the subtitle carried none of the giveaway
 *   words. The default is `de.app.loading` now, and the subtitle is gone rather
 *   than translated — a spinner does not need a second line, and inventing a
 *   German joke for someone else's voice is not a colour sweep's job.
 * - **The dark theme never applied.** The rule was `:global(.dark) .iconStage`,
 *   which is styled-jsx / CSS-modules syntax; inside a plain `<style>` element
 *   the browser drops the whole selector as invalid. So the vehicle kept its
 *   light hull on `#0b1120`. The colours are tokens now and flip themselves,
 *   which is also why there is no dark rule left to get wrong.
 * - **The hull was `gray-800`, the label `gray-900`.** Palette, like everything
 *   else this sweep touched: the ring is the primary, the vehicle is ink, and
 *   the glass is the page colour rather than `#fff` — white glass on a dark
 *   hull is fine, white glass on a dark *page* is a hole.
 */
type LoadingProps = {
  label?: string;
  className?: string;
  intervalMs?: number; // default 1000
};

type Mode = "train" | "car" | "bus";

export default function Loading({
  label = de.app.loading,
  className = "",
  intervalMs = 1000,
}: LoadingProps) {
  const modes = useMemo<Mode[]>(() => ["train", "car", "bus"], []);
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => {
      setIdx((prev) => (prev + 1) % modes.length);
    }, intervalMs);

    return () => window.clearInterval(id);
  }, [intervalMs, modes.length]);

  const active = modes[idx];

  return (
    <div
      className={[
        "flex min-h-80 w-full flex-col items-center justify-center gap-4",
        className,
      ].join(" ")}
      role="status"
      aria-live="polite"
    >
      <div className="iconStage" aria-hidden="true">
        {/* Swirl ring */}
        <div className="swirl" />

        {/* TRAIN */}
        <div className={["icon", active === "train" ? "in" : "out"].join(" ")}>
          <TrainIcon />
        </div>

        {/* CAR */}
        <div className={["icon", active === "car" ? "in" : "out"].join(" ")}>
          <CarIcon />
        </div>

        {/* BUS */}
        <div className={["icon", active === "bus" ? "in" : "out"].join(" ")}>
          <BusIcon />
        </div>
      </div>

      <p className="text-sm font-medium text-foreground">{label}</p>

      <style>{`
        .iconStage {
          position: relative;
          width: 170px;
          height: 170px;
          display: grid;
          place-items: center;
          /* Tokens, so the theme is handled by the theme and this element has
             no dark rule of its own. The hull is ink at a step below the text
             so the vehicle reads as an illustration rather than as a heading. */
          --hull: var(--color-muted-foreground);
          --glass: var(--color-card);
          color: var(--color-foreground);
        }

        .swirl {
          position: absolute;
          inset: 18px;
          border-radius: 999px;
          border: 3px solid var(--color-primary);
          border-top-color: transparent;
          border-right-color: transparent;
          filter: blur(.1px);
          animation: swirl 900ms linear infinite;
        }

        .icon {
          position: absolute;
          inset: 0;
          display: grid;
          place-items: center;
          transform-origin: 50% 60%;
          opacity: 0;
          pointer-events: none;
        }

        /* Active icon animates in */
        .icon.in {
          animation: spinIn 320ms ease-out forwards;
        }

        /* Inactive icon animates out (but only if it was visible) */
        .icon.out {
          animation: spinOut 320ms ease-in forwards;
        }

        /* Keep things smooth between swaps */
        @keyframes spinIn {
          0%   { opacity: 0; transform: rotate(-18deg) scale(0.88); }
          70%  { opacity: 1; transform: rotate(6deg) scale(1.04); }
          100% { opacity: 1; transform: rotate(0deg) scale(1.0); }
        }
        @keyframes spinOut {
          0%   { opacity: 1; transform: rotate(0deg) scale(1.0); }
          100% { opacity: 0; transform: rotate(18deg) scale(0.86); }
        }
        @keyframes swirl {
          to { transform: rotate(360deg); }
        }

        @media (prefers-reduced-motion: reduce) {
          .swirl, .icon.in, .icon.out { animation: none !important; }
          .icon.in { opacity: 1; }
          .icon.out { opacity: 0; }
        }
      `}</style>
    </div>
  );
}

/** Shared helpers: all icons use currentColor plus the two CSS vars above. */
function TrainIcon() {
  return (
    <svg width="150" height="150" viewBox="0 0 160 160" fill="none">
      {/* rails */}
      <path
        d="M44 150V120M116 150V120"
        stroke="currentColor"
        strokeWidth="8"
        strokeLinecap="round"
        opacity="0.35"
      />
      {/* body */}
      <rect x="30" y="26" width="100" height="104" rx="18" fill="var(--hull)" />
      {/* destination */}
      <rect
        x="52"
        y="32"
        width="56"
        height="12"
        rx="6"
        fill="var(--glass)"
        opacity="0.9"
      />
      {/* windshield */}
      <rect
        x="44"
        y="48"
        width="72"
        height="40"
        rx="10"
        fill="var(--glass)"
        opacity="0.95"
      />
      {/* headlights */}
      <circle cx="50" cy="104" r="5" fill="var(--glass)" />
      <circle cx="110" cy="104" r="5" fill="var(--glass)" />
      {/* coupler */}
      <rect
        x="72"
        y="116"
        width="16"
        height="8"
        rx="2"
        fill="currentColor"
        opacity="0.35"
      />
      {/* face */}
      <circle cx="68" cy="92" r="3" fill="currentColor" opacity="0.9" />
      <circle cx="92" cy="92" r="3" fill="currentColor" opacity="0.9" />
      <path
        d="M68 98c4 4 20 4 24 0"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        opacity="0.9"
      />
    </svg>
  );
}

function CarIcon() {
  return (
    <svg width="150" height="150" viewBox="0 0 160 160" fill="none">
      {/* shadow/ground */}
      <path
        d="M38 124h84"
        stroke="currentColor"
        strokeWidth="7"
        strokeLinecap="round"
        opacity="0.25"
      />

      {/* car body */}
      <path
        d="M52 92c2-10 7-18 17-18h22c10 0 15 8 17 18l3 12c1 5-3 10-9 10H55c-6 0-10-5-9-10l6-12z"
        fill="var(--hull)"
      />

      {/* windshield */}
      <path
        d="M66 78c2-4 5-6 9-6h10c4 0 7 2 9 6l4 10H62l4-10z"
        fill="var(--glass)"
        opacity="0.95"
      />

      {/* headlights */}
      <circle cx="56" cy="102" r="4.5" fill="var(--glass)" />
      <circle cx="104" cy="102" r="4.5" fill="var(--glass)" />

      {/* wheels */}
      <circle cx="62" cy="116" r="8" fill="currentColor" opacity="0.9" />
      <circle cx="98" cy="116" r="8" fill="currentColor" opacity="0.9" />
      <circle cx="62" cy="116" r="3" fill="var(--glass)" opacity="0.85" />
      <circle cx="98" cy="116" r="3" fill="var(--glass)" opacity="0.85" />

      {/* face */}
      <circle cx="74" cy="98" r="2.6" fill="currentColor" opacity="0.9" />
      <circle cx="86" cy="98" r="2.6" fill="currentColor" opacity="0.9" />
      <path
        d="M74 104c2.5 2.5 9.5 2.5 12 0"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        opacity="0.9"
      />
    </svg>
  );
}

function BusIcon() {
  return (
    <svg width="150" height="150" viewBox="0 0 160 160" fill="none">
      {/* body */}
      <rect x="40" y="46" width="80" height="78" rx="16" fill="var(--hull)" />

      {/* destination */}
      <rect
        x="56"
        y="52"
        width="48"
        height="10"
        rx="5"
        fill="var(--glass)"
        opacity="0.9"
      />

      {/* windows */}
      <rect
        x="50"
        y="66"
        width="60"
        height="24"
        rx="8"
        fill="var(--glass)"
        opacity="0.95"
      />
      <rect
        x="50"
        y="94"
        width="28"
        height="16"
        rx="6"
        fill="var(--glass)"
        opacity="0.9"
      />
      <rect
        x="82"
        y="94"
        width="28"
        height="16"
        rx="6"
        fill="var(--glass)"
        opacity="0.9"
      />

      {/* wheels */}
      <circle cx="58" cy="124" r="8" fill="currentColor" opacity="0.9" />
      <circle cx="102" cy="124" r="8" fill="currentColor" opacity="0.9" />
      <circle cx="58" cy="124" r="3" fill="var(--glass)" opacity="0.85" />
      <circle cx="102" cy="124" r="3" fill="var(--glass)" opacity="0.85" />

      {/* headlights */}
      <circle cx="46" cy="110" r="4" fill="var(--glass)" opacity="0.9" />
      <circle cx="114" cy="110" r="4" fill="var(--glass)" opacity="0.9" />

      {/* face */}
      <circle cx="72" cy="110" r="2.6" fill="currentColor" opacity="0.9" />
      <circle cx="88" cy="110" r="2.6" fill="currentColor" opacity="0.9" />
      <path
        d="M72 116c3 3 10 3 16 0"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        opacity="0.9"
      />
    </svg>
  );
}
