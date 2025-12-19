import { useState, useEffect, useRef } from "react";
import type { WSStatus, WSChatMessagePayload } from "../types/wsTypes";
import { ChatWSClient } from "../utils/chatWS";

interface UseChatSocketOptions {
  gameId: string;
  enabled?: boolean;
}

interface UseChatSocketResult {
  messages: WSChatMessagePayload[];
  status: WSStatus;
  error: string | null;
  isConnected: boolean;
  sendMessage: (text: string) => boolean;
}

export function useChatSocket(
  options: UseChatSocketOptions
): UseChatSocketResult {
  const { gameId, enabled = true } = options;

  const [messages, setMessages] = useState<WSChatMessagePayload[]>([]);
  const [status, setStatus] = useState<WSStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  const clientRef = useRef<ChatWSClient | null>(null);

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
        setMessages(message.messages || []);
        setError(null);
      } else if (message.type === "chat.message") {
        setMessages((prev) => [...prev, message.message]);
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
  }, [gameId, enabled]);

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
