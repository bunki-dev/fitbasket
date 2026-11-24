"""Turn a meal plan into a weekly shop: plan minus pantry, cheapest safe packs,
specials first, preferred brands respected."""

from __future__ import annotations

import math
from collections import defaultdict

from ..models import Basket, BasketLine, MealPlan, Product
from ..store import ReferenceData, UserState
from .rules import allowed_products


def required_quantities(plan: MealPlan, ref: ReferenceData) -> dict[str, float]:
    need: dict[str, float] = defaultdict(float)
    for m in plan.meals:
        for ing in ref.recipes[m.recipe_id].ingredients:
            need[ing.ingredient] += ing.qty * m.servings
    return dict(need)


def _fmt_qty(q: float, unit: str) -> str:
    if unit in ("g", "ml"):
        return f"{q:g} {unit}"
    n = math.ceil(q)
    return f"{n} slice{'s' if n != 1 else ''}" if unit == "slice" else str(n)


def _pick(candidates: list[Product], need: float) -> tuple[Product, int]:
    def cost(p: Product) -> tuple[float, float]:
        packs = math.ceil(need / p.pack_size)
        return packs * p.effective_price, packs * p.pack_size - need  # cheapest, then least waste

    best = min(candidates, key=cost)
    return best, math.ceil(need / best.pack_size)


def build_basket(state: UserState, ref: ReferenceData) -> Basket:
    if state.meal_plan is None:
        raise ValueError("No meal plan yet. Create a meal plan before building the basket.")
    profile = state.profile
    need = required_quantities(state.meal_plan, ref)

    lines: list[BasketLine] = []
    from_pantry: list[str] = []
    unavailable: list[str] = []
    for ing in sorted(need):
        unit = ref.ingredients[ing].unit
        remaining = round(need[ing] - state.pantry.get(ing, 0), 2)
        if remaining <= 0:
            from_pantry.append(ref.ingredients[ing].name)
            continue

        candidates = allowed_products(ing, ref, profile)
        if not candidates:
            unavailable.append(ref.ingredients[ing].name)
            continue

        preferred = profile.preferred_brands.get(ing)
        preferred_pool = [c for c in candidates if c.brand == preferred]
        if preferred_pool:
            product, packs = _pick(preferred_pool, remaining)
            reason = f"Your preferred brand ({preferred})"
            if product.on_special:
                reason += ", on special this week"
        else:
            product, packs = _pick(candidates, remaining)
            if product.on_special:
                reason = f"Weekly special, saves ${(product.price - product.special_price) * packs:.2f}"
            else:
                reason = f"Best value for {_fmt_qty(remaining, unit)} needed"
            if state.pantry.get(ing):
                reason += f" (pantry covers {_fmt_qty(state.pantry[ing], unit)})"

        saving = (product.price - product.effective_price) * packs
        lines.append(
            BasketLine(
                product_id=product.id,
                name=product.name,
                brand=product.brand,
                ingredient=ing,
                packs=packs,
                unit_price=product.effective_price,
                line_total=round(packs * product.effective_price, 2),
                on_special=product.on_special,
                saving=round(saving, 2),
                needed_qty=remaining,
                unit=unit,
                used_fraction=round(remaining / (packs * product.pack_size), 2),
                reason=reason,
            )
        )

    total = round(sum(line.line_total for line in lines), 2)
    budget = profile.weekly_budget
    tips = _budget_tips(lines, total, budget)
    return Basket(
        lines=lines,
        total=total,
        total_saving=round(sum(line.saving for line in lines), 2),
        specials_used=sum(line.on_special for line in lines),
        covered_by_pantry=from_pantry,
        unavailable=unavailable,
        budget=budget,
        within_budget=None if budget is None else total <= budget,
        tips=tips,
    )


def _budget_tips(lines: list[BasketLine], total: float, budget: float | None) -> list[str]:
    """Explain where the money goes when the shop is over budget."""
    if budget is None or total <= budget:
        return []
    over = total - budget
    tips = [f"This shop is ${over:.2f} over your ${budget:.0f} budget."]
    # Bulk items mostly carried into next week are the easiest to defer.
    bulk = sorted((ln for ln in lines if ln.used_fraction < 0.5), key=lambda ln: -ln.line_total)
    for ln in bulk[:3]:
        tips.append(
            f"{ln.name} (${ln.line_total:.2f}): only {ln.used_fraction:.0%} is used this week, "
            "so skip it if you can make do, or swap the meals that need it."
        )
    pricey = max(lines, key=lambda ln: ln.line_total, default=None)
    if pricey and pricey not in bulk[:3]:
        tips.append(
            f"Biggest single cost: {pricey.name} (${pricey.line_total:.2f}). "
            "Swapping some of those meals would save the most."
        )
    return tips
