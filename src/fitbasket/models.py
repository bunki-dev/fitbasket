"""Domain models shared by the tools, the agent, the API and the evals."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Allergen = Literal["dairy", "egg", "gluten", "peanut", "tree_nut", "fish", "soy", "sesame"]
Diet = Literal["omnivore", "pescatarian", "vegetarian", "vegan"]
Goal = Literal["fat_loss", "maintain", "muscle_gain"]
MealType = Literal["breakfast", "lunch", "dinner", "snack"]
Day = Literal["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAYS: list[str] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

_ALLERGEN_ALIASES = {
    "nuts": "tree_nut",
    "tree nuts": "tree_nut",
    "tree nut": "tree_nut",
    "almonds": "tree_nut",
    "peanuts": "peanut",
    "milk": "dairy",
    "lactose": "dairy",
    "eggs": "egg",
    "wheat": "gluten",
    "coeliac": "gluten",
    "celiac": "gluten",
    "seafood": "fish",
    "shellfish": "fish",
    "sesame seeds": "sesame",
}


def normalise_allergies(values: list[str] | None) -> list[str] | None:
    """Map common ways people name allergies onto the catalogue's allergen labels."""
    if values is None:
        return None
    out = []
    for a in values:
        key = str(a).lower().strip()
        out.append(_ALLERGEN_ALIASES.get(key, key))
    return list(dict.fromkeys(out))


# ---------- catalogue / reference data ----------


class Ingredient(BaseModel):
    key: str
    name: str
    unit: str
    category: str
    animal_flags: list[str] = []


class Product(BaseModel):
    id: str
    ingredient: str
    brand: str
    name: str
    pack_size: float
    unit: str
    price: float
    special_price: float | None = None
    special_label: str | None = None
    allergens: list[str] = []
    tags: list[str] = []

    @property
    def effective_price(self) -> float:
        return self.special_price if self.special_price is not None else self.price

    @property
    def on_special(self) -> bool:
        return self.special_price is not None


class RecipeIngredient(BaseModel):
    ingredient: str
    qty: float


class Macros(BaseModel):
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


class Recipe(BaseModel):
    id: str
    name: str
    meal_type: MealType
    minutes: int
    ingredients: list[RecipeIngredient]
    per_serve: Macros
    steps: list[str]


class Exercise(BaseModel):
    id: str
    name: str
    type: Literal["strength", "core", "cardio", "mobility"]
    muscles: list[str]
    equipment: Literal["none", "dumbbells", "gym"]
    level: Literal["beginner", "intermediate", "advanced"]
    prescription: str
    video_query: str
    video_id: str | None = None  # a curated how-to video, checked by hand
    video_title: str | None = None

    @property
    def video_url(self) -> str | None:
        return f"https://www.youtube.com/watch?v={self.video_id}" if self.video_id else None


# ---------- user state ----------


class TrainingPrefs(BaseModel):
    days_per_week: int = Field(3, ge=1, le=6)
    session_minutes: int = Field(40, ge=15, le=120)
    equipment: list[Literal["none", "dumbbells", "gym"]] = ["none"]
    level: Literal["beginner", "intermediate", "advanced"] = "beginner"
    focus: list[str] = ["full_body"]
    sport_days: list[Day] = []
    unavailable_days: list[Day] = []


class Profile(BaseModel):
    name: str = "Friend"
    age: int = Field(30, ge=16, le=100)
    sex: Literal["male", "female"] = "male"
    height_cm: float = Field(175, ge=120, le=230)
    weight_kg: float = Field(75, ge=35, le=250)
    goal: Goal = "maintain"
    activity_level: Literal["sedentary", "light", "moderate", "active"] = "light"
    diet: Diet = "omnivore"
    allergies: list[Allergen] = []
    dislikes: list[str] = Field(default_factory=list, description="Ingredient keys to avoid")
    preferred_brands: dict[str, str] = Field(default_factory=dict, description="ingredient key -> brand")
    avoid_brands: list[str] = []
    weekly_budget: float | None = Field(None, ge=0)
    meals_per_day: list[MealType] = ["breakfast", "lunch", "dinner"]
    max_prep_minutes: int = 45
    training: TrainingPrefs = TrainingPrefs()

    @field_validator("allergies", mode="before")
    @classmethod
    def _norm_allergies(cls, v: list[str]) -> list[str]:
        return normalise_allergies(v)


class NutritionTargets(BaseModel):
    kcal: int
    protein_g: int
    carbs_g: int = 0
    fat_g: int = 0
    note: str


class FoodEntry(BaseModel):
    """One food the user logged on their device (scanned or typed in), already scaled to the amount eaten."""

    name: str = Field(max_length=120)
    grams: float = Field(ge=0, le=5000)
    kcal: float = Field(ge=0, le=10000)
    protein_g: float = Field(ge=0, le=1000)
    carbs_g: float = Field(ge=0, le=1000)
    fat_g: float = Field(ge=0, le=1000)
    source: Literal["openfoodfacts", "manual"] = "manual"


class PlannedMeal(BaseModel):
    day: str
    meal_type: MealType
    recipe_id: str
    recipe_name: str
    servings: float = 1


class MealPlan(BaseModel):
    days: list[str]
    meals: list[PlannedMeal]
    daily_avg: Macros
    targets: NutritionTargets


class BasketLine(BaseModel):
    product_id: str
    name: str
    brand: str
    ingredient: str
    packs: int
    unit_price: float
    line_total: float
    on_special: bool
    saving: float
    needed_qty: float
    unit: str
    used_fraction: float = Field(description="Share of the purchased quantity this week's plan uses")
    pack_label: str = Field("", description="Pack size as printed, e.g. '500 g' or '12 pack'")
    was_price: float | None = Field(None, description="Regular price per pack when on special")
    reason: str


class Basket(BaseModel):
    lines: list[BasketLine]
    total: float
    total_saving: float
    specials_used: int
    covered_by_pantry: list[str]
    unavailable: list[str] = []
    budget: float | None = None
    within_budget: bool | None = None
    tips: list[str] = []


class WorkoutExercise(BaseModel):
    exercise_id: str
    name: str
    prescription: str
    video_query: str
    video_id: str | None = None
    video_title: str | None = None


class WorkoutSession(BaseModel):
    day: str
    focus: str
    exercises: list[WorkoutExercise]


class WorkoutPlan(BaseModel):
    sessions: list[WorkoutSession]
    rest_days: list[str]
    sport_days: list[str] = []
    notes: list[str]


class Video(BaseModel):
    title: str
    url: str
    channel: str | None = None
    source: Literal["curated", "youtube_api", "search_link"]
