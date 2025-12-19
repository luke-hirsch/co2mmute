import { useState, useEffect, useRef } from "react";
import type { WSPlayer, WSStatus } from "../types/wsTypes";
import { LobbyWSClient } from "../utils/lobbyWS";

interface UseLobbySocketOptions {
  gameId: string;
  enabled?: boolean;
}

interface UseLobbySocketResult {
  players: WSPlayer[];
  status: WSStatus;
  error: string | null;
  isConnected: boolean;
}

/**
 * Hook to manage lobby WebSocket connection
 */
export function useLobbySocket(
  options: UseLobbySocketOptions
): UseLobbySocketResult {
  const { gameId, enabled = true } = options;

  const [players, setPlayers] = useState<WSPlayer[]>([]);
  const [status, setStatus] = useState<WSStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  const clientRef = useRef<LobbyWSClient | null>(null);

  // Create and connect to lobby socket
  useEffect(() => {
    if (!enabled) return;

    // Initialize client if not already done
    if (!clientRef.current) {
      // Construct WebSocket URL from current location
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.host;
      const wsUrl = `${protocol}//${host}/ws/lobby/${gameId}/`;

      clientRef.current = new LobbyWSClient(wsUrl);
    }

    const client = clientRef.current;

    // Subscribe to messages
    const unsubscribeMessage = client.onLobbyMessage((message: any) => {
      if (message.type === "lobby.roster") {
        setPlayers(message.players);
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

    // Connect
    client.connect().catch((err: any) => {
      setError(err instanceof Error ? err.message : "Failed to connect");
    });

    // Cleanup on unmount
    return () => {
      unsubscribeMessage();
      unsubscribeStatus();
      client.disconnect();
      clientRef.current = null;
    };
  }, [gameId, enabled]);

  const isConnected = status === "open";

  return {
    players,
    status,
    error,
    isConnected,
  };
}
