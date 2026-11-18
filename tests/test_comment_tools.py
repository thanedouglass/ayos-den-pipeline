"""Unit tests for comment moderation and sovereign reply tools."""

from app.tools.comment_moderation_tools import (
    analyze_comment_semiotics,
    generate_sovereign_reply,
    stage_comment_reply,
)


def test_analyze_comment_semiotics():
    # Troll detection
    troll_res = analyze_comment_semiotics("Men used to go to war, this is cringe and mid")
    assert troll_res["category"] == "TROLL_OR_HATER"
    assert troll_res["sovereign_mode"] == "LOW_EFFORT_BAIT"

    # Fashion detection
    fashion_res = analyze_comment_semiotics("Where did you get that vintage jacket and cargo pants styling?")
    assert fashion_res["category"] == "FASHION_AESTHETIC"
    assert fashion_res["sovereign_mode"] == "SUPPORTER"

    # Hype detection
    hype_res = analyze_comment_semiotics("YOU ATE AND LEFT NO CRUMBS BESTIE 🔥👑")
    assert hype_res["category"] == "HYPE"
    assert hype_res["energy_level"] >= 4


def test_generate_sovereign_reply_brevity_cap():
    # Low effort bait should be max 10-12 words
    reply = generate_sovereign_reply(
        comment_text="Men used to go to war",
        category="TROLL_OR_HATER",
        energy_level=3,
    )
    assert reply["word_count"] <= 12
    assert "losing one" in reply["reply_text"]


def test_stage_comment_reply():
    staged = stage_comment_reply(
        comment_id="cmt_test_001",
        video_id="M1G92FWmdJw",
        author_name="@tester",
        input_comment="how did you hit that transition at 0:15?!",
    )
    assert staged["comment_id"] == "cmt_test_001"
    assert staged["status"] == "PENDING_APPROVAL"
    assert len(staged["model_draft_reply"].split()) <= 15
