import { useState, useEffect, useMemo, useCallback } from "react";
import { useGameSocket } from "../../hooks/useGameSocket";
import { usePlayerMove } from "../../hooks/usePlayerMove";
import { useGameDetails, usePlayerGameDetails } from "../../hooks/gameHooks";
import { useMapGraph } from "../../hooks/mapHooks";
import { useAgentRoutes } from "../../hooks/usePathfinding";
import Loading from "../Loading";
import GameMapViewer from "./GameMapViewer";
import type { ExtendedMapGraph, TransportMode, CarOptimization } from "../../types/routeTypes";

interface GamePlayProps {
  gameId: string;
  playerId?: string;
  isHost?: boolean;
}

type GamePhase = "lobby" | "playing" | "waiting" | "round_results";

const TRANSPORT_OPTIONS: {
  id: TransportMode;
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
    description: "Fast, high CO2",
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
    description: "Zero CO2",
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

// Agent colors for visual distinction
const AGENT_COLORS = [
  { text: "text-blue-600 dark:text-blue-400", bg: "bg-blue-50 dark:bg-blue-900/20" },
  { text: "text-green-600 dark:text-green-400", bg: "bg-green-50 dark:bg-green-900/20" },
  { text: "text-orange-600 dark:text-orange-400", bg: "bg-orange-50 dark:bg-orange-900/20" },
  { text: "text-purple-600 dark:text-purple-400", bg: "bg-purple-50 dark:bg-purple-900/20" },
  { text: "text-pink-600 dark:text-pink-400", bg: "bg-pink-50 dark:bg-pink-900/20" },
  { text: "text-cyan-600 dark:text-cyan-400", bg: "bg-cyan-50 dark:bg-cyan-900/20" },
];

export default function GamePlay({
  gameId,
  playerId,
  isHost = false,
}: GamePlayProps) {
  const {
    isConnected,
    error: gameError,
    gameState,
  } = useGameSocket({ gameId });

  const {
    submitMove,
    isLoading: isSubmitting,
    error: moveError,
  } = usePlayerMove({
    gameId,
    playerId: playerId || "",
  });

  const [isSubmitted, setIsSubmitted] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null);
  const [showCarOptions, setShowCarOptions] = useState<number | null>(null); // agentId showing car options
  const [animationEnabled, setAnimationEnabled] = useState(true);
  const [animationSpeed, setAnimationSpeed] = useState(100); // ms per step

  // Fetch game details to get map ID and player data
  const hostGameDetails = useGameDetails(gameId, isHost);
  const playerGameDetails = usePlayerGameDetails(
    gameId,
    playerId || "",
    !isHost && !!playerId
  );

  const gameDetails = isHost ? hostGameDetails.data : playerGameDetails.data;
  const gameDetailsLoading = isHost
    ? hostGameDetails.isLoading
    : playerGameDetails.isLoading;

  // Fetch map graph once we have the map ID
  const mapId = gameDetails?.game_map;
  const {
    data: mapGraph,
    isLoading: mapLoading,
    error: mapError,
  } = useMapGraph(mapId ?? "", undefined);

  // Get player's agent assignments
  const playerData = useMemo(() => {
    if (!playerGameDetails.data) return null;
    const data = playerGameDetails.data as Record<string, unknown>;
    if (data.agent_assignments) {
      return data as {
        agent_assignments: {
          home_node: number;
          agents: { id: number; destination_node: number }[];
        };
      };
    }
    return null;
  }, [playerGameDetails.data]);

  const agentAssignments = playerData?.agent_assignments?.agents ?? [];
  const homeNode = playerData?.agent_assignments?.home_node;

  // Initialize agent routes hook
  const {
    agents,
    setAgentMode,
    findAgentRoute,
    clearAgentRoute,
    allRoutesComplete,
    getSubmissionPayload,
    activePathfindingState,
  } = useAgentRoutes(agentAssignments, {
    scale: (mapGraph as ExtendedMapGraph)?.scale ?? 100,
    enableAnimation: animationEnabled,
    animationSpeed,
  });

  // Reset submission state when round changes
  useEffect(() => {
    setIsSubmitted(false);
    setShowCarOptions(null);
  }, [gameState?.currentRound]);

  // Derive phase
  const phase: GamePhase = useMemo(() => {
    if (!gameState || (!gameState.isActive && !gameState.endedAt)) {
      return "lobby";
    }
    if (gameState.isActive) {
      if (isSubmitted) {
        return "waiting";
      }
      return "playing";
    }
    return "lobby";
  }, [gameState, isSubmitted]);

  // Get route segments for visualization
  const selectedAgentRoute = useMemo(() => {
    if (selectedAgentId === null) return null;
    const agent = agents.find((a) => a.agentId === selectedAgentId);
    return agent?.route ?? null;
  }, [selectedAgentId, agents]);

  // Get destination node for selected agent
  const selectedDestination = useMemo(() => {
    if (selectedAgentId === null) return undefined;
    const agent = agents.find((a) => a.agentId === selectedAgentId);
    return agent?.destinationNode;
  }, [selectedAgentId, agents]);

  const handleFindRoute = useCallback(async (agentId: number) => {
    if (!mapGraph || homeNode === undefined) {
      console.warn("[GamePlay] Cannot find route: missing mapGraph or homeNode");
      return;
    }

    const extendedGraph: ExtendedMapGraph = {
      ...mapGraph,
      bus_lines: (mapGraph as ExtendedMapGraph).bus_lines ?? [],
      train_lines: (mapGraph as ExtendedMapGraph).train_lines ?? [],
      scale: (mapGraph as ExtendedMapGraph).scale ?? 100,
    };

    await findAgentRoute(agentId, extendedGraph, homeNode);
  }, [mapGraph, homeNode, findAgentRoute]);

  const handleTransportSelect = useCallback((agentId: number, mode: TransportMode) => {
    if (mode === "car") {
      setShowCarOptions(agentId);
      setAgentMode(agentId, mode, "time");
    } else {
      setShowCarOptions(null);
      setAgentMode(agentId, mode);
      // Auto-find route for non-car modes
      setTimeout(() => handleFindRoute(agentId), 100);
    }
    // Select this agent for map visualization
    setSelectedAgentId(agentId);
  }, [setAgentMode, handleFindRoute]);

  const handleCarOptimizationSelect = useCallback((agentId: number, optimization: CarOptimization) => {
    setAgentMode(agentId, "car", optimization);
    setShowCarOptions(null);
    // Auto-find route after selecting optimization
    setTimeout(() => handleFindRoute(agentId), 100);
  }, [setAgentMode, handleFindRoute]);

  const handleClearRoute = useCallback((agentId: number) => {
    clearAgentRoute(agentId);
    setShowCarOptions(null);
  }, [clearAgentRoute]);

  const handleSubmit = async () => {
    const payload = getSubmissionPayload();
    if (!payload) return;

    const success = await submitMove("route_submission", { agents: payload.agents });
    if (success) {
      setIsSubmitted(true);
    }
  };

  // Check if any agent is currently pathfinding
  const isAnyPathfinding = agents.some((a) => a.isPathfinding);

  // Format helpers
  const formatTime = (minutes: number): string => {
    if (minutes < 60) return `${Math.round(minutes)} min`;
    const hours = Math.floor(minutes / 60);
    const mins = Math.round(minutes % 60);
    return `${hours}h ${mins}m`;
  };

  const formatDistance = (meters: number): string => {
    if (meters < 1000) return `${Math.round(meters)} m`;
    return `${(meters / 1000).toFixed(1)} km`;
  };

  if (!isConnected) {
    return (
      <div className="flex flex-col items-center justify-center gap-4">
        <Loading />
        <p className="text-muted dark:text-darkmutedtext">Connecting to game...</p>
      </div>
    );
  }

  if (gameError) {
    return (
      <div className="text-red-600 dark:text-red-400">Error: {gameError}</div>
    );
  }

  if (!gameState) {
    return <Loading />;
  }

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

        <div className="bg-surface dark:bg-darksurface rounded-lg p-6 border border-subtle dark:border-darksubtle">
          <h3 className="text-lg font-semibold mb-4">Your Agents ({agentAssignments.length || "..."})</h3>
          <div className="grid grid-cols-2 gap-3">
            {agentAssignments.map((agent, index) => {
              const color = AGENT_COLORS[index % AGENT_COLORS.length];
              return (
                <div
                  key={agent.id}
                  className={`p-3 ${color.bg} rounded-lg flex items-center gap-3`}
                >
                  <span className={`text-2xl font-bold ${color.text}`}>#{agent.id}</span>
                  <div className="text-left">
                    <p className="font-medium">Agent {agent.id}</p>
                    <p className="text-sm text-muted dark:text-darkmutedtext">
                      → Node {agent.destination_node}
                    </p>
                  </div>
                </div>
              );
            })}
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

  // Render waiting phase
  if (phase === "waiting") {
    return (
      <div className="w-full max-w-2xl text-center">
        <div className="mb-8">
          <div className="text-6xl mb-4">✅</div>
          <h1 className="text-2xl font-bold mb-2">All Agents Dispatched!</h1>
        </div>

        <div className="bg-surface dark:bg-darksurface rounded-lg p-6 border border-subtle dark:border-darksubtle mb-6">
          <h3 className="text-lg font-semibold mb-4">Your Choices</h3>
          <div className="space-y-2">
            {agents.map((agent, index) => {
              const color = AGENT_COLORS[index % AGENT_COLORS.length];
              const transport = TRANSPORT_OPTIONS.find((t) => t.id === agent.selectedMode);
              return (
                <div
                  key={agent.agentId}
                  className="flex items-center justify-between p-3 bg-elevated dark:bg-darkelevated rounded"
                >
                  <div className="flex items-center gap-2">
                    <span className={`font-bold ${color.text}`}>#{agent.agentId}</span>
                    <span className="font-medium">Agent {agent.agentId}</span>
                    <span className="text-muted dark:text-darkmutedtext">→ Node {agent.destinationNode}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span>{transport?.emoji}</span>
                    <span>{transport?.label}</span>
                    {agent.route && (
                      <span className="text-xs text-muted dark:text-darkmutedtext">
                        ({formatDistance(agent.route.totalDistanceM)})
                      </span>
                    )}
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

        <div className="mt-6 text-sm text-muted dark:text-darkmutedtext">
          Round {gameState.currentRound} of {gameState.maxRounds}
        </div>
      </div>
    );
  }

  // Render playing phase
  return (
    <div className="w-full max-w-4xl">
      {/* Round header */}
      <div className="text-center mb-6">
        <h1 className="text-2xl font-bold mb-2">
          Round {gameState.currentRound} of {gameState.maxRounds}
        </h1>
        <p className="text-muted dark:text-darkmutedtext">
          Choose transportation for each agent
        </p>

        {/* CO2 Progress */}
        <div className="mt-4 max-w-md mx-auto">
          <div className="flex justify-between text-sm mb-1">
            <span>CO2 Budget</span>
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

      {/* Dijkstra Algorithm Progress */}
      {isAnyPathfinding && activePathfindingState && animationEnabled && (
        <div className="mb-4 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-lg">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-sm font-medium text-blue-700 dark:text-blue-300">
              Dijkstra's Algorithm
            </span>
            <span className="text-xs text-blue-500 dark:text-blue-400 font-mono">
              {activePathfindingState.visitedNodes.size} nodes visited
              {" | "}
              {activePathfindingState.exploredEdges.size} edges explored
            </span>
          </div>
          <div className="w-full bg-blue-200 dark:bg-blue-800 rounded-full h-1.5">
            <div
              className="h-1.5 rounded-full bg-blue-500 transition-all duration-150"
              style={{
                width: `${Math.min(
                  (activePathfindingState.visitedNodes.size / (mapGraph?.nodes.length ?? 1)) * 100,
                  100
                )}%`,
              }}
            />
          </div>
        </div>
      )}
      {isAnyPathfinding && !animationEnabled && (
        <div className="mb-4 p-3 bg-blue-100 dark:bg-blue-900/30 border border-blue-300 dark:border-blue-700 rounded-lg flex items-center justify-center gap-3">
          <svg className="animate-spin h-5 w-5 text-blue-600 dark:text-blue-400" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          <span className="text-blue-700 dark:text-blue-300 font-medium">Finding optimal route...</span>
        </div>
      )}

      {/* Map viewer */}
      <div className="bg-surface dark:bg-darksurface rounded-lg p-4 border border-subtle dark:border-darksubtle mb-6">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-semibold">
            City Map
            {selectedAgentId && (
              <span className="ml-2 text-sm font-normal text-muted dark:text-darkmutedtext">
                — Showing Agent {selectedAgentId} route
              </span>
            )}
          </h3>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-1.5 text-sm cursor-pointer select-none">
              <input
                type="checkbox"
                checked={animationEnabled}
                onChange={(e) => setAnimationEnabled(e.target.checked)}
                className="rounded"
              />
              <span className="text-muted dark:text-darkmutedtext">Show Dijkstra</span>
            </label>
            {animationEnabled && (
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-muted dark:text-darkmutedtext">Fast</span>
                <input
                  type="range"
                  min={20}
                  max={500}
                  step={10}
                  value={animationSpeed}
                  onChange={(e) => setAnimationSpeed(Number(e.target.value))}
                  className="w-20 h-1 accent-primary-500"
                />
                <span className="text-xs text-muted dark:text-darkmutedtext">Slow</span>
              </div>
            )}
          </div>
        </div>
        <GameMapViewer
          mapGraph={mapGraph ?? null}
          isLoading={mapLoading || gameDetailsLoading}
          error={mapError ? "Failed to load map" : null}
          homeNodeId={homeNode}
          destinationNodeId={selectedDestination}
          routeSegments={selectedAgentRoute?.segments}
          highlightedNodes={
            selectedAgentRoute
              ? new Set(selectedAgentRoute.segments.flatMap((s) => [s.startNode, s.endNode]))
              : undefined
          }
          showDijkstraViz={animationEnabled && !!activePathfindingState}
          pathfindingVisited={activePathfindingState?.visitedNodes}
          pathfindingCurrent={activePathfindingState?.currentNode}
          pathfindingExploredEdges={activePathfindingState?.exploredEdges}
          pathfindingRelaxedEdge={activePathfindingState?.relaxedEdge}
          pathfindingDistances={activePathfindingState?.tentativeDistances}
          pathfindingFinalPath={activePathfindingState?.finalPath}
          pathfindingPreviousEdges={activePathfindingState?.previousEdges}
        />
      </div>

      {/* Agent selection cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {agents.map((agent, index) => {
          const color = AGENT_COLORS[index % AGENT_COLORS.length];
          const isAgentSelected = selectedAgentId === agent.agentId;
          const isDisabled = isSubmitting || isSubmitted;
          const showingCarOptions = showCarOptions === agent.agentId;

          return (
            <div
              key={agent.agentId}
              onClick={() => !isDisabled && setSelectedAgentId(isAgentSelected ? null : agent.agentId)}
              className={`bg-surface dark:bg-darksurface rounded-lg p-4 border-2 transition-all ${
                isDisabled ? "cursor-not-allowed opacity-60" : "cursor-pointer"
              } ${
                isAgentSelected
                  ? "border-primary-500 ring-2 ring-primary-200 dark:ring-primary-800"
                  : "border-subtle dark:border-darksubtle"
              } ${!isDisabled && !isAgentSelected ? "hover:border-gray-400" : ""}`}
            >
              {/* Agent header */}
              <div className="flex items-center gap-3 mb-3">
                <span className={`text-2xl font-bold ${color.text}`}>#{agent.agentId}</span>
                <div className="flex-1">
                  <h3 className={`font-semibold ${color.text}`}>Agent {agent.agentId}</h3>
                  <p className="text-xs text-muted dark:text-darkmutedtext">
                    🏠 → Node {agent.destinationNode}
                  </p>
                </div>
                {agent.isPathfinding && (
                  <div className="flex items-center gap-1 text-xs bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 px-2 py-1 rounded">
                    <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Finding...
                  </div>
                )}
                {agent.route && !agent.isPathfinding && (
                  <span className="text-xs bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300 px-2 py-1 rounded">
                    Route found
                  </span>
                )}
              </div>

              {/* Route result display */}
              {agent.route && !showingCarOptions && (
                <div className="mb-3 p-2 bg-gray-50 dark:bg-gray-800 rounded text-sm">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-xl">
                        {TRANSPORT_OPTIONS.find((t) => t.id === agent.selectedMode)?.emoji}
                      </span>
                      <span className="font-medium">
                        {TRANSPORT_OPTIONS.find((t) => t.id === agent.selectedMode)?.label}
                      </span>
                      {agent.selectedMode === "car" && agent.selectedOptimization && (
                        <span className="text-xs text-muted dark:text-darkmutedtext">
                          ({CAR_OPTIMIZATION_OPTIONS.find((o) => o.id === agent.selectedOptimization)?.label})
                        </span>
                      )}
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleClearRoute(agent.agentId);
                      }}
                      disabled={isDisabled}
                      className="text-xs text-red-500 hover:text-red-700 dark:text-red-400"
                    >
                      Change
                    </button>
                  </div>
                  <div className="text-xs text-muted dark:text-darkmutedtext mt-1">
                    {formatDistance(agent.route.totalDistanceM)} · {formatTime(agent.route.estimatedTimeMin)}
                  </div>
                </div>
              )}

              {/* Error display */}
              {agent.error && (
                <div className="mb-3 p-2 bg-red-100 dark:bg-red-900/30 rounded text-sm text-red-700 dark:text-red-300">
                  {agent.error}
                </div>
              )}

              {/* Car optimization options */}
              {showingCarOptions && !agent.route && (
                <div className="mb-3" onClick={(e) => e.stopPropagation()}>
                  <p className="text-sm text-muted dark:text-darkmutedtext mb-2">
                    Choose route optimization:
                  </p>
                  <div className="grid grid-cols-3 gap-2">
                    {CAR_OPTIMIZATION_OPTIONS.map((opt) => (
                      <button
                        key={opt.id}
                        onClick={() => handleCarOptimizationSelect(agent.agentId, opt.id)}
                        disabled={isDisabled || agent.isPathfinding}
                        className={`p-2 rounded-lg border-2 transition-all ${
                          agent.selectedOptimization === opt.id
                            ? "border-red-400 bg-red-100 dark:bg-red-900/30"
                            : "border-gray-200 dark:border-gray-600 hover:border-red-300"
                        } ${isDisabled || agent.isPathfinding ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
                      >
                        <div className="text-xs font-medium">{opt.label}</div>
                        <div className="text-[10px] text-muted dark:text-darkmutedtext">{opt.description}</div>
                      </button>
                    ))}
                  </div>
                  <button
                    onClick={() => {
                      setShowCarOptions(null);
                      handleClearRoute(agent.agentId);
                    }}
                    className="text-xs text-gray-500 hover:text-gray-700 mt-2"
                  >
                    Back
                  </button>
                </div>
              )}

              {/* Transport options - show when no route and not showing car options */}
              {!agent.route && !showingCarOptions && (
                <div className="grid grid-cols-4 gap-2" onClick={(e) => e.stopPropagation()}>
                  {TRANSPORT_OPTIONS.map((transport) => {
                    const isTransportSelected = agent.selectedMode === transport.id;
                    return (
                      <button
                        key={transport.id}
                        onClick={() => handleTransportSelect(agent.agentId, transport.id)}
                        disabled={isDisabled || agent.isPathfinding}
                        className={`p-2 rounded-lg border-2 transition-all duration-200 ${transport.color} ${
                          isTransportSelected
                            ? "ring-2 ring-primary-500 border-primary-500"
                            : "border-transparent"
                        } ${!isDisabled && !isTransportSelected ? "hover:border-gray-400" : ""} ${
                          isDisabled || agent.isPathfinding
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
              )}
            </div>
          );
        })}
      </div>

      {/* Submit button */}
      <div className="text-center">
        <button
          onClick={handleSubmit}
          disabled={!allRoutesComplete || isSubmitting || isSubmitted || !playerId || isAnyPathfinding}
          className={`px-8 py-3 rounded-lg font-semibold text-lg transition-all duration-200 ${
            allRoutesComplete && !isSubmitting && !isSubmitted && playerId && !isAnyPathfinding
              ? "bg-primary-600 text-white hover:bg-primary-700 cursor-pointer"
              : "bg-gray-300 dark:bg-gray-700 text-gray-500 dark:text-gray-400 cursor-not-allowed"
          }`}
        >
          {isSubmitting ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Submitting...
            </span>
          ) : allRoutesComplete ? (
            "Submit All Routes"
          ) : isAnyPathfinding ? (
            "Finding routes..."
          ) : (
            `Plan routes for all ${agents.length} agents`
          )}
        </button>
      </div>

      {/* Route Summary */}
      {allRoutesComplete && !isSubmitted && (
        <div className="mt-4 p-4 bg-gray-100 dark:bg-gray-800 rounded-lg max-w-md mx-auto">
          <h3 className="font-semibold mb-2 text-center">Route Summary</h3>
          <div className="text-sm space-y-1">
            <div className="flex justify-between">
              <span>Total Distance:</span>
              <span>
                {(agents.reduce((sum, a) => sum + (a.route?.totalDistanceM ?? 0), 0) / 1000).toFixed(1)} km
              </span>
            </div>
            <div className="flex justify-between">
              <span>Est. Total Time:</span>
              <span>
                {Math.round(agents.reduce((sum, a) => sum + (a.route?.estimatedTimeMin ?? 0), 0))} min
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Error message */}
      {moveError && (
        <div className="mt-4 p-4 rounded bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-200 text-center">
          {moveError}
        </div>
      )}
    </div>
  );
}
