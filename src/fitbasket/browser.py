"""Bridge for running FitBasket entirely in the browser with Pyodide.

The web app loads this module in a Web Worker. It keeps one session in memory and
exchanges JSON strings with JavaScript. Saved state lives on the user's device only.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from .agent.agent import FitBasketAgent
from .agent.providers.browser_http import AnthropicBrowserProvider, AzureBrowserProvider, ProviderError
from .agent.providers.offline import OfflineProvider
from .agent.types import Message, message_from_dict, message_to_dict
from .store import UserState

MAX_HISTORY = 40

_state = UserState.demo()
_history: list[Message] = []


def _provider(settings: dict):
    kind = (settings or {}).get("provider", "offline")
    key = (settings or {}).get("api_key", "").strip()
    if kind == "anthropic" and key:
        return AnthropicBrowserProvider(key, settings.get("model") or "claude-sonnet-5-5")
    if kind == "azure" and key and settings.get("endpoint") and settings.get("deployment"):
        return AzureBrowserProvider(
            key, settings["endpoint"], settings["deployment"], settings.get("api_version") or "2024-10-21"
        )
    return OfflineProvider()


def _turns() -> list[dict]:
    """The visible conversation: user messages and the assistant's text replies."""
    out = []
    for m in _history:
        if m.role == "user":
            out.append({"role": "user", "text": m.content})
        elif m.role == "assistant" and m.content and not m.tool_calls:
            out.append({"role": "assistant", "text": m.content})
    return out


def _saved() -> dict:
    return {"state": _state.snapshot(), "history": [message_to_dict(m) for m in _history[-MAX_HISTORY:]]}


def init(saved_json: str | None = None) -> str:
    """Start the session, restoring what was saved on this device if there is anything."""
    global _state, _history
    _state, _history = UserState.demo(), []
    if saved_json:
        try:
            saved = json.loads(saved_json)
            _state = UserState.from_snapshot(saved["state"])
            _history = [message_from_dict(m) for m in saved.get("history", [])]
        except Exception:
            _state, _history = UserState.demo(), []  # corrupt or outdated save: start fresh
    return json.dumps({"state": _state.snapshot(), "turns": _turns()}, default=str)


def reset(blank: bool = False) -> str:
    global _state, _history
    _state, _history = (UserState() if blank else UserState.demo()), []
    return json.dumps({"state": _state.snapshot(), "turns": [], "saved": _saved()}, default=str)


def describe(settings_json: str = "{}") -> str:
    p = _provider(json.loads(settings_json or "{}"))
    return json.dumps({"status": "ok", "provider": p.name, "model": p.model})


async def chat(message: str, settings_json: str = "{}") -> str:
    global _history
    agent = FitBasketAgent(_provider(json.loads(settings_json or "{}")))
    try:
        res = await agent.arun(_state, message, _history)
    except ProviderError as e:
        return json.dumps({"error": str(e)})
    _history = res.history[-MAX_HISTORY:]
    return json.dumps(
        {
            "reply": res.reply,
            "tool_events": [asdict(e) for e in res.tool_events],
            "usage": {"input_tokens": res.usage.input_tokens, "output_tokens": res.usage.output_tokens},
            "est_cost_usd": None,
            "latency_ms": res.latency_ms,
            "flags": res.flags,
            "trace": res.trace,
            "state": _state.snapshot(),
            "saved": _saved(),
        },
        default=str,
    )
