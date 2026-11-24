"""HTTP API for the web UI.

uvicorn fitbasket.api:app --reload
"""

from __future__ import annotations

import os
import threading
import uuid
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from .agent.agent import FitBasketAgent
from .agent.providers.base import get_provider
from .agent.types import Message
from .domain.videos import find_videos
from .models import Profile
from .store import UserState, reference_data
from .tools import TOOLS_BY_NAME, ToolError

MAX_SESSIONS = 500


@dataclass
class Session:
    state: UserState
    history: list[Message] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)


class SessionStore:
    """In-memory, size-capped. Swap for Redis/Cosmos DB in a real deployment."""

    def __init__(self, cap: int = MAX_SESSIONS):
        self._items: OrderedDict[str, Session] = OrderedDict()
        self._cap = cap
        self._lock = threading.Lock()

    def create(self, blank: bool = False) -> tuple[str, Session]:
        sid = uuid.uuid4().hex
        with self._lock:
            self._items[sid] = Session(UserState() if blank else UserState.demo())
            while len(self._items) > self._cap:
                self._items.popitem(last=False)
        return sid, self._items[sid]

    def get(self, sid: str) -> Session:
        with self._lock:
            if sid not in self._items:
                raise HTTPException(404, "Session not found. Start a new one.")
            self._items.move_to_end(sid)
            return self._items[sid]


class NewSession(BaseModel):
    blank: bool = False


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class PantryIn(BaseModel):
    items: dict[str, float]


app = FastAPI(title="FitBasket", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("FITBASKET_CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
sessions = SessionStore()
agent = FitBasketAgent(get_provider())


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "provider": agent.provider.name, "model": agent.provider.model}


@app.post("/api/sessions")
def new_session(body: NewSession | None = None) -> dict:
    sid, s = sessions.create(blank=bool(body and body.blank))
    return {"session_id": sid, "state": s.state.snapshot()}


@app.get("/api/sessions/{sid}")
def get_session(sid: str) -> dict:
    return {"session_id": sid, "state": sessions.get(sid).state.snapshot()}


@app.post("/api/sessions/{sid}/chat")
def chat(sid: str, body: ChatIn) -> dict:
    s = sessions.get(sid)
    with s.lock:  # one turn at a time per session
        res = agent.run(s.state, body.message, s.history)
        s.history = res.history[-40:]  # bound context growth
        return {
            "reply": res.reply,
            "tool_events": [asdict(e) for e in res.tool_events],
            "usage": {"input_tokens": res.usage.input_tokens, "output_tokens": res.usage.output_tokens},
            "est_cost_usd": res.est_cost_usd,
            "latency_ms": res.latency_ms,
            "flags": res.flags,
            "trace": res.trace,
            "state": s.state.snapshot(),
        }


@app.put("/api/sessions/{sid}/profile")
def put_profile(sid: str, profile: Profile) -> dict:
    s = sessions.get(sid)
    with s.lock:
        s.state.profile = profile
        s.state.meal_plan = s.state.basket = s.state.workout_plan = None
        return {"state": s.state.snapshot()}


@app.put("/api/sessions/{sid}/pantry")
def put_pantry(sid: str, body: PantryIn) -> dict:
    s = sessions.get(sid)
    with s.lock:
        try:
            current = list(s.state.pantry)
            TOOLS_BY_NAME["update_pantry"].run(
                s.state, {"set": body.items, "remove": [k for k in current if k not in body.items]}
            )
        except (ToolError, ValidationError) as e:
            raise HTTPException(422, str(e)) from e
        return {"state": s.state.snapshot()}


@app.get("/api/catalogue/ingredients")
def ingredients() -> list[dict]:
    return [i.model_dump() for i in reference_data().ingredients.values()]


@app.get("/api/videos")
def videos(query: str) -> list[dict]:
    try:
        return [v.model_dump() for v in find_videos(query)]
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


# Serve the built React app (web/dist) when it exists, e.g. inside the Docker image.
_dist = Path(os.getenv("FITBASKET_WEB_DIST", Path(__file__).resolve().parents[2] / "web" / "dist"))
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="web")
