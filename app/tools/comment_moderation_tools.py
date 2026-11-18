"""Comment Moderation & Sovereign Reply Architect Tools for Ayo's Den & IoChat."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.guards import sanitize_untrusted_text
from app.store import store
from app.tools.decisions_grader import triage_and_grade_comment


SLANG_LEXICON = {
    "ate": "HIGH_PRAISE",
    "left no crumbs": "HIGH_PRAISE",
    "cooked": "INTENSE_PERFORMANCE",
    "blud": "CASUAL_MEME",
    "no cap": "SINCERITY",
    "fr": "SINCERITY",
    "main character": "AESTHETIC_PRAISE",
    "w": "POSITIVE_VALIDATION",
    "l": "NEGATIVE_DISMISSAL",
    "ratio": "TROLL_MARKER",
    "rent was due": "PASSION_PRAISE",
    "fire": "HIGH_HYPE",
    "serving": "AESTHETIC_PRAISE",
    "slay": "HIGH_PRAISE",
    "mid": "TROLL_CRITICISM",
    "cringe": "TROLL_CRITICISM",
}


def analyze_comment_semiotics(comment_text: str) -> Dict[str, Any]:
    """Evaluates emotional tone, semiotic markers, and creator-culture intent."""
    sanitized = sanitize_untrusted_text(comment_text)
    if sanitized["flags"]:
        store.record_audit_event(
            event_type="UNTRUSTED_COMMUNITY_TEXT_SANITIZED",
            tool_name="analyze_comment_semiotics",
            arguments={"raw_comment": comment_text},
            result={"sanitized_text": sanitized["sanitized_text"], "flags": sanitized["flags"]},
            status="SANITIZED",
            sanitization_flags=sanitized["flags"],
            guard_status="PII_OR_INJECTION_STRIPPED",
        )
    cleaned = sanitized["sanitized_text"].strip()
    lower_text = cleaned.lower()

    detected_slang = [phrase for phrase in SLANG_LEXICON if phrase in lower_text]

    # Compute energy voltage 1-5
    exclamation_count = cleaned.count("!")
    caps_words = len([w for w in cleaned.split() if w.isupper() and len(w) > 1])
    fire_emojis = len(re.findall(r"[🔥✨⚡👑💥❤️😍😭💀]", cleaned))

    energy = 2
    if exclamation_count >= 2 or caps_words >= 2 or fire_emojis >= 2:
        energy += 2
    elif exclamation_count >= 1 or caps_words >= 1 or fire_emojis >= 1:
        energy += 1

    if any(s in ["ate", "fire", "rent was due", "left no crumbs", "slay"] for s in detected_slang):
        energy = max(energy, 4)
    energy = min(5, max(1, energy))

    # Category classification
    if any(k in lower_text for k in ["mid", "cringe", "ratio", "delete video", "unsub", "who asked", "ugly", "slop", "flop"]):
        category = "TROLL_OR_HATER"
        intent = "TROLL_ATTACK"
        mode = "LOW_EFFORT_BAIT"
    elif any(k in lower_text for k in ["jacket", "fit", "outfit", "boots", "sunglasses", "hair", "styling"]):
        category = "FASHION_AESTHETIC"
        intent = "AESTHETIC_FIT_INQUIRY"
        mode = "SUPPORTER"
    elif any(k in lower_text for k in ["footwork", "transition", "count", "routine", "tutorial", "dance", "choreo"]):
        category = "DANCE_CHOREO"
        intent = "CHOREO_TECHNIQUE_INQUIRY"
        mode = "SUPPORTER"
    elif any(k in lower_text for k in ["ate", "left no crumbs", "main character", "perfection", "slayed", "queen"]):
        category = "HYPE"
        intent = "HIGH_ENERGY_PRAISE"
        mode = "SUPPORTER"
    elif any(k in lower_text for k in ["cult leader", "delusional", "you think you're better", "fan fiction"]):
        category = "BANTER"
        intent = "DELUSIONAL_PROJECTION"
        mode = "THEATRICAL_OPENING"
    else:
        category = "BANTER"
        intent = "CREATOR_COMMUNITY_BANTER"
        mode = "JOKE_NON_HATE"

    return {
        "category": category,
        "semiotic_intent": intent,
        "sovereign_mode": mode,
        "energy_level": energy,
        "detected_slang": detected_slang,
    }


def generate_sovereign_reply(
    comment_text: str,
    category: str = "BANTER",
    energy_level: int = 3,
) -> Dict[str, Any]:
    """Generates an unbothered, sovereign 1-sentence creator reply obeying the 4 calibration modes."""
    cat = category.upper()
    lower = comment_text.lower()

    if cat == "TROLL_OR_HATER":
        # Mode 3: Razor-Sharp Sarcasm (Max 10 words, never validate bait)
        if "men used to go to war" in lower:
            reply = "and you're losing one in my comments rn."
        elif "nobody asked" in lower:
            reply = "yet here you are paying rent in the replies."
        else:
            reply = "thanks for the algorithm boost on your way out."
        mode = "Razor-Sharp Sarcasm (LOW_EFFORT_BAIT)"
    elif cat in ["HYPE", "DANCE_CHOREO", "FASHION_AESTHETIC"]:
        # Mode 1: Warm Grace (1-2 sentences, genuine)
        if cat == "DANCE_CHOREO":
            reply = "That transition took 40 studio takes to lock down the count 3 pivot!"
        elif cat == "FASHION_AESTHETIC":
            reply = "Thrifted vintage jacket with customized cargo trousers, thank you!"
        else:
            reply = "This energy means everything, keeping us locked in for the next drop!"
        mode = "Warm Grace (SUPPORTER)"
    elif "cult leader" in lower or "you clearly think" in lower:
        # Mode 4: Theatrical Opening (Detachment Lock, Absurd Escalation, Brevity Cap <= 12 words)
        reply = "dues are due on the 1st btw, don't be late."
        mode = "Deliberately Messy (THEATRICAL_OPENING)"
    else:
        # Mode 2: Join the Joke (Playful, yes-and)
        if "3am" in lower or "sleep" in lower:
            reply = "bold of you to assume i got any sleep at all."
        else:
            reply = "caught us in 4K but the energy was still immaculate."
        mode = "Join the Joke (JOKE_NON_HATE)"

    return {
        "reply_text": reply,
        "sovereign_mode": mode,
        "word_count": len(reply.split()),
        "token_economy": "Pass (1 Sentence)",
    }


def rewrite_comment_reply(
    comment_text: str,
    draft_reply: str,
    failing_criteria: List[str],
    analysis: Dict[str, Any],
) -> str:
    """Targeted rewrite sub-agent for comment reply obeying Decisions rubric feedback."""
    words = draft_reply.strip().split()
    reply = draft_reply

    # 1. Target under_12_words failure
    if "under_12_words" in failing_criteria or len(words) > 12:
        reply = " ".join(words[:10])
        if not reply.endswith((".", "!", "?")):
            reply += "."

    # 2. Target non_defensive_detachment failure
    if "non_defensive_detachment" in failing_criteria:
        if analysis.get("category") == "TROLL_OR_HATER":
            reply = "thanks for the boost on your way out."
        elif "cult leader" in comment_text.lower():
            reply = "dues are due on the 1st btw."
        else:
            reply = "staying unbothered, focused on the next drop."

    # 3. Target grounded_in_context failure
    if "grounded_in_context" in failing_criteria:
        lower_c = comment_text.lower()
        if "jacket" in lower_c or "fit" in lower_c:
            reply = "vintage thrifted pieces with custom styling."
        elif "dance" in lower_c or "transition" in lower_c:
            reply = "took 40 takes to hit that exact count."

    # Brevity safety lock: ensure strictly under 12 words
    final_words = reply.strip().split()
    if len(final_words) > 12:
        reply = " ".join(final_words[:10]) + "."

    return reply


def stage_comment_reply(
    comment_id: str,
    video_id: str,
    author_name: str,
    input_comment: str,
    video_title: str = "Ayo's Den Short",
) -> Dict[str, Any]:
    """Pipelines an inbound comment through semiotics, generates a draft, and stages it for HITL review."""
    # Context Governance: Sanitize untrusted community input before LLM evaluation
    sanitized = sanitize_untrusted_text(input_comment)
    if sanitized["flags"]:
        store.record_audit_event(
            event_type="UNTRUSTED_COMMUNITY_TEXT_SANITIZED",
            tool_name="stage_comment_reply",
            arguments={"comment_id": comment_id, "video_id": video_id, "raw_comment": input_comment},
            result={"sanitized_text": sanitized["sanitized_text"], "flags": sanitized["flags"]},
            status="SANITIZED",
            sanitization_flags=sanitized["flags"],
            guard_status="PII_OR_INJECTION_STRIPPED",
        )
    clean_comment = sanitized["sanitized_text"]

    analysis = analyze_comment_semiotics(clean_comment)
    draft = generate_sovereign_reply(
        comment_text=clean_comment,
        category=analysis["category"],
        energy_level=analysis["energy_level"],
    )

    # Decisions Quality Gate (gemini-decision-1)
    grade = triage_and_grade_comment(
        comment_text=clean_comment,
        draft_reply=draft["reply_text"],
        reddit_context=video_title,
    )

    # Log initial decision event to WebMCP Inspector event stream
    from app.ws_bridge import log_decision_event
    log_decision_event(
        event_type="COMMENT_REPLY_GRADED",
        tool_name="triage_and_grade_comment",
        target_id=comment_id,
        latency_ms=grade.get("latency_ms", 0.0),
        probabilities=grade.get("probabilities", {}),
        confidence=grade.get("confidence", {}),
        passed=grade["passed"],
        failing_criteria=grade.get("failing_criteria", []),
        details={
            "triage_category": grade.get("triage_category", "OTHER"),
            "diagnostic_flags": grade.get("diagnostic_flags", {}),
        },
    )

    final_reply = draft["reply_text"]
    if not grade["passed"]:
        # Self-Correction Routing: One targeted rewrite based on failing rubric criteria
        final_reply = rewrite_comment_reply(
            comment_text=clean_comment,
            draft_reply=draft["reply_text"],
            failing_criteria=grade.get("failing_criteria", []),
            analysis=analysis,
        )
        re_grade = triage_and_grade_comment(
            comment_text=clean_comment,
            draft_reply=final_reply,
            reddit_context=video_title,
        )
        # Log rewritten decision event to WebMCP Inspector event stream
        log_decision_event(
            event_type="COMMENT_REPLY_REWRITTEN_AND_REGRADED",
            tool_name="triage_and_grade_comment",
            target_id=comment_id,
            latency_ms=re_grade.get("latency_ms", 0.0),
            probabilities=re_grade.get("probabilities", {}),
            confidence=re_grade.get("confidence", {}),
            passed=re_grade["passed"],
            failing_criteria=re_grade.get("failing_criteria", []),
            details={"rewritten": True, "final_reply": final_reply},
        )

    triage_cat = grade.get("triage_category")
    mapped_cat = analysis["category"]
    if triage_cat == "LOW_EFFORT_BAIT":
        mapped_cat = "TROLL_OR_HATER"
    elif triage_cat == "THEATRICAL_OPENING":
        mapped_cat = "BANTER"

    payload = {
        "comment_id": comment_id,
        "video_id": video_id,
        "video_title": video_title,
        "author_name": author_name,
        "input_comment": clean_comment,
        "category": mapped_cat,
        "semiotic_intent": analysis["semiotic_intent"],
        "energy_level": analysis["energy_level"],
        "model_draft_reply": final_reply,
    }

    staged = store.add_staged_comment(payload)
    return staged
