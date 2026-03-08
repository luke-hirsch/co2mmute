/**
 * AgentRouteSelector - Component for selecting transport mode and route for an agent
 */

import { useState } from "react";
import type {
  TransportMode,
  CarOptimization,
  PTOptimization,
  AgentRoute,
  RouteSegment,
} from "../../types/routeTypes";

interface AgentRouteSelectorProps {
  agentId: number;
  agentIndex: number;
  destinationNode: number;
  selectedMode: TransportMode | null;
  selectedOptimization?: CarOptimization;
  selectedPTOptimization?: PTOptimization;
  route: AgentRoute | null;
  isPathfinding: boolean;
  error: string | null;
  onSelectMode: (mode: TransportMode, optimization?: CarOptimization, ptOptimization?: PTOptimization) => void;
  onFindRoute: () => void;
  onClearRoute: () => void;
  disabled?: boolean;
}

const TRANSPORT_OPTIONS: {
  id: TransportMode;
  label: string;
  emoji: string;
  color: string;
  borderColor: string;
  description: string;
}[] = [
  {
    id: "car",
    label: "Car",
    emoji: "🚗",
    color: "bg-red-100 dark:bg-red-900/30",
    borderColor: "border-red-400 dark:border-red-600",
    description: "Drive by car",
  },
  {
    id: "public",
    label: "Public",
    emoji: "🚌",
    color: "bg-yellow-100 dark:bg-yellow-900/30",
    borderColor: "border-yellow-400 dark:border-yellow-600",
    description: "Bus or train",
  },
  {
    id: "bike",
    label: "Bike",
    emoji: "🚴",
    color: "bg-green-100 dark:bg-green-900/30",
    borderColor: "border-green-400 dark:border-green-600",
    description: "Cycle",
  },
  {
    id: "walk",
    label: "Walk",
    emoji: "🚶",
    color: "bg-blue-100 dark:bg-blue-900/30",
    borderColor: "border-blue-400 dark:border-blue-600",
    description: "Walk",
  },
];

const CAR_OPTIMIZATION_OPTIONS: {
  id: CarOptimization;
  label: string;
  description: string;
}[] = [
  { id: "time", label: "Fastest", description: "Consider traffic" },
  { id: "distance", label: "Shortest", description: "Ignore traffic" },
  { id: "co2", label: "Greenest", description: "Lowest emissions" },
];

const PT_OPTIMIZATION_OPTIONS: {
  id: PTOptimization;
  label: string;
  description: string;
}[] = [
  { id: "fastest", label: "Fastest", description: "Minimize total time" },
  { id: "fewest_transfers", label: "Fewest Transfers", description: "Prefer direct lines" },
  { id: "no_bus", label: "No Bus", description: "Train & walk only" },
];

function formatTime(minutes: number): string {
  if (minutes < 60) return `${Math.round(minutes)} min`;
  const hours = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  return `${hours}h ${mins}m`;
}

function formatDistance(meters: number): string {
  if (meters < 1000) return `${Math.round(meters)} m`;
  return `${(meters / 1000).toFixed(1)} km`;
}

/** Group consecutive segments into display legs */
interface RouteLeg {
  mode: "walk" | "bus" | "train";
  label: string;
  distanceM: number;
}

function buildLegs(segments: RouteSegment[]): RouteLeg[] {
  if (segments.length === 0) return [];

  const legs: RouteLeg[] = [];

  for (const seg of segments) {
    const mode = seg.mode === "bus" ? "bus" : seg.mode === "train" ? "train" : "walk";
    const label =
      mode === "bus" ? (seg.ptLineName ?? "Bus")
      : mode === "train" ? (seg.ptLineName ?? "Train")
      : "Walk";

    const last = legs.at(-1);
    if (last && last.label === label) {
      last.distanceM += seg.distanceM;
    } else {
      legs.push({ mode, label, distanceM: seg.distanceM });
    }
  }

  return legs;
}

function legEmoji(mode: "walk" | "bus" | "train"): string {
  if (mode === "bus") return "🚌";
  if (mode === "train") return "🚆";
  return "🚶";
}

export default function AgentRouteSelector({
  agentId: _agentId,
  agentIndex,
  destinationNode,
  selectedMode,
  selectedOptimization,
  selectedPTOptimization,
  route,
  isPathfinding,
  error,
  onSelectMode,
  onFindRoute,
  onClearRoute,
  disabled = false,
}: AgentRouteSelectorProps) {
  const [showOptimization, setShowOptimization] = useState(false);

  const handleModeSelect = (mode: TransportMode) => {
    console.log(`[AgentRouteSelector] Mode selected for agent ${_agentId}:`, mode);
    if (mode === "car" || mode === "public") {
      setShowOptimization(true);
      if (mode === "car") {
        onSelectMode(mode, "time");
      } else {
        onSelectMode(mode, undefined, "fastest");
      }
    } else {
      setShowOptimization(false);
      onSelectMode(mode);
    }
  };

  const handleCarOptimizationSelect = (optimization: CarOptimization) => {
    onSelectMode("car", optimization);
    setShowOptimization(false);
    setTimeout(() => onFindRoute(), 100);
  };

  const handlePTOptimizationSelect = (ptOptimization: PTOptimization) => {
    onSelectMode("public", undefined, ptOptimization);
    setShowOptimization(false);
    setTimeout(() => onFindRoute(), 100);
  };

  return (
    <div className="border rounded-lg p-4 bg-white dark:bg-gray-800 shadow-sm">
      {/* Agent Header */}
      <div className="flex justify-between items-center mb-3">
        <h3 className="font-semibold text-lg">Agent {agentIndex + 1}</h3>
        <span className="text-sm text-muted dark:text-darkmutedtext">
          To node {destinationNode}
        </span>
      </div>

      {/* Transport Mode Selection */}
      {!route && !showOptimization && (
        <div className="grid grid-cols-4 gap-2">
          {TRANSPORT_OPTIONS.map((transport) => (
            <button
              key={transport.id}
              onClick={() => handleModeSelect(transport.id)}
              disabled={disabled || isPathfinding}
              className={`p-2 rounded-lg border-2 transition-all duration-200 flex flex-col items-center ${
                selectedMode === transport.id
                  ? `${transport.borderColor} ${transport.color}`
                  : "border-gray-200 dark:border-gray-600 hover:border-gray-400"
              } ${disabled || isPathfinding ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
            >
              <span className="text-2xl">{transport.emoji}</span>
              <span className="text-xs mt-1">{transport.label}</span>
            </button>
          ))}
        </div>
      )}

      {/* Car Optimization Selection */}
      {showOptimization && selectedMode === "car" && !route && (
        <div className="space-y-2">
          <p className="text-sm text-muted dark:text-darkmutedtext mb-2">
            Choose route optimization:
          </p>
          <div className="grid grid-cols-3 gap-2">
            {CAR_OPTIMIZATION_OPTIONS.map((opt) => (
              <button
                key={opt.id}
                onClick={() => handleCarOptimizationSelect(opt.id)}
                disabled={disabled || isPathfinding}
                className={`p-2 rounded-lg border-2 transition-all duration-200 ${
                  selectedOptimization === opt.id
                    ? "border-red-400 bg-red-100 dark:bg-red-900/30"
                    : "border-gray-200 dark:border-gray-600 hover:border-red-300"
                } ${disabled || isPathfinding ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
              >
                <div className="text-sm font-medium">{opt.label}</div>
                <div className="text-xs text-muted dark:text-darkmutedtext">
                  {opt.description}
                </div>
              </button>
            ))}
          </div>
          <button
            onClick={() => { setShowOptimization(false); onClearRoute(); }}
            className="text-sm text-gray-500 hover:text-gray-700 mt-2"
          >
            Back
          </button>
        </div>
      )}

      {/* PT Optimization Selection */}
      {showOptimization && selectedMode === "public" && !route && (
        <div className="space-y-2">
          <p className="text-sm text-muted dark:text-darkmutedtext mb-2">
            Choose PT preference:
          </p>
          <div className="grid grid-cols-3 gap-2">
            {PT_OPTIMIZATION_OPTIONS.map((opt) => (
              <button
                key={opt.id}
                onClick={() => handlePTOptimizationSelect(opt.id)}
                disabled={disabled || isPathfinding}
                className={`p-2 rounded-lg border-2 transition-all duration-200 ${
                  selectedPTOptimization === opt.id
                    ? "border-yellow-400 bg-yellow-100 dark:bg-yellow-900/30"
                    : "border-gray-200 dark:border-gray-600 hover:border-yellow-300"
                } ${disabled || isPathfinding ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
              >
                <div className="text-sm font-medium">{opt.label}</div>
                <div className="text-xs text-muted dark:text-darkmutedtext">
                  {opt.description}
                </div>
              </button>
            ))}
          </div>
          <button
            onClick={() => { setShowOptimization(false); onClearRoute(); }}
            className="text-sm text-gray-500 hover:text-gray-700 mt-2"
          >
            Back
          </button>
        </div>
      )}

      {/* Find Route Button */}
      {selectedMode && !route && !showOptimization && (
        <div className="mt-3">
          <button
            onClick={onFindRoute}
            disabled={disabled || isPathfinding}
            className={`w-full py-2 px-4 rounded-lg font-medium transition-all ${
              isPathfinding
                ? "bg-gray-300 dark:bg-gray-600 cursor-wait"
                : "bg-primary-500 hover:bg-primary-600 text-white"
            }`}
          >
            {isPathfinding ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                    fill="none"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Finding route...
              </span>
            ) : (
              "Find Route"
            )}
          </button>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="mt-3 p-2 rounded bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* Route Display */}
      {route && (
        <div className="mt-3 space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-2xl">
              {TRANSPORT_OPTIONS.find((t) => t.id === selectedMode)?.emoji}
            </span>
            <div>
              <div className="font-medium">
                {TRANSPORT_OPTIONS.find((t) => t.id === selectedMode)?.label}
                {selectedMode === "car" && selectedOptimization && (
                  <span className="text-sm text-muted ml-2">
                    ({CAR_OPTIMIZATION_OPTIONS.find((o) => o.id === selectedOptimization)?.label})
                  </span>
                )}
                {selectedMode === "public" && selectedPTOptimization && (
                  <span className="text-sm text-muted ml-2">
                    ({PT_OPTIMIZATION_OPTIONS.find((o) => o.id === selectedPTOptimization)?.label})
                  </span>
                )}
              </div>
              <div className="text-sm text-muted dark:text-darkmutedtext">
                {formatDistance(route.totalDistanceM)} &middot;{" "}
                {formatTime(route.estimatedTimeMin)}
              </div>
            </div>
          </div>

          {/* PT route leg breakdown */}
          {selectedMode === "public" && (
            <div className="text-xs text-muted dark:text-darkmutedtext flex flex-wrap items-center gap-1">
              {buildLegs(route.segments).map((leg, i) => (
                <span key={i} className="flex items-center gap-1">
                  {i > 0 && <span className="text-gray-400">→</span>}
                  <span>
                    {legEmoji(leg.mode)}{" "}
                    {leg.mode !== "walk" && <span className="font-medium">{leg.label}: </span>}
                    {formatDistance(leg.distanceM)}
                  </span>
                </span>
              ))}
            </div>
          )}

          {/* Non-PT segment count */}
          {selectedMode !== "public" && (
            <div className="text-xs text-muted dark:text-darkmutedtext">
              {route.segments.length} segment{route.segments.length !== 1 ? "s" : ""}
            </div>
          )}

          <button
            onClick={onClearRoute}
            disabled={disabled}
            className="text-sm text-red-500 hover:text-red-700 dark:text-red-400"
          >
            Change selection
          </button>
        </div>
      )}
    </div>
  );
}
