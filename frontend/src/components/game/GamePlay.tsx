import { useState, useEffect, useMemo } from "react";
import { useGameSocket } from "../../hooks/useGameSocket";
import { usePlayerMove } from "../../hooks/usePlayerMove";
import { useGameDetails, usePlayerGameDetails } from "../../hooks/gameHooks";
import { useMapGraph } from "../../hooks/mapHooks";
import { useAgentRoutes } from "../../hooks/usePathfinding";
import Loading from "../Loading";
import GameMapViewer from "./GameMapViewer";
import AgentRouteSelector from "./AgentRouteSelector";
import type { ExtendedMapGraph, TransportMode, CarOptimization } from "../../types/routeTypes";

interface GamePlayProps {
  gameId: string;
  playerId?: string;
  isHost?: boolean;
}

export default function GamePlay({
  gameId,
  playerId,
  isHost = false,
}: GamePlayProps) {
  const {
    isConnected,
    error: gameError,
    gameState,
  } = useGameSocket({
    gameId,
  });

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
    // The player data might be nested - check the structure
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
  } = useAgentRoutes(agentAssignments, { scale: 100 });

  // Reset submission state when round changes
  useEffect(() => {
    setIsSubmitted(false);
  }, [gameState?.currentRound]);

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

  const handleSubmit = async () => {
    const payload = getSubmissionPayload();
    if (!payload) return;

    const success = await submitMove("route_submission", { agents: payload.agents });
    if (success) {
      setIsSubmitted(true);
    }
  };

  const handleFindRoute = async (agentId: number) => {
    if (!mapGraph || homeNode === undefined) return;

    // Cast mapGraph to ExtendedMapGraph for PT routing
    const extendedGraph: ExtendedMapGraph = {
      ...mapGraph,
      bus_lines: (mapGraph as ExtendedMapGraph).bus_lines ?? [],
      train_lines: (mapGraph as ExtendedMapGraph).train_lines ?? [],
      scale: 100,
    };

    await findAgentRoute(agentId, extendedGraph, homeNode);
  };

  if (!isConnected) {
    return (
      <div className="flex flex-col items-center justify-center gap-4">
        <Loading />
        <p className="text-muted">Connecting to game...</p>
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

  return (
    <div className="w-full max-w-6xl mx-auto">
      {/* Game Header */}
      <div className="mb-6 text-center">
        <h1 className="text-3xl font-bold text-main dark:text-darktext mb-2">
          {gameState.gameName || `Game ${gameId}`}
        </h1>
        <div className="flex justify-center gap-6 text-sm text-muted dark:text-darkmutedtext">
          <span>
            Round {gameState.currentRound} of {gameState.maxRounds}
          </span>
          <span>|</span>
          <span>
            CO2: {(gameState.totalEmissionsG / 1000).toFixed(1)} /{" "}
            {(gameState.maxCo2LevelG / 1000).toFixed(0)} kg
          </span>
        </div>
      </div>

      {/* CO2 Progress Bar */}
      <div className="mb-6">
        <div className="flex justify-between mb-2 text-sm">
          <span className="font-semibold">CO2 Progress</span>
          <span>
            {((gameState.totalEmissionsG / gameState.maxCo2LevelG) * 100).toFixed(1)}%
          </span>
        </div>
        <div className="w-full bg-gray-300 dark:bg-gray-600 rounded-full h-3">
          <div
            className={`h-3 rounded-full transition-all duration-300 ${
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

      {/* Main Content: Map + Agent Selection */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Map View */}
        <div>
          <h2 className="text-xl font-semibold mb-4 text-main dark:text-darktext">
            Map
          </h2>
          <GameMapViewer
            mapGraph={mapGraph ?? null}
            isLoading={mapLoading || gameDetailsLoading}
            error={mapError ? "Failed to load map" : null}
            compact={false}
            homeNodeId={homeNode}
            destinationNodeId={selectedDestination}
            routeSegments={selectedAgentRoute?.segments}
            highlightedNodes={
              selectedAgentRoute
                ? new Set(selectedAgentRoute.segments.flatMap((s) => [s.startNode, s.endNode]))
                : undefined
            }
          />
        </div>

        {/* Agent Selection */}
        <div>
          <h2 className="text-xl font-semibold mb-4 text-main dark:text-darktext">
            Plan Routes for Your Agents
          </h2>

          {agentAssignments.length === 0 ? (
            <div className="text-muted dark:text-darkmutedtext p-4 bg-gray-100 dark:bg-gray-800 rounded-lg">
              Loading agent assignments...
            </div>
          ) : (
            <div className="space-y-4">
              {agents.map((agent, index) => (
                <div
                  key={agent.agentId}
                  onMouseEnter={() => setSelectedAgentId(agent.agentId)}
                  onMouseLeave={() => setSelectedAgentId(null)}
                  className={`transition-all ${
                    selectedAgentId === agent.agentId ? "ring-2 ring-primary-500 rounded-lg" : ""
                  }`}
                >
                  <AgentRouteSelector
                    agentId={agent.agentId}
                    agentIndex={index}
                    destinationNode={agent.destinationNode}
                    selectedMode={agent.selectedMode}
                    selectedOptimization={agent.selectedOptimization}
                    route={agent.route}
                    isPathfinding={agent.isPathfinding}
                    error={agent.error}
                    onSelectMode={(mode: TransportMode, optimization?: CarOptimization) =>
                      setAgentMode(agent.agentId, mode, optimization)
                    }
                    onFindRoute={() => handleFindRoute(agent.agentId)}
                    onClearRoute={() => clearAgentRoute(agent.agentId)}
                    disabled={isSubmitted || isSubmitting}
                  />
                </div>
              ))}
            </div>
          )}

          {/* Submit Button */}
          {agentAssignments.length > 0 && (
            <div className="mt-6">
              <button
                onClick={handleSubmit}
                disabled={!allRoutesComplete || isSubmitting || isSubmitted}
                className={`w-full py-3 px-6 rounded-lg font-semibold text-lg transition-all ${
                  allRoutesComplete && !isSubmitted
                    ? "bg-green-500 hover:bg-green-600 text-white"
                    : "bg-gray-300 dark:bg-gray-600 text-gray-500 cursor-not-allowed"
                }`}
              >
                {isSubmitting ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
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
                    Submitting...
                  </span>
                ) : isSubmitted ? (
                  "Waiting for other players..."
                ) : allRoutesComplete ? (
                  "Submit All Routes"
                ) : (
                  `Plan routes for all ${agents.length} agents`
                )}
              </button>
            </div>
          )}

          {/* Route Summary */}
          {allRoutesComplete && !isSubmitted && (
            <div className="mt-4 p-4 bg-gray-100 dark:bg-gray-800 rounded-lg">
              <h3 className="font-semibold mb-2">Route Summary</h3>
              <div className="text-sm space-y-1">
                <div className="flex justify-between">
                  <span>Total Distance:</span>
                  <span>
                    {(
                      agents.reduce((sum, a) => sum + (a.route?.totalDistanceM ?? 0), 0) / 1000
                    ).toFixed(1)}{" "}
                    km
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Est. Total Time:</span>
                  <span>
                    {Math.round(
                      agents.reduce((sum, a) => sum + (a.route?.estimatedTimeMin ?? 0), 0)
                    )}{" "}
                    min
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Status Messages */}
      {moveError && (
        <div className="mt-4 p-4 rounded bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-200">
          {moveError}
        </div>
      )}

      {isSubmitted && (
        <div className="mt-4 p-4 rounded bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-200">
          Routes submitted! Waiting for other players...
        </div>
      )}
    </div>
  );
}
