"""Video Production Pipeline Tools: 4-Agent Autonomous Graph for Ayo's Den."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from app.guards import sanitize_untrusted_text
from app.store import store
from app.tools.decisions_grader import grade_short_package


# Load skills schema dynamically
def get_metadata_skill_schema() -> Dict[str, Any]:
    schema_path = Path("skills/youtube-metadata-generator.json")
    if schema_path.exists():
        try:
            return json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "title": "YouTubeMetadataPayload",
        "strategy_tiers": ["FEED_FUEL", "SEO_ARTIFACT", "SOVEREIGN_BEACON"],
    }


def sentiment_indexer(raw_text: str) -> Dict[str, Any]:
    """Agent 1: Cultural & Sentiment Indexer.
    
    Audits emotional heat, discourse friction, and cultural sparks from raw chatter.
    """
    cleaned = raw_text.strip()
    is_hot = any(term in cleaned.lower() for term in ["canceled", "refund", "outrage", "dispute", "broke", "urgent", "breaking", "lawsuit"])
    spark_detected = is_hot or len(cleaned) > 20

    sentiment_desc = (
        "High engagement / Fan advocacy friction"
        if is_hot
        else "Moderate cultural discourse / Trend propagation"
    )

    return {
        "agent": "Agent 1: Cultural & Sentiment Indexer",
        "sentiment": sentiment_desc,
        "sparkDetected": spark_detected,
        "emotional_voltage": 4 if is_hot else 2,
    }


def competitor_velocity_auditor(views: int = 15000, hours: float = 2.0) -> Dict[str, Any]:
    """Agent 4: Competitor Intelligence & Velocity Auditor.
    
    Computes velocity score (views/hour) to detect breakout competitor outliers.
    """
    safe_hours = max(0.1, hours)
    velocity = round(views / safe_hours, 2)
    is_outlier = velocity > 5000.0

    return {
        "agent": "Agent 4: Competitor Intelligence & Velocity Auditor",
        "velocityScore": velocity,
        "outlierHit": is_outlier,
        "benchmark": "5000 views/hour threshold",
    }


def distribution_strategist(
    topic: str,
    sentiment: str = "High engagement",
    template_type: str = "breaking_news",
) -> Dict[str, Any]:
    """Agent 2: Distribution Strategist.
    
    Constructs double-layer titles, SEO descriptions, and tags conforming strictly to YouTubeMetadataPayload.
    """
    schema = get_metadata_skill_schema()
    tier = "FEED_FUEL" if template_type in ["breaking_news", "viral_short"] else "SEO_ARTIFACT"

    # Enforce title syntax matching Ayo's Den channel format
    if "katseye" in topic.lower():
        viral_title = f"KATSEYE Alert: {topic[:45]} 🚨 #Shorts"
        description = (
            f"Context breakdown: {topic}\n\n"
            "When management leaves a vacuum of answers, the narrative gets left in the audience's hands. "
            "Ayo's Den breakdown of venue shifts and community advocacy.\n\n"
            "#KATSEYE #EYEKONS #Shorts"
        )
        tags = ["KATSEYE", "HxG", "EYEKONS", "tour update", "Ayo's Den", "YouTube Shorts"]
    else:
        viral_title = f"{topic[:55]} | Full Story Explained 🚨 #Shorts"
        description = (
            f"Deep dive into the latest subculture trends: {topic}.\n\n"
            "Produced autonomously via the Ayo's Den Studio Pipeline.\n\n"
            "#AyosDen #Trends #Shorts"
        )
        tags = ["Ayo's Den", "trending shorts", "pop culture", "subculture update", "YouTube Shorts"]

    return {
        "agent": "Agent 2: Distribution Strategist",
        "schema_applied": schema.get("title", "YouTubeMetadataPayload"),
        "viral_title": viral_title,
        "title": viral_title,
        "description": description,
        "tags": tags,
        "strategy_tier": tier,
    }


def script_architect(viral_title: str, strategy_tier: str = "FEED_FUEL") -> Dict[str, Any]:
    """Agent 3: Script & Transmission Architect.
    
    Compiles high-retention Short hook durations and narrative pacing directives.
    """
    hook_duration = "3 seconds" if strategy_tier == "FEED_FUEL" else "5 seconds"
    pacing = (
        "Fast narrative pivot from breaking headline to community advocacy stakes"
        if strategy_tier == "FEED_FUEL"
        else "Structured investigative breakdown with timestamp citations"
    )

    return {
        "agent": "Agent 3: Script & Transmission Architect",
        "hookDuration": hook_duration,
        "pacing": pacing,
        "targetLength": "45-60s Short",
        "retention_checkpoint": "0:03 cold open hook lock",
    }


def rewrite_short_package(
    metadata: Dict[str, Any],
    script: Dict[str, Any],
    failing_criteria: List[str],
    raw_text: str,
    lore_context: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Self-correction generator sub-agent: executes targeted rewrite based on failing rubric criteria."""
    rewritten_meta = dict(metadata)
    rewritten_script = dict(script)

    viral_title = metadata.get("viral_title", "")
    description = metadata.get("description", "")
    hook_duration = script.get("hookDuration", "3 seconds")
    pacing = script.get("pacing", "High retention pivot")

    # 1. Target hook_strength failure
    if "hook_strength" in failing_criteria or "average_score" in failing_criteria:
        if "katseye" in raw_text.lower():
            viral_title = f"KATSEYE BREAKING: {raw_text[:38]}... The Real Reason Why 🚨 #Shorts"
        else:
            viral_title = f"EXCLUSIVE: {raw_text[:45]} | The Real Story 🚨 #Shorts"
        hook_duration = "2 seconds"
        pacing = "Aggressive 0:02 high-voltage shock hook locking in 100% viewer retention before fast narrative pivot"

    # 2. Target lore_continuity or grounding failure
    if "lore_continuity" in failing_criteria or "is_grounded_in_lore" in failing_criteria:
        lore_prefix = (
            "Ayo's Den Exclusive Dossier: Situating today's developments within our ongoing channel narrative. "
            f"Ground-truth context: {raw_text}.\n\n"
        )
        if not description.startswith("Ayo's Den Exclusive Dossier:"):
            description = lore_prefix + description

    # 3. Target fan_advocacy_tone failure
    if "fan_advocacy_tone" in failing_criteria:
        advocacy_block = (
            "\n\nSOVEREIGN ADVOCACY PERSPECTIVE: When management creates an information vacuum, "
            "the audience deserves unfiltered accountability and transparency."
        )
        if "SOVEREIGN ADVOCACY" not in description:
            description += advocacy_block

    rewritten_meta["viral_title"] = viral_title
    rewritten_meta["title"] = viral_title
    rewritten_meta["description"] = description
    rewritten_script["hookDuration"] = hook_duration
    rewritten_script["pacing"] = pacing

    return rewritten_meta, rewritten_script


def run_autonomous_pipeline(
    source: str = "Reddit_r_KATSEYE",
    raw_text: str = "Detroit show canceled after soundcheck, fans demanding answers and refunds",
    competitor_views: int = 15000,
    competitor_hours: float = 2.0,
) -> Dict[str, Any]:
    """Executes the full 4-agent cycle with self-healing reflection and commits payload to WebMcpStore."""
    item_id = int(time.time() * 1000)

    # Context Governance: Sanitize untrusted input from Reddit/external feeds
    sanitized = sanitize_untrusted_text(raw_text)
    if sanitized["flags"]:
        store.record_audit_event(
            event_type="UNTRUSTED_COMMUNITY_TEXT_SANITIZED",
            tool_name="run_autonomous_pipeline",
            arguments={"source": source, "raw_text": raw_text},
            result={"sanitized_text": sanitized["sanitized_text"], "flags": sanitized["flags"]},
            status="SANITIZED",
            sanitization_flags=sanitized["flags"],
            guard_status="PII_OR_INJECTION_STRIPPED",
        )
    raw_text = sanitized["sanitized_text"]

    # Step 1: Sentiment Indexing
    sentiment = sentiment_indexer(raw_text)

    # Step 2: Competitor Velocity Check
    velocity_check = competitor_velocity_auditor(competitor_views, competitor_hours)

    # Step 3: Distribution Strategy & Metadata Payload
    metadata = distribution_strategist(raw_text, sentiment=sentiment["sentiment"], template_type="breaking_news")

    # Step 4: Script Architecture
    script = script_architect(metadata["viral_title"], strategy_tier=metadata["strategy_tier"])

    # Step 5: Gemini Decisions API Quality Gate (gemini-decision-1)
    lore_context = (
        f"Channel: Ayo's Den. Source: {source}. Topic: {raw_text}. "
        f"Ongoing Narrative: Community advocacy, venue shifts, and management accountability."
    )
    hook_str = f"{script.get('hookDuration', '3 seconds')} | {script.get('pacing', '')}"

    grade = grade_short_package(
        viral_title=metadata["viral_title"],
        description=metadata["description"],
        hook=hook_str,
        lore_context=lore_context,
    )

    # Log initial decision event to WebMCP Inspector event stream
    from app.ws_bridge import log_decision_event
    log_decision_event(
        event_type="SHORT_PACKAGE_GRADED",
        tool_name="grade_short_package",
        target_id=item_id,
        latency_ms=grade.get("latency_ms", 0.0),
        probabilities=grade.get("probabilities", {}),
        confidence=grade.get("confidence", {}),
        passed=grade["passed"],
        failing_criteria=grade.get("failing_criteria", []),
        details={"scores": grade.get("scores", {}), "average_score": grade.get("average_score", 0.0)},
    )

    rewritten = False
    final_grade = grade
    if not grade["passed"]:
        # Self-Correction Routing: Pass failing rubric criteria back for targeted rewrite
        metadata, script = rewrite_short_package(
            metadata=metadata,
            script=script,
            failing_criteria=grade.get("failing_criteria", []),
            raw_text=raw_text,
            lore_context=lore_context,
        )
        rewritten = True
        hook_str_rewritten = f"{script.get('hookDuration', '2 seconds')} | {script.get('pacing', '')}"
        final_grade = grade_short_package(
            viral_title=metadata["viral_title"],
            description=metadata["description"],
            hook=hook_str_rewritten,
            lore_context=lore_context,
        )
        # Log self-corrected decision event to WebMCP Inspector event stream
        log_decision_event(
            event_type="SHORT_PACKAGE_REWRITTEN_AND_REGRADED",
            tool_name="grade_short_package",
            target_id=item_id,
            latency_ms=final_grade.get("latency_ms", 0.0),
            probabilities=final_grade.get("probabilities", {}),
            confidence=final_grade.get("confidence", {}),
            passed=final_grade["passed"],
            failing_criteria=final_grade.get("failing_criteria", []),
            details={"rewritten": True, "scores": final_grade.get("scores", {})},
        )

    payload = {
        "id": item_id,
        "ingestionSource": source,
        "rawInput": raw_text,
        "metadata": metadata,
        "script": script,
        "agentResults": {
            "sentiment": sentiment,
            "velocityCheck": velocity_check,
            "metadata": metadata,
            "script": script,
            "decisions_gate": {
                "initial_grade": grade,
                "rewritten": rewritten,
                "failing_criteria": grade.get("failing_criteria", []),
                "final_grade": final_grade,
                "passed": final_grade["passed"],
            },
        },
        "status": "Staged",
    }

    # Commit to store & queue.json
    saved_record = store.add_staged_metadata(payload)
    return saved_record
