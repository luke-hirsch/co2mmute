import { useState, useEffect, useRef, useCallback } from "react";
import type {
  WSStatus,
  WSChatMessagePayload,
  WSConnectionQuality,
  WSChatMessage,
} from "../types/wsTypes";
import { ChatWSClient } from "../utils/chatWS";

interface UseChatSocketOptions {
  gameId: string;
  enabled?: boolean;
  currentPlayerName?: string;
}

interface ChatMessageWithMeta extends WSChatMessagePayload {
  isCurrentUser: boolean;
  isSystem?: false;
}

interface SystemMessage {
  ts: number;
  message: string;
  isSystem: true;
}

type ChatMessage = ChatMessageWithMeta | SystemMessage;

interface UseChatSocketResult {
  messages: ChatMessage[];
  status: WSStatus;
  error: string | null;
  isConnected: boolean;
  sendMessage: (text: string) => boolean;
  connectionQuality: WSConnectionQuality | null;
}

export function useChatSocket(
  options: UseChatSocketOptions
): UseChatSocketResult {
  const { gameId, currentPlayerName, enabled = true } = options;

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<WSStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [connectionQuality, setConnectionQuality] =
    useState<WSConnectionQuality | null>(null);

  const clientRef = useRef<ChatWSClient | null>(null);

  // Helper function to enrich messages with isCurrentUser flag
  const enrichMessage = useCallback(
    (message: WSChatMessagePayload): ChatMessageWithMeta => ({
      ...message,
      isCurrentUser: currentPlayerName
        ? message.playerName === currentPlayerName
        : false,
      isSystem: false as const,
    }),
    [currentPlayerName]
  );

  useEffect(() => {
    if (!enabled) return;

    if (!clientRef.current) {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.host;
      const wsUrl = `${protocol}//${host}/ws/chat/${gameId}/`;

      clientRef.current = new ChatWSClient(wsUrl);
    }

    const client = clientRef.current;

    const unsubscribeMessage = client.onChatMessage((message: WSChatMessage) => {
      if (message.type === "chat.history") {
        setMessages((message.messages || []).map(enrichMessage));
        setError(null);
      } else if (message.type === "chat.message") {
        setMessages((prev) => [...prev, enrichMessage(message.message)]);
        setError(null);
      } else if (message.type === "chat.system") {
        const systemMessage: SystemMessage = {
          ts: Date.now(),
          message: message.message,
          isSystem: true,
        };
        setMessages((prev) => [...prev, systemMessage]);
      } else if (message.type === "chat.error") {
        setError(message.error);
      }
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
  }, [gameId, enabled, enrichMessage]);

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
    connectionQuality,
  };
}
