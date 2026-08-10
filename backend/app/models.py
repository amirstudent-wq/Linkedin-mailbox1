from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, Integer, Text, DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import relationship

from .database import Base


class Conversation(Base):
    """Cached LinkedIn conversation metadata."""
    __tablename__ = "conversations"

    id = Column(String, primary_key=True)  # LinkedIn conversation URN
    participants = Column(JSON)            # list of {name, profile_id, avatar_url, headline}
    last_message_at = Column(DateTime)
    last_message_text = Column(Text, default="")
    is_read = Column(Boolean, default=True)
    # True if the authenticated user sent the last message in the thread
    last_message_is_mine = Column(Boolean, default=False)
    # True when a counterpart sent a message we have not yet replied to
    awaiting_reply = Column(Boolean, default=False)
    message_count = Column(Integer, default=0)
    synced_at = Column(DateTime, default=datetime.utcnow)

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    ai_drafts = relationship("AIDraft", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    """Individual messages within a conversation."""
    __tablename__ = "messages"

    id = Column(String, primary_key=True)   # LinkedIn event URN
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    sender_id = Column(String)
    sender_name = Column(String)
    sender_avatar = Column(String, default="")
    body = Column(Text, default="")
    sent_at = Column(DateTime)
    is_mine = Column(Boolean, default=False)

    conversation = relationship("Conversation", back_populates="messages")


class UseCase(Base):
    """User-defined AI reply use cases / personas."""
    __tablename__ = "use_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    system_prompt = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    ai_drafts = relationship("AIDraft", back_populates="use_case")


class AIDraft(Base):
    """AI-generated reply drafts produced during daily scans."""
    __tablename__ = "ai_drafts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    use_case_id = Column(Integer, ForeignKey("use_cases.id"), nullable=True)
    draft_text = Column(Text, nullable=False)
    reasoning = Column(Text, default="")   # why this reply was suggested
    status = Column(String, default="pending")  # pending | sent | dismissed
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="ai_drafts")
    use_case = relationship("UseCase", back_populates="ai_drafts")
