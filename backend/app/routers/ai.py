from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..database import get_db
from ..models import Conversation, Message, AIDraft, UseCase
from ..schemas import AIReplyRequest, AIReplyResponse, AIDraftOut, AIDraftUpdate
from ..services.ai_agent import generate_reply

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/reply/{conversation_id}", response_model=AIReplyResponse)
async def generate_ai_reply(
    conversation_id: str,
    body: AIReplyRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate an AI reply draft for a conversation.
    Uses the specified use_case or the default prompt if none is given.
    """
    # Load messages
    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.sent_at.asc())
    )
    messages = msg_result.scalars().all()

    if not messages:
        raise HTTPException(
            status_code=404,
            detail="No messages found for this conversation. Load the conversation first.",
        )

    history = [
        {"sender_name": m.sender_name, "body": m.body, "is_mine": m.is_mine}
        for m in messages
    ]

    # Load system prompt from use case if specified
    system_prompt = None
    if body.use_case_id:
        uc = await db.get(UseCase, body.use_case_id)
        if uc:
            system_prompt = uc.system_prompt

    ai_result = generate_reply(
        conversation_history=history,
        system_prompt=system_prompt,
        custom_instructions=body.custom_instructions,
    )

    if not ai_result.get("draft"):
        raise HTTPException(status_code=502, detail="AI failed to generate a reply.")

    # Persist draft
    draft = AIDraft(
        conversation_id=conversation_id,
        use_case_id=body.use_case_id,
        draft_text=ai_result["draft"],
        reasoning=ai_result.get("reasoning", ""),
        status="pending",
    )
    db.add(draft)
    await db.commit()
    await db.refresh(draft)

    return AIReplyResponse(
        draft=ai_result["draft"],
        reasoning=ai_result.get("reasoning", ""),
        draft_id=draft.id,
    )


@router.get("/drafts", response_model=list[AIDraftOut])
async def list_drafts(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all AI drafts (optionally filtered by status)."""
    stmt = select(AIDraft).order_by(AIDraft.created_at.desc())
    if status:
        stmt = stmt.where(AIDraft.status == status)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/drafts/{draft_id}", response_model=AIDraftOut)
async def get_draft(draft_id: int, db: AsyncSession = Depends(get_db)):
    draft = await db.get(AIDraft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found.")
    return draft


@router.patch("/drafts/{draft_id}", response_model=AIDraftOut)
async def update_draft_status(
    draft_id: int,
    body: AIDraftUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a draft's status (e.g. mark as sent or dismissed)."""
    draft = await db.get(AIDraft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found.")
    draft.status = body.status
    await db.commit()
    await db.refresh(draft)
    return draft
