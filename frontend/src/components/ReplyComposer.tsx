"use client";
import { useState, useRef, useEffect } from "react";
import { Send, Sparkles, Loader2, ChevronDown, ChevronUp } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { sendReply, generateAIReply, getUseCases, updateDraftStatus } from "@/services/api";
import type { UseCase, AIReplyResponse } from "@/types";

interface Props {
  conversationId: string | null;
}

export default function ReplyComposer({ conversationId }: Props) {
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [generatingAI, setGeneratingAI] = useState(false);
  const [aiDraft, setAIDraft] = useState<AIReplyResponse | null>(null);
  const [selectedUseCaseId, setSelectedUseCaseId] = useState<number | undefined>();
  const [customInstructions, setCustomInstructions] = useState("");
  const [showAIPanel, setShowAIPanel] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const qc = useQueryClient();

  const { data: useCasesData } = useQuery({
    queryKey: ["use-cases"],
    queryFn: () => getUseCases().then((r) => r.data),
  });
  const useCases: UseCase[] = useCasesData ?? [];

  // Auto-grow textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [message]);

  async function handleSend() {
    if (!conversationId || !message.trim()) return;
    setSending(true);
    setError("");
    setSuccess("");
    try {
      await sendReply(conversationId, message.trim());
      setMessage("");
      setAIDraft(null);
      setSuccess("Message sent!");
      qc.invalidateQueries({ queryKey: ["conversation", conversationId] });
      qc.invalidateQueries({ queryKey: ["conversations"] });
      setTimeout(() => setSuccess(""), 3000);
    } catch {
      setError("Failed to send message.");
    } finally {
      setSending(false);
    }
  }

  async function handleGenerateAI() {
    if (!conversationId) return;
    setGeneratingAI(true);
    setError("");
    setAIDraft(null);
    try {
      const res = await generateAIReply(conversationId, {
        use_case_id: selectedUseCaseId,
        custom_instructions: customInstructions || undefined,
      });
      setAIDraft(res.data);
      setMessage(res.data.draft);
    } catch {
      setError("Failed to generate AI reply. Make sure messages are loaded.");
    } finally {
      setGeneratingAI(false);
    }
  }

  async function handleDismissDraft() {
    if (aiDraft?.draft_id) {
      await updateDraftStatus(aiDraft.draft_id, "dismissed");
    }
    setAIDraft(null);
    setMessage("");
  }

  if (!conversationId) {
    return null;
  }

  return (
    <div className="border-t border-gray-200 bg-white">
      {/* AI Draft banner */}
      {aiDraft && (
        <div className="mx-4 mt-3 p-3 bg-linkedin-50 border border-linkedin-200 rounded-lg text-xs">
          <div className="flex items-center justify-between mb-1">
            <span className="font-semibold text-linkedin-700 flex items-center gap-1">
              <Sparkles className="h-3.5 w-3.5" /> AI Draft
            </span>
            <button
              onClick={handleDismissDraft}
              className="text-gray-400 hover:text-gray-600 text-xs underline"
            >
              Dismiss
            </button>
          </div>
          <p className="text-gray-600 italic">{aiDraft.reasoning}</p>
        </div>
      )}

      {/* AI config panel */}
      {showAIPanel && (
        <div className="mx-4 mt-2 p-3 bg-gray-50 border border-gray-200 rounded-lg space-y-2">
          <p className="text-xs font-semibold text-gray-600">AI Reply Settings</p>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Use Case</label>
            <select
              value={selectedUseCaseId ?? ""}
              onChange={(e) =>
                setSelectedUseCaseId(e.target.value ? Number(e.target.value) : undefined)
              }
              className="w-full text-xs border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-linkedin-500"
            >
              <option value="">Default (general professional)</option>
              {useCases.map((uc) => (
                <option key={uc.id} value={uc.id}>
                  {uc.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Custom Instructions</label>
            <input
              type="text"
              value={customInstructions}
              onChange={(e) => setCustomInstructions(e.target.value)}
              placeholder="e.g. Be brief and mention our product demo"
              className="w-full text-xs border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-linkedin-500"
            />
          </div>
        </div>
      )}

      {/* Main composer */}
      <div className="p-3">
        {error && <p className="text-xs text-red-500 mb-2">{error}</p>}
        {success && <p className="text-xs text-green-600 mb-2">{success}</p>}

        <div className="flex gap-2 items-end">
          <textarea
            ref={textareaRef}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Write a message… (Enter to send, Shift+Enter for newline)"
            rows={2}
            className="flex-1 resize-none border border-gray-300 rounded-2xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-linkedin-500 max-h-40 overflow-y-auto"
          />

          <div className="flex flex-col gap-1">
            {/* AI generate button */}
            <button
              onClick={handleGenerateAI}
              disabled={generatingAI}
              title="Generate AI reply"
              className="p-2.5 rounded-full bg-purple-100 text-purple-700 hover:bg-purple-200 disabled:opacity-50 transition-colors"
            >
              {generatingAI ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
            </button>

            {/* Send button */}
            <button
              onClick={handleSend}
              disabled={sending || !message.trim()}
              title="Send message"
              className="p-2.5 rounded-full bg-linkedin-500 text-white hover:bg-linkedin-600 disabled:opacity-40 transition-colors"
            >
              {sending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </button>
          </div>
        </div>

        {/* Toggle AI settings */}
        <button
          onClick={() => setShowAIPanel((v) => !v)}
          className="mt-1.5 flex items-center gap-1 text-xs text-gray-400 hover:text-linkedin-500"
        >
          {showAIPanel ? (
            <ChevronUp className="h-3 w-3" />
          ) : (
            <ChevronDown className="h-3 w-3" />
          )}
          AI settings
        </button>
      </div>
    </div>
  );
}
