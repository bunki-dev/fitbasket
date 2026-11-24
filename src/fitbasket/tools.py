"""The agent's tools.

Each tool has a typed (pydantic) input model, so the same definitions drive:
  * JSON schemas sent to the LLM (Anthropic and Azure OpenAI formats),
  * argument validation before anything runs (bad model output never reaches the domain code),
  * the MCP server, which exposes the same tools to any MCP client.

Tool results are kept compact: the model gets what it needs to explain the result,
and the UI reads the full objects from session state.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from .domain.basket import build_basket
from .domain.meals import plan_meals, swap_meal
from .domain.rules import allowed_products, basket_violations, nutrition_targets, recipe_ok
from .domain.videos import find_videos
from .domain.workouts import plan_workouts
from .models import Allergen, Day, Diet, Goal, MealType, Profile, normalise_allergies
from .store import ReferenceData, UserState, reference_data


class ToolError(Exception):
    """An error the model should see and can recover from (bad args, missing prerequisite...)."""


# ---------- input models ----------


class NoArgs(BaseModel):
    pass


class ProfileUpdate(BaseModel):
    """Only the fields to change. Lists replace the existing list."""

    name: str | None = None
    age: int | None = Field(None, ge=16, le=100)
    sex: Literal["male", "female"] | None = None
    height_cm: float | None = Field(None, ge=120, le=230)
    weight_kg: float | None = Field(None, ge=35, le=250)
    goal: Goal | None = None
    activity_level: Literal["sedentary", "light", "moderate", "active"] | None = None
    diet: Diet | None = None
    allergies: list[Allergen] | None = None
    dislikes: list[str] | None = Field(None, description="Ingredient keys, e.g. 'feta', 'salmon_fillet'")
    preferred_brands: dict[str, str] | None = Field(None, description="ingredient key -> brand name")
    avoid_brands: list[str] | None = None
    weekly_budget: float | None = Field(None, ge=0, le=2000)
    meals_per_day: list[MealType] | None = None
    max_prep_minutes: int | None = Field(None, ge=5, le=180)
    training_days_per_week: int | None = Field(None, ge=1, le=6)
    training_session_minutes: int | None = Field(None, ge=15, le=120)
    training_equipment: list[Literal["none", "dumbbells", "gym"]] | None = None
    training_level: Literal["beginner", "intermediate", "advanced"] | None = None
    training_focus: list[str] | None = None
    sport_days: list[Day] | None = None
    unavailable_days: list[Day] | None = None

    @field_validator("allergies", mode="before")
    @classmethod
    def _norm(cls, v: list[str] | None) -> list[str] | None:
        return normalise_allergies(v)


class PantryUpdate(BaseModel):
    set: dict[str, float] = Field(
        default_factory=dict, description="ingredient key -> quantity on hand (g, ml or count)"
    )
    remove: list[str] = Field(default_factory=list, description="ingredient keys now used up")


class RecipeSearch(BaseModel):
    meal_type: MealType | None = None
    query: str | None = Field(None, description="Word to match in the recipe name or ingredients")


class RecipeId(BaseModel):
    recipe_id: str


class MealPlanArgs(BaseModel):
    days: int = Field(7, ge=1, le=7)
    include_recipes: list[str] = Field(default_factory=list, description="Recipe ids the user asked for")
    exclude_recipes: list[str] = Field(default_factory=list, description="Recipe ids the user rejected")


class SwapArgs(BaseModel):
    day: Day
    meal_type: MealType
    recipe_id: str


class ProductSearch(BaseModel):
    ingredient: str | None = Field(None, description="Ingredient key, e.g. 'chicken_breast'")
    specials_only: bool = False


class VideoSearch(BaseModel):
    exercise_id: str | None = Field(None, description="Exercise id from the workout plan")
    query: str | None = Field(None, description="Free-text search if there is no exercise id")


# ---------- handlers ----------


def _profile_summary(p: Profile) -> dict:
    t = nutrition_targets(p)
    return {**p.model_dump(), "targets": t.model_dump()}


def get_profile(state: UserState, ref: ReferenceData, _: NoArgs) -> dict:
    return _profile_summary(state.profile)


def update_profile(state: UserState, ref: ReferenceData, args: ProfileUpdate) -> dict:
    changes = args.model_dump(exclude_none=True)
    for key in changes.get("dislikes", []):
        if key not in ref.ingredients:
            raise ToolError(f"Unknown ingredient '{key}'. Valid keys: {', '.join(sorted(ref.ingredients))}")
    training = state.profile.training.model_dump()
    for field in ("days_per_week", "session_minutes", "equipment", "level", "focus"):
        if (v := changes.pop(f"training_{field}", None)) is not None:
            training[field] = v
    for field in ("sport_days", "unavailable_days"):
        if (v := changes.pop(field, None)) is not None:
            training[field] = v
    try:
        state.profile = Profile(**{**state.profile.model_dump(), **changes, "training": training})
    except ValidationError as e:
        raise ToolError(str(e)) from e
    # Plans built on the old profile may now be wrong; drop them so they get rebuilt.
    state.meal_plan = state.basket = state.workout_plan = None
    return {
        "updated": sorted(args.model_dump(exclude_none=True)),
        "profile": _profile_summary(state.profile),
        "note": "Existing plans were cleared because the profile changed.",
    }


def get_pantry(state: UserState, ref: ReferenceData, _: NoArgs) -> dict:
    return {k: {"qty": v, "unit": ref.ingredients[k].unit} for k, v in state.pantry.items() if k in ref.ingredients}


def update_pantry(state: UserState, ref: ReferenceData, args: PantryUpdate) -> dict:
    unknown = [k for k in [*args.set, *args.remove] if k not in ref.ingredients]
    if unknown:
        raise ToolError(f"Unknown ingredient keys {unknown}. Valid keys: {', '.join(sorted(ref.ingredients))}")
    for k, v in args.set.items():
        if v < 0:
            raise ToolError(f"Quantity for {k} cannot be negative.")
        state.pantry[k] = v
    for k in args.remove:
        state.pantry.pop(k, None)
    state.basket = None
    return get_pantry(state, ref, NoArgs())


def search_recipes(state: UserState, ref: ReferenceData, args: RecipeSearch) -> dict:
    q = (args.query or "").lower()
    out = []
    for r in ref.recipes.values():
        if args.meal_type and r.meal_type != args.meal_type:
            continue
        if q and q not in r.name.lower() and not any(q in i.ingredient for i in r.ingredients):
            continue
        out.append(
            {
                "id": r.id,
                "name": r.name,
                "meal_type": r.meal_type,
                "minutes": r.minutes,
                **r.per_serve.model_dump(),
                "fits_profile": recipe_ok(r, ref, state.profile),
            }
        )
    return {"recipes": out}


def get_recipe(state: UserState, ref: ReferenceData, args: RecipeId) -> dict:
    r = ref.recipes.get(args.recipe_id)
    if r is None:
        raise ToolError(f"Unknown recipe '{args.recipe_id}'.")
    return {
        **r.model_dump(),
        "fits_profile": recipe_ok(r, ref, state.profile),
        "ingredient_names": {i.ingredient: ref.ingredients[i.ingredient].name for i in r.ingredients},
    }


def create_meal_plan(state: UserState, ref: ReferenceData, args: MealPlanArgs) -> dict:
    plan = plan_meals(state, ref, args.days, args.exclude_recipes, args.include_recipes)
    if not plan.meals:
        raise ToolError("No recipes fit this profile (check allergies, diet, dislikes and max prep time).")
    state.meal_plan, state.basket = plan, None
    by_day: dict[str, list[str]] = {}
    for m in plan.meals:
        by_day.setdefault(m.day, []).append(f"{m.meal_type}: {m.recipe_name} x{m.servings:g}")
    return {"targets": plan.targets.model_dump(), "daily_avg": plan.daily_avg.model_dump(), "plan": by_day}


def swap_meal_tool(state: UserState, ref: ReferenceData, args: SwapArgs) -> dict:
    try:
        state.meal_plan = swap_meal(state, ref, args.day, args.meal_type, args.recipe_id)
    except ValueError as e:
        raise ToolError(str(e)) from e
    state.basket = None
    return {"swapped": args.model_dump(), "daily_avg": state.meal_plan.daily_avg.model_dump()}


def build_shopping_basket(state: UserState, ref: ReferenceData, _: NoArgs) -> dict:
    try:
        basket = build_basket(state, ref)
    except ValueError as e:
        raise ToolError(str(e)) from e
    # Output guardrail: re-verify the basket against hard rules before anyone sees it.
    problems = basket_violations([ln.product_id for ln in basket.lines], ref, state.profile)
    if problems:
        raise ToolError("Basket failed safety checks: " + "; ".join(problems))
    state.basket = basket
    return {
        "total": basket.total,
        "total_saving": basket.total_saving,
        "specials_used": basket.specials_used,
        "budget": basket.budget,
        "within_budget": basket.within_budget,
        "tips": basket.tips,
        "covered_by_pantry": basket.covered_by_pantry,
        "unavailable": basket.unavailable,
        "lines": [f"{ln.packs} x {ln.name} ${ln.line_total:.2f} ({ln.reason})" for ln in basket.lines],
    }


def search_products(state: UserState, ref: ReferenceData, args: ProductSearch) -> dict:
    if args.ingredient and args.ingredient not in ref.ingredients:
        raise ToolError(f"Unknown ingredient '{args.ingredient}'.")
    pool = (
        allowed_products(args.ingredient, ref, state.profile)
        if args.ingredient
        else [p for i in ref.ingredients for p in allowed_products(i, ref, state.profile)]
    )
    if args.specials_only:
        pool = [p for p in pool if p.on_special]
    return {
        "products": [
            {
                "id": p.id,
                "name": p.name,
                "brand": p.brand,
                "pack": f"{p.pack_size:g} {p.unit}",
                "price": p.price,
                "special_price": p.special_price,
            }
            for p in pool[:40]
        ]
    }


def create_workout_plan(state: UserState, ref: ReferenceData, _: NoArgs) -> dict:
    plan = plan_workouts(state.profile, ref)
    if not plan.sessions:
        raise ToolError("No training days are available. Ask the user which days they can train.")
    state.workout_plan = plan
    return {
        "sessions": {
            s.day: {
                "focus": s.focus,
                "exercises": [f"{e.name} ({e.prescription}) [{e.exercise_id}]" for e in s.exercises],
            }
            for s in plan.sessions
        },
        "rest_days": plan.rest_days,
        "notes": plan.notes,
    }


def find_exercise_videos(state: UserState, ref: ReferenceData, args: VideoSearch) -> dict:
    if args.exercise_id:
        ex = ref.exercises.get(args.exercise_id)
        if ex is None:
            raise ToolError(f"Unknown exercise '{args.exercise_id}'.")
        query = ex.video_query
    elif args.query:
        query = args.query
    else:
        raise ToolError("Give an exercise_id or a query.")
    return {"query": query, "videos": [v.model_dump() for v in find_videos(query)]}


# ---------- registry ----------


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[[UserState, ReferenceData, Any], dict]
    mutates: bool = False

    def json_schema(self) -> dict:
        schema = self.args_model.model_json_schema()
        schema.pop("title", None)
        return schema

    def run(self, state: UserState, raw_args: dict | None, ref: ReferenceData | None = None) -> dict:
        try:
            args = self.args_model.model_validate(raw_args or {})
        except ValidationError as e:
            raise ToolError(f"Invalid arguments for {self.name}: {e.errors(include_url=False)}") from e
        return self.handler(state, ref or reference_data(), args)


TOOLS: list[Tool] = [
    Tool("get_profile", "Read the user's profile, preferences and daily nutrition targets.", NoArgs, get_profile),
    Tool(
        "update_profile",
        "Change profile fields: goal, diet, allergies, dislikes, preferred or avoided "
        "brands, weekly budget, meals, prep time, training days/equipment/level, sport and unavailable days. "
        "Clears existing plans.",
        ProfileUpdate,
        update_profile,
        mutates=True,
    ),
    Tool("get_pantry", "List what the user already has at home.", NoArgs, get_pantry),
    Tool(
        "update_pantry",
        "Record pantry items on hand (ingredient key -> quantity) or remove used-up items.",
        PantryUpdate,
        update_pantry,
        mutates=True,
    ),
    Tool(
        "search_recipes",
        "Find recipes by meal type or keyword, with macros and whether they fit the profile.",
        RecipeSearch,
        search_recipes,
    ),
    Tool("get_recipe", "Get a recipe's ingredients and method.", RecipeId, get_recipe),
    Tool(
        "create_meal_plan",
        "Create a weekly meal plan that hits calorie/protein targets, respects allergies, "
        "diet and dislikes, and prefers recipes using this week's specials and pantry items.",
        MealPlanArgs,
        create_meal_plan,
        mutates=True,
    ),
    Tool(
        "swap_meal", "Replace one meal in the current plan with another recipe.", SwapArgs, swap_meal_tool, mutates=True
    ),
    Tool(
        "build_shopping_basket",
        "Build the weekly shop from the current meal plan: subtracts pantry stock, "
        "picks the cheapest safe packs, uses specials and preferred brands, and checks the budget.",
        NoArgs,
        build_shopping_basket,
        mutates=True,
    ),
    Tool(
        "search_products",
        "Browse grocery products the user can eat, optionally specials only.",
        ProductSearch,
        search_products,
    ),
    Tool(
        "create_workout_plan",
        "Create a weekly workout plan from the profile's training preferences, "
        "avoiding sport days and unavailable days.",
        NoArgs,
        create_workout_plan,
        mutates=True,
    ),
    Tool(
        "find_exercise_videos",
        "Find YouTube how-to videos for an exercise (by id) or a free-text query.",
        VideoSearch,
        find_exercise_videos,
    ),
]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}
