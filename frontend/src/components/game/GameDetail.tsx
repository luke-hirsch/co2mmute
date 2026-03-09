import { useState, useEffect, useRef } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useGameDetails, usePlayerGameDetails } from "../../hooks/gameHooks";
import { useGameSocket } from "../../hooks/useGameSocket";
import Loading from "../Loading";
import { API_BASE_URL } from "../../config";
import { apiFetch } from "../../utils/api";

interface GameDetailProps {
  id: string;
  role: "host" | "player";
  playerId?: string;
}

interface GameInfo {
  game_name: string;
  game_qr_code: string;
  game_password: string;
  chat_enabled: boolean;
  max_players: number;
  agent_per_player: number;
  max_rounds: number;
  max_CO2_level: number;
  people_per_agent: number;
  is_active: boolean;
  started_at?: string | null;
  ended_at?: string | null;
}

export default function GameDetail({ id, role, playerId }: GameDetailProps) {
  const [isStartingGame, setIsStartingGame] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [isEditingSettings, setIsEditingSettings] = useState(false);
  const [editedGame, setEditedGame] = useState<Partial<GameInfo>>({});
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isEditingPassword, setIsEditingPassword] = useState<boolean>(false);
  const [editedPassword, setEditedPassword] = useState<string>("");
  const [isSavingPassword, setIsSavingPassword] = useState<boolean>(false);
  const [zoomQR, setZoomQR] = useState<boolean>(false);

  const navigate = useNavigate();

  // Fetch game data via REST API (hooks must be called unconditionally)
  const hostGameData = useGameDetails(id);
  const playerGameData = usePlayerGameDetails(id, playerId || "");

  // Select the appropriate data based on role
  const gameData = role === "host" ? hostGameData : playerGameData;

  // Store refetch in a ref so callbacks can access it without stale closures
  const refetchRef = useRef(gameData.refetch);
  refetchRef.current = gameData.refetch;

  // Connect to game websocket and receive game state updates
  const { gameState, sendMessage } = useGameSocket({
    gameId: id,
    onGameStarted: (data) => {
      console.log("Game started:", data);
      // Refetch game data to sync REST state
      refetchRef.current?.();
    },
    onGameEnded: (data) => {
      console.log("Game ended:", data);
      refetchRef.current?.();
    },
    onRoundStarted: (data) => {
      console.log("Round started:", data);
    },
    onRoundCompleted: (data) => {
      console.log("Round completed:", data);
    },
  });

  // Redirect players to game when it becomes active (host stays in lobby)
  useEffect(() => {
    if (!gameState?.isActive) return;

    if (role === "player") {
      // Players always redirect when game starts
      navigate({ to: "/game/$gameId", params: { gameId: id } });
    }
    // Host does NOT auto-redirect - they can use the "Go to Game" button
  }, [gameState?.isActive, id, navigate, role]);


  if (gameData.isLoading) return <Loading />;
  if (gameData.isError) return (window.location.href = "/");

  const game: GameInfo = gameData.data;

  const handleStartGame = async () => {
    setIsStartingGame(true);
    setStartError(null);

    try {
      const data = await apiFetch(`${API_BASE_URL}/api/game/${id}/`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: true }),
      });

      // apiFetch already parses JSON and returns the data
      if (data && typeof data === "object" && "error" in data) {
        setStartError(data.error || "Failed to start game");
        return;
      }
      console.log(data);

      // If we got a successful response, immediately update local state
      // This gives instant feedback while the refetch happens in background
      if (data && data.is_active) {
        // Force immediate refetch to update UI
        await gameData.refetch?.();
      }

      // Game started successfully, navigation will happen via game state
      // The router should redirect to /game/$gameId when game becomes active
    } catch (error) {
      setStartError(
        error instanceof Error ? error.message : "Failed to start game"
      );
    } finally {
      setIsStartingGame(false);
    }
  };

  const handleStopGame = async () => {
    setIsStartingGame(true);
    setStartError(null);

    try {
      const data = await apiFetch(`${API_BASE_URL}/api/game/${id}/`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: false }),
      });

      if (data && typeof data === "object" && "error" in data) {
        setStartError(data.error || "Failed to stop game");
        return;
      }

      // Force immediate refetch to update UI
      await gameData.refetch?.();
    } catch (error) {
      setStartError(
        error instanceof Error ? error.message : "Failed to stop game"
      );
    } finally {
      setIsStartingGame(false);
    }
  };

  const handleSaveSettings = async () => {
    if (!editedGame || Object.keys(editedGame).length === 0) {
      setIsEditingSettings(false);
      return;
    }

    setIsSavingSettings(true);
    setSaveError(null);

    try {
      const data = await apiFetch(`${API_BASE_URL}/api/game/${id}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(editedGame),
      });

      if (data && typeof data === "object" && "error" in data) {
        setSaveError(data.error || "Failed to save settings");
        return;
      }

      // Refresh game data
      gameData.refetch?.();
      setIsEditingSettings(false);
      setEditedGame({});
    } catch (error) {
      setSaveError(
        error instanceof Error ? error.message : "Failed to save settings"
      );
    } finally {
      setIsSavingSettings(false);
    }
  };

  const handleToggleChat = async () => {
    const newChatState = !game.chat_enabled;

    try {
      const data = await apiFetch(`${API_BASE_URL}/api/game/${id}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chat_enabled: newChatState }),
      });

      if (data && typeof data === "object" && "error" in data) {
        setSaveError(data.error || "Failed to toggle chat");
      } else {
        // Refresh game data to reflect the change
        gameData.refetch?.();
      }
    } catch (error) {
      setSaveError(
        error instanceof Error ? error.message : "Failed to toggle chat"
      );
    }
  };

  const handleSavePassword = async () => {
    if (!editedPassword) {
      setIsEditingPassword(false);
      return;
    }

    setIsSavingPassword(true);
    setSaveError(null);

    try {
      const data = await apiFetch(`${API_BASE_URL}/api/game/${id}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ game_password: editedPassword }),
      });

      if (data && typeof data === "object" && "error" in data) {
        setSaveError(data.error || "Failed to save password");
        return;
      }

      // Refresh game data
      gameData.refetch?.();
      setIsEditingPassword(false);
      setEditedPassword("");
    } catch (error) {
      setSaveError(
        error instanceof Error ? error.message : "Failed to save password"
      );
    } finally {
      setIsSavingPassword(false);
    }
  };

  return (
    <div className=" w-full max-w-2xl flex flex-col gap-8">
      {/* Header */}
      <div>
        <h1 className="mb-2 text-3xl font-bold">{game.game_name}</h1>
        <p className="text-sm text-muted dark:text-darkmutedtext">
          {role === "host" ? "Hosting this game" : "You are a player"}
        </p>
      </div>

      {/* QR Code + Game ID + Password Card */}
      {role === "host" && (
        <div className="static rounded-lg border border-subtle bg-elevated p-6 dark:border-darksubtle dark:bg-darkelevated shadow-md">
          {/* qr code zoom */}
          {zoomQR && (
            <div
              onClick={() => setZoomQR(!zoomQR)}
              className="absolute t-0 l-0 z-30 place-content-center dark:bg-darkbody bg-body p-6 cursor-pointer"
            >
              <img
                src={game.game_qr_code}
                alt="QR code to join game"
                className="mx-auto h-90 w-auto rounded border-2 border-primary-600 p-3"
              />
              <p className="mt-3 text-2xl text-center font-mono font-bold text-primary-600">
                {game.game_password}
              </p>
            </div>
          )}
          <div className=" flex flex-col lg:flex-row gap-6 lg:gap-8">
            {/* QR Code - Left Side */}
            <div
              onClick={() => setZoomQR(!zoomQR)}
              className=" flex flex-col items-center gap-3 lg:w-1/3 cursor-pointer"
            >
              <h3 className="text-sm font-semibold text-muted dark:text-darkmutedtext">
                Share this code with players
              </h3>
              <img
                src={game.game_qr_code}
                alt="QR code to join game"
                className="h-40 w-40 rounded border-2 border-primary-600"
              />
            </div>

            {/* Session ID + Password - Right Side */}
            <div className="flex flex-col gap-6 lg:w-2/3 lg:border-l lg:border-subtle lg:pl-6 dark:lg:border-darksubtle">
              {/* Game ID */}
              <div className="flex flex-col items-center lg:items-start gap-2">
                <p className="text-xs font-semibold text-muted dark:text-darkmutedtext">
                  GAME ID
                </p>
                <code className="rounded bg-surface px-4 py-2 text-2xl font-mono font-bold text-primary-600 dark:bg-darksurface">
                  {id}
                </code>
              </div>

              {/* Password Section */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-sm font-semibold">Access Password</h4>
                  <button
                    onClick={() => {
                      setIsEditingPassword(!isEditingPassword);
                      setEditedPassword(game.game_password);
                    }}
                    className="text-xs font-semibold text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300"
                  >
                    {isEditingPassword ? "Cancel" : "Change"}
                  </button>
                </div>

                {isEditingPassword ? (
                  <div className="space-y-2">
                    {saveError && (
                      <div className="rounded bg-red-100 p-2 text-xs text-red-700 dark:bg-red-900 dark:text-red-200">
                        {saveError}
                      </div>
                    )}
                    <input
                      type="text"
                      value={editedPassword}
                      onChange={(e) => setEditedPassword(e.target.value)}
                      className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                      placeholder="Enter new password"
                    />
                    <button
                      onClick={handleSavePassword}
                      disabled={isSavingPassword}
                      className="w-full rounded bg-primary-600 px-3 py-1 text-xs font-semibold text-white hover:bg-primary-700 disabled:opacity-50 dark:bg-primary-600 dark:hover:bg-primary-700"
                    >
                      {isSavingPassword ? "Saving..." : "Save"}
                    </button>
                  </div>
                ) : (
                  <p className="text-2xl font-mono font-bold text-primary-600">
                    {game.game_password}
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Game Settings */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Game Settings</h3>
          {role === "host" && !game.is_active && !game.ended_at && (
            <button
              onClick={() => {
                setIsEditingSettings(!isEditingSettings);
                setEditedGame({});
              }}
              className="text-xs font-semibold text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300"
            >
              {isEditingSettings ? "Cancel" : "Edit"}
            </button>
          )}
        </div>

        {isEditingSettings && role === "host" && (
          <div className="mb-4 space-y-3">
            {saveError && (
              <div className="rounded bg-red-100 p-3 text-sm text-red-700 dark:bg-red-900 dark:text-red-200">
                {saveError}
              </div>
            )}
            <div>
              <label className="block text-sm font-medium mb-1">
                Game Name
              </label>
              <input
                type="text"
                value={editedGame.game_name ?? game.game_name}
                onChange={(e) =>
                  setEditedGame({ ...editedGame, game_name: e.target.value })
                }
                className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-sm font-medium mb-1">
                  Max Players
                </label>
                <input
                  type="number"
                  min="2"
                  value={editedGame.max_players ?? game.max_players}
                  onChange={(e) =>
                    setEditedGame({
                      ...editedGame,
                      max_players: parseInt(e.target.value),
                    })
                  }
                  className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  Agents per Player
                </label>
                <input
                  type="number"
                  min="1"
                  value={editedGame.agent_per_player ?? game.agent_per_player}
                  onChange={(e) =>
                    setEditedGame({
                      ...editedGame,
                      agent_per_player: parseInt(e.target.value),
                    })
                  }
                  className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-sm font-medium mb-1">
                  Max Rounds
                </label>
                <input
                  type="number"
                  min="1"
                  value={editedGame.max_rounds ?? game.max_rounds}
                  onChange={(e) =>
                    setEditedGame({
                      ...editedGame,
                      max_rounds: parseInt(e.target.value),
                    })
                  }
                  className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  CO₂ Limit (kg)
                </label>
                <input
                  type="number"
                  min="100"
                  step="50"
                  value={editedGame.max_CO2_level ?? game.max_CO2_level}
                  onChange={(e) =>
                    setEditedGame({
                      ...editedGame,
                      max_CO2_level: parseInt(e.target.value),
                    })
                  }
                  className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">
                People per Agent
              </label>
              <input
                type="number"
                min="1"
                value={editedGame.people_per_agent ?? game.people_per_agent}
                onChange={(e) =>
                  setEditedGame({
                    ...editedGame,
                    people_per_agent: parseInt(e.target.value),
                  })
                }
                className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              />
              <p className="mt-1 text-xs text-muted dark:text-darkmutedtext">
                How many individuals each agent represents in the simulation.
              </p>
            </div>

            <button
              onClick={handleSaveSettings}
              disabled={isSavingSettings}
              className="w-full rounded bg-primary-600 px-3 py-2 text-sm font-semibold text-white hover:bg-primary-700 disabled:opacity-50 dark:bg-primary-600 dark:hover:bg-primary-700"
            >
              {isSavingSettings ? "Saving..." : "Save Settings"}
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
          <div className="p-3 rounded bg-elevated dark:bg-darkelevated">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted dark:text-darkmutedtext mb-1">
              Max Players
            </h4>
            <p className="text-lg font-bold text-primary-600">
              {game.max_players}
            </p>
          </div>

          <div className="p-3 rounded bg-elevated dark:bg-darkelevated">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted dark:text-darkmutedtext mb-1">
              Agents per Player
            </h4>
            <p className="text-lg font-bold text-primary-600">
              {game.agent_per_player}
            </p>
          </div>

          <div className="p-3 rounded bg-elevated dark:bg-darkelevated">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted dark:text-darkmutedtext mb-1">
              Max Rounds
            </h4>
            <p className="text-lg font-bold text-primary-600">
              {game.max_rounds}
            </p>
          </div>

          <div className="p-3 rounded bg-elevated dark:bg-darkelevated">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted dark:text-darkmutedtext mb-1">
              CO₂ Limit
            </h4>
            <p className="text-lg font-bold text-primary-600">
              {game.max_CO2_level} kg
            </p>
          </div>

          <div className="p-3 rounded bg-elevated dark:bg-darkelevated">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted dark:text-darkmutedtext mb-1">
              People per Agent
            </h4>
            <p className="text-lg font-bold text-primary-600">
              {game.people_per_agent}
            </p>
          </div>

          <div className="p-3 rounded bg-elevated dark:bg-darkelevated">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted dark:text-darkmutedtext mb-1">
              Chat
            </h4>
            <div className="flex items-center gap-2">
              {role === "host" ? (
                <button
                  onClick={handleToggleChat}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    game.chat_enabled
                      ? "bg-green-600"
                      : "bg-gray-300 dark:bg-gray-600"
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      game.chat_enabled ? "translate-x-6" : "translate-x-1"
                    }`}
                  />
                </button>
              ) : (
                <span
                  className={`text-sm font-semibold ${
                    game.chat_enabled
                      ? "text-green-600 dark:text-green-400"
                      : "text-gray-500 dark:text-gray-400"
                  }`}
                >
                  {game.chat_enabled ? "✓ Enabled" : "✗ Disabled"}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Status Section */}
      <div className="rounded-lg border border-subtle bg-elevated p-4 dark:border-darksubtle dark:bg-darkelevated">
        <div className="flex items-center gap-2">
          <div
            className={`h-3 w-3 rounded-full ${
              game.is_active ? "bg-green-500" : "bg-amber-500"
            }`}
          />
          <p className="text-sm font-medium text-main dark:text-darktext">
            {game.is_active
              ? "Game is active - players are in-game"
              : "Waiting to start"}
          </p>
        </div>
      </div>

      {/* Real-time Game State (from WebSocket) */}
      {gameState && (
        <div className="rounded-lg border border-primary-300 bg-primary-50 p-4 dark:border-primary-700 dark:bg-primary-900/20">
          <h3 className="text-lg font-semibold mb-3 text-primary-700 dark:text-primary-300">
            Live Game State
          </h3>

          {/* Round Progress */}
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div className="p-3 rounded bg-white dark:bg-darksurface">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted dark:text-darkmutedtext mb-1">
                Current Round
              </p>
              <p className="text-2xl font-bold text-primary-600">
                {gameState.currentRound} / {gameState.maxRounds}
              </p>
            </div>
            <div className="p-3 rounded bg-white dark:bg-darksurface">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted dark:text-darkmutedtext mb-1">
                Total CO₂
              </p>
              <p className="text-2xl font-bold text-primary-600">
                {(gameState.totalEmissionsG / 1000).toFixed(2)} kg
              </p>
              <div className="mt-1 h-2 rounded-full bg-gray-200 dark:bg-gray-700">
                <div
                  className={`h-2 rounded-full transition-all ${
                    gameState.totalEmissionsG / gameState.maxCo2LevelG > 0.8
                      ? "bg-red-500"
                      : gameState.totalEmissionsG / gameState.maxCo2LevelG > 0.5
                        ? "bg-amber-500"
                        : "bg-green-500"
                  }`}
                  style={{
                    width: `${Math.min(100, (gameState.totalEmissionsG / gameState.maxCo2LevelG) * 100)}%`,
                  }}
                />
              </div>
              <p className="text-xs text-muted dark:text-darkmutedtext mt-1">
                Limit: {(gameState.maxCo2LevelG / 1000).toFixed(0)} kg
              </p>
            </div>
          </div>

          {/* Between-Round Phase Indicator */}
          {gameState.betweenRoundPhase && gameState.betweenRoundPhase !== "none" && (
            <div className="mb-4 p-3 rounded bg-white dark:bg-darksurface border border-subtle dark:border-darksubtle">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="h-2 w-2 rounded-full bg-amber-500 animate-pulse" />
                  <span className="text-sm font-medium">
                    {gameState.betweenRoundPhase === "stats" && "Players reviewing stats"}
                    {gameState.betweenRoundPhase === "discussion" && "Discussion phase"}
                    {gameState.betweenRoundPhase === "voting" && "Voting in progress"}
                  </span>
                  {gameState.betweenRoundPhase === "voting" && gameState.voteProgress && (
                    <span className="text-xs text-muted dark:text-darkmutedtext">
                      ({gameState.voteProgress.cast}/{gameState.voteProgress.needed} votes)
                    </span>
                  )}
                </div>
                {role === "host" && gameState.betweenRoundPhase === "discussion" && (
                  <button
                    onClick={() => sendMessage({ type: "vote.open" })}
                    className="px-4 py-1.5 rounded bg-primary-600 text-white text-sm font-semibold hover:bg-primary-700 transition-colors"
                  >
                    Open Voting
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Game End Status */}
          {gameState.endedAt && (
            <div
              className={`p-3 rounded mb-4 ${
                gameState.endReason === "co2_limit"
                  ? "bg-red-100 dark:bg-red-900/30"
                  : "bg-green-100 dark:bg-green-900/30"
              }`}
            >
              <p
                className={`font-semibold ${
                  gameState.endReason === "co2_limit"
                    ? "text-red-700 dark:text-red-300"
                    : "text-green-700 dark:text-green-300"
                }`}
              >
                {gameState.endReason === "co2_limit"
                  ? "Game Over - CO₂ limit exceeded!"
                  : "Game Complete - All rounds finished!"}
              </p>
            </div>
          )}

          {/* Last Round Stats */}
          {gameState.lastRoundStats && gameState.lastRoundStats.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold mb-2 text-muted dark:text-darkmutedtext">
                Last Round Results
              </h4>
              <div className="space-y-2">
                {gameState.lastRoundStats.map((stat) => (
                  <div
                    key={stat.player_id}
                    className="flex items-center justify-between p-2 rounded bg-white dark:bg-darksurface text-sm"
                  >
                    <span className="font-medium">{stat.player_name}</span>
                    <div className="flex gap-4 text-xs">
                      <span
                        className={`px-2 py-1 rounded ${
                          stat.action === "car"
                            ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300"
                            : stat.action === "public"
                              ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300"
                              : stat.action === "bike"
                                ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300"
                                : "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300"
                        }`}
                      >
                        {stat.action}
                      </span>
                      <span className="text-muted dark:text-darkmutedtext">
                        {stat.emissions_g}g CO₂
                      </span>
                      <span className="text-muted dark:text-darkmutedtext">
                        €{stat.cost_eur.toFixed(2)}
                      </span>
                      <span className="text-muted dark:text-darkmutedtext">
                        {stat.time_min}min
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Host Controls */}
      {role === "host" && (
        <div className="mt-auto space-y-3 border-t border-subtle pt-6 dark:border-darksubtle">
          {startError && (
            <div className="rounded bg-red-100 p-3 text-sm text-red-700 dark:bg-red-900 dark:text-red-200">
              {startError}
            </div>
          )}

          {!game.ended_at ? (
            <>
              {game.is_active ? (
                <>
                  <button
                    onClick={() =>
                      navigate({ to: "/game/$gameId", params: { gameId: id } })
                    }
                    className="w-full rounded-lg bg-green-600 px-6 py-3 font-semibold text-white transition-colors duration-200 hover:bg-green-500 focus-visible:outline focus-visible:outline-offset-2 focus-visible:outline-green-600 dark:bg-green-600 dark:hover:bg-green-500"
                  >
                    Go to Game
                  </button>
                  <button
                    onClick={handleStopGame}
                    disabled={isStartingGame}
                    className="w-full rounded-lg bg-red-600 px-6 py-3 font-semibold text-white transition-colors duration-200 hover:bg-red-500 focus-visible:outline focus-visible:outline-offset-2 focus-visible:outline-red-600 disabled:opacity-50 disabled:cursor-not-allowed dark:bg-red-600 dark:hover:bg-red-500"
                  >
                    {isStartingGame ? "Stopping Game..." : "Stop Game"}
                  </button>
                </>
              ) : (
                <button
                  onClick={handleStartGame}
                  disabled={isStartingGame}
                  className="w-full rounded-lg bg-primary-600 px-6 py-3 font-semibold text-white transition-colors duration-200 hover:bg-primary-500 focus-visible:outline focus-visible:outline-offset-2 focus-visible:outline-primary-600 disabled:opacity-50 disabled:cursor-not-allowed dark:bg-primary-600 dark:hover:bg-primary-500"
                >
                  {isStartingGame ? "Starting Game..." : "Start Game"}
                </button>
              )}
              <p className="text-center text-xs text-muted dark:text-darkmutedtext">
                {game.is_active
                  ? "All players are in the game room"
                  : "Make sure all players have joined the lobby"}
              </p>
            </>
          ) : (
            <div className="space-y-3">
              <button
                onClick={() =>
                  navigate({ to: "/game/$gameId", params: { gameId: id } })
                }
                className="block w-full rounded-lg bg-primary-600 px-6 py-3 font-semibold text-white text-center transition-colors duration-200 hover:bg-primary-500 focus-visible:outline focus-visible:outline-offset-2 focus-visible:outline-primary-600 dark:bg-primary-600 dark:hover:bg-primary-500"
              >
                View Summary
              </button>
              <p className="text-center text-xs text-muted dark:text-darkmutedtext">
                Game has ended
              </p>
            </div>
          )}
        </div>
      )}

      {/* Player Info */}
      {role === "player" && (
        <div className="mt-auto space-y-3 border-t border-subtle pt-6 dark:border-darksubtle">
          <div className="rounded bg-amber-100 p-3 text-sm text-amber-700 dark:bg-amber-900 dark:text-amber-200">
            Waiting for the host to start the game...
          </div>
        </div>
      )}
    </div>
  );
}
