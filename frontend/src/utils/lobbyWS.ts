import { BaseWSClient } from "./ws";
import type { WSLobbyMessage } from "../types/wsTypes";

type LobbyMessageHandler = (message: WSLobbyMessage) => void;

export class LobbyWSClient extends BaseWSClient {
  private lobbyHandlers: LobbyMessageHandler[] = [];

  /**
   * Handle incoming messages from lobby server
   */
  protected handleMessage(data: any): void {
    try {
      const payload = typeof data === "string" ? JSON.parse(data) : data;

      // Auto-respond to pings with pong
      if (payload.type === "ping") {
        this.handlePing();
        return;
      }

      // Type guard: is this a valid lobby message?
      if (!isWSLobbyMessage(payload)) {
        console.warn("Received invalid lobby message:", payload);
        return;
      }

      // Call subclass handlers
      for (const handler of this.lobbyHandlers) {
        try {
          handler(payload);
        } catch (err) {
          console.error("Lobby message handler error:", err);
        }
      }
    } catch (err) {
      console.error("Failed to parse lobby message:", err);
    }
  }

  /**
   * Subscribe to lobby roster updates
   */
  onLobbyMessage(handler: LobbyMessageHandler): () => void {
    this.lobbyHandlers.push(handler);

    return () => {
      const idx = this.lobbyHandlers.indexOf(handler);
      if (idx >= 0) this.lobbyHandlers.splice(idx, 1);
    };
  }
}

/**
 * Type guard to check if message is a valid WSLobbyMessage
 */
function isWSLobbyMessage(data: any): data is WSLobbyMessage {
  return (
    data &&
    (data.type === "lobby.roster" || data.type === "pong") &&
    (data.type === "pong" || Array.isArray(data.players))
  );
}
