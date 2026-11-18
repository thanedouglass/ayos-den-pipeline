"""Unit tests for the 4-agent video production tools."""

from app.tools.video_pipeline_tools import (
    competitor_velocity_auditor,
    distribution_strategist,
    run_autonomous_pipeline,
    script_architect,
    sentiment_indexer,
)


def test_sentiment_indexer():
    res = sentiment_indexer("Detroit show canceled after soundcheck, fans demanding refunds")
    assert res["sparkDetected"] is True
    assert "Fan advocacy" in res["sentiment"]


def test_competitor_velocity_auditor():
    # Below outlier threshold
    res_normal = competitor_velocity_auditor(views=6000, hours=2.0)
    assert res_normal["velocityScore"] == 3000.0
    assert res_normal["outlierHit"] is False

    # Outlier breakout
    res_outlier = competitor_velocity_auditor(views=18000, hours=2.0)
    assert res_outlier["velocityScore"] == 9000.0
    assert res_outlier["outlierHit"] is True


def test_distribution_strategist_schema():
    res = distribution_strategist(
        topic="KATSEYE Detroit tour venue updates",
        sentiment="High engagement",
        template_type="breaking_news",
    )
    assert "viral_title" in res
    assert "description" in res
    assert isinstance(res["tags"], list)
    assert res["strategy_tier"] in ["FEED_FUEL", "SEO_ARTIFACT", "SOVEREIGN_BEACON"]


def test_script_architect():
    res = script_architect("KATSEYE Alert", strategy_tier="FEED_FUEL")
    assert res["hookDuration"] == "3 seconds"
    assert "Fast narrative pivot" in res["pacing"]


def test_run_autonomous_pipeline():
    result = run_autonomous_pipeline(
        source="Reddit_Test",
        raw_text="Megan and Daniela tour perks update",
        competitor_views=16000,
        competitor_hours=2.0,
    )
    assert result["id"] is not None
    assert result["status"] == "Staged"
    assert "agentResults" in result
    assert result["agentResults"]["velocityCheck"]["outlierHit"] is True
