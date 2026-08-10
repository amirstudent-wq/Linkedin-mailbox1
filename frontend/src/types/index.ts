export interface Participant {
  profile_id: string;
  name: string;
  headline?: string;
  avatar_url?: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  sender_id: string;
  sender_name: string;
  sender_avatar?: string;
  body: string;
  sent_at: string;
  is_mine: boolean;
}

export interface Conversation {
  id: string;
  participants: Participant[];
  last_message_at: string | null;
  last_message_text: string;
  is_read: boolean;
  last_message_is_mine: boolean;
  awaiting_reply: boolean;
  message_count: number;
  synced_at?: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface UseCase {
  id: number;
  name: string;
  description: string;
  system_prompt: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AIDraft {
  id: number;
  conversation_id: string;
  use_case_id: number | null;
  draft_text: string;
  reasoning: string;
  status: "pending" | "sent" | "dismissed";
  created_at: string;
}

export interface AIReplyResponse {
  draft: string;
  reasoning: string;
  draft_id: number | null;
}

export interface ScanResult {
  conversations_scanned: number;
  unanswered_found: number;
  drafts_created: number;
  errors: string[];
}

export type SortBy = "last_message_at" | "participant_name";
export type SortDir = "asc" | "desc";

export interface ConversationFilters {
  unread_only: boolean;
  awaiting_reply: boolean | null;
  search: string;
  sort_by: SortBy;
  sort_dir: SortDir;
}
