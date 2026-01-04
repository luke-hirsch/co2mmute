import { useState, useCallback } from "react";
import { API_BASE_URL } from "../config";
import { apiFetch } from "../utils/api";

interface UsePlayerMoveOptions {
  gameId: string;
  playerId: string;
}

interface UsePlayerMoveResult {
  submitMove: (action: string) => Promise<boolean>;
  isLoading: boolean;
  error: string | null;
}

/**
 * Hook to submit player moves (transportation choices)
 */
export function usePlayerMove({
  gameId,
  playerId,
}: UsePlayerMoveOptions): UsePlayerMoveResult {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submitMove = useCallback(
    async (action: string): Promise<boolean> => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await apiFetch(
          `${API_BASE_URL}/api/game/${gameId}/player/${playerId}/move/`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ action }),
          }
        );

        if (!response.ok) {
          const errorData = await response.json();
          setError(errorData.error || "Failed to submit move");
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
