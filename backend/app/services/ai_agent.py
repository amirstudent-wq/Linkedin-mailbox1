"""
AI Agent service — generates contextual LinkedIn reply drafts using Claude.
"""

from __future__ import annotations

import logging
from typing import List, Optional

import anthropic

from ..config import settings

logger = logging.getLogger(__name__)

_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY must be set in the environment.")
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


# ── Default system prompt ────────────────────────────────────────────────────

DEFAULT_SYSTEM_PROMPT = """You are a professional LinkedIn messaging assistant.
Your task is to craft thoughtful, concise, and personalized reply messages.

Guidelines:
- Keep replies professional but warm
- Match the tone of the conversation
- Be direct and clear
- Avoid generic or overly formal language
- Do not use excessive filler phrases like "Hope this message finds you well"
- Keep it brief unless the context requires detail (2-4 sentences is usually ideal)

Always respond with valid JSON in this exact format:
{
  "draft": "the reply text",
  "reasoning": "brief explanation of why you wrote it this way"
}
"""


def generate_reply(
    conversation_history: List[dict],
    system_prompt: Optional[str] = None,
    custom_instructions: Optional[str] = None,
) -> dict:
    """
    Generate an AI reply draft for a conversation.

    Args:
        conversation_history: List of {sender_name, body, is_mine} dicts, oldest first.
        system_prompt: Custom system prompt from a UseCase.
        custom_instructions: One-off instructions to append.

    Returns:
        dict with 'draft' and 'reasoning' keys.
    """
    client = _get_client()

    base_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
    if custom_instructions:
        base_prompt += f"\n\nAdditional instructions: {custom_instructions}"

    # Build the conversation context string
    context_lines: List[str] = []
    for msg in conversation_history[-10:]:  # last 10 messages for context
        role = "Me" if msg.get("is_mine") else msg.get("sender_name", "Them")
        context_lines.append(f"{role}: {msg.get('body', '')}")

    context = "\n".join(context_lines)
    user_message = (
        f"Here is the recent conversation:\n\n{context}\n\n"
        "Please write a reply to the last message. "
        "Respond with JSON only: {\"draft\": \"...\", \"reasoning\": \"...\"}"
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=base_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text.strip()

        # Parse JSON from response
        import json, re
        # Handle code-fenced JSON
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        json_str = match.group(1) if match else raw
        result = json.loads(json_str)
        return {
            "draft": result.get("draft", ""),
            "reasoning": result.get("reasoning", ""),
        }
    except Exception as exc:
        logger.error("AI reply generation failed: %s", exc)
        return {"draft": "", "reasoning": f"Generation failed: {exc}"}


def generate_use_case_prompt(use_case_name: str, use_case_description: str) -> str:
    """
    Ask Claude to generate a system prompt for a given use case.
    Used when creating new use cases to give users a starting-point prompt.
    """
    client = _get_client()
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Write a concise system prompt for a LinkedIn messaging AI assistant "
                        f"that handles this use case:\n\nName: {use_case_name}\n"
                        f"Description: {use_case_description}\n\n"
                        "The system prompt should tell the AI how to reply to LinkedIn messages "
                        "for this specific purpose. Output only the system prompt text, no explanation."
                    ),
                }
            ],
        )
        return response.content[0].text.strip()
    except Exception as exc:
        logger.error("System prompt generation failed: %s", exc)
        return DEFAULT_SYSTEM_PROMPT
