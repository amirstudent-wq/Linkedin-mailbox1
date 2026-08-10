"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Sparkles, Send, X, ChevronDown, ChevronUp, Loader2, CheckCircle } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { getDrafts, updateDraftStatus, sendReply } from "@/services/api";
import type { AIDraft } from "@/types";

interface Props {
  onSelectConversation?: (id: string) => void;
}

export default function DraftsSidebar({ onSelectConversation }: Props) {
  const qc = useQueryClient();
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["drafts", "pending"],
    queryFn: () => getDrafts("pending").then((r) => r.data),
    refetchInterval: 60_000,
  });
  const drafts: AIDraft[] = data ?? [];

  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [sending, setSending] = useState<number | null>(null);
  const [sent, setSent] = useState<Set<number>>(new Set());

  async function handleSend(draft: AIDraft) {
    setSending(draft.id);
    try {
      await sendReply(draft.conversation_id, draft.draft_text);
      await updateDraftStatus(draft.id, "sent");
      setSent((s) => new Set(s).add(draft.id));
      qc.invalidateQueries({ queryKey: ["conversations"] });
      qc.invalidateQueries({ queryKey: ["drafts"] });
    } catch {
      /* noop */
    } finally {
      setSending(null);
    }
  }

  async function handleDismiss(draft: AIDraft) {
    await updateDraftStatus(draft.id, "dismissed");
    qc.invalidateQueries({ queryKey: ["drafts"] });
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-gray-900 text-sm flex items-center gap-1.5">
            <Sparkles className="h-4 w-4 text-purple-500" />
            AI Drafts
            {drafts.length > 0 && (
              <span className="ml-1 px-1.5 py-0.5 rounded-full bg-purple-100 text-purple-700 text-xs font-bold">
                {drafts.length}
              </span>
            )}
          </h2>
          <p className="text-xs text-gray-400">Prepared by daily scan</p>
        </div>
        <button
          onClick={() => refetch()}
          className="text-xs text-gray-400 hover:text-linkedin-500 underline"
        >
          Refresh
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {isLoading && (
          <div className="flex justify-center py-8">
            <Loader2 className="w-6 h-6 text-purple-400 animate-spin" />
          </div>
        )}

        {!isLoading && drafts.length === 0 && (
          <div className="text-center py-8 text-sm text-gray-400">
            <Sparkles className="w-8 h-8 mx-auto opacity-30 mb-2" />
            <p>No pending AI drafts.</p>
            <p className="mt-1">Run an AI Scan to generate them.</p>
          </div>
        )}

        {drafts.map((draft) => {
          const isExpanded = expandedId === draft.id;
          const wasSent = sent.has(draft.id);

          return (
            <div
              key={draft.id}
              className={`border rounded-xl overflow-hidden transition-all ${
                wasSent ? "border-green-200 bg-green-50" : "border-purple-100 bg-white"
              }`}
            >
              {/* Header */}
              <button
                onClick={() => setExpandedId(isExpanded ? null : draft.id)}
                className="w-full flex items-center justify-between p-3 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center gap-2 min-w-0">
                  {wasSent ? (
                    <CheckCircle className="h-4 w-4 text-green-500 flex-shrink-0" />
                  ) : (
                    <Sparkles className="h-4 w-4 text-purple-500 flex-shrink-0" />
                  )}
                  <p className="text-xs font-medium text-gray-700 truncate">
                    {draft.conversation_id.slice(0, 30)}…
                  </p>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className="text-xs text-gray-400">
                    {formatDistanceToNow(new Date(draft.created_at), { addSuffix: true })}
                  </span>
                  {isExpanded ? (
                    <ChevronUp className="h-3.5 w-3.5 text-gray-400" />
                  ) : (
                    <ChevronDown className="h-3.5 w-3.5 text-gray-400" />
                  )}
                </div>
              </button>

              {/* Expanded content */}
              {isExpanded && (
                <div className="px-3 pb-3 space-y-3">
                  {draft.reasoning && (
                    <p className="text-xs text-gray-500 italic bg-gray-50 rounded p-2">
                      💡 {draft.reasoning}
                    </p>
                  )}

                  <div className="bg-purple-50 border border-purple-100 rounded-lg p-3">
                    <p className="text-sm text-gray-800 leading-relaxed">{draft.draft_text}</p>
                  </div>

                  <div className="flex gap-2 justify-end">
                    {onSelectConversation && (
                      <button
                        onClick={() => onSelectConversation(draft.conversation_id)}
                        className="text-xs text-linkedin-500 hover:underline"
                      >
                        View thread
                      </button>
                    )}

                    <button
                      onClick={() => handleDismiss(draft)}
                      className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-full border border-gray-300 text-gray-600 hover:bg-gray-50"
                    >
                      <X className="h-3 w-3" /> Dismiss
                    </button>

                    <button
                      onClick={() => handleSend(draft)}
                      disabled={sending === draft.id || wasSent}
                      className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-full bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50 transition-colors"
                    >
                      {sending === draft.id ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        <Send className="h-3 w-3" />
                      )}
                      {wasSent ? "Sent!" : "Send"}
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
