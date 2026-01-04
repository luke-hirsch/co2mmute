import { useState, useEffect, useRef } from "react";
import type {
  WSStatus,
  WSConnectionQuality,
  WSGameState,
  WSGameStats,
} from "../types/wsTypes";
import { GameStateWSClient } from "../utils/gameStateWS";

interface UseGameStateOptions {
  gameId: string;
  enabled?: boolean;
}

interface UseGameStateResult {
  gameState: WSGameState | null;
  gameStats: WSGameStats | null;
  status: WSStatus;
  error: string | null;
  isConnected: boolean;
  connectionQuality: WSConnectionQuality | null;
}

/**
 * Hook to manage game state WebSocket connection
 */
export function useGameState(options: UseGameStateOptions): UseGameStateResult {
  const { gameId, enabled = true } = options;

  const [gameState, setGameState] = useState<WSGameState | null>(null);
  const [gameStats, setGameStats] = useState<WSGameStats | null>(null);
  const [status, setStatus] = useState<WSStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [connectionQuality, setConnectionQuality] =
    useState<WSConnectionQuality | null>(null);

  const clientRef = useRef<GameStateWSClient | null>(null);

  // Create and connect to game state socket
  useEffect(() => {
    if (!enabled) return;

    // Initialize client if not already done
    if (!clientRef.current) {
      // Construct WebSocket URL from current location
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.host;
      const wsUrl = `${protocol}//${host}/ws/gamestate/${gameId}/`;

      clientRef.current = new GameStateWSClient(wsUrl);
    }

    const client = clientRef.current;

    // Subscribe to messages
    const unsubscribeMessage = client.onGameStateMessage((message: any) => {
      if (message.type === "gamestate.update") {
        setGameState(message.game);
        setGameStats(message.stats);
        setError(null);
      }
    });

    // Subscribe to status changes
    const unsubscribeStatus = client.onStatusChange((newStatus: any) => {
      setStatus(newStatus);

      if (newStatus === "open") {
        setError(null);
      } else if (newStatus === "error") {
        setError("Connection error occurred");
      }
    });

    // Subscribe to connection quality changes
    const unsubscribeQuality = client.onConnectionQualityChange(
      (quality: any) => {
        setConnectionQuality(quality);
      }
    );

    // Connect
    client.connect().catch((err: any) => {
      setError(err instanceof Error ? err.message : "Failed to connect");
    });

    // Cleanup on unmount
    return () => {
      unsubscribeMessage();
      unsubscribeStatus();
      unsubscribeQuality();
      client.disconnect();
      clientRef.current = null;
    };
  }, [gameId, enabled]);

  const isConnected = status === "open";

  return {
    gameState,
    gameStats,
    status,
    error,
    isConnected,
    connectionQuality,
  };
}
