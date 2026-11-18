"""Deterministic before_tool_callback Guardrails for Google ADK Agent."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from app.store import store

logger = logging.getLogger("ayos_den.guards")

# Prompt injection patterns
_PROMPT_INJECTION_TAGS = re.compile(
    r"\[\s*(?:SYSTEM|ADMIN|INSTRUCTION|PROMPT|DEVELOPER|OVERRIDE)\s*:[^\]]*\]",
    re.IGNORECASE,
)
_PROMPT_INJECTION_PHRASES = re.compile(
    r"\b(?:ignore|disregard|forget)\s+(?:all\s+)?(?:previous|prior|above|system)\s+instructions\b",
    re.IGNORECASE,
)
_PROMPT_INJECTION_DIRECTIVES = re.compile(
    r"\b(?:system\s+prompt\s+override|you\s+are\s+now\s+in\s+developer\s+mode|bypass\s+all\s+guardrails)\b",
    re.IGNORECASE,
)

# PII patterns
_EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)
_PHONE_PATTERN = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
)


def sanitize_untrusted_text(text: str) -> Dict[str, Any]:
    """Sanitizes untrusted community text against indirect prompt injections and redacts PII.

    Returns:
        dict: {"sanitized_text": str, "flags": list[str]}
    """
    if not text:
        return {"sanitized_text": "", "flags": []}

    flags: List[str] = []
    current_text = text

    # 1. Strip prompt injection tags [SYSTEM: ...], [ADMIN: ...], etc.
    if _PROMPT_INJECTION_TAGS.search(current_text):
        flags.append("PROMPT_INJECTION_DETECTED")
        current_text = _PROMPT_INJECTION_TAGS.sub("", current_text)

    # 2. Strip prompt injection phrases
    if _PROMPT_INJECTION_PHRASES.search(current_text):
        if "PROMPT_INJECTION_DETECTED" not in flags:
            flags.append("PROMPT_INJECTION_DETECTED")
        current_text = _PROMPT_INJECTION_PHRASES.sub("", current_text)

    if _PROMPT_INJECTION_DIRECTIVES.search(current_text):
        if "PROMPT_INJECTION_DETECTED" not in flags:
            flags.append("PROMPT_INJECTION_DETECTED")
        current_text = _PROMPT_INJECTION_DIRECTIVES.sub("", current_text)

    # 3. Redact Email addresses
    if _EMAIL_PATTERN.search(current_text):
        flags.append("PII_EMAIL_REDACTED")
        current_text = _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", current_text)

    # 4. Redact Phone numbers
    if _PHONE_PATTERN.search(current_text):
        flags.append("PII_PHONE_REDACTED")
        current_text = _PHONE_PATTERN.sub("[REDACTED_PHONE]", current_text)

    # Normalize whitespace
    sanitized_text = re.sub(r"\s+", " ", current_text).strip()

    return {
        "sanitized_text": sanitized_text,
        "flags": flags,
    }



def publish_metadata_guard(args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Deterministic guardrail: Requires explicit creator confirmation before publishing metadata."""
    metadata_id = args.get("metadata_id")
    user_confirmed = bool(args.get("user_confirmed", False))
    confirmation_token = args.get("confirmation_token")

    # If already confirmed via argument or pre-confirmed in store, allow
    if user_confirmed:
        return None

    if metadata_id:
        record = store.get_staged_metadata(int(metadata_id))
        if record and record.get("status") == "Confirmed":
            return None

    # Block execution and return structured interception payload
    logger.warning(f"[Guardrail: publish_metadata_guard] Blocked unconfirmed publication for metadata_id: {metadata_id}")
    return {
        "guard_status": "CONFIRMATION_REQUIRED",
        "guard_name": "publish_metadata_guard",
        "message": "Deterministic Guardrail: Video metadata publication halted. Explicit creator confirmation required.",
        "action_required": "CONFIRM_IN_COMMAND_DECK",
        "metadata_id": metadata_id,
        "title": args.get("title"),
        "staged_state": "CONFIRMATION_PENDING",
    }


def post_comment_reply_guard(args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Deterministic guardrail: Requires explicit human approval before posting live YouTube replies."""
    comment_id = args.get("comment_id")
    human_confirmed = bool(args.get("human_confirmed", False))

    if human_confirmed:
        return None

    # Check if comment is already approved in store
    if comment_id:
        comments = store.list_staged_comments()
        for c in comments:
            if c.get("comment_id") == comment_id and c.get("status") in ["APPROVED", "EDITED", "Confirmed"]:
                return None

    # Block execution and return structured interception payload
    logger.warning(f"[Guardrail: post_comment_reply_guard] Blocked unapproved reply dispatch for comment_id: {comment_id}")
    return {
        "guard_status": "CONFIRMATION_REQUIRED",
        "guard_name": "post_comment_reply_guard",
        "message": "Deterministic Guardrail: Live comment reply dispatch halted. Explicit human-in-the-loop approval required.",
        "action_required": "APPROVE_IN_COMMAND_DECK",
        "comment_id": comment_id,
        "reply_text": args.get("reply_text"),
        "staged_state": "HITL_PENDING",
    }


def unified_before_tool_callback(tool: Any, args: Dict[str, Any], tool_context: Any = None) -> Optional[Dict[str, Any]]:
    """Unified ADK before_tool_callback router.
    
    Returns None to proceed with tool execution, or a dict to halt tool execution
    and return the dict as the tool's result.
    """
    tool_name = getattr(tool, "name", str(tool))
    if hasattr(tool, "__name__"):
        tool_name = tool.__name__

    if tool_name == "publish_video_metadata":
        return publish_metadata_guard(args)

    if tool_name == "post_comment_reply":
        return post_comment_reply_guard(args)

    return None
