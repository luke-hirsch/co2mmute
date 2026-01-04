import { useState } from "react";
import { useGameState } from "../../hooks/useGameState";
import { usePlayerMove } from "../../hooks/usePlayerMove";
import Loading from "../Loading";

interface GamePlayProps {
  gameId: string;
  playerId?: string;
}

const TRANSPORTATION_OPTIONS = [
  {
    id: "car",
    label: "Car 🚗",
    color: "bg-red-100 dark:bg-red-900",
    borderColor: "border-red-400 dark:border-red-600",
    emoji: "🚗",
    co2: "120 kg CO₂",
    description: "High emissions, fast travel",
  },
  {
    id: "public",
    label: "Public Transport 🚌",
    color: "bg-yellow-100 dark:bg-yellow-900",
    borderColor: "border-yellow-400 dark:border-yellow-600",
    emoji: "🚌",
    co2: "60 kg CO₂",
    description: "Medium emissions, eco-friendly",
  },
  {
    id: "bike",
    label: "Bike 🚴",
    color: "bg-green-100 dark:bg-green-900",
    borderColor: "border-green-400 dark:border-green-600",
    emoji: "🚴",
    co2: "0 kg CO₂",
    description: "Zero emissions, active travel",
  },
  {
    id: "walk",
    label: "Walk 🚶",
    color: "bg-blue-100 dark:bg-blue-900",
    borderColor: "border-blue-400 dark:border-blue-600",
    emoji: "🚶",
    co2: "0 kg CO₂",
    description: "Zero emissions, healthy",
  },
];

export default function GamePlay({ gameId, playerId }: GamePlayProps) {
  const {
    gameState,
    gameStats,
    isConnected,
    error: gameError,
  } = useGameState({
    gameId,
  });
  const {
    submitMove,
    isLoading,
    error: moveError,
  } = usePlayerMove({
    gameId,
    playerId: playerId || "",
  });
  const [selectedTransport, setSelectedTransport] = useState<string | null>(
    null
  );

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

  const handleSelectTransport = async (transportId: string) => {
    setSelectedTransport(transportId);
    const success = await submitMove(transportId);
    if (!success) {
      setSelectedTransport(null);
    }
  };

  return (
    <div className="w-full max-w-4xl">
      {/* Game Header */}
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-bold text-main dark:text-darktext mb-2">
          {gameState.game_name}
        </h1>
        <div className="flex justify-center gap-6 text-sm text-muted dark:text-darkmutedtext">
          <span>
            Round {gameState.current_round} of {gameState.max_rounds}
          </span>
          <span>•</span>
          <span>
            CO₂: {gameStats?.totalCo2.toFixed(1)} / {gameState.max_co2} kg
          </span>
        </div>
      </div>

      {/* CO2 Progress Bar */}
      {gameStats && (
        <div className="mb-8">
          <div className="flex justify-between mb-2 text-sm">
            <span className="font-semibold">CO₂ Progress</span>
            <span>{gameStats.co2Percentage.toFixed(1)}%</span>
          </div>
          <div className="w-full bg-gray-300 dark:bg-gray-600 rounded-full h-3">
            <div
              className={`h-3 rounded-full transition-all duration-300 ${
                gameStats.co2Percentage > 75
                  ? "bg-red-500"
                  : gameStats.co2Percentage > 50
                    ? "bg-yellow-500"
                    : "bg-green-500"
              }`}
              style={{ width: `${Math.min(gameStats.co2Percentage, 100)}%` }}
            />
          </div>
        </div>
      )}

      {/* Transportation Selection */}
      <div className="mb-8">
        <h2 className="text-xl font-semibold mb-4 text-main dark:text-darktext">
          Choose your transportation method
        </h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {TRANSPORTATION_OPTIONS.map((transport) => (
            <button
              key={transport.id}
              onClick={() => handleSelectTransport(transport.id)}
              disabled={isLoading || selectedTransport !== null}
              className={`p-4 rounded-lg border-2 transition-all duration-200 ${
                selectedTransport === transport.id
                  ? `${transport.borderColor} ${transport.color} ring-2 ring-primary-500`
                  : `border-gray-300 dark:border-gray-600 hover:border-primary-500 dark:hover:border-primary-400`
              } ${isLoading || selectedTransport !== null ? "opacity-50 cursor-not-allowed" : "cursor-pointer hover:shadow-md"}`}
            >
              <div className="text-4xl mb-2">{transport.emoji}</div>
              <div className="font-semibold text-sm mb-1">
                {transport.label}
              </div>
              <div className="text-xs text-muted dark:text-darkmutedtext">
                {transport.co2}
              </div>
              <div className="text-xs text-muted dark:text-darkmutedtext mt-1">
                {transport.description}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Status Messages */}
      {moveError && (
        <div className="p-4 rounded bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-200 mb-4">
          {moveError}
        </div>
      )}

      {selectedTransport && isLoading && (
        <div className="p-4 rounded bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-200">
          Submitting your choice...
        </div>
      )}

      {selectedTransport && !isLoading && !moveError && (
        <div className="p-4 rounded bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-200">
          ✓ Move submitted! Waiting for other players...
        </div>
      )}
    </div>
  );
}
