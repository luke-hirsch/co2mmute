import { useState, useEffect, useRef } from "react";
import type { WSStatus, WSChatMessagePayload } from "../types/wsTypes";
import { ChatWSClient } from "../utils/chatWS";

interface UseChatSocketOptions {
  gameId: string;
  enabled?: boolean;
  currentPlayerName?: string;
}

interface ChatMessageWithMeta extends WSChatMessagePayload {
  isCurrentUser: boolean;
}

interface UseChatSocketResult {
  messages: ChatMessageWithMeta[];
  status: WSStatus;
  error: string | null;
  isConnected: boolean;
  sendMessage: (text: string) => boolean;
}

export function useChatSocket(
  options: UseChatSocketOptions
): UseChatSocketResult {
  const { gameId, currentPlayerName, enabled = true } = options;

  const [messages, setMessages] = useState<ChatMessageWithMeta[]>([]);
  const [status, setStatus] = useState<WSStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  const clientRef = useRef<ChatWSClient | null>(null);

  // Helper function to enrich messages with isCurrentUser flag
  const enrichMessage = (
    message: WSChatMessagePayload
  ): ChatMessageWithMeta => ({
    ...message,
    isCurrentUser: currentPlayerName
      ? message.playerName === currentPlayerName
      : false,
  });

  useEffect(() => {
    if (!enabled) return;

    if (!clientRef.current) {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.host;
      const wsUrl = `${protocol}//${host}/ws/chat/${gameId}/`;

      clientRef.current = new ChatWSClient(wsUrl);
    }

    const client = clientRef.current;

    const unsubscribeMessage = client.onChatMessage((message: any) => {
      if (message.type === "chat.history") {
        setMessages((message.messages || []).map(enrichMessage));
        setError(null);
      } else if (message.type === "chat.message") {
        setMessages((prev) => [...prev, enrichMessage(message.message)]);
        setError(null);
      } else if (message.type === "chat.error") {
        setError(message.error);
      }
    });

    const unsubscribeStatus = client.onStatusChange((newStatus: any) => {
      setStatus(newStatus);

      if (newStatus === "open") {
        setError(null);
      } else if (newStatus === "error") {
        setError("Connection error occurred");
      }
    });

    client.connect().catch((err: any) => {
      setError(err instanceof Error ? err.message : "Failed to connect");
    });

    return () => {
      unsubscribeMessage();
      unsubscribeStatus();
      client.disconnect();
      clientRef.current = null;
    };
  }, [gameId, enabled, currentPlayerName]);

  const sendMessage = (text: string): boolean => {
    if (!clientRef.current) return false;
    return clientRef.current.sendChatMessage(text);
  };

  const isConnected = status === "open";

  return {
    messages,
    status,
    error,
    isConnected,
    sendMessage,
  };
}
