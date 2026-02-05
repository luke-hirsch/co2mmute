import { useState, useEffect, useRef, useCallback } from "react";
import type {
  WSStatus,
  WSConnectionQuality,
  WSGameState,
  WSGameStartedMessage,
  WSGameEndedMessage,
  WSRoundStartedMessage,
  WSRoundCompletedMessage,
  WSRosterUpdateMessage,
  WSGameStateInitMessage,
} from "../types/wsTypes";
import { GameWSClient } from "../utils/gameWS";

interface UseGameSocketOptions {
  gameId: string;
  enabled?: boolean;
  onGameStarted?: (data: WSGameStartedMessage["data"]) => void;
  onGameEnded?: (data: WSGameEndedMessage["data"]) => void;
  onRoundStarted?: (data: WSRoundStartedMessage["data"]) => void;
  onRoundCompleted?: (data: WSRoundCompletedMessage["data"]) => void;
}

interface UseGameSocketResult {
  status: WSStatus;
  error: string | null;
  isConnected: boolean;
  connectionQuality: WSConnectionQuality | null;
  gameState: WSGameState | null;
  sendMessage: (data: object) => boolean;
}

/**
 * Hook to manage game WebSocket connection
 * Handles game state events: game.started, game.ended, round.started, round.completed
 */
export function useGameSocket(
  options: UseGameSocketOptions,
): UseGameSocketResult {
  const {
    gameId,
    enabled = true,
    onGameStarted,
    onGameEnded,
    onRoundStarted,
    onRoundCompleted,
  } = options;

  const [status, setStatus] = useState<WSStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [connectionQuality, setConnectionQuality] =
    useState<WSConnectionQuality | null>(null);
  const [gameState, setGameState] = useState<WSGameState | null>(null);

  const clientRef = useRef<GameWSClient | null>(null);

  // Store callbacks in refs to avoid effect re-runs
  const callbacksRef = useRef({
    onGameStarted,
    onGameEnded,
    onRoundStarted,
    onRoundCompleted,
  });
  // callbacksRef.current = {
  //   onGameStarted,
  //   onGameEnded,
  //   onRoundStarted,
  //   onRoundCompleted,
  // };

  const handleGameMessage = useCallback(
    (message: unknown) => {
      if (!message || typeof message !== "object" || !("type" in message)) {
        console.debug("Unknown game message format:", message);
        return;
      }

      const msg = message as { type: string; game_id?: string; data?: unknown };
      console.debug("Game message received:", msg.type, msg);

      switch (msg.type) {
        case "game.started": {
          const data = msg.data as WSGameStartedMessage["data"];
          setGameState((prev) => ({
            gameId: msg.game_id || gameId,
            gameName: data.game_name,
            isActive: true,
            endedAt: null,
            endReason: null,
            maxRounds: data.max_rounds,
            maxCo2LevelG: data.max_co2_level * 1000, // convert kg to g
            currentRound: data.current_round,
            totalEmissionsG: 0,
            lastRoundStats: prev?.lastRoundStats || null,
            roster: prev?.roster || [],
          }));
          callbacksRef.current.onGameStarted?.(data);
          break;
        }

        case "game.ended": {
          const data = msg.data as WSGameEndedMessage["data"];
          setGameState((prev) => ({
            ...(prev || {
              gameId: msg.game_id || gameId,
              gameName: "",
              maxRounds: 0,
              maxCo2LevelG: data.max_co2_level_g,
              currentRound: data.final_round,
              lastRoundStats: null,
              roster: [],
            }),
            isActive: false,
            endedAt: data.ended_at,
            endReason: data.reason,
            totalEmissionsG: data.total_emissions_g,
          }));
          callbacksRef.current.onGameEnded?.(data);
          break;
        }

        case "round.started": {
          const data = msg.data as WSRoundStartedMessage["data"];
          setGameState((prev) => ({
            ...(prev || {
              gameId: msg.game_id || gameId,
              gameName: "",
              isActive: true,
              endedAt: null,
              endReason: null,
              lastRoundStats: null,
              roster: [],
            }),
            currentRound: data.round_number,
            maxRounds: data.max_rounds,
            maxCo2LevelG: data.max_co2_level_g,
            totalEmissionsG: data.total_game_emissions_g,
          }));
          callbacksRef.current.onRoundStarted?.(data);
          break;
        }

        case "round.completed": {
          const data = msg.data as WSRoundCompletedMessage["data"];
          setGameState((prev) => ({
            ...(prev || {
              gameId: msg.game_id || gameId,
              gameName: "",
              isActive: true,
              endedAt: null,
              endReason: null,
              currentRound: data.round_number,
              maxRounds: 0,
              roster: [],
            }),
            totalEmissionsG: data.total_game_emissions_g,
            maxCo2LevelG: data.max_co2_level_g,
            lastRoundStats: data.player_stats,
          }));
          callbacksRef.current.onRoundCompleted?.(data);
          break;
        }

        case "roster.update": {
          const players = (msg as WSRosterUpdateMessage).players;
          setGameState((prev) => {
            if (!prev) {
              // Initialize minimal state if none exists
              return {
                gameId: msg.game_id || gameId,
                gameName: "",
                isActive: false,
                endedAt: null,
                endReason: null,
                maxRounds: 0,
                maxCo2LevelG: 0,
                currentRound: 0,
                totalEmissionsG: 0,
                lastRoundStats: null,
                roster: players,
              };
            }
            return {
              ...prev,
              roster: players,
            };
          });
          break;
        }

        case "game.state": {
          // Initial state sync on reconnect
          const data = (msg as WSGameStateInitMessage).data;
          setGameState((prev) => ({
            gameId: msg.game_id || gameId,
            gameName: prev?.gameName || "",
            isActive: data.isActive,
            endedAt: data.endedAt,
            endReason: prev?.endReason || null,
            maxRounds: data.maxRounds,
            maxCo2LevelG: data.maxCo2LevelG,
            currentRound: data.currentRound,
            totalEmissionsG: data.totalEmissionsG,
            lastRoundStats: prev?.lastRoundStats || null,
            roster: prev?.roster || [],
          }));
          break;
        }

        default:
          console.debug("Unhandled game message type:", msg.type);
      }
    },
    [gameId],
  );

  useEffect(() => {
    if (!enabled) return;

    if (!clientRef.current) {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.host;
      const wsUrl = `${protocol}//${host}/ws/game/${gameId}/`;

      clientRef.current = new GameWSClient(wsUrl);
    }

    const client = clientRef.current;

    const unsubscribeMessage = client.onGameMessage(handleGameMessage);

    const unsubscribeStatus = client.onStatusChange((newStatus: WSStatus) => {
      setStatus(newStatus);

      if (newStatus === "open") {
        setError(null);
      } else if (newStatus === "error") {
        setError("Connection error occurred");
      }
    });

    const unsubscribeQuality = client.onConnectionQualityChange(
      (quality: WSConnectionQuality) => {
        setConnectionQuality(quality);
      },
    );

    client.connect().catch((err: unknown) => {
      setError(err instanceof Error ? err.message : "Failed to connect");
    });

    return () => {
      unsubscribeMessage();
      unsubscribeStatus();
      unsubscribeQuality();
      client.disconnect();
      clientRef.current = null;
    };
  }, [gameId, enabled, handleGameMessage]);

  const sendMessage = (data: object): boolean => {
    if (!clientRef.current) return false;
    return clientRef.current.send(data);
  };

  const isConnected = status === "open";

  return {
    status,
    error,
    isConnected,
    connectionQuality,
    gameState,
    sendMessage,
  };
}
