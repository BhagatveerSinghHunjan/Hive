"""Tool schemas/handlers that expose club-ops workflows to the Leader."""

from __future__ import annotations

from hive.workflows.club_ops import WORKFLOWS


WORKFLOW_TOOLS = {
    "workflow_triage_inbox": {
        "description": (
            "Triage unread club email into categories (venue, sponsor, volunteer, "
            "meeting, urgent), rank priority, and propose drafts/follow-up tasks. "
            "Read-only by default. Use this for 'what needs my attention' requests."
        ),
        "parameters": {
            "query": {"type": "string", "description": "Gmail query (default: unread last 7 days)"},
            "max_results": {"type": "integer", "description": "Maximum messages (default 20)"},
            "create_tasks": {"type": "boolean", "description": "Create local follow-up tasks (default false)"},
        },
        "required": [],
    },
    "workflow_prepare_meeting": {
        "description": (
            "Build a meeting briefing: event details, related email, open questions, "
            "and a suggested agenda. Read-only. Use before a meeting or when the user "
            "asks what they need to know for an upcoming event."
        ),
        "parameters": {
            "event_query": {"type": "string", "description": "Title/location fragment to match (optional)"},
            "days": {"type": "integer", "description": "Calendar window in days (default 7)"},
            "max_emails": {"type": "integer", "description": "Related emails to include (default 5)"},
        },
        "required": [],
    },
    "workflow_post_meeting_followup": {
        "description": (
            "Turn meeting notes into action-item tasks and a recap email draft for "
            "attendees. Creates local tasks; the recap is returned as a draft action "
            "that still needs human approval before sending."
        ),
        "parameters": {
            "meeting_title": {"type": "string", "description": "Meeting title"},
            "notes": {"type": "string", "description": "Raw notes/decisions, one per line"},
            "attendees": {"type": "string", "description": "Comma-separated recap emails"},
            "due": {"type": "string", "description": "Follow-up due date (YYYY-MM-DD)"},
            "create_tasks": {"type": "boolean", "description": "Create local tasks (default true)"},
        },
        "required": ["meeting_title"],
    },
    "workflow_sponsor_reminders": {
        "description": (
            "Find sponsorship threads and prepare reminder drafts plus follow-up tasks. "
            "Never sends; drafts require approval."
        ),
        "parameters": {
            "days": {"type": "integer", "description": "Lookback window in days (default 30)"},
            "create_tasks": {"type": "boolean", "description": "Create local tasks (default false)"},
        },
        "required": [],
    },
    "workflow_volunteer_schedule": {
        "description": (
            "Propose volunteer shifts using free calendar slots and draft the ask "
            "email to volunteers. Read-only plus draft actions."
        ),
        "parameters": {
            "event_title": {"type": "string", "description": "Event to staff"},
            "volunteers": {"type": "string", "description": "Comma-separated volunteer emails"},
            "duration_minutes": {"type": "integer", "description": "Shift length (default 60)"},
            "days": {"type": "integer", "description": "Scheduling window in days (default 7)"},
        },
        "required": ["event_title"],
    },
    "workflow_venue_confirmation": {
        "description": (
            "Summarize venue threads and draft a confirmation email. Use when the "
            "goal is to get the venue confirmed."
        ),
        "parameters": {
            "venue_email": {"type": "string", "description": "Venue contact (optional)"},
            "event_title": {"type": "string", "description": "Event name (optional)"},
            "days": {"type": "integer", "description": "Lookback window in days (default 21)"},
        },
        "required": [],
    },
    "workflow_daily_brief": {
        "description": (
            "Morning brief: today's agenda, unread email count, tasks due soon, and "
            "connectors needing attention. Read-only."
        ),
        "parameters": {
            "days": {"type": "integer", "description": "Agenda window in days (default 1)"},
        },
        "required": [],
    },
}


WORKFLOW_TOOLS.update({
    "mission_list": {
        "description": (
            "List available missions (named, parameterized workflows such as "
            "morning_brief, inbox_triage, meeting_prep, sponsor_followups)."
        ),
        "parameters": {},
        "required": [],
    },
    "mission_run": {
        "description": (
            "Run a mission by name with optional parameters. Missions return a "
            "brief plus next_actions; outbound actions still require approval."
        ),
        "parameters": {
            "name": {"type": "string", "description": "Mission name"},
            "params": {"type": "object", "description": "Mission parameters (key/value)"},
        },
        "required": ["name"],
    },
})


async def run_workflow_tool(tool_name: str, **kwargs) -> dict:
    if tool_name == "mission_list":
        from hive.missions import list_missions

        return list_missions()
    if tool_name == "mission_run":
        from hive.missions import run_mission

        params = kwargs.get("params") or {}
        if isinstance(params, str):
            import json

            try:
                params = json.loads(params)
            except json.JSONDecodeError:
                params = {}
        return await run_mission(kwargs.get("name", ""), params)

    workflow_name = tool_name.removeprefix("workflow_")
    workflow = WORKFLOWS.get(workflow_name)
    if workflow is None:
        return {"error": f"Unknown workflow tool: {tool_name}"}
    return await workflow(**kwargs)
