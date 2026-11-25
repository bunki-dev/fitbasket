"""Offline providers: no API key, fully deterministic.

`OfflineProvider` is a small keyword router that plays the role of the model so the
whole app (UI, API, MCP, evals) can be run and demoed without credentials. It is
deliberately simple; the real behaviour comes from the Anthropic and Azure providers.

`ScriptedProvider` replays canned responses and is used by the unit tests.
"""

from __future__ import annotations

import itertools
import json
import re

from ..types import LLMResponse, Message, ToolCall, ToolSpec, Usage

_ids = itertools.count(1)

ALLERGENS = {
    "peanut": "peanut",
    "nut": "tree_nut",
    "dairy": "dairy",
    "lactose": "dairy",
    "gluten": "gluten",
    "egg": "egg",
    "fish": "fish",
    "seafood": "fish",
    "soy": "soy",
    "sesame": "sesame",
}
DAY_WORDS = {"mon": "Mon", "tue": "Tue", "wed": "Wed", "thu": "Thu", "fri": "Fri", "sat": "Sat", "sun": "Sun"}


def _call(name: str, **args) -> ToolCall:
    return ToolCall(id=f"offline_{next(_ids)}", name=name, arguments=args)


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class OfflineProvider:
    name = "offline"
    model = "offline-router"

    def complete(self, system: str, messages: list[Message], tools: list[ToolSpec]) -> LLMResponse:
        last_user = next(i for i in range(len(messages) - 1, -1, -1) if messages[i].role == "user")
        tool_results = [m for m in messages[last_user + 1 :] if m.role == "tool"]
        prompt_tokens = _estimate_tokens(system + "".join(m.content for m in messages))
        if tool_results:
            text = self._compose_reply(tool_results)
            return LLMResponse(text, [], Usage(prompt_tokens, _estimate_tokens(text)), self.model)
        calls = self._route(messages[last_user].content)
        text = (
            ""
            if calls
            else (
                "I can build a weekly meal plan, a deal-aware shopping basket from it, and a workout plan with "
                "how-to videos. Tell me your goal, any allergies, your budget and which days you train."
            )
        )
        return LLMResponse(text, calls, Usage(prompt_tokens, _estimate_tokens(text) + 20 * len(calls)), self.model)

    # ---- intent routing ----
    def _route(self, text: str) -> list[ToolCall]:
        t = text.lower()
        calls: list[ToolCall] = []
        update: dict = {}
        if allergies := sorted({v for k, v in ALLERGENS.items() if re.search(rf"allerg\w*[^.]*\b{k}", t)}):
            update["allergies"] = allergies
        for diet in ("vegan", "vegetarian", "pescatarian"):
            if re.search(rf"\b(i'?m|i am|go|going|eat)\b[^.]*\b{diet}", t):
                update["diet"] = diet
        if m := re.search(r"budget[^0-9$]*\$?\s?(\d{2,4})|\$(\d{2,4})\s*(a|per)\s*week", t):
            update["weekly_budget"] = float(m.group(1) or m.group(2))
        if m := re.search(r"(\d)\s*(days?|x|times)\s*(a|per)\s*week", t):
            update["training_days_per_week"] = int(m.group(1))
        if m := re.search(r"(?:play|game|match)\w*[^.]*?\bon\s+(\w+)", t):
            if (d := DAY_WORDS.get(m.group(1)[:3])) is not None:
                update["sport_days"] = [d]
        if update:
            calls.append(_call("update_profile", **update))

        wants_shop = bool(re.search(r"shop|basket|grocer|shopping list|buy", t))
        wants_meals = wants_shop or bool(re.search(r"meal|eat|food|diet plan|menu|recipes for the week", t))
        wants_workout = bool(re.search(r"workout|train|exercise|gym|abs|routine", t))
        wants_video = bool(re.search(r"video|how (do|to) i do|how to do|show me how|youtube", t))
        wants_deals = bool(re.search(r"special|deal|on sale|discount", t)) and not wants_shop

        wants_intake = bool(
            re.search(r"(left|remaining|so far|eaten|logged|today|intake|tracked)", t)
            and re.search(r"macro|calorie|kcal|protein|carb|fat|eat|food|intake|today", t)
            and not re.search(r"plan|shop|basket|week", t)
        )
        if wants_intake:
            return [_call("get_todays_intake")]
        if wants_video:
            calls.append(_call("find_exercise_videos", query=self._video_query(t)))
        elif wants_workout:
            calls.append(_call("create_workout_plan"))
        if wants_meals:
            calls.append(_call("create_meal_plan", days=7))
        if wants_shop:
            calls.append(_call("build_shopping_basket"))
        if wants_deals:
            calls.append(_call("search_products", specials_only=True))
        if not calls and re.search(r"profile|target|calorie|protein|macro", t):
            calls.append(_call("get_profile"))
        return calls

    @staticmethod
    def _video_query(t: str) -> str:
        m = re.search(
            r"(?:how (?:do|to) i do|how to do|show me how to do|video (?:for|of|on))\s+(?:a |an |the )?"
            r"([a-z' -]+)",
            t,
        )
        return (m.group(1).strip() if m else "beginner core workout") + " form"

    # ---- reply composition ----
    def _compose_reply(self, results: list[Message]) -> str:
        parts: list[str] = []
        for r in results:
            if r.is_error:
                parts.append(f"I hit a problem: {r.content}")
                continue
            data = json.loads(r.content)
            if r.name == "update_profile":
                parts.append(f"Updated your profile ({', '.join(data['updated'])}).")
            elif r.name == "create_meal_plan":
                t, a = data["targets"], data["daily_avg"]
                parts.append(
                    f"Your 7-day meal plan averages {a['kcal']:.0f} kcal and {a['protein_g']:.0f} g protein a day "
                    f"(target {t['kcal']} kcal, {t['protein_g']} g protein), favouring this week's specials."
                )
            elif r.name == "build_shopping_basket":
                s = (
                    f"Your basket comes to ${data['total']:.2f} with {data['specials_used']} specials saving "
                    f"${data['total_saving']:.2f}."
                )
                if data["covered_by_pantry"]:
                    s += f" Already in your pantry: {', '.join(data['covered_by_pantry'])}."
                if data["within_budget"] is False:
                    s += " " + " ".join(data["tips"][:2])
                parts.append(s)
            elif r.name == "create_workout_plan":
                days = ", ".join(f"{d} ({v['focus']})" for d, v in data["sessions"].items())
                parts.append(f"Workout plan: {days}. Rest days: {', '.join(data['rest_days'])}.")
            elif r.name == "find_exercise_videos":
                v = data["videos"][0]
                parts.append(f"Here's a how-to for {data['query']}: {v['url']}")
            elif r.name == "search_products":
                deals = [f"{p['name']} ${p['special_price']:.2f} (was ${p['price']:.2f})" for p in data["products"][:6]]
                parts.append("This week's specials: " + "; ".join(deals) + ".")
            elif r.name == "get_todays_intake":
                if not data["logged_items"]:
                    parts.append(data["note"])
                else:
                    e, left = data["eaten"], data["remaining"]
                    parts.append(
                        f"Today so far: {e['kcal']:.0f} kcal, {e['protein_g']:.0f} g protein, "
                        f"{e['carbs_g']:.0f} g carbs, {e['fat_g']:.0f} g fat. Left for today: "
                        f"{max(left['kcal'], 0):.0f} kcal and {max(left['protein_g'], 0):.0f} g protein."
                    )
            elif r.name == "get_profile":
                t = data["targets"]
                parts.append(
                    f"Your daily targets are about {t['kcal']} kcal and {t['protein_g']} g protein. {t['note']}"
                )
        return " ".join(parts) or "Done."


class ScriptedProvider:
    """Replays a fixed list of responses. For tests."""

    name = "scripted"
    model = "scripted"

    def __init__(self, responses: list[LLMResponse]):
        self._responses = list(responses)
        self.calls: list[list[Message]] = []

    def complete(self, system: str, messages: list[Message], tools: list[ToolSpec]) -> LLMResponse:
        self.calls.append(list(messages))
        if not self._responses:
            return LLMResponse("(no more scripted responses)", [], Usage(), self.model)
        return self._responses.pop(0)
