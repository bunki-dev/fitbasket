"""Deal- and pantry-aware weekly meal planning."""

from __future__ import annotations

from ..models import DAYS, Macros, MealPlan, MealType, PlannedMeal, Recipe
from ..store import ReferenceData, UserState
from .rules import allowed_products, nutrition_targets, recipe_ok

MAX_USES_PER_WEEK = 2
SERVING_STEP = 0.25


def _deal_fraction(recipe: Recipe, ref: ReferenceData, state: UserState) -> float:
    hits = sum(
        any(p.on_special for p in allowed_products(i.ingredient, ref, state.profile)) for i in recipe.ingredients
    )
    return hits / len(recipe.ingredients)


def _pantry_fraction(recipe: Recipe, state: UserState) -> float:
    return sum(state.pantry.get(i.ingredient, 0) > 0 for i in recipe.ingredients) / len(recipe.ingredients)


def score_recipe(recipe: Recipe, ref: ReferenceData, state: UserState) -> float:
    protein_density = recipe.per_serve.protein_g / max(recipe.per_serve.kcal, 1) * 100  # g per 100 kcal
    return 2.0 * _deal_fraction(recipe, ref, state) + 1.0 * _pantry_fraction(recipe, state) + 0.25 * protein_density


def plan_meals(
    state: UserState,
    ref: ReferenceData,
    days: int = 7,
    exclude_recipes: list[str] | None = None,
    include_recipes: list[str] | None = None,
) -> MealPlan:
    profile = state.profile
    targets = nutrition_targets(profile)
    exclude = set(exclude_recipes or [])
    include = [r for r in (include_recipes or []) if r in ref.recipes]
    day_names = DAYS[: max(1, min(days, 7))]

    candidates: dict[str, list[Recipe]] = {}
    for meal_type in profile.meals_per_day:
        pool = [
            r
            for r in ref.recipes.values()
            if r.meal_type == meal_type and r.id not in exclude and recipe_ok(r, ref, profile)
        ]
        # Recipes the user explicitly asked for go first; then by deal/pantry/protein score.
        pool.sort(key=lambda r: (r.id not in include, -score_recipe(r, ref, state), r.id))
        candidates[meal_type] = pool

    uses: dict[str, int] = {}
    meals: list[PlannedMeal] = []
    previous: dict[MealType, str] = {}
    for day in day_names:
        day_meals: list[tuple[MealType, Recipe]] = []
        for meal_type in profile.meals_per_day:
            pool = candidates.get(meal_type, [])
            if not pool:
                continue
            choice = next(
                (r for r in pool if uses.get(r.id, 0) < MAX_USES_PER_WEEK and r.id != previous.get(meal_type)),
                None,
            ) or min(pool, key=lambda r: uses.get(r.id, 0))
            uses[choice.id] = uses.get(choice.id, 0) + 1
            previous[meal_type] = choice.id
            day_meals.append((meal_type, choice))

        # Scale portions so the day lands near the calorie target.
        day_kcal = sum(r.per_serve.kcal for _, r in day_meals) or 1
        factor = min(max(targets.kcal / day_kcal, 0.75), 1.75)
        servings = round(factor / SERVING_STEP) * SERVING_STEP
        for meal_type, r in day_meals:
            meals.append(
                PlannedMeal(day=day, meal_type=meal_type, recipe_id=r.id, recipe_name=r.name, servings=servings)
            )

    return MealPlan(days=day_names, meals=meals, daily_avg=_daily_avg(meals, ref, len(day_names)), targets=targets)


def _daily_avg(meals: list[PlannedMeal], ref: ReferenceData, n_days: int) -> Macros:
    tot = {"kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
    for m in meals:
        ps = ref.recipes[m.recipe_id].per_serve
        for k in tot:
            tot[k] += getattr(ps, k) * m.servings
    return Macros(**{k: round(v / max(n_days, 1)) for k, v in tot.items()})


def swap_meal(state: UserState, ref: ReferenceData, day: str, meal_type: MealType, recipe_id: str) -> MealPlan:
    if state.meal_plan is None:
        raise ValueError("No meal plan yet. Create one first.")
    recipe = ref.recipes.get(recipe_id)
    if recipe is None:
        raise ValueError(f"Unknown recipe '{recipe_id}'.")
    if recipe.meal_type != meal_type:
        raise ValueError(f"{recipe.name} is a {recipe.meal_type} recipe, not {meal_type}.")
    if not recipe_ok(recipe, ref, state.profile):
        raise ValueError(f"{recipe.name} conflicts with the profile's allergies, diet, dislikes or prep time.")
    plan = state.meal_plan.model_copy(deep=True)
    for m in plan.meals:
        if m.day == day and m.meal_type == meal_type:
            m.recipe_id, m.recipe_name = recipe.id, recipe.name
            break
    else:
        raise ValueError(f"No {meal_type} planned on {day}.")
    plan.daily_avg = _daily_avg(plan.meals, ref, len(plan.days))
    return plan
