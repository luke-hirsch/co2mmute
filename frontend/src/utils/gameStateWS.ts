import { BaseWSClient } from "./ws";
import type { WSGameStateMessage } from "../types/wsTypes";

type GameStateMessageHandler = (message: WSGameStateMessage) => void;

export class GameStateWSClient extends BaseWSClient {
  private gameStateHandlers: GameStateMessageHandler[] = [];

  /**
   * Handle incoming messages from game state server
   */
  protected handleMessage(data: any): void {
    try {
      const payload = typeof data === "string" ? JSON.parse(data) : data;

      // Auto-respond to pings with pong
      if (payload.type === "ping") {
        this.handlePing();
        return;
      }

      // Type guard: is this a valid game state message?
      if (!isWSGameStateMessage(payload)) {
        console.warn("Received invalid game state message:", payload);
        return;
      }

      // Call subclass handlers
      for (const handler of this.gameStateHandlers) {
        try {
          handler(payload);
        } catch (err) {
          console.error("Game state message handler error:", err);
        }
      }
    } catch (err) {
      console.error("Failed to parse game state message:", err);
    }
  }

  /**
   * Subscribe to game state updates
   */
  onGameStateMessage(handler: GameStateMessageHandler): () => void {
    this.gameStateHandlers.push(handler);

    return () => {
      const idx = this.gameStateHandlers.indexOf(handler);
      if (idx >= 0) this.gameStateHandlers.splice(idx, 1);
    };
  }
}

/**
 * Type guard to check if message is a valid WSGameStateMessage
 */
function isWSGameStateMessage(data: any): data is WSGameStateMessage {
  return (
    data &&
    (data.type === "gamestate.update" || data.type === "pong") &&
    (data.type === "pong" || (data.game && data.stats))
  );
}
