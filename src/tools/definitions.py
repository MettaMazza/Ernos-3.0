"""
Standard Tool Definitions for Ernos 3.0.
Refactored into submodules.
"""
# Import from submodules to maintain backward compatibility for direct imports
import os
import json
import datetime
from pathlib import Path
from src.tools.registry import ToolRegistry

from .filesystem import read_file_page, search_codebase
from .web import search_web, browse_site, check_world_news, start_deep_research
from .memory import (
    add_reaction, 
    recall_user, 
    review_my_reasoning,
    search_context_logs,
    publish_to_bridge,
    read_public_bridge,
    evaluate_advice
)
from .memory import manage_goals  # sync wrapper for backward compat
from .coding import create_program, manage_project

# P1-P4: New tool modules
from . import task_tracker        # plan_task, complete_step, skip_step, get_task_status
from . import planning_tools      # draft_plan, get_plan
from . import verification_tools  # verify_files, verify_syntax

# Weekly quota & review pipeline
from . import weekly_quota        # get_quota_status, assign_dev_task, complete_dev_task, stage_for_review, get_feedback_report
from . import review_pipeline     # get_review_queue, approve_review, reject_review
