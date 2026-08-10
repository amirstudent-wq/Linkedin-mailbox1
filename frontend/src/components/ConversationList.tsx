"use client";
import { formatDistanceToNow } from "date-fns";
import { MessageCircle, Clock, CheckCircle, AlertCircle } from "lucide-react";
import { clsx } from "clsx";
import type { Conversation } from "@/types";

interface Props {
  conversations: Conversation[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  isLoading: boolean;
}

function Avatar({ name, url }: { name: string; url?: string }) {
  if (url) {
    return (
      <img
        src={url}
        alt={name}
        className="w-12 h-12 rounded-full object-cover flex-shrink-0"
        onError={(e) => {
          (e.target as HTMLImageElement).style.display = "none";
        }}
      />
    );
  }
  const initials = name
    .split(" ")
    .slice(0, 2)
    .map((n) => n[0]?.toUpperCase() ?? "")
    .join("");
  return (
    <div className="w-12 h-12 rounded-full bg-linkedin-100 text-linkedin-700 flex items-center justify-center text-sm font-bold flex-shrink-0">
      {initials || "?"}
    </div>
  );
}

function StatusBadge({ conv }: { conv: Conversation }) {
  if (!conv.is_read) {
    return (
      <span className="w-2.5 h-2.5 rounded-full bg-linkedin-500 flex-shrink-0" title="Unread" />
    );
  }
  if (conv.awaiting_reply) {
    return (
      <span title="Awaiting your reply">
        <AlertCircle className="w-4 h-4 text-amber-500 flex-shrink-0" />
      </span>
    );
  }
  if (conv.last_message_is_mine) {
    return (
      <span title="You replied last">
        <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" /></span>
    );
  }
  return null;
}

export default function ConversationList({
  conversations,
  selectedId,
  onSelect,
  isLoading,
}: Props) {
  if (isLoading) {
    return (
      <div className="flex-1 overflow-y-auto divide-y divide-gray-100">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="p-4 animate-pulse">
            <div className="flex gap-3">
              <div className="w-12 h-12 rounded-full bg-gray-200" />
              <div className="flex-1 space-y-2">
                <div className="h-4 bg-gray-200 rounded w-3/4" />
                <div className="h-3 bg-gray-100 rounded w-full" />
                <div className="h-3 bg-gray-100 rounded w-1/2" />
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!conversations.length) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-gray-400 gap-3 p-8">
        <MessageCircle className="w-12 h-12 opacity-30" />
        <p className="text-sm text-center">
          No conversations found.
          <br />
          Press <strong>Sync</strong> to load from LinkedIn.
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto divide-y divide-gray-100">
      {conversations.map((conv) => {
        const primaryParticipant = conv.participants[0];
        const name = primaryParticipant?.name ?? "Unknown";
        const avatar = primaryParticipant?.avatar_url;
        const headline = primaryParticipant?.headline ?? "";
        const timeAgo = conv.last_message_at
          ? formatDistanceToNow(new Date(conv.last_message_at), { addSuffix: true })
          : "";

        return (
          <button
            key={conv.id}
            onClick={() => onSelect(conv.id)}
            className={clsx(
              "w-full text-left p-4 hover:bg-gray-50 transition-colors",
              selectedId === conv.id && "bg-linkedin-50 border-l-4 border-l-linkedin-500"
            )}
          >
            <div className="flex gap-3">
              <Avatar name={name} url={avatar} />

              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <span
                    className={clsx(
                      "text-sm truncate",
                      !conv.is_read ? "font-bold text-gray-900" : "font-medium text-gray-800"
                    )}
                  >
                    {name}
                  </span>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <StatusBadge conv={conv} />
                    {timeAgo && (
                      <span className="text-xs text-gray-400 whitespace-nowrap">{timeAgo}</span>
                    )}
                  </div>
                </div>

                {headline && (
                  <p className="text-xs text-gray-400 truncate">{headline}</p>
                )}

                <p
                  className={clsx(
                    "text-xs mt-0.5 truncate",
                    !conv.is_read ? "font-semibold text-gray-700" : "text-gray-500"
                  )}
                >
                  {conv.last_message_is_mine && (
                    <span className="text-linkedin-400 mr-1">You:</span>
                  )}
                  {conv.last_message_text || "No messages yet"}
                </p>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
