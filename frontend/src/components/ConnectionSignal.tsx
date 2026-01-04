import { useEffect, useState } from "react";
import type { WSConnectionQuality } from "../types/wsTypes";

interface ConnectionSignalProps {
  quality: WSConnectionQuality;
  showTooltip?: boolean;
  size?: "sm" | "md" | "lg";
}

/**
 * Displays a WiFi-style signal strength indicator based on connection quality
 * - 0 arcs: disconnected (all arcs greyed out)
 * - 1 arc: poor (high latency or reconnecting)
 * - 2 arcs: fair (moderate latency)
 * - 3 arcs: good (acceptable latency)
 * - 4 arcs: very good (low latency)
 * - 5 arcs: excellent (very low latency)
 */
export default function ConnectionSignal({
  quality,
  showTooltip = true,
  size = "md",
}: ConnectionSignalProps) {
  // Animate signal strength from 0 to the target value over 2 seconds
  const [animatedStrength, setAnimatedStrength] = useState(0);

  useEffect(() => {
    let animationFrame: number;
    let startTime: number | null = null;
    const duration = 2000; // 2 seconds

    const animate = (currentTime: number) => {
      if (startTime === null) {
        startTime = currentTime;
      }

      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);

      // Smoothly animate to the target signal strength
      const targetStrength = quality.signalStrength;
      const newStrength = Math.round(progress * targetStrength);

      setAnimatedStrength(newStrength);

      if (progress < 1) {
        animationFrame = requestAnimationFrame(animate);
      }
    };

    animationFrame = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(animationFrame);
    };
  }, [quality.signalStrength]);
  const getStatusText = (): string => {
    switch (quality.status) {
      case "open":
        if (quality.signalStrength === 5) return "Excellent";
        if (quality.signalStrength === 4) return "Very Good";
        if (quality.signalStrength === 3) return "Good";
        if (quality.signalStrength === 2) return "Fair";
        if (quality.signalStrength === 1) return "Poor";
        return "Connecting...";
      case "connecting":
        return "Connecting...";
      case "error":
        return "Connection Error";
      case "closed":
        return "Disconnected";
      default:
        return "Idle";
    }
  };

  const tooltipText = showTooltip
    ? `${getStatusText()} (${quality.latency.current}ms)`
    : undefined;

  const sizeClasses = {
    sm: "w-4 h-4",
    md: "w-5 h-5",
    lg: "w-6 h-6",
  };

  const getStrokeOpacity = (arcIndex: number): number => {
    if (animatedStrength === 0) return 0.2; // All greyed out when disconnected
    return arcIndex < animatedStrength ? 1 : 0.2;
  };

  return (
    <div title={tooltipText} className="inline-flex">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        strokeWidth="1.5"
        stroke="currentColor"
        className={`${sizeClasses[size]} text-gray-600 dark:text-gray-400 transition-opacity duration-300`}
      >
        {/* Innermost arc (1 bar) - closest to source */}
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M8.288 15.038a5.25 5.25 0 0 1 7.424 0"
          style={{ opacity: getStrokeOpacity(1) }}
        />

        {/* Second arc (2 bars) */}
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M5.106 11.856c3.807-3.808 9.98-3.808 13.788 0"
          style={{ opacity: getStrokeOpacity(2) }}
        />

        {/* Third arc (3 bars) */}
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M1.924 8.674c5.565-5.565 14.587-5.565 20.152 0"
          style={{ opacity: getStrokeOpacity(3) }}
        />

        {/* Dot at the bottom */}
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M12.53 18.22l-.53.53-.53-.53a.75.75 0 0 1 1.06 0Z"
          style={{ opacity: animatedStrength === 0 ? 0.2 : 1 }}
        />
      </svg>
    </div>
  );
}
