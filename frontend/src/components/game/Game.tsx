import { useState, useEffect, useCallback, useMemo } from "react";
import { usePlayerMove } from "../../hooks/usePlayerMove";
import { useMapGraph } from "../../hooks/mapHooks";
import GameMapViewer from "./GameMapViewer";
import type { WSGameState, WSPlayerRoundStats } from "../../types/wsTypes";
import type { PlayerAgentAssignments } from "../../types/types";

interface GameProps {
  gameId: string;
  gameState: WSGameState | null;
  playerId?: string;
  isHost: boolean;
  agentCount?: number;
  mapId?: number;
  agentAssignments?: PlayerAgentAssignments;
}

type GamePhase = "lobby" | "playing" | "waiting" | "round_results";
type TransportType = "car" | "public" | "bike" | "walk";

const TRANSPORTATION_OPTIONS: {
  id: TransportType;
  label: string;
  emoji: string;
  color: string;
  description: string;
}[] = [
  {
    id: "car",
    label: "Car",
    emoji: "🚗",
    color: "bg-red-100 dark:bg-red-900/30 border-red-300 dark:border-red-700",
    description: "Fast, high CO₂",
  },
  {
    id: "public",
    label: "Bus/Train",
    emoji: "🚌",
    color: "bg-yellow-100 dark:bg-yellow-900/30 border-yellow-300 dark:border-yellow-700",
    description: "Balanced",
  },
  {
    id: "bike",
    label: "Bike",
    emoji: "🚴",
    color: "bg-green-100 dark:bg-green-900/30 border-green-300 dark:border-green-700",
    description: "Eco-friendly",
  },
  {
    id: "walk",
    label: "Walk",
    emoji: "🚶",
    color: "bg-blue-100 dark:bg-blue-900/30 border-blue-300 dark:border-blue-700",
    description: "Zero CO₂",
  },
];

// Agent colors for visual distinction
const AGENT_COLORS = [
  "text-blue-600",
  "text-green-600",
  "text-orange-600",
  "text-purple-600",
  "text-pink-600",
  "text-cyan-600",
];

interface AgentChoice {
  agentId: number;
  transport: TransportType | null;
}

interface Agent {
  id: number;
  name: string;
  destinationNode: number | null;
  color: string;
}

interface RoundState {
  round: number;
  hasMovedThisRound: boolean;
  agentChoices: AgentChoice[];
  showingResults: boolean;
  resultsStats: WSPlayerRoundStats[] | null;
  selectedAgentId: number | null;
}

const Game = ({ gameId, gameState, playerId, isHost, agentCount = 4, mapId, agentAssignments }: GameProps) => {
  // Generate agents dynamically based on count and assignments
  const agents: Agent[] = useMemo(() => {
    return Array.from({ length: agentCount }, (_, i) => {
      const agentId = i + 1;
      const assignment = agentAssignments?.agents?.find((a) => a.id === agentId);
      return {
        id: agentId,
        name: `Agent ${agentId}`,
        destinationNode: assignment?.destination_node ?? null,
        color: AGENT_COLORS[i % AGENT_COLORS.length],
      };
    });
  }, [agentCount, agentAssignments]);

  // Fetch map data for visualization
  const { data: mapGraph, isLoading: mapLoading, error: mapError } = useMapGraph(mapId ?? 0);

  const initialAgentChoices = useMemo(
    () => agents.map((a) => ({ agentId: a.id, transport: null as TransportType | null })),
    [agents.length]
  );

  const [roundState, setRoundState] = useState<RoundState>({
    round: 0,
    hasMovedThisRound: false,
    agentChoices: initialAgentChoices,
    showingResults: false,
    resultsStats: null,
    selectedAgentId: null,
  });

  const { submitMove, isLoading: isSubmitting, error: moveError } = usePlayerMove({
    gameId,
    playerId: playerId || "",
  });

  const currentRound = gameState?.currentRound ?? 0;
  const lastRoundStats = gameState?.lastRoundStats;

  // Memoize stats key to detect changes
  const statsKey = useMemo(
    () => (lastRoundStats ? JSON.stringify(lastRoundStats) : ""),
    [lastRoundStats]
  );

  // Handle round/stats changes
  useEffect(() => {
    if (!gameState?.isActive) return;

    const roundChanged = currentRound !== roundState.round && roundState.round !== 0;
    const hasNewStats = lastRoundStats && lastRoundStats.length > 0;

    if (roundChanged && hasNewStats) {
      const showTimer = setTimeout(() => {
        setRoundState((prev) => ({
          ...prev,
          showingResults: true,
          resultsStats: lastRoundStats,
        }));
      }, 0);

      const hideTimer = setTimeout(() => {
        setRoundState({
          round: currentRound,
          hasMovedThisRound: false,
          agentChoices: initialAgentChoices,
          showingResults: false,
          resultsStats: null,
          selectedAgentId: null,
        });
      }, 3000);

      return () => {
        clearTimeout(showTimer);
        clearTimeout(hideTimer);
      };
    } else if (roundChanged) {
      const timer = setTimeout(() => {
        setRoundState({
          round: currentRound,
          hasMovedThisRound: false,
          agentChoices: initialAgentChoices,
          showingResults: false,
          resultsStats: null,
          selectedAgentId: null,
        });
      }, 0);
      return () => clearTimeout(timer);
    } else if (roundState.round === 0 && currentRound > 0) {
      const timer = setTimeout(() => {
        setRoundState((prev) => ({
          ...prev,
          round: currentRound,
        }));
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [currentRound, statsKey, gameState?.isActive, roundState.round, lastRoundStats, initialAgentChoices]);

  // Derive phase from current state
  const phase: GamePhase = useMemo(() => {
    if (!gameState || (!gameState.isActive && !gameState.endedAt)) {
      return "lobby";
    }
    if (gameState.isActive) {
      if (roundState.showingResults && roundState.resultsStats) {
        return "round_results";
      }
      if (roundState.hasMovedThisRound) {
        return "waiting";
      }
      return "playing";
    }
    return "lobby";
  }, [gameState, roundState]);

  // Check if all agents have a transport selected
  const allAgentsSelected = roundState.agentChoices.every((c) => c.transport !== null);

  const handleAgentTransportSelect = useCallback((agentId: number, transport: TransportType) => {
    setRoundState((prev) => ({
      ...prev,
      agentChoices: prev.agentChoices.map((c) =>
        c.agentId === agentId ? { ...c, transport } : c
      ),
    }));
  }, []);

  const handleSubmitAllChoices = useCallback(async () => {
    if (!playerId || roundState.hasMovedThisRound || isSubmitting || !allAgentsSelected) return;

    // Build payload with all agent choices
    const payload = {
      agents: roundState.agentChoices.map((c) => ({
        agent_id: c.agentId,
        action: c.transport,
      })),
    };

    // For the dry run, we'll use the first agent's choice as the "action" and put all in payload
    const primaryAction = roundState.agentChoices[0]?.transport || "walk";
    const success = await submitMove(primaryAction, payload);

    if (success) {
      setRoundState((prev) => ({ ...prev, hasMovedThisRound: true }));
    }
  }, [playerId, roundState.hasMovedThisRound, roundState.agentChoices, isSubmitting, allAgentsSelected, submitMove]);

  // Render lobby phase
  if (phase === "lobby") {
    return (
      <div className="w-full max-w-2xl text-center">
        <div className="mb-8">
          <div className="text-6xl mb-4">🎮</div>
          <h1 className="text-2xl font-bold mb-2">Waiting for game to start</h1>
          <p className="text-muted dark:text-darkmutedtext">
            {isHost
              ? "Start the game when all players have joined"
              : "The host will start the game soon"}
          </p>
        </div>

        {/* Show agents preview */}
        <div className="bg-surface dark:bg-darksurface rounded-lg p-6 border border-subtle dark:border-darksubtle">
          <h3 className="text-lg font-semibold mb-4">Your Agents ({agents.length})</h3>
          <div className="grid grid-cols-2 gap-3">
            {agents.map((agent) => (
              <div
                key={agent.id}
                className="p-3 bg-elevated dark:bg-darkelevated rounded-lg flex items-center gap-3"
              >
                <span className={`text-2xl font-bold ${agent.color}`}>#{agent.id}</span>
                <div className="text-left">
                  <p className="font-medium">{agent.name}</p>
                  <p className="text-sm text-muted dark:text-darkmutedtext">
                    {agent.destinationNode ? `→ Node ${agent.destinationNode}` : "Awaiting assignment"}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-6 animate-pulse flex justify-center gap-2">
          <div className="w-3 h-3 bg-primary-500 rounded-full"></div>
          <div className="w-3 h-3 bg-primary-500 rounded-full animation-delay-200"></div>
          <div className="w-3 h-3 bg-primary-500 rounded-full animation-delay-400"></div>
        </div>
      </div>
    );
  }

  // Render round results phase
  if (phase === "round_results" && roundState.resultsStats) {
    const completedRound = currentRound - 1;
    return (
      <div className="w-full max-w-2xl">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold mb-2">Round {completedRound} Complete!</h1>
          <p className="text-muted dark:text-darkmutedtext">
            Next round starting soon...
          </p>
        </div>

        <div className="bg-surface dark:bg-darksurface rounded-lg p-6 border border-subtle dark:border-darksubtle">
          <h2 className="text-lg font-semibold mb-4">Round Results</h2>
          <div className="space-y-3">
            {roundState.resultsStats.map((stat, index) => (
              <div
                key={stat.player_id}
                className="flex items-center justify-between p-3 bg-elevated dark:bg-darkelevated rounded"
              >
                <div className="flex items-center gap-3">
                  <span className="text-lg font-bold text-primary-600 dark:text-primary-400">
                    #{index + 1}
                  </span>
                  <div>
                    <p className="font-medium">{stat.player_name}</p>
                    <p className="text-sm text-muted dark:text-darkmutedtext">
                      {TRANSPORTATION_OPTIONS.find((t) => t.id === stat.action)?.emoji}{" "}
                      {stat.action}
                    </p>
                  </div>
                </div>
                <div className="text-right text-sm">
                  <p className="font-medium">{stat.emissions_g}g CO₂</p>
                  <p className="text-muted dark:text-darkmutedtext">
                    {stat.time_min} min
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-6 flex justify-center">
          <div className="animate-spin w-6 h-6 border-2 border-primary-500 border-t-transparent rounded-full"></div>
        </div>
      </div>
    );
  }

  // Render waiting phase
  if (phase === "waiting") {
    return (
      <div className="w-full max-w-2xl text-center">
        <div className="mb-8">
          <div className="text-6xl mb-4">✅</div>
          <h1 className="text-2xl font-bold mb-2">All Agents Dispatched!</h1>
        </div>

        {/* Show submitted choices */}
        <div className="bg-surface dark:bg-darksurface rounded-lg p-6 border border-subtle dark:border-darksubtle mb-6">
          <h3 className="text-lg font-semibold mb-4">Your Choices</h3>
          <div className="space-y-2">
            {agents.map((agent) => {
              const choice = roundState.agentChoices.find((c) => c.agentId === agent.id);
              const transport = TRANSPORTATION_OPTIONS.find((t) => t.id === choice?.transport);
              return (
                <div
                  key={agent.id}
                  className="flex items-center justify-between p-3 bg-elevated dark:bg-darkelevated rounded"
                >
                  <div className="flex items-center gap-2">
                    <span className={`font-bold ${agent.color}`}>#{agent.id}</span>
                    <span className="font-medium">{agent.name}</span>
                    {agent.destinationNode && (
                      <span className="text-muted dark:text-darkmutedtext">→ Node {agent.destinationNode}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span>{transport?.emoji}</span>
                    <span>{transport?.label}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="bg-surface dark:bg-darksurface rounded-lg p-6 border border-subtle dark:border-darksubtle">
          <p className="text-lg mb-4">Waiting for other players...</p>
          <div className="flex justify-center gap-2">
            <div className="w-3 h-3 bg-primary-500 rounded-full animate-bounce"></div>
            <div className="w-3 h-3 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: "0.1s" }}></div>
            <div className="w-3 h-3 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }}></div>
          </div>
        </div>

        {gameState && (
          <div className="mt-6 text-sm text-muted dark:text-darkmutedtext">
            Round {gameState.currentRound} of {gameState.maxRounds}
          </div>
        )}
      </div>
    );
  }

  // Render playing phase (agent transport selection)
  return (
    <div className="w-full max-w-4xl">
      {/* Round header */}
      {gameState && (
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold mb-2">
            Round {gameState.currentRound} of {gameState.maxRounds}
          </h1>
          <p className="text-muted dark:text-darkmutedtext">
            Choose transportation for each family member
          </p>

          {/* CO2 Progress */}
          <div className="mt-4 max-w-md mx-auto">
            <div className="flex justify-between text-sm mb-1">
              <span>CO₂ Budget</span>
              <span>
                {(gameState.totalEmissionsG / 1000).toFixed(1)} /{" "}
                {(gameState.maxCo2LevelG / 1000).toFixed(0)} kg
              </span>
            </div>
            <div className="w-full bg-gray-300 dark:bg-gray-600 rounded-full h-2">
              <div
                className={`h-2 rounded-full transition-all duration-300 ${
                  gameState.totalEmissionsG / gameState.maxCo2LevelG > 0.75
                    ? "bg-red-500"
                    : gameState.totalEmissionsG / gameState.maxCo2LevelG > 0.5
                      ? "bg-yellow-500"
                      : "bg-green-500"
                }`}
                style={{
                  width: `${Math.min((gameState.totalEmissionsG / gameState.maxCo2LevelG) * 100, 100)}%`,
                }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Map viewer - full width, prominent */}
      {mapId && (
        <div className="bg-surface dark:bg-darksurface rounded-lg p-4 border border-subtle dark:border-darksubtle mb-6">
          <h3 className="text-lg font-semibold mb-3">
            City Map
            {roundState.selectedAgentId && (
              <span className="ml-2 text-sm font-normal text-muted dark:text-darkmutedtext">
                — Showing Agent {roundState.selectedAgentId} route
              </span>
            )}
          </h3>
          <GameMapViewer
            mapGraph={mapGraph ?? null}
            isLoading={mapLoading}
            error={mapError ? String(mapError) : null}
            homeNodeId={agentAssignments?.home_node}
            destinationNodeId={
              roundState.selectedAgentId
                ? agents.find((a) => a.id === roundState.selectedAgentId)?.destinationNode ?? undefined
                : undefined
            }
          />
        </div>
      )}

      {/* Agent selection cards */}
      <div className={`grid grid-cols-1 md:grid-cols-2 gap-4 mb-6 ${roundState.hasMovedThisRound ? "opacity-60" : ""}`}>
        {agents.map((agent) => {
          const choice = roundState.agentChoices.find((c) => c.agentId === agent.id);
          const isAgentSelected = roundState.selectedAgentId === agent.id;
          const isDisabled = isSubmitting || roundState.hasMovedThisRound;
          return (
            <div
              key={agent.id}
              onClick={() => !isDisabled && setRoundState((prev) => ({
                ...prev,
                selectedAgentId: isAgentSelected ? null : agent.id
              }))}
              className={`bg-surface dark:bg-darksurface rounded-lg p-4 border-2 transition-all ${
                isDisabled ? "cursor-not-allowed" : "cursor-pointer"
              } ${
                isAgentSelected
                  ? "border-primary-500 ring-2 ring-primary-200 dark:ring-primary-800"
                  : "border-subtle dark:border-darksubtle"
              } ${!isDisabled && !isAgentSelected ? "hover:border-gray-400" : ""}`}
            >
              {/* Agent header */}
              <div className="flex items-center gap-3 mb-3">
                <span className={`text-2xl font-bold ${agent.color}`}>#{agent.id}</span>
                <div className="flex-1">
                  <h3 className={`font-semibold ${agent.color}`}>{agent.name}</h3>
                  <p className="text-xs text-muted dark:text-darkmutedtext">
                    🏠 → {agent.destinationNode ? `Node ${agent.destinationNode}` : "?"}
                  </p>
                </div>
                {isAgentSelected && (
                  <span className="text-xs bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300 px-2 py-1 rounded">
                    Selected
                  </span>
                )}
              </div>

              {/* Transport options */}
              <div className="grid grid-cols-4 gap-2">
                {TRANSPORTATION_OPTIONS.map((transport) => {
                  const isTransportSelected = choice?.transport === transport.id;
                  return (
                    <button
                      key={transport.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        if (!isDisabled) handleAgentTransportSelect(agent.id, transport.id);
                      }}
                      disabled={isDisabled}
                      className={`p-2 rounded-lg border-2 transition-all duration-200 ${transport.color} ${
                        isTransportSelected
                          ? "ring-2 ring-primary-500 border-primary-500"
                          : "border-transparent"
                      } ${!isDisabled && !isTransportSelected ? "hover:border-gray-400" : ""} ${
                          isSubmitting || roundState.hasMovedThisRound
                            ? "opacity-50 cursor-not-allowed"
                            : "cursor-pointer hover:shadow-md"
                        }`}
                      >
                        <div className="text-2xl mb-1">{transport.emoji}</div>
                        <div className="text-xs font-medium">{transport.label}</div>
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

      {/* Submit button */}
      <div className="text-center">
        <button
          onClick={handleSubmitAllChoices}
          disabled={!allAgentsSelected || isSubmitting || roundState.hasMovedThisRound || !playerId}
          className={`px-8 py-3 rounded-lg font-semibold text-lg transition-all duration-200 ${
            allAgentsSelected && !isSubmitting && !roundState.hasMovedThisRound && playerId
              ? "bg-primary-600 text-white hover:bg-primary-700 cursor-pointer"
              : "bg-gray-300 dark:bg-gray-700 text-gray-500 dark:text-gray-400 cursor-not-allowed"
          }`}
        >
          {isSubmitting
            ? "Submitting..."
            : allAgentsSelected
              ? "Submit All Choices"
              : `Select transport for all ${agents.length} agents`}
        </button>
      </div>

      {/* Error message */}
      {moveError && (
        <div className="mt-4 p-4 rounded bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-200 text-center">
          {moveError}
        </div>
      )}
    </div>
  );
};

export default Game;
