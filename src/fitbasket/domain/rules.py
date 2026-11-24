"""Hard safety and preference rules.

These are deterministic checks, not LLM judgement: allergies, diet and disliked
ingredients must never depend on what the model decides to say.
"""

from __future__ import annotations

from ..models import Ingredient, NutritionTargets, Product, Profile, Recipe
from ..store import ReferenceData

ACTIVITY_FACTORS = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "active": 1.725}
GOAL_ADJUST = {"fat_loss": 0.82, "maintain": 1.0, "muscle_gain": 1.1}
PROTEIN_PER_KG = {"fat_loss": 2.0, "maintain": 1.6, "muscle_gain": 1.8}
# Never plan below these daily intakes, whatever the user or the model asks for.
CALORIE_FLOOR = {"male": 1500, "female": 1200}


def nutrition_targets(p: Profile) -> NutritionTargets:
    """Mifflin-St Jeor BMR x activity factor, adjusted for the goal."""
    bmr = 10 * p.weight_kg + 6.25 * p.height_cm - 5 * p.age + (5 if p.sex == "male" else -161)
    tdee = bmr * ACTIVITY_FACTORS[p.activity_level]
    kcal = max(round(tdee * GOAL_ADJUST[p.goal] / 10) * 10, CALORIE_FLOOR[p.sex])
    protein = round(p.weight_kg * PROTEIN_PER_KG[p.goal])
    note = (
        f"Estimated maintenance ~{round(tdee)} kcal/day. These are general estimates, not medical or dietetic advice."
    )
    return NutritionTargets(kcal=int(kcal), protein_g=int(protein), note=note)


def diet_allows(product: Product, ingredient: Ingredient, p: Profile) -> bool:
    flags = set(ingredient.animal_flags)
    if p.diet == "vegan":
        return not flags or "vegan" in product.tags
    if p.diet == "vegetarian":
        return not flags & {"meat", "fish"}
    if p.diet == "pescatarian":
        return "meat" not in flags
    return True


def product_allowed(product: Product, ref: ReferenceData, p: Profile) -> bool:
    if set(product.allergens) & set(p.allergies):
        return False
    if product.brand in p.avoid_brands:
        return False
    return diet_allows(product, ref.ingredients[product.ingredient], p)


def allowed_products(ingredient: str, ref: ReferenceData, p: Profile) -> list[Product]:
    return [x for x in ref.catalogue.products_for(ingredient) if product_allowed(x, ref, p)]


def ingredient_ok(ingredient: str, ref: ReferenceData, p: Profile) -> bool:
    return ingredient not in p.dislikes and bool(allowed_products(ingredient, ref, p))


def recipe_ok(recipe: Recipe, ref: ReferenceData, p: Profile) -> bool:
    return recipe.minutes <= p.max_prep_minutes and all(ingredient_ok(i.ingredient, ref, p) for i in recipe.ingredients)


def basket_violations(basket_product_ids: list[str], ref: ReferenceData, p: Profile) -> list[str]:
    """Re-check a finished basket. Used as an output guardrail and by the evals."""
    by_id = {x.id: x for x in ref.catalogue.all_products()}
    problems = []
    for pid in basket_product_ids:
        prod = by_id.get(pid)
        if prod is None:
            problems.append(f"unknown product {pid}")
            continue
        if hit := set(prod.allergens) & set(p.allergies):
            problems.append(f"{prod.name} contains {', '.join(sorted(hit))}")
        if not diet_allows(prod, ref.ingredients[prod.ingredient], p):
            problems.append(f"{prod.name} does not fit a {p.diet} diet")
        if prod.brand in p.avoid_brands:
            problems.append(f"{prod.name} is from avoided brand {prod.brand}")
        if prod.ingredient in p.dislikes:
            problems.append(f"{prod.name} is a disliked ingredient")
    return problems
