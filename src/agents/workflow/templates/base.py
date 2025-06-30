"""Base utilities for workflow templates"""

from ..config import BUSINESS_RULES


def format_onboarding_tasks_instruction() -> str:
    """Format the onboarding tasks instruction with configurable offsets"""
    offsets = BUSINESS_RULES["onboarding_task_offsets"]
    return (
        f"Create the following Salesforce Tasks: "
        f"1) Subject='Schedule kickoff call' with ActivityDate={offsets['kickoff_call']} days from today, "
        f"2) Subject='Send welcome packet' with ActivityDate={offsets['welcome_packet']} day from today, "
        f"3) Subject='Technical setup' with ActivityDate={offsets['technical_setup']} days from today, "
        f"4) Subject='Training session' with ActivityDate={offsets['training_session']} days from today. "
        "For ALL tasks set: WhatId='{opportunity_id}' (links to Opportunity which auto-populates Account), "
        "Status='Not Started', Priority='Normal'. Use ActivityDate field NOT DueDate. "
        "Use the salesforce_create tool for each task."
    )