"""The in-browser bridge, exercised in CPython (Pyodide runs the same code)."""

import asyncio
import json

import pytest

from fitbasket import browser
from fitbasket.agent.agent import FitBasketAgent
from fitbasket.agent.providers.browser_http import AnthropicBrowserProvider, AzureBrowserProvider, ProviderError
from fitbasket.agent.types import Message
from fitbasket.store import UserState


def test_chat_then_restore_from_save():
    browser.init(None)
    out = json.loads(asyncio.run(browser.chat("I'm allergic to fish. Build my weekly shop", "{}")))
    assert out["state"]["basket"]["total"] > 0
    saved = json.dumps(out["saved"])

    restored = json.loads(browser.init(saved))
    assert restored["state"]["profile"]["allergies"] == ["fish"]
    assert restored["state"]["basket"]["total"] == out["state"]["basket"]["total"]
    assert [t["role"] for t in restored["turns"]] == ["user", "assistant"]


def test_corrupt_save_starts_fresh():
    out = json.loads(browser.init('{"state": {"profile": {"age": "old"}}}'))
    assert out["state"]["profile"]["name"] == "Alex" and out["turns"] == []


def test_snapshot_round_trip(state, ref):
    from fitbasket.domain.basket import build_basket
    from fitbasket.domain.meals import plan_meals

    state.meal_plan = plan_meals(state, ref)
    state.basket = build_basket(state, ref)
    again = UserState.from_snapshot(json.loads(json.dumps(state.snapshot())))
    assert again.snapshot() == state.snapshot()


def fake_fetch(status, payload, seen):
    async def _fetch(url, headers, body):
        seen.update(url=url, headers=headers, body=body)
        return status, payload

    return _fetch


def test_anthropic_browser_provider_runs_the_loop(state):
    replies = [
        {"content": [{"type": "tool_use", "id": "t1", "name": "create_meal_plan", "input": {}}], "usage": {}},
        {"content": [{"type": "text", "text": "Planned."}], "usage": {"input_tokens": 5, "output_tokens": 2}},
    ]
    seen = {}

    async def _fetch(url, headers, body):
        seen.update(headers=headers, body=body)
        return 200, replies.pop(0)

    agent = FitBasketAgent(AnthropicBrowserProvider("sk-test", "claude-x", fetch_json=_fetch))
    res = asyncio.run(agent.arun(state, "plan my week"))
    assert res.reply == "Planned." and state.meal_plan is not None
    assert seen["headers"]["anthropic-dangerous-direct-browser-access"] == "true"
    assert seen["body"]["messages"][-1]["content"][0]["type"] == "tool_result"


def test_azure_browser_provider_parses_tool_calls():
    call = {"id": "c", "function": {"name": "get_profile", "arguments": "{}"}}
    payload = {
        "choices": [{"message": {"content": None, "tool_calls": [call]}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 1},
    }
    seen = {}
    p = AzureBrowserProvider("k", "https://x.openai.azure.com/", "gpt", fetch_json=fake_fetch(200, payload, seen))
    out = asyncio.run(p.acomplete("sys", [Message("user", "hi")], []))
    assert out.tool_calls[0].name == "get_profile"
    assert seen["url"].startswith("https://x.openai.azure.com/openai/deployments/gpt/chat/completions")


def test_bad_key_is_a_friendly_error():
    p = AnthropicBrowserProvider("bad", fetch_json=fake_fetch(401, {"error": {"message": "invalid x-api-key"}}, {}))
    with pytest.raises(ProviderError, match="Settings"):
        asyncio.run(p.acomplete("sys", [Message("user", "hi")], []))


def test_chat_reads_the_food_log_sent_by_the_phone():
    browser.init(None)
    log = [{"name": "Protein bar", "grams": 60, "kcal": 210, "protein_g": 20, "carbs_g": 22, "fat_g": 7}]
    out = json.loads(asyncio.run(browser.chat("How much protein have I got left today?", "{}", json.dumps(log))))
    assert "get_todays_intake" in [e["name"] for e in out["tool_events"]]
    assert "20 g protein" in out["reply"]
    assert out["state"]["targets"]["protein_g"] > 0


def test_bad_food_log_is_ignored():
    browser.init(None)
    out = json.loads(asyncio.run(browser.chat("what have I eaten today", "{}", '[{"name": 5}]')))
    assert "Nothing logged" in out["reply"]
