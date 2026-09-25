"""Tool registry: name -> (schema, argument model, handler).

The agent loop only ever calls `ToolRegistry.invoke`, which validates
raw arguments against the tool's Pydantic model before the handler
sees them, so a handler never has to defend against a malformed or
missing field — that failure surfaces as `ToolArgumentError` and is
handled uniformly by the loop.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from jobpilot.agent.tools import (
    FETCH_RESUME_SCHEMA,
    GET_JOB_DETAILS_SCHEMA,
    RECALL_MEMORY_SCHEMA,
    SEARCH_JOBS_SCHEMA,
    AgentToolContext,
    FetchResumeArgs,
    GetJobDetailsArgs,
    RecallMemoryArgs,
    SearchJobsArgs,
    fetch_resume,
    get_job_details,
    recall_memory,
    search_jobs,
)
from jobpilot.errors import ToolArgumentError, UnknownToolError


@dataclass(frozen=True)
class ToolSpec:
    name: str
    schema: dict[str, Any]
    args_model: type[BaseModel]
    handler: Callable[[AgentToolContext, Any], Any]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def schemas(self) -> list[dict[str, Any]]:
        return [spec.schema for spec in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def invoke(self, ctx: AgentToolContext, name: str, raw_arguments: dict[str, Any]) -> Any:
        spec = self._tools.get(name)
        if spec is None:
            raise UnknownToolError(f"no tool registered with name {name!r}")

        try:
            args = spec.args_model.model_validate(raw_arguments)
        except ValidationError as exc:
            raise ToolArgumentError(f"invalid arguments for tool {name!r}: {exc}") from exc

        return spec.handler(ctx, args)


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ToolSpec("search_jobs", SEARCH_JOBS_SCHEMA, SearchJobsArgs, search_jobs))
    registry.register(
        ToolSpec("recall_memory", RECALL_MEMORY_SCHEMA, RecallMemoryArgs, recall_memory)
    )
    registry.register(ToolSpec("fetch_resume", FETCH_RESUME_SCHEMA, FetchResumeArgs, fetch_resume))
    registry.register(
        ToolSpec("get_job_details", GET_JOB_DETAILS_SCHEMA, GetJobDetailsArgs, get_job_details)
    )
    return registry
