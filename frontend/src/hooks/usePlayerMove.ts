import { useState, useCallback } from "react";
import { API_BASE_URL } from "../config";
import { apiFetch } from "../utils/api";

interface UsePlayerMoveOptions {
  gameId: string;
  playerId: string;
}

interface UsePlayerMoveResult {
  submitMove: (action: string, payload?: Record<string, unknown>) => Promise<boolean>;
  isLoading: boolean;
  error: string | null;
}

/**
 * Hook to submit player moves (transportation choices)
 * @param action - Primary action type (car, public, bike, walk)
 * @param payload - Optional additional data (e.g., per-agent choices)
 */
export function usePlayerMove({
  gameId,
  playerId,
}: UsePlayerMoveOptions): UsePlayerMoveResult {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submitMove = useCallback(
    async (action: string, payload?: Record<string, unknown>): Promise<boolean> => {
      setIsLoading(true);
      setError(null);

      try {
        // apiFetch returns parsed JSON directly, not a Response object
        const data = await apiFetch(
          `${API_BASE_URL}/api/game/${gameId}/player/${playerId}/move/`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ action, payload }),
          }
        );

        // Check for error in response data
        if (data.error) {
          setError(data.error);
          return false;
        }

        setError(null);
        return true;
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Network error";
        setError(errorMessage);
        return false;
      } finally {
        setIsLoading(false);
      }
    },
    [gameId, playerId]
  );

  return {
    submitMove,
    isLoading,
    error,
  };
}
