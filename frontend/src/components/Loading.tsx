import { useEffect, useMemo, useState } from "react";

type LoadingProps = {
  label?: string;
  className?: string;
  intervalMs?: number; // default 1000
};

type Mode = "train" | "car" | "bus";

export default function Loading({
  label = "Loading…",
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

      <div className="flex flex-col items-center gap-1 text-center">
        <div className="text-sm font-medium text-gray-900 dark:text-gray-100">
          {label}
        </div>
        <div className="text-xs text-gray-500 dark:text-gray-400">
          Adapting to the network. Modal shift, but make it latency.
        </div>
      </div>

      <style>{`
        .iconStage {
          position: relative;
          width: 170px;
          height: 170px;
          display: grid;
          place-items: center;
        }

        /* Theme vars */
        .iconStage {
          --fg: rgb(17 24 39);         /* gray-900 */
          --fgSoft: rgba(17,24,39,.35);
          --hull: rgb(31 41 55);       /* gray-800 */
          --hullDarkMode: rgb(107 114 128); /* gray-500 */
          color: var(--fg);
        }
        :global(.dark) .iconStage {
          --fg: rgb(229 231 235);      /* gray-200 */
          --fgSoft: rgba(229,231,235,.28);
          --hull: var(--hullDarkMode); /* lighten hull in dark mode */
          color: var(--fg);
        }

        .swirl {
          position: absolute;
          inset: 18px;
          border-radius: 999px;
          border: 3px solid var(--fgSoft);
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

/** Shared helpers: all icons use currentColor + CSS var hull */
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
        fill="#fff"
        opacity="0.9"
      />
      {/* windshield */}
      <rect
        x="44"
        y="48"
        width="72"
        height="40"
        rx="10"
        fill="#fff"
        opacity="0.95"
      />
      {/* headlights */}
      <circle cx="50" cy="104" r="5" fill="#fff" />
      <circle cx="110" cy="104" r="5" fill="#fff" />
      {/* coupler */}
      <rect
        x="72"
        y="116"
        width="16"
        height="8"
        rx="2"
        fill="#000"
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
        fill="#fff"
        opacity="0.95"
      />

      {/* headlights */}
      <circle cx="56" cy="102" r="4.5" fill="#fff" />
      <circle cx="104" cy="102" r="4.5" fill="#fff" />

      {/* wheels */}
      <circle cx="62" cy="116" r="8" fill="currentColor" opacity="0.9" />
      <circle cx="98" cy="116" r="8" fill="currentColor" opacity="0.9" />
      <circle cx="62" cy="116" r="3" fill="#fff" opacity="0.85" />
      <circle cx="98" cy="116" r="3" fill="#fff" opacity="0.85" />

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
        fill="#fff"
        opacity="0.9"
      />

      {/* windows */}
      <rect
        x="50"
        y="66"
        width="60"
        height="24"
        rx="8"
        fill="#fff"
        opacity="0.95"
      />
      <rect
        x="50"
        y="94"
        width="28"
        height="16"
        rx="6"
        fill="#fff"
        opacity="0.9"
      />
      <rect
        x="82"
        y="94"
        width="28"
        height="16"
        rx="6"
        fill="#fff"
        opacity="0.9"
      />

      {/* wheels */}
      <circle cx="58" cy="124" r="8" fill="currentColor" opacity="0.9" />
      <circle cx="102" cy="124" r="8" fill="currentColor" opacity="0.9" />
      <circle cx="58" cy="124" r="3" fill="#fff" opacity="0.85" />
      <circle cx="102" cy="124" r="3" fill="#fff" opacity="0.85" />

      {/* headlights */}
      <circle cx="46" cy="110" r="4" fill="#fff" opacity="0.9" />
      <circle cx="114" cy="110" r="4" fill="#fff" opacity="0.9" />

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
