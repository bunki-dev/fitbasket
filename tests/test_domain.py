import itertools

import pytest

from fitbasket.domain.basket import build_basket, required_quantities
from fitbasket.domain.meals import plan_meals, swap_meal
from fitbasket.domain.rules import CALORIE_FLOOR, basket_violations, nutrition_targets
from fitbasket.domain.workouts import plan_workouts
from fitbasket.models import DAYS, Profile

ALLERGENS = ["dairy", "egg", "gluten", "peanut", "tree_nut", "fish", "soy"]
DIETS = ["omnivore", "pescatarian", "vegetarian", "vegan"]


def _shop(state, ref):
    state.meal_plan = plan_meals(state, ref)
    state.basket = build_basket(state, ref)
    return state.basket


@pytest.mark.parametrize("diet,allergy", list(itertools.product(DIETS, ALLERGENS)))
def test_basket_never_breaks_allergy_or_diet(state, ref, diet, allergy):
    state.profile = state.profile.model_copy(update={"diet": diet, "allergies": [allergy]})
    basket = _shop(state, ref)
    assert basket_violations([ln.product_id for ln in basket.lines], ref, state.profile) == []


def test_calorie_floor_holds_for_small_people():
    p = Profile(sex="female", age=60, height_cm=150, weight_kg=45, goal="fat_loss", activity_level="sedentary")
    assert nutrition_targets(p).kcal >= CALORIE_FLOOR["female"]


def test_meal_plan_lands_near_calorie_target(state, ref):
    plan = plan_meals(state, ref)
    assert len(plan.days) == 7
    assert abs(plan.daily_avg.kcal - plan.targets.kcal) / plan.targets.kcal < 0.15


def test_meal_plan_respects_dislikes_and_prep_time(state, ref):
    state.profile = state.profile.model_copy(update={"dislikes": ["salmon_fillet"], "max_prep_minutes": 20})
    plan = plan_meals(state, ref)
    for m in plan.meals:
        recipe = ref.recipes[m.recipe_id]
        assert recipe.minutes <= 20
        assert "salmon_fillet" not in {i.ingredient for i in recipe.ingredients}


def test_no_recipe_more_than_twice_a_week(state, ref):
    plan = plan_meals(state, ref)
    counts = {}
    for m in plan.meals:
        counts[m.recipe_id] = counts.get(m.recipe_id, 0) + 1
    assert max(counts.values()) <= 2


def test_pantry_is_subtracted(state, ref):
    state.pantry = {}
    without = _shop(state, ref)
    state.pantry = {k: 10_000 for k in required_quantities(state.meal_plan, ref)}
    with_everything = build_basket(state, ref)
    assert with_everything.lines == []
    assert without.total > 0


def test_preferred_brand_is_used(state, ref):
    basket = _shop(state, ref)
    chicken = [ln for ln in basket.lines if ln.ingredient == "chicken_breast"]
    assert chicken and all(ln.brand == "Paddock Co" for ln in chicken)


def test_specials_are_counted(state, ref):
    basket = _shop(state, ref)
    assert basket.specials_used == sum(ln.on_special for ln in basket.lines) > 0
    assert basket.total_saving > 0


def test_over_budget_gives_tips(state, ref):
    state.profile = state.profile.model_copy(update={"weekly_budget": 50})
    basket = _shop(state, ref)
    assert basket.within_budget is False
    assert basket.tips and "over your" in basket.tips[0]


def test_swap_rejects_conflicting_recipe(state, ref):
    state.profile = state.profile.model_copy(update={"allergies": ["fish"]})
    state.meal_plan = plan_meals(state, ref)
    with pytest.raises(ValueError):
        swap_meal(state, ref, "Mon", "dinner", "salmon_sweet_potato")


def test_workouts_avoid_sport_and_unavailable_days(ref):
    p = Profile(
        training={
            "days_per_week": 5,
            "sport_days": ["Sat"],
            "unavailable_days": ["Sun", "Wed"],
            "equipment": ["none"],
            "focus": ["core"],
        }
    )
    plan = plan_workouts(p, ref)
    days = [s.day for s in plan.sessions]
    assert not {"Sat", "Sun", "Wed"} & set(days)
    for s in plan.sessions:
        if s.day == "Fri":
            assert not s.focus.startswith(("Lower", "Conditioning"))
        exercises = [ref.exercises[e.exercise_id] for e in s.exercises]
        assert all(e.equipment == "none" for e in exercises)
        assert sum(e.type == "core" for e in exercises) >= 2


def test_beginner_gets_no_advanced_exercises(ref):
    plan = plan_workouts(Profile(training={"level": "beginner", "equipment": ["none", "dumbbells"]}), ref)
    for s in plan.sessions:
        assert all(ref.exercises[e.exercise_id].level == "beginner" for e in s.exercises)


def test_days_are_valid(ref):
    plan = plan_workouts(Profile(training={"days_per_week": 6}), ref)
    assert all(s.day in DAYS for s in plan.sessions)
