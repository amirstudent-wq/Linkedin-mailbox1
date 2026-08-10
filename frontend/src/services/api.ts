import axios from "axios";
import type {
  Conversation,
  ConversationDetail,
  UseCase,
  AIDraft,
  AIReplyResponse,
  ScanResult,
  ConversationFilters,
} from "@/types";

const api = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

// ── Auth ─────────────────────────────────────────────────────────────────────

export const getAuthStatus = () =>
  api.get<{ connected: boolean; linkedin_email: string | null; message: string }>("/auth/status");

// ── Messages ─────────────────────────────────────────────────────────────────

export const syncConversations = () =>
  api.post<{ synced: number; errors: number; message: string }>("/messages/sync");

export const getConversations = (filters: Partial<ConversationFilters> = {}) => {
  const params: Record<string, string | boolean> = {};
  if (filters.unread_only) params.unread_only = true;
  if (filters.awaiting_reply != null) params.awaiting_reply = filters.awaiting_reply;
  if (filters.search) params.search = filters.search;
  if (filters.sort_by) params.sort_by = filters.sort_by;
  if (filters.sort_dir) params.sort_dir = filters.sort_dir;
  return api.get<Conversation[]>("/messages", { params });
};

export const getConversation = (id: string) =>
  api.get<ConversationDetail>(`/messages/${encodeURIComponent(id)}`);

export const sendReply = (conversationId: string, message: string) =>
  api.post<{ success: boolean; message: string }>(
    `/messages/${encodeURIComponent(conversationId)}/reply`,
    { message }
  );

// ── AI ───────────────────────────────────────────────────────────────────────

export const generateAIReply = (
  conversationId: string,
  opts: { use_case_id?: number; custom_instructions?: string } = {}
) =>
  api.post<AIReplyResponse>(`/ai/reply/${encodeURIComponent(conversationId)}`, opts);

export const getDrafts = (status?: string) =>
  api.get<AIDraft[]>("/ai/drafts", { params: status ? { status } : {} });

export const updateDraftStatus = (draftId: number, status: string) =>
  api.patch<AIDraft>(`/ai/drafts/${draftId}`, { status });

// ── Use Cases ─────────────────────────────────────────────────────────────────

export const getUseCases = () => api.get<UseCase[]>("/use-cases");

export const createUseCase = (data: {
  name: string;
  description?: string;
  system_prompt: string;
  is_active?: boolean;
}) => api.post<UseCase>("/use-cases", data);

export const updateUseCase = (
  id: number,
  data: Partial<{ name: string; description: string; system_prompt: string; is_active: boolean }>
) => api.patch<UseCase>(`/use-cases/${id}`, data);

export const deleteUseCase = (id: number) => api.delete(`/use-cases/${id}`);

// ── Scheduler ─────────────────────────────────────────────────────────────────

export const triggerDailyScan = () => api.post<ScanResult>("/scheduler/run");
