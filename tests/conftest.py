import pytest

from fitbasket.store import UserState, reference_data


@pytest.fixture
def ref():
    return reference_data()


@pytest.fixture
def state():
    return UserState.demo()


@pytest.fixture(autouse=True)
def _no_network_or_traces(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.delenv("FITBASKET_TRACE_DIR", raising=False)
