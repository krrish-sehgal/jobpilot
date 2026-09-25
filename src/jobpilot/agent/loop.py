"""
The agent loop.

This is the core idea of an "agentic" chatbot, as opposed to a plain
prompt-and-response bot: the model is given a set of tools and a turn
of conversation, and it decides for itself which tool (if any) to call,
looks at the result, and decides again — until it either has enough
information to answer, or it hits a step limit.

See docs/architecture.md for a diagram of this loop.

This module is a structural stub. It shows the shape of the loop
without calling any real model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from jobpilot.agent.prompts import AGENT_SYSTEM_PROMPT
from jobpilot.agent.tools import TOOL_REGISTRY

MAX_TOOL_STEPS = 4
"""Hard ceiling on tool calls per turn, so a confused agent can't loop
forever waiting on a model that never decides it's done."""


class StepKind(str, Enum):
    TOOL_CALL = "tool_call"
    FINAL_ANSWER = "final_answer"


@dataclass
class AgentStep:
    """One step of the loop: either a tool call the model chose to make,
    or the model's final answer."""

    kind: StepKind
    tool_name: str | None = None
    tool_args: dict[str, Any] = field(default_factory=dict)
    tool_result: Any = None
    answer_text: str | None = None


@dataclass
class AgentTurnResult:
    """Everything that happened while resolving one user turn."""

    steps: list[AgentStep]
    final_answer: str


def decide_next_step(
    conversation_so_far: list[dict[str, str]],
    prior_steps: list[AgentStep],
) -> AgentStep:
    """Ask the model what to do next: call a tool, or answer.

    In a real implementation this sends AGENT_SYSTEM_PROMPT, the
    conversation, and the results of prior_steps to an LLM with tool
    definitions attached, and parses whichever the model chose. This
    demo never actually calls a model — it exists purely to show where
    that call would happen and what it would return.
    """
    raise NotImplementedError("demo only: would call an LLM with tool definitions here")


def run_agent_turn(user_id: str, conversation_so_far: list[dict[str, str]]) -> AgentTurnResult:
    """Run the agent loop for a single turn, up to MAX_TOOL_STEPS tool
    calls, and return the final answer plus the trace of steps taken.

    The real control flow would look like this:

        steps = []
        for _ in range(MAX_TOOL_STEPS):
            step = decide_next_step(conversation_so_far, steps)
            if step.kind == StepKind.FINAL_ANSWER:
                return AgentTurnResult(steps=steps, final_answer=step.answer_text)
            tool_fn = TOOL_REGISTRY[step.tool_name]
            step.tool_result = tool_fn(**step.tool_args)
            steps.append(step)
        # step limit reached without a final answer: fall back to a
        # generic "couldn't find enough" response.

    This demo does not execute that loop since decide_next_step has no
    model behind it. It is left here as the documented shape of the
    control flow described in docs/architecture.md.
    """
    raise NotImplementedError("demo only: see docstring for the intended control flow")


__all__ = [
    "MAX_TOOL_STEPS",
    "StepKind",
    "AgentStep",
    "AgentTurnResult",
    "decide_next_step",
    "run_agent_turn",
    "AGENT_SYSTEM_PROMPT",
    "TOOL_REGISTRY",
]
