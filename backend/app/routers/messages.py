from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..database import get_db
from ..models import Conversation, Message
from ..schemas import ConversationSummary, ConversationDetail, MessageOut, ReplyRequest, SyncStatus
from ..services import linkedin as li_service

router = APIRouter(prefix="/api/messages", tags=["messages"])


async def _sync_conversation_to_db(session: AsyncSession, raw: dict):
    existing = await session.get(Conversation, raw["id"])
    if existing:
        for k, v in raw.items():
            setattr(existing, k, v)
        existing.synced_at = datetime.utcnow()
    else:
        session.add(Conversation(**raw, synced_at=datetime.utcnow()))


@router.post("/sync", response_model=SyncStatus)
async def sync_conversations(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Fetch latest conversations from LinkedIn and cache them."""
    try:
        raw_list = li_service.fetch_conversations(limit=80)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    errors = 0
    for raw in raw_list:
        try:
            await _sync_conversation_to_db(db, raw)
        except Exception:
            errors += 1

    await db.commit()
    return SyncStatus(
        synced=len(raw_list) - errors,
        errors=errors,
        message=f"Synced {len(raw_list) - errors} conversations.",
    )


@router.get("", response_model=List[ConversationSummary])
async def list_conversations(
    # Filters
    unread_only: bool = Query(False),
    awaiting_reply: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, description="Search by participant name or last message"),
    # Sort
    sort_by: str = Query("last_message_at", enum=["last_message_at", "participant_name"]),
    sort_dir: str = Query("desc", enum=["asc", "desc"]),
    # Pagination
    skip: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Return cached conversations with optional filtering and sorting.
    Call /sync first to populate the cache from LinkedIn.
    """
    stmt = select(Conversation)

    if unread_only:
        stmt = stmt.where(Conversation.is_read == False)  # noqa: E712

    if awaiting_reply is not None:
        stmt = stmt.where(Conversation.awaiting_reply == awaiting_reply)

    if search:
        search_lower = search.lower()
        stmt = stmt.where(
            Conversation.last_message_text.ilike(f"%{search_lower}%")
        )

    # Sorting
    if sort_by == "last_message_at":
        order_col = Conversation.last_message_at
    else:
        # participant_name — sort by JSON field is tricky in SQLite; fall back to last_message_at
        order_col = Conversation.last_message_at

    if sort_dir == "desc":
        stmt = stmt.order_by(order_col.desc().nulls_last())
    else:
        stmt = stmt.order_by(order_col.asc().nulls_last())

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    conversations = result.scalars().all()

    # Post-filter by participant name (JSON field) if sorting by participant_name
    if search and sort_by == "participant_name":
        conversations = [
            c for c in conversations
            if any(
                search.lower() in p.get("name", "").lower()
                for p in (c.participants or [])
            )
        ]

    return conversations


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single conversation with its full message thread."""
    conv = await db.get(Conversation, conversation_id)
    if not conv:
        # Try to fetch from LinkedIn on the fly
        try:
            raw_list = li_service.fetch_conversations(limit=1)
        except RuntimeError as exc:
            raise HTTPException(status_code=404, detail="Conversation not found. Run /sync first.")

    # Fetch and cache messages if not yet loaded
    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.sent_at.asc())
    )
    messages = msg_result.scalars().all()

    if not messages:
        # Pull from LinkedIn
        try:
            raw_msgs = li_service.fetch_messages(conversation_id)
            for raw in raw_msgs:
                existing = await db.get(Message, raw["id"])
                if not existing:
                    db.add(Message(**raw))
            await db.commit()

            msg_result = await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.sent_at.asc())
            )
            messages = msg_result.scalars().all()
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Could not load messages: {exc}")

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    # Mark as read in DB
    conv.is_read = True
    await db.commit()

    return ConversationDetail(
        id=conv.id,
        participants=conv.participants or [],
        last_message_at=conv.last_message_at,
        last_message_text=conv.last_message_text,
        is_read=conv.is_read,
        last_message_is_mine=conv.last_message_is_mine,
        awaiting_reply=conv.awaiting_reply,
        message_count=conv.message_count,
        synced_at=conv.synced_at,
        messages=[MessageOut.model_validate(m) for m in messages],
    )


@router.post("/{conversation_id}/reply")
async def reply_to_conversation(
    conversation_id: str,
    body: ReplyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a reply message to a LinkedIn conversation."""
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message body cannot be empty.")

    success = li_service.send_message(conversation_id, body.message)
    if not success:
        raise HTTPException(status_code=502, detail="Failed to send message to LinkedIn.")

    # Update conversation state in DB
    conv = await db.get(Conversation, conversation_id)
    if conv:
        conv.last_message_is_mine = True
        conv.awaiting_reply = False
        conv.last_message_text = body.message
        conv.last_message_at = datetime.utcnow()
        await db.commit()

    return {"success": True, "message": "Message sent."}
