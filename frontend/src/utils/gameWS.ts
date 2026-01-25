import { BaseWSClient } from "./ws";

type GameMessageHandler = (message: unknown) => void;

export class GameWSClient extends BaseWSClient {
  private gameHandlers: GameMessageHandler[] = [];

  /**
   * Handle incoming messages from game server
   */
  protected handleMessage(data: unknown): void {
    try {
      const payload = typeof data === "string" ? JSON.parse(data) : data;

      // Auto-respond to pings with pong
      if (
        payload &&
        typeof payload === "object" &&
        "type" in payload &&
        payload.type === "ping"
      ) {
        this.handlePing();
        return;
      }

      // Call handlers for all other messages
      for (const handler of this.gameHandlers) {
        try {
          handler(payload);
        } catch (err) {
          console.error("Game message handler error:", err);
        }
      }
    } catch (err) {
      console.error("Failed to parse game message:", err);
    }
  }

  /**
   * Subscribe to game messages
   */
  onGameMessage(handler: GameMessageHandler): () => void {
    this.gameHandlers.push(handler);

    return () => {
      const idx = this.gameHandlers.indexOf(handler);
      if (idx >= 0) this.gameHandlers.splice(idx, 1);
    };
  }
}
