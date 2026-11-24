"""Reference data (catalogue, recipes, exercises) and per-user session state.

The grocery catalogue sits behind the `CatalogueSource` protocol so the mock data
can be swapped for a real retailer API without touching the tools or the agent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources
from typing import Protocol

from .models import Basket, Exercise, Ingredient, MealPlan, Product, Profile, Recipe, WorkoutPlan


def _load(name: str) -> list | dict:
    return json.loads(resources.files("fitbasket.data").joinpath(f"{name}.json").read_text())


class CatalogueSource(Protocol):
    """Anything that can list products for an ingredient (mock, retailer API, cache...)."""

    def products_for(self, ingredient: str) -> list[Product]: ...

    def all_products(self) -> list[Product]: ...


class MockCatalogue:
    """Static demo catalogue with fictional brands and this week's specials."""

    def __init__(self, products: list[Product]):
        self._products = products
        self._by_ing: dict[str, list[Product]] = {}
        for p in products:
            self._by_ing.setdefault(p.ingredient, []).append(p)

    def products_for(self, ingredient: str) -> list[Product]:
        return list(self._by_ing.get(ingredient, []))

    def all_products(self) -> list[Product]:
        return list(self._products)


@dataclass(frozen=True)
class ReferenceData:
    ingredients: dict[str, Ingredient]
    recipes: dict[str, Recipe]
    exercises: dict[str, Exercise]
    catalogue: CatalogueSource


@lru_cache(maxsize=1)
def reference_data() -> ReferenceData:
    return ReferenceData(
        ingredients={i["key"]: Ingredient(**i) for i in _load("ingredients")},
        recipes={r["id"]: Recipe(**r) for r in _load("recipes")},
        exercises={e["id"]: Exercise(**e) for e in _load("exercises")},
        catalogue=MockCatalogue([Product(**p) for p in _load("catalogue")]),
    )


@dataclass
class UserState:
    """Everything the agent knows and has produced for one user session."""

    profile: Profile = field(default_factory=Profile)
    pantry: dict[str, float] = field(default_factory=dict)
    meal_plan: MealPlan | None = None
    basket: Basket | None = None
    workout_plan: WorkoutPlan | None = None

    @classmethod
    def demo(cls) -> UserState:
        raw = _load("demo_profile")
        return cls(profile=Profile(**raw["profile"]), pantry=dict(raw["pantry"]))

    def snapshot(self) -> dict:
        return {
            "profile": self.profile.model_dump(),
            "pantry": self.pantry,
            "meal_plan": self.meal_plan.model_dump() if self.meal_plan else None,
            "basket": self.basket.model_dump() if self.basket else None,
            "workout_plan": self.workout_plan.model_dump() if self.workout_plan else None,
        }
