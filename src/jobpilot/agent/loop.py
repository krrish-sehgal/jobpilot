"""The agentic loop: the model picks a tool, the result feeds back in,
and it decides again — until it answers or a turn budget is hit.

The budget exists so a model that gets stuck in a tool-calling cycle
(calling search_jobs with near-identical arguments repeatedly, say)
cannot run indefinitely. `agent_max_turns` bounds the number of
model round-trips; `agent_max_tool_calls_per_turn` bounds how many
tool calls a single model response may request.
"""

from __future__ import annotations

from jobpilot.agent.prompts import AGENT_SYSTEM_PROMPT, REPLY_STYLE_PROMPT
from jobpilot.agent.registry import ToolRegistry
from jobpilot.agent.tools import AgentToolContext
from jobpilot.errors import ToolError, TurnBudgetExceededError
from jobpilot.integrations.llm import LLMClient
from jobpilot.logging import get_logger
from jobpilot.models import AgentTurn, ToolCall

logger = get_logger(__name__)


class AgentLoop:
    def __init__(
        self,
        *,
        llm: LLMClient,
        registry: ToolRegistry,
        max_turns: int = 6,
        max_tool_calls_per_turn: int = 4,
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._max_turns = max_turns
        self._max_tool_calls_per_turn = max_tool_calls_per_turn

    def run(self, ctx: AgentToolContext, user_message: str) -> AgentTurn:
        turn = AgentTurn(conversation_id=ctx.conversation_id, user_message=user_message)
        messages: list[dict[str, str]] = [{"role": "user", "content": user_message}]

        for turn_index in range(1, self._max_turns + 1):
            is_last_turn = turn_index == self._max_turns
            system_prompt = AGENT_SYSTEM_PROMPT
            if is_last_turn:
                system_prompt = f"{AGENT_SYSTEM_PROMPT}\n\n{REPLY_STYLE_PROMPT}\n\nThis is your final turn: you must answer now without requesting another tool call."

            response = self._llm.complete(
                system_prompt=system_prompt,
                messages=messages,
                tools=self._registry.schemas(),
            )

            tool_calls = response.get("tool_calls") or []
            if not tool_calls:
                turn.final_reply = response.get("content") or ""
                turn.turns_used = turn_index
                turn.completed = True
                return turn

            if len(tool_calls) > self._max_tool_calls_per_turn:
                tool_calls = tool_calls[: self._max_tool_calls_per_turn]

            tool_results_text_parts = []
            for raw_call in tool_calls:
                name = raw_call["name"]
                arguments = raw_call.get("arguments", {})
                call_record = ToolCall(name=name, arguments=arguments)
                try:
                    result = self._registry.invoke(ctx, name, arguments)
                    call_record.result = result
                    tool_results_text_parts.append(f"[{name} result]: {result}")
                except ToolError as exc:
                    call_record.error = str(exc)
                    tool_results_text_parts.append(f"[{name} error]: {exc}")
                    logger.warning("tool_call_failed", tool=name, error=str(exc))
                turn.tool_calls.append(call_record)

            messages.append(
                {
                    "role": "assistant",
                    "content": f"(called tools: {[c['name'] for c in tool_calls]})",
                }
            )
            messages.append({"role": "user", "content": "\n".join(tool_results_text_parts)})

        raise TurnBudgetExceededError(
            f"agent loop exceeded max_turns={self._max_turns} without producing a final reply"
        )
