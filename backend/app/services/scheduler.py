"""
Daily scanner — runs at a configured hour and generates AI reply drafts
for all unanswered LinkedIn conversations.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..config import settings
from ..database import AsyncSessionLocal
from ..models import Conversation, Message, UseCase, AIDraft
from ..services.linkedin import fetch_conversations, fetch_messages
from ..services.ai_agent import generate_reply

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _upsert_conversations(session: AsyncSession, raw_list: list) -> None:
    """Upsert fetched conversations into the database."""
    for raw in raw_list:
        existing = await session.get(Conversation, raw["id"])
        if existing:
            for k, v in raw.items():
                setattr(existing, k, v)
            existing.synced_at = datetime.utcnow()
        else:
            session.add(Conversation(**raw, synced_at=datetime.utcnow()))
    await session.commit()


async def _upsert_messages(session: AsyncSession, raw_msgs: list) -> None:
    for raw in raw_msgs:
        existing = await session.get(Message, raw["id"])
        if not existing:
            session.add(Message(**raw))
    await session.commit()


async def run_daily_scan() -> dict:
    """
    Main daily scan job:
    1. Fetch all conversations from LinkedIn
    2. Identify unanswered threads
    3. For each unanswered thread, fetch messages and generate an AI draft
       using all active use cases
    Returns a result summary dict.
    """
    result = {
        "conversations_scanned": 0,
        "unanswered_found": 0,
        "drafts_created": 0,
        "errors": [],
    }

    logger.info("Daily scan started at %s", datetime.utcnow().isoformat())

    try:
        # Pull fresh conversations from LinkedIn
        raw_conversations = fetch_conversations(limit=100)
    except Exception as exc:
        msg = f"Failed to fetch conversations: {exc}"
        logger.error(msg)
        result["errors"].append(msg)
        return result

    result["conversations_scanned"] = len(raw_conversations)

    async with AsyncSessionLocal() as session:
        await _upsert_conversations(session, raw_conversations)

        # Load active use cases
        uc_result = await session.execute(select(UseCase).where(UseCase.is_active == True))  # noqa: E712
        use_cases = uc_result.scalars().all()

        # If no use cases, create a default one for the scan
        default_use_case = None
        if not use_cases:
            default_use_case = UseCase(
                name="General",
                description="Default professional LinkedIn reply",
                system_prompt=(
                    "You are a professional LinkedIn messaging assistant. "
                    "Write concise, warm, and professional replies. "
                    "Always respond with JSON: {\"draft\": \"...\", \"reasoning\": \"...\"}"
                ),
                is_active=True,
            )
            session.add(default_use_case)
            await session.commit()
            use_cases = [default_use_case]

        for conv_data in raw_conversations:
            if not conv_data.get("awaiting_reply"):
                continue

            result["unanswered_found"] += 1
            conv_id = conv_data["id"]

            # Fetch and cache messages for this conversation
            try:
                raw_msgs = fetch_messages(conv_id)
                await _upsert_messages(session, raw_msgs)
            except Exception as exc:
                result["errors"].append(f"Fetch messages for {conv_id}: {exc}")
                continue

            # Build history for AI
            history = [
                {
                    "sender_name": m["sender_name"],
                    "body": m["body"],
                    "is_mine": m["is_mine"],
                }
                for m in raw_msgs
            ]

            # Generate a draft per active use case
            for uc in use_cases:
                # Skip if a pending draft already exists for this conversation + use case
                existing_draft = await session.execute(
                    select(AIDraft).where(
                        AIDraft.conversation_id == conv_id,
                        AIDraft.use_case_id == uc.id,
                        AIDraft.status == "pending",
                    )
                )
                if existing_draft.scalars().first():
                    continue

                try:
                    ai_result = generate_reply(
                        conversation_history=history,
                        system_prompt=uc.system_prompt,
                    )
                    if ai_result.get("draft"):
                        draft = AIDraft(
                            conversation_id=conv_id,
                            use_case_id=uc.id,
                            draft_text=ai_result["draft"],
                            reasoning=ai_result.get("reasoning", ""),
                            status="pending",
                        )
                        session.add(draft)
                        result["drafts_created"] += 1
                except Exception as exc:
                    result["errors"].append(f"AI draft for {conv_id}/{uc.name}: {exc}")

        await session.commit()

    logger.info("Daily scan complete: %s", result)
    return result


def start_scheduler():
    """Register and start the APScheduler job."""
    scheduler.add_job(
        run_daily_scan,
        CronTrigger(hour=settings.daily_scan_hour, minute=settings.daily_scan_minute),
        id="daily_scan",
        replace_existing=True,
        name="Daily LinkedIn message scan",
    )
    scheduler.start()
    logger.info(
        "Scheduler started — daily scan at %02d:%02d UTC",
        settings.daily_scan_hour,
        settings.daily_scan_minute,
    )


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
