import TextInput from "./TextInput";
import { type ChatMessage } from "../utils/types";
import { useState } from "react";
import { PaperAirplaneIcon } from "@heroicons/react/24/solid";
const ChatSidebar = () => {
  const sendMessage = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    console.log("Send message");
    const formData = new FormData(e.currentTarget);

    setMessages([
      ...messages,
      {
        id: (messages.length + 1).toString(),
        authorId: "user",
        content: formData.get("message")?.toString() || "",
        timestamp: Date.now(),
      },
    ]);
    // Clear input field
    e.currentTarget.reset();
  };
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "1",
      authorId: "system",
      content: "Achtung! Nachrichten sind nicht verschlüsselt.",
      timestamp: Date.now(),
    },
  ]);
  return (
    <div className="flex flex-col justify-between max-h-dvh overflow-y-auto rounded border border-subtle bg-surface p-4 text-main shadow-sm transition-colors duration-300 dark:border-darksubtle dark:bg-darksurface dark:text-darktext">
      {[...messages].map((message) => (
        <div key={message.id} className="mb-2">
          <div className="text-sm font-semibold">{message.authorId}</div>
          <div className="text-base">{message.content}</div>
          <div className="text-xs text-muted">
            {new Date(message.timestamp).toLocaleTimeString()}
          </div>
        </div>
      ))}

      <form className="mt-auto" onSubmit={sendMessage}>
        <TextInput
          additionalClasses="relative"
          margin="my-2"
          name="message"
          placeholder="Nachricht schreiben..."
        />

        <button
          type="submit"
          className="w-full flex rounded bg-primary-600 p-2 text-left font-semibold textt-darktext transition-colors duration-200 hover:bg-primary-500 focus-visible:outline focus-visible:outline-offset-2 focus-visible:outline-primary-600 dark:bg-primary-600 dark:hover:bg-primary-500"
        >
          <PaperAirplaneIcon className="w-5 h-5" /> Send
        </button>
      </form>
    </div>
  );
};

export default ChatSidebar;
