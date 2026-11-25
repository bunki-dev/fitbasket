import json
from unittest import mock

import pytest

from fitbasket.domain import videos
from fitbasket.tools import TOOLS, TOOLS_BY_NAME, ToolError


def run(name, state, args=None):
    return TOOLS_BY_NAME[name].run(state, args or {})


def test_every_tool_has_an_object_schema():
    for t in TOOLS:
        schema = t.json_schema()
        assert schema["type"] == "object", t.name
        json.dumps(schema)


def test_invalid_args_become_tool_errors(state):
    with pytest.raises(ToolError, match="Invalid arguments"):
        run("update_profile", state, {"age": 5})
    with pytest.raises(ToolError):
        run("swap_meal", state, {"day": "Funday", "meal_type": "dinner", "recipe_id": "x"})


def test_allergy_aliases_are_normalised(state):
    out = run("update_profile", state, {"allergies": ["peanuts", "Nuts", "lactose"]})
    assert out["profile"]["allergies"] == ["peanut", "tree_nut", "dairy"]


def test_basket_needs_a_plan_first(state):
    with pytest.raises(ToolError, match="meal plan"):
        run("build_shopping_basket", state)


def test_profile_change_clears_plans(state):
    run("create_meal_plan", state)
    run("build_shopping_basket", state)
    run("update_profile", state, {"diet": "vegan"})
    assert state.meal_plan is None and state.basket is None


def test_unknown_pantry_item_rejected(state):
    with pytest.raises(ToolError, match="Unknown ingredient"):
        run("update_pantry", state, {"set": {"unicorn_meat": 2}})


def test_specials_search_only_returns_specials(state):
    out = run("search_products", state, {"specials_only": True})
    assert out["products"] and all(p["special_price"] is not None for p in out["products"])


def test_curated_video_comes_first(state):
    out = run("find_exercise_videos", state, {"exercise_id": "plank"})
    assert out["videos"][0]["source"] == "curated"
    assert out["videos"][0]["url"] == "https://www.youtube.com/watch?v=6LqqeBtFn9M"


def test_free_text_video_fallback_is_a_search_link_not_a_made_up_video(state):
    out = run("find_exercise_videos", state, {"query": "cricket bowling drills"})
    assert out["videos"][0]["source"] == "search_link"
    assert out["videos"][0]["url"].startswith("https://www.youtube.com/results?")


def test_every_exercise_has_a_curated_video(ref):
    for ex in ref.exercises.values():
        assert ex.video_id and len(ex.video_id) == 11, ex.id


def test_video_api_results_are_parsed():
    payload = {"items": [{"id": {"videoId": "abc123"}, "snippet": {"title": "Plank form", "channelTitle": "Coach"}}]}
    fake = mock.MagicMock()
    fake.__enter__.return_value = fake
    with (
        mock.patch.object(videos.urllib.request, "urlopen", return_value=fake),
        mock.patch.object(videos.json, "load", return_value=payload),
    ):
        out = videos.find_videos("plank", api_key="k")
    assert out[0].url == "https://www.youtube.com/watch?v=abc123" and out[0].source == "youtube_api"


def test_video_api_failure_degrades_to_link():
    with mock.patch.object(videos.urllib.request, "urlopen", side_effect=OSError("down")):
        out = videos.find_videos("plank", api_key="k")
    assert out[0].source == "search_link"
