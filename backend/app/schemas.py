from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel


# ── Participant ──────────────────────────────────────────────────────────────

class Participant(BaseModel):
    profile_id: str
    name: str
    headline: Optional[str] = ""
    avatar_url: Optional[str] = ""


# ── Message ──────────────────────────────────────────────────────────────────

class MessageOut(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    sender_name: str
    sender_avatar: Optional[str] = ""
    body: str
    sent_at: datetime
    is_mine: bool

    model_config = {"from_attributes": True}


# ── Conversation ─────────────────────────────────────────────────────────────

class ConversationSummary(BaseModel):
    id: str
    participants: List[Participant]
    last_message_at: Optional[datetime] = None
    last_message_text: str
    is_read: bool
    last_message_is_mine: bool
    awaiting_reply: bool
    message_count: int
    synced_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ConversationDetail(ConversationSummary):
    messages: List[MessageOut] = []


# ── Replies ──────────────────────────────────────────────────────────────────

class ReplyRequest(BaseModel):
    message: str


class AIReplyRequest(BaseModel):
    use_case_id: Optional[int] = None
    custom_instructions: Optional[str] = None


class AIReplyResponse(BaseModel):
    draft: str
    reasoning: str
    draft_id: Optional[int] = None


# ── Use Cases ────────────────────────────────────────────────────────────────

class UseCaseCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    system_prompt: str
    is_active: bool = True


class UseCaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    is_active: Optional[bool] = None


class UseCaseOut(BaseModel):
    id: int
    name: str
    description: str
    system_prompt: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── AI Drafts ────────────────────────────────────────────────────────────────

class AIDraftOut(BaseModel):
    id: int
    conversation_id: str
    use_case_id: Optional[int] = None
    draft_text: str
    reasoning: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AIDraftUpdate(BaseModel):
    status: str  # pending | sent | dismissed


# ── Scheduler ────────────────────────────────────────────────────────────────

class ScanResult(BaseModel):
    conversations_scanned: int
    unanswered_found: int
    drafts_created: int
    errors: List[str] = []


# ── Auth ─────────────────────────────────────────────────────────────────────

class AuthStatus(BaseModel):
    connected: bool
    linkedin_email: Optional[str] = None
    message: str


class SyncStatus(BaseModel):
    synced: int
    errors: int
    message: str
