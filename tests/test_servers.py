import asyncio

import pytest


def test_mcp_server_exposes_all_tools():
    from fitbasket.mcp_server import build_server
    from fitbasket.tools import TOOLS

    server = build_server()

    async def go():
        tools = await server.list_tools()
        assert {t.name for t in tools} == {t.name for t in TOOLS}
        result = await server.call_tool("create_meal_plan", {"days": 3})
        assert "daily_avg" in str(result)

    asyncio.run(go())


def test_http_api_flow():
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from fitbasket.api import app

    client = TestClient(app)
    assert client.get("/api/health").json()["status"] == "ok"
    sid = client.post("/api/sessions", json={}).json()["session_id"]
    res = client.post(f"/api/sessions/{sid}/chat", json={"message": "Build my weekly shop"}).json()
    assert res["state"]["basket"]["total"] > 0
    assert any(e["name"] == "build_shopping_basket" for e in res["tool_events"])
    assert client.get("/api/sessions/nope").status_code == 404
    bad = client.put(f"/api/sessions/{sid}/pantry", json={"items": {"unicorn": 1}})
    assert bad.status_code == 422
