import TextInput from "./TextInput";
import { useState, useEffect, useRef } from "react";
import { PaperAirplaneIcon } from "@heroicons/react/24/solid";
import { useChatSocket } from "../hooks/useChatSocket";
import { useAuth } from "../context/AuthContext";
import ConnectionSignal from "./ConnectionSignal";

interface ChatSidebarProps {
  gameId: string;
  chatEnabled?: boolean;
}

const ChatSidebar = ({ gameId, chatEnabled = true }: ChatSidebarProps) => {
  const { auth } = useAuth();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Get current player name - for hosts, construct it as "username (Host)"
  // For regular players, use the player name
  const currentPlayerName =
    auth?.kind === "host" && auth?.username
      ? `${auth.username} (Host)`
      : auth?.player?.name;

  const { messages, error, isConnected, sendMessage, connectionQuality } =
    useChatSocket({
      gameId,
      currentPlayerName,
      enabled: chatEnabled,
    });

  const [inputText, setInputText] = useState("");

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSendMessage = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    const trimmedMessage = inputText.trim();
    if (!trimmedMessage) return;

    const sent = sendMessage(trimmedMessage);
    if (sent) {
      setInputText("");
    } else if (!isConnected) {
      console.warn("Not connected to chat");
    }
  };

  return (
    <div className="flex flex-col justify-between max-h-full overflow-y-auto rounded border border-subtle bg-surface p-4 text-main shadow-sm transition-colors duration-300 dark:border-darksubtle dark:bg-darksurface dark:text-darktext">
      {/* Status indicator */}
      <div className="mb-2">
        <div className="text-xs font-semibold flex items-center justify-between">
          <div>
            {isConnected ? (
              <span className="text-green-600 dark:text-green-400">
                ● Connected
              </span>
            ) : (
              <span className="text-amber-600 dark:text-amber-400">
                ● Connecting...
              </span>
            )}
          </div>
          {connectionQuality && (
            <ConnectionSignal quality={connectionQuality} showTooltip={true} />
          )}
        </div>
        {error && (
          <div className="text-xs text-red-600 dark:text-red-400">{error}</div>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto mb-4">
        {messages.length === 0 && (
          <div className="text-xs text-muted italic">No messages yet</div>
        )}
        {messages.map((message, idx) => {
          if (message.isSystem) {
            return (
              <div key={idx} className="mb-3 flex justify-center">
                <div className="px-3 py-1 text-xs text-muted italic bg-gray-100 dark:bg-gray-800 rounded-full">
                  {message.message}
                </div>
              </div>
            );
          }

          const isHostMessage = message.playerName.includes("(Host)");

          return (
            <div
              key={idx}
              className={`mb-3 flex ${message.isCurrentUser ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-xs px-3 py-2 ${
                  message.isCurrentUser
                    ? "bg-primary-600 text-darktext rounded-lg shadow-md"
                    : isHostMessage
                      ? "bg-amber-100 dark:bg-amber-900 text-amber-950 dark:text-amber-50 rounded-lg shadow-md border-2 border-amber-300 dark:border-amber-600"
                      : "bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-lg shadow-sm"
                }`}
              >
                {!message.isCurrentUser && (
                  <div
                    className={`text-sm font-semibold mb-1 ${
                      isHostMessage ? "text-amber-700 dark:text-amber-200" : ""
                    }`}
                  >
                    {message.playerName}
                  </div>
                )}
                <div className="text-base wrap-break-word">
                  {message.message}
                </div>
                <div
                  className={`text-xs mt-1 ${
                    message.isCurrentUser
                      ? "text-darktext opacity-70"
                      : isHostMessage
                        ? "text-amber-600 dark:text-amber-300"
                        : "text-muted"
                  }`}
                >
                  {new Date(message.ts).toLocaleTimeString()}
                </div>
              </div>
            </div>
          );
        })}
        <div ref={messagesEndRef} />
      </div>

      {/* Input form */}
      <form className="mt-auto" onSubmit={handleSendMessage}>
        <TextInput
          additionalClasses="relative"
          margin="my-2"
          name="message"
          placeholder="Nachricht schreiben..."
          value={inputText}
          onChange={(e) => setInputText(e.currentTarget.value)}
          disabled={!isConnected}
        />

        <button
          type="submit"
          disabled={!isConnected || !inputText.trim()}
          className="w-full flex justify-center rounded bg-primary-600 p-2 text-left font-semibold text-darktext transition-colors duration-200 hover:bg-primary-500 focus-visible:outline focus-visible:outline-offset-2 focus-visible:outline-primary-600 dark:bg-primary-600 dark:hover:bg-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <PaperAirplaneIcon className="w-5 h-5" /> Send
        </button>
      </form>
    </div>
  );
};

export default ChatSidebar;
