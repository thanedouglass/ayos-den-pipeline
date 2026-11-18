"""Tool registry for the Unified Ayo's Den & IoChat Google ADK Agent."""

from app.tools.video_pipeline_tools import (
    competitor_velocity_auditor,
    distribution_strategist,
    run_autonomous_pipeline,
    script_architect,
    sentiment_indexer,
)
from app.tools.comment_moderation_tools import (
    analyze_comment_semiotics,
    generate_sovereign_reply,
    stage_comment_reply,
)
from app.tools.decisions_grader import (
    grade_short_package,
    triage_and_grade_comment,
)
from app.tools.youtube_tools import (
    poll_video_comments,
    post_comment_reply,
    publish_video_metadata,
    sync_youtube_studio_drafts,
)

ALL_ADK_TOOLS = [
    sentiment_indexer,
    competitor_velocity_auditor,
    distribution_strategist,
    script_architect,
    run_autonomous_pipeline,
    analyze_comment_semiotics,
    generate_sovereign_reply,
    stage_comment_reply,
    grade_short_package,
    triage_and_grade_comment,
    poll_video_comments,
    sync_youtube_studio_drafts,
    publish_video_metadata,
    post_comment_reply,
]
