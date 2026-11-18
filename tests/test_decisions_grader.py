"""Unit and integration tests for the Gemini Decisions API (gemini-decision-1) Quality Gate & Router."""

from unittest.mock import patch, MagicMock
import pytest
from google.genai.decisions import (
    ChoiceAnswer,
    CreateDecisionResponse,
    NoulAnswer,
    ScoreAnswer,
)

from app.store import store
from app.tools.decisions_grader import (
    client,
    grade_short_package,
    triage_and_grade_comment,
)
from app.tools.video_pipeline_tools import run_autonomous_pipeline
from app.tools.comment_moderation_tools import stage_comment_reply


def create_mock_score_answer(score: float, confidence: float = 0.9) -> ScoreAnswer:
    return ScoreAnswer(
        score=score,
        confidence=confidence,
        probabilities={"0": 0.05, "1": 0.10, "2": 0.35, "3": 0.50},
        legend={"0": "Poor", "1": "Fair", "2": "Good", "3": "Excellent"},
        type="score",
    )


def create_mock_noul_answer(noul: float, confidence: float = 0.9) -> NoulAnswer:
    return NoulAnswer(noul=noul, confidence=confidence, type="noul")


def create_mock_choice_answer(choice: str, confidence: float = 0.95) -> ChoiceAnswer:
    return ChoiceAnswer(
        choice=choice,
        confidence=confidence,
        probabilities={choice: confidence, "OTHER": round(1.0 - confidence, 2)},
        type="choice",
    )


def test_grade_short_package_high_scoring_passes():
    """Verify that high-scoring metadata (score >= 2.0 and noul >= 0.80) passes on first try."""
    mock_resp = CreateDecisionResponse(
        answers={
            "hook_strength": create_mock_score_answer(2.8, 0.95),
            "lore_continuity": create_mock_score_answer(2.6, 0.92),
            "fan_advocacy_tone": create_mock_score_answer(2.7, 0.94),
            "is_grounded_in_lore": create_mock_noul_answer(0.92, 0.96),
        }
    )

    with patch.object(client.decisions, "create", return_value=mock_resp) as mock_create:
        res = grade_short_package(
            viral_title="KATSEYE Alert: Venue Shifts Explained 🚨 #Shorts",
            description="Ayo's Den deep dive into tour logistics and fan advocacy.",
            hook="3 seconds | Fast retention pivot",
            lore_context="Topic: KATSEYE tour venue updates.",
        )

        mock_create.assert_called_once()
        assert res["passed"] is True
        assert res["average_score"] == 2.7
        assert res["scores"]["hook_strength"] == 2.8
        assert res["scores"]["lore_continuity"] == 2.6
        assert res["scores"]["fan_advocacy_tone"] == 2.7
        assert res["is_grounded_in_lore"]["noul"] == 0.92
        assert res["confidence"]["hook_strength"] == 0.95
        assert len(res["failing_criteria"]) == 0
        assert "latency_ms" in res


def test_grade_short_package_low_scoring_fails():
    """Verify that low-scoring metadata (score < 2.0) fails and reports failing rubric criteria."""
    mock_resp = CreateDecisionResponse(
        answers={
            "hook_strength": create_mock_score_answer(1.2, 0.85),
            "lore_continuity": create_mock_score_answer(1.5, 0.80),
            "fan_advocacy_tone": create_mock_score_answer(1.8, 0.82),
            "is_grounded_in_lore": create_mock_noul_answer(0.90, 0.90),
        }
    )

    with patch.object(client.decisions, "create", return_value=mock_resp) as mock_create:
        res = grade_short_package(
            viral_title="Boring video title",
            description="Brief text",
            hook="10s slow intro",
            lore_context="Generic topic",
        )

        mock_create.assert_called_once()
        assert res["passed"] is False
        assert res["average_score"] < 2.0
        assert "hook_strength" in res["failing_criteria"]
        assert "lore_continuity" in res["failing_criteria"]
        assert "fan_advocacy_tone" in res["failing_criteria"]


def test_grade_short_package_ungrounded_fails():
    """Verify that ungrounded metadata (noul < 0.80) fails even if rubric scores are high."""
    mock_resp = CreateDecisionResponse(
        answers={
            "hook_strength": create_mock_score_answer(2.9, 0.95),
            "lore_continuity": create_mock_score_answer(2.8, 0.92),
            "fan_advocacy_tone": create_mock_score_answer(2.7, 0.94),
            "is_grounded_in_lore": create_mock_noul_answer(0.65, 0.85),
        }
    )

    with patch.object(client.decisions, "create", return_value=mock_resp) as mock_create:
        res = grade_short_package(
            viral_title="Hallucinated Wild Claims 🚨 #Shorts",
            description="Completely ungrounded rumors.",
            hook="3 seconds hook",
            lore_context="Verified tour report.",
        )

        mock_create.assert_called_once()
        assert res["passed"] is False
        assert "is_grounded_in_lore" in res["failing_criteria"]


def test_triage_and_grade_comment_passes():
    """Verify that triage classification and passing draft reply returns passed: True with diagnostic flags."""
    mock_resp = CreateDecisionResponse(
        answers={
            "comment_triage": create_mock_choice_answer("SUPPORTER", 0.96),
            "under_12_words": create_mock_noul_answer(0.95, 0.94),
            "grounded_in_context": create_mock_noul_answer(0.92, 0.91),
            "non_defensive_detachment": create_mock_noul_answer(0.97, 0.95),
        }
    )

    with patch.object(client.decisions, "create", return_value=mock_resp) as mock_create:
        res = triage_and_grade_comment(
            comment_text="Where did you get that vintage jacket?!",
            draft_reply="Thrifted vintage jacket with customized cargo trousers, thank you!",
            reddit_context="Fashion styling short",
        )

        mock_create.assert_called_once()
        assert res["passed"] is True
        assert res["triage_category"] == "SUPPORTER"
        assert res["flags"]["under_12_words"] is True
        assert res["flags"]["grounded_in_context"] is True
        assert res["flags"]["non_defensive_detachment"] is True
        assert res["diagnostic_flags"]["word_count"] <= 12
        assert len(res["failing_criteria"]) == 0
        assert "latency_ms" in res


def test_triage_and_grade_comment_fails_and_diagnostics():
    """Verify that failing brevity or defensive replies are flagged with diagnostic flags."""
    mock_resp = CreateDecisionResponse(
        answers={
            "comment_triage": create_mock_choice_answer("LOW_EFFORT_BAIT", 0.93),
            "under_12_words": create_mock_noul_answer(0.40, 0.88),
            "grounded_in_context": create_mock_noul_answer(0.85, 0.89),
            "non_defensive_detachment": create_mock_noul_answer(0.30, 0.90),
        }
    )

    with patch.object(client.decisions, "create", return_value=mock_resp) as mock_create:
        res = triage_and_grade_comment(
            comment_text="Men used to go to war, this is cringe and mid",
            draft_reply="Why are you so angry at me? I worked really hard on this video and you have no right to judge my content like that!",
            reddit_context="Ayo's Den Short",
        )

        mock_create.assert_called_once()
        assert res["passed"] is False
        assert res["triage_category"] == "LOW_EFFORT_BAIT"
        assert res["flags"]["under_12_words"] is False
        assert res["flags"]["non_defensive_detachment"] is False
        assert "under_12_words" in res["failing_criteria"]
        assert "non_defensive_detachment" in res["failing_criteria"]


def test_pipeline_high_scoring_passes_first_try():
    """Verify that high-scoring metadata passes quality gate without triggering rewrite."""
    resp_pass = CreateDecisionResponse(
        answers={
            "hook_strength": create_mock_score_answer(2.8, 0.95),
            "lore_continuity": create_mock_score_answer(2.7, 0.92),
            "fan_advocacy_tone": create_mock_score_answer(2.9, 0.96),
            "is_grounded_in_lore": create_mock_noul_answer(0.95, 0.95),
        }
    )

    with patch.object(client.decisions, "create", return_value=resp_pass) as mock_create:
        result = run_autonomous_pipeline(
            source="Reddit_High_Score_Test",
            raw_text="KATSEYE Detroit show venue shifts and fan advocacy",
            competitor_views=16000,
            competitor_hours=2.0,
        )

        assert mock_create.call_count == 1
        assert result["status"] == "Staged"
        gate = result["agentResults"]["decisions_gate"]
        assert gate["passed"] is True
        assert gate["rewritten"] is False
        assert gate["initial_grade"]["passed"] is True


def test_pipeline_low_scoring_triggers_rewrite():
    """Verify that low-scoring metadata (score < 2.0) triggers the rewrite sub-agent path."""
    resp_fail = CreateDecisionResponse(
        answers={
            "hook_strength": create_mock_score_answer(1.1, 0.85),
            "lore_continuity": create_mock_score_answer(1.4, 0.80),
            "fan_advocacy_tone": create_mock_score_answer(1.3, 0.82),
            "is_grounded_in_lore": create_mock_noul_answer(0.85, 0.90),
        }
    )
    resp_pass = CreateDecisionResponse(
        answers={
            "hook_strength": create_mock_score_answer(2.9, 0.95),
            "lore_continuity": create_mock_score_answer(2.8, 0.94),
            "fan_advocacy_tone": create_mock_score_answer(2.7, 0.93),
            "is_grounded_in_lore": create_mock_noul_answer(0.95, 0.96),
        }
    )

    with patch.object(client.decisions, "create", side_effect=[resp_fail, resp_pass]) as mock_create:
        result = run_autonomous_pipeline(
            source="Reddit_Rewrite_Test",
            raw_text="KATSEYE Detroit show canceled after soundcheck",
            competitor_views=18000,
            competitor_hours=2.0,
        )

        # Verified: exactly 2 calls (initial check -> rewrite -> regrade)
        assert mock_create.call_count == 2
        assert result["status"] == "Staged"
        gate = result["agentResults"]["decisions_gate"]
        assert gate["rewritten"] is True
        assert gate["initial_grade"]["passed"] is False
        assert "hook_strength" in gate["failing_criteria"]
        assert gate["final_grade"]["passed"] is True
        # Verify targeted rewrite improved title and hook
        assert "BREAKING" in result["metadata"]["viral_title"]
        assert result["script"]["hookDuration"] == "2 seconds"


def test_comment_moderation_triggers_rewrite_on_failure():
    """Verify that an ungrounded or non-detached reply triggers the rewrite sub-agent."""
    resp_fail = CreateDecisionResponse(
        answers={
            "comment_triage": create_mock_choice_answer("LOW_EFFORT_BAIT", 0.95),
            "under_12_words": create_mock_noul_answer(0.92, 0.90),
            "grounded_in_context": create_mock_noul_answer(0.90, 0.89),
            "non_defensive_detachment": create_mock_noul_answer(0.35, 0.88),  # Fails detachment!
        }
    )
    resp_pass = CreateDecisionResponse(
        answers={
            "comment_triage": create_mock_choice_answer("LOW_EFFORT_BAIT", 0.95),
            "under_12_words": create_mock_noul_answer(0.96, 0.95),
            "grounded_in_context": create_mock_noul_answer(0.93, 0.91),
            "non_defensive_detachment": create_mock_noul_answer(0.95, 0.94),
        }
    )

    with patch.object(client.decisions, "create", side_effect=[resp_fail, resp_pass]) as mock_create:
        staged = stage_comment_reply(
            comment_id="cmt_rewrite_test",
            video_id="M1G92FWmdJw",
            author_name="@troll_user",
            input_comment="mid and cringe ratio",
        )

        assert mock_create.call_count == 2
        assert staged["status"] == "PENDING_APPROVAL"
        # Verify sovereign rewrite was applied
        assert len(staged["model_draft_reply"].split()) <= 12
        assert "boost on your way out" in staged["model_draft_reply"]
