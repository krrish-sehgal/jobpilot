"""Progress events emitted while the agent loop runs.

The loop is synchronous and returns only at the end of a turn, which is
too late for a UI that wants to show "Searching remote backend roles"
while it happens. Rather than make the loop async or teach it about
HTTP, it accepts an optional callback and reports what it is doing. The
web layer turns these into server-sent events; the webhook channel simply
passes no callback and behaves exactly as before.

Labels and summaries are produced here, next to the tool definitions they
describe, so the text a user sees changes together with the tools.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

_MAX_LABEL_QUERY_CHARS = 60


@dataclass(frozen=True)
class AgentEvent:
    """One step of progress.

    `kind` is `status`, `tool_call`, or `tool_result`. `data` is the
    JSON-safe payload for the client. `result` carries the raw tool
    return value on `tool_result` so the consumer can pull structured
    artifacts out of it; it is never serialised to the client.
    """

    kind: str
    data: dict[str, Any]
    result: Any = None


EventHook = Callable[[AgentEvent], None]


def describe_tool_call(name: str, arguments: dict[str, Any]) -> str:
    """Human text for "the agent just started this tool"."""

    if name == "search_jobs":
        query = str(arguments.get("query", "")).strip()[:_MAX_LABEL_QUERY_CHARS]
        return f"Searching {query}" if query else "Searching jobs"
    if name == "recall_memory":
        return "Recalling what I know about you"
    if name == "fetch_resume":
        return "Reading your resume"
    if name == "get_job_details":
        return "Looking up the job details"
    if name == "tailor_resume":
        return "Tailoring your resume for this role"
    return f"Running {name}"


def tool_succeeded(result: Any) -> bool:
    """A tool can return normally and still report "nothing happened"."""

    if isinstance(result, dict):
        return result.get("found") is not False and result.get("started") is not False
    return True


def summarize_tool_result(name: str, result: Any) -> str:
    """Human text for "the tool finished"."""

    if name == "search_jobs" and isinstance(result, list):
        if not result:
            return "No matching roles found"
        return f"Found {len(result)} matching role{'s' if len(result) != 1 else ''}"
    if name == "recall_memory" and isinstance(result, list):
        return f"Recalled {len(result)} thing{'s' if len(result) != 1 else ''} about you"
    if name == "fetch_resume" and isinstance(result, dict):
        return "Found your resume" if result.get("found") else "No resume on file"
    if name == "get_job_details" and isinstance(result, dict):
        if result.get("found"):
            return f"Loaded {result.get('title')} at {result.get('company')}"
        return "Could not find that job"
    if name == "tailor_resume" and isinstance(result, dict):
        if result.get("started"):
            return f"Started tailoring for {result.get('job_title')}"
        reasons = {
            "no_resume": "You have not uploaded a resume yet",
            "job_not_found": "Could not find that job",
            "resume_not_ready": "Your resume is still being processed",
        }
        return reasons.get(str(result.get("reason")), "Could not start tailoring")
    return "Done"
