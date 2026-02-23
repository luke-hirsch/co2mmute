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
  WSStatsAllAckedMessage,
  WSVoteRecordedMessage,
  WSVoteResultMessage,
  BetweenRoundPhase,
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

      const defaultBetweenRound = {
        betweenRoundPhase: "none" as BetweenRoundPhase,
        hasMapVersions: false,
        mapVersions: [] as WSGameState["mapVersions"],
        voteProgress: null,
        voteResult: null,
      };

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
            maxCo2LevelG: data.max_co2_level * 1000,
            currentRound: data.current_round,
            totalEmissionsG: 0,
            lastRoundStats: prev?.lastRoundStats || null,
            roster: prev?.roster || [],
            ...defaultBetweenRound,
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
              ...defaultBetweenRound,
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
            // Reset between-round state
            ...defaultBetweenRound,
            lastRoundStats: null,
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
            betweenRoundPhase: "stats" as BetweenRoundPhase,
            hasMapVersions: data.has_map_versions,
            mapVersions: data.map_versions || [],
            voteProgress: null,
            voteResult: null,
          }));
          callbacksRef.current.onRoundCompleted?.(data);
          break;
        }

        case "stats.all_acked": {
          const data = msg.data as WSStatsAllAckedMessage["data"];
          if (data.next_phase === "discussion") {
            setGameState((prev) =>
              prev ? { ...prev, betweenRoundPhase: "discussion" } : prev,
            );
          }
          // If next_phase is "next_round", the round.started message will follow
          break;
        }

        case "vote.opened": {
          setGameState((prev) =>
            prev ? { ...prev, betweenRoundPhase: "voting" } : prev,
          );
          break;
        }

        case "vote.recorded": {
          const data = msg.data as WSVoteRecordedMessage["data"];
          setGameState((prev) =>
            prev
              ? {
                  ...prev,
                  voteProgress: {
                    cast: data.votes_cast,
                    needed: data.votes_needed,
                  },
                }
              : prev,
          );
          break;
        }

        case "vote.result": {
          const data = msg.data as WSVoteResultMessage["data"];
          setGameState((prev) =>
            prev ? { ...prev, voteResult: data } : prev,
          );
          break;
        }

        case "roster.update": {
          const players = (msg as WSRosterUpdateMessage).players;
          setGameState((prev) => {
            if (!prev) {
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
                ...defaultBetweenRound,
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
            betweenRoundPhase: data.betweenRoundPhase || "none",
            hasMapVersions: data.hasMapVersions || false,
            mapVersions: data.mapVersions || [],
            voteProgress: prev?.voteProgress || null,
            voteResult: prev?.voteResult || null,
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
