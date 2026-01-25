import { useState, useEffect, useRef } from "react";
import type { WSStatus, WSConnectionQuality } from "../types/wsTypes";
import { GameWSClient } from "../utils/gameWS";

interface UseGameSocketOptions {
  gameId: string;
  enabled?: boolean;
}

interface UseGameSocketResult {
  status: WSStatus;
  error: string | null;
  isConnected: boolean;
  connectionQuality: WSConnectionQuality | null;
  sendMessage: (data: object) => boolean;
}

/**
 * Hook to manage game WebSocket connection
 * This replaces both useLobbySocket and useGameState
 */
export function useGameSocket(
  options: UseGameSocketOptions
): UseGameSocketResult {
  const { gameId, enabled = true } = options;

  const [status, setStatus] = useState<WSStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [connectionQuality, setConnectionQuality] =
    useState<WSConnectionQuality | null>(null);

  const clientRef = useRef<GameWSClient | null>(null);

  useEffect(() => {
    if (!enabled) return;

    if (!clientRef.current) {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.host;
      const wsUrl = `${protocol}//${host}/ws/game/${gameId}/`;

      clientRef.current = new GameWSClient(wsUrl);
    }

    const client = clientRef.current;

    const unsubscribeMessage = client.onGameMessage((message: unknown) => {
      // Message handling will be implemented as the GameConsumer is built
      console.debug("Game message received:", message);
    });

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
      }
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
  }, [gameId, enabled]);

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
    sendMessage,
  };
}
