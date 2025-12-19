import TextInput from "./TextInput";
import { useState } from "react";
import { PaperAirplaneIcon } from "@heroicons/react/24/solid";
import { useChatSocket } from "../hooks/useChatSocket";

interface ChatSidebarProps {
  gameId: string;
}

const ChatSidebar = ({ gameId }: ChatSidebarProps) => {
  const { messages, error, isConnected, sendMessage } = useChatSocket({
    gameId,
  });

  const [inputText, setInputText] = useState("");

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
        <div className="text-xs font-semibold">
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
        {error && (
          <div className="text-xs text-red-600 dark:text-red-400">{error}</div>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto mb-4">
        {messages.length === 0 && (
          <div className="text-xs text-muted italic">No messages yet</div>
        )}
        {messages.map((message, idx) => (
          <div key={idx} className="mb-3">
            <div className="text-sm font-semibold">{message.playerName}</div>
            <div className="text-base wrap-break-word">{message.message}</div>
            <div className="text-xs text-muted">
              {new Date(message.ts).toLocaleTimeString()}
            </div>
          </div>
        ))}
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
          className="w-full flex rounded bg-primary-600 p-2 text-left font-semibold textt-darktext transition-colors duration-200 hover:bg-primary-500 focus-visible:outline focus-visible:outline-offset-2 focus-visible:outline-primary-600 dark:bg-primary-600 dark:hover:bg-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <PaperAirplaneIcon className="w-5 h-5" /> Send
        </button>
      </form>
    </div>
  );
};

export default ChatSidebar;
