"use client";
import { format } from "date-fns";
import { Loader2, MessageCircle } from "lucide-react";
import { clsx } from "clsx";
import type { ConversationDetail, Message } from "@/types";

interface Props {
  conversation: ConversationDetail | null;
  isLoading: boolean;
}

function MessageBubble({ message }: { message: Message }) {
  const isMine = message.is_mine;
  return (
    <div className={clsx("flex gap-2 mb-3", isMine ? "flex-row-reverse" : "flex-row")}>
      {/* Avatar */}
      <div
        className={clsx(
          "w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-1",
          isMine ? "bg-linkedin-500 text-white" : "bg-gray-200 text-gray-700"
        )}
      >
        {message.sender_name?.charAt(0)?.toUpperCase() ?? "?"}
      </div>

      <div className={clsx("max-w-[72%] space-y-1", isMine ? "items-end" : "items-start")}>
        {!isMine && (
          <span className="text-xs text-gray-500 ml-1">{message.sender_name}</span>
        )}
        <div
          className={clsx(
            "px-4 py-2.5 rounded-2xl text-sm leading-relaxed shadow-sm",
            isMine
              ? "bg-linkedin-500 text-white rounded-tr-sm"
              : "bg-white text-gray-800 rounded-tl-sm border border-gray-100"
          )}
        >
          {message.body}
        </div>
        <p className={clsx("text-xs text-gray-400 px-1", isMine ? "text-right" : "text-left")}>
          {message.sent_at ? format(new Date(message.sent_at), "MMM d, h:mm a") : ""}
        </p>
      </div>
    </div>
  );
}

export default function ConversationThread({ conversation, isLoading }: Props) {
  if (!conversation && !isLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-gray-300 gap-4">
        <MessageCircle className="w-16 h-16 opacity-30" />
        <p className="text-sm text-gray-400">Select a conversation to view messages</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-linkedin-400 animate-spin" />
      </div>
    );
  }

  if (!conversation) return null;

  return (
    <div className="flex-1 overflow-y-auto p-4" id="message-thread">
      {/* Header info */}
      <div className="flex items-center gap-3 pb-4 mb-4 border-b border-gray-100">
        <div className="w-10 h-10 rounded-full bg-linkedin-100 text-linkedin-700 flex items-center justify-center font-bold">
          {conversation.participants[0]?.name?.charAt(0)?.toUpperCase() ?? "?"}
        </div>
        <div>
          <p className="font-semibold text-gray-900 text-sm">
            {conversation.participants.map((p) => p.name).join(", ")}
          </p>
          <p className="text-xs text-gray-400">
            {conversation.participants[0]?.headline || "LinkedIn Member"}
          </p>
        </div>
      </div>

      {/* Messages */}
      {conversation.messages.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-8">
          No messages loaded yet.
        </p>
      ) : (
        conversation.messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)
      )}
    </div>
  );
}
