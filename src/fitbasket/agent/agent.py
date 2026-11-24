"""The agent loop: model -> tool calls -> tool results -> model, with limits and tracing."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from ..store import UserState, reference_data
from ..tools import TOOLS, TOOLS_BY_NAME, Tool, ToolError
from .guardrails import check_input
from .prompts import SYSTEM_PROMPT
from .providers.base import LLMProvider, get_provider
from .tracing import Trace
from .types import Message, ToolSpec, Usage

MAX_STEPS = 6  # model calls per user turn
MAX_TOOL_CALLS = 12  # tool calls per user turn
MAX_TOOL_RESULT_CHARS = 6000


@dataclass
class ToolEvent:
    name: str
    arguments: dict
    ok: bool
    duration_ms: float
    error: str | None = None


@dataclass
class AgentResult:
    reply: str
    history: list[Message]
    tool_events: list[ToolEvent] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    latency_ms: float = 0.0
    flags: list[str] = field(default_factory=list)
    trace: dict = field(default_factory=dict)
    model: str = ""

    @property
    def est_cost_usd(self) -> float | None:
        """Cost estimate from FITBASKET_PRICE_IN/OUT (USD per million tokens), if configured."""
        try:
            p_in = float(os.environ["FITBASKET_PRICE_IN"])
            p_out = float(os.environ["FITBASKET_PRICE_OUT"])
        except (KeyError, ValueError):
            return None
        return round((self.usage.input_tokens * p_in + self.usage.output_tokens * p_out) / 1e6, 6)


class FitBasketAgent:
    def __init__(self, provider: LLMProvider | None = None, tools: list[Tool] | None = None):
        self.provider = provider or get_provider()
        self.tools = tools or TOOLS
        self._by_name = {t.name: t for t in self.tools} if tools else TOOLS_BY_NAME
        self._specs = [ToolSpec(t.name, t.description, t.json_schema()) for t in self.tools]

    def run(self, state: UserState, user_message: str, history: list[Message] | None = None) -> AgentResult:
        trace = Trace()
        history = list(history or [])
        ref = reference_data()

        with trace.span("input_guardrail", "guardrail") as s:
            guard = check_input(user_message)
            s.attributes["flags"] = guard.flags
        history.append(Message("user", user_message))
        if not guard.allowed:
            history.append(Message("assistant", guard.response or ""))
            return self._finish(
                trace, AgentResult(guard.response or "", history, flags=guard.flags, model=self.provider.model)
            )

        result = AgentResult("", history, flags=list(guard.flags), model=self.provider.model)
        tool_calls_used = 0
        for step in range(MAX_STEPS):
            with trace.span("llm", "llm", step=step, model=self.provider.model) as s:
                resp = self.provider.complete(SYSTEM_PROMPT, history, self._specs)
                s.attributes.update(
                    input_tokens=resp.usage.input_tokens,
                    output_tokens=resp.usage.output_tokens,
                    tool_calls=[c.name for c in resp.tool_calls],
                )
            result.usage += resp.usage
            history.append(Message("assistant", resp.text, tool_calls=resp.tool_calls))
            if not resp.tool_calls:
                result.reply = resp.text
                break

            for call in resp.tool_calls:
                tool_calls_used += 1
                if tool_calls_used > MAX_TOOL_CALLS:
                    content, ok, err = "Tool call limit reached for this turn. Summarise what you have.", False, None
                else:
                    content, ok, err = self._execute(call.name, call.arguments, state, ref, trace, result)
                history.append(Message("tool", content, tool_call_id=call.id, name=call.name, is_error=not ok))
        else:
            result.flags.append("max_steps_reached")
            result.reply = (
                "I've done as much as I can in one go. Here's where things are up to; "
                "ask me to continue if you need more."
            )
            history.append(Message("assistant", result.reply))

        return self._finish(trace, result)

    def _execute(self, name, arguments, state, ref, trace, result) -> tuple[str, bool, str | None]:
        tool = self._by_name.get(name)
        with trace.span(name, "tool", arguments=arguments) as s:
            try:
                if tool is None:
                    raise ToolError(f"Unknown tool '{name}'. Available: {', '.join(self._by_name)}")
                output = tool.run(state, arguments, ref)
                content, ok, err = json.dumps(output, default=str)[:MAX_TOOL_RESULT_CHARS], True, None
            except ToolError as e:
                content, ok, err = f"Error: {e}", False, str(e)
                s.error = err
            except Exception as e:  # unexpected bug: don't leak internals to the model
                content, ok, err = "Error: the tool failed unexpectedly. Try a different approach.", False, repr(e)
                s.error = err
        result.tool_events.append(ToolEvent(name, arguments, ok, s.duration_ms, err))
        return content, ok, err

    @staticmethod
    def _finish(trace: Trace, result: AgentResult) -> AgentResult:
        result.latency_ms = trace.duration_ms
        result.trace = trace.to_dict()
        trace.export(
            {
                "model": result.model,
                "flags": result.flags,
                "usage": {"input": result.usage.input_tokens, "output": result.usage.output_tokens},
            }
        )
        return result
