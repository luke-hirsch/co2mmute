import { BaseWSClient } from "./ws";
import type { WSChatMessage } from "../types/wsTypes";

type ChatMessageHandler = (message: WSChatMessage) => void;

export class ChatWSClient extends BaseWSClient {
  private chatHandlers: ChatMessageHandler[] = [];

  protected handleMessage(data: any): void {
    try {
      const payload = typeof data === "string" ? JSON.parse(data) : data;

      if (payload.type === "ping") {
        this.handlePing();
        return;
      }

      if (!isWSChatMessage(payload)) {
        console.warn("Received invalid chat message:", payload);
        return;
      }

      for (const handler of this.chatHandlers) {
        try {
          handler(payload);
        } catch (err) {
          console.error("Chat message handler error:", err);
        }
      }
    } catch (err) {
      console.error("Failed to parse chat message:", err);
    }
  }

  /**
   * Send a chat message to the server
   */
  sendChatMessage(messageText: string): boolean {
    return this.send({
      type: "chat.message",
      message: messageText,
    });
  }

  /**
   * Subscribe to chat messages (history, new messages, errors)
   */
  onChatMessage(handler: ChatMessageHandler): () => void {
    this.chatHandlers.push(handler);

    return () => {
      const idx = this.chatHandlers.indexOf(handler);
      if (idx >= 0) this.chatHandlers.splice(idx, 1);
    };
  }
}

function isWSChatMessage(data: any): data is WSChatMessage {
  if (!data || !data.type) return false;

  const validTypes = ["ping", "chat.history", "chat.message", "chat.error"];

  return validTypes.includes(data.type);
}
