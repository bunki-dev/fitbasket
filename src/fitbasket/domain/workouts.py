"""Weekly workout planning that works around sport days and available equipment."""

from __future__ import annotations

from ..models import DAYS, Exercise, Profile, WorkoutExercise, WorkoutPlan, WorkoutSession
from ..store import ReferenceData

LEVELS = ["beginner", "intermediate", "advanced"]

# Session templates: (focus label, exercise types/muscle hints to draw from)
TEMPLATES = {
    "lower": ("Lower body + core", ["quads", "glutes", "hamstrings"]),
    "upper": ("Upper body + core", ["chest", "back", "shoulders", "triceps", "biceps"]),
    "conditioning": ("Conditioning + core", ["cardio"]),
    "full": ("Full body + mobility", ["quads", "chest", "back", "glutes"]),
}
ROTATION = ["lower", "upper", "conditioning", "full", "upper", "lower"]


def _usable(ex: Exercise, p: Profile) -> bool:
    level_ok = LEVELS.index(ex.level) <= LEVELS.index(p.training.level)
    return level_ok and ex.equipment in p.training.equipment


def _pick_days(p: Profile) -> list[str]:
    blocked = set(p.training.unavailable_days) | set(p.training.sport_days)
    free = [d for d in DAYS if d not in blocked]
    n = min(p.training.days_per_week, len(free))
    if n == 0:
        return []
    # Spread sessions across the week as evenly as the free days allow.
    step = len(free) / n
    return [free[int(i * step)] for i in range(n)]


def plan_workouts(p: Profile, ref: ReferenceData) -> WorkoutPlan:
    pool = [e for e in ref.exercises.values() if _usable(e, p)]
    core = [e for e in pool if e.type == "core"]
    mobility = [e for e in pool if e.type == "mobility"]
    per_session = max(3, min(8, p.training.session_minutes // 7))
    core_count = 2 if "core" in p.training.focus else 1

    days = _pick_days(p)
    day_before_sport = {DAYS[(DAYS.index(s) - 1) % 7] for s in p.training.sport_days}
    sessions: list[WorkoutSession] = []
    for i, day in enumerate(days):
        kind = ROTATION[i % len(ROTATION)]
        if day in day_before_sport and kind in ("lower", "conditioning"):
            kind = "upper"  # keep legs fresh for game day
        label, hints = TEMPLATES[kind]
        if kind == "conditioning":
            main = [e for e in pool if e.type == "cardio"]
        else:
            main = [e for e in pool if e.type == "strength" and set(e.muscles) & set(hints)]
        main = main[i % max(len(main), 1) :] + main[: i % max(len(main), 1)]  # rotate for variety
        chosen = main[: per_session - core_count]
        chosen += (core[i % max(len(core), 1) :] + core)[:core_count]
        if kind == "full" and mobility:
            chosen.append(mobility[i % len(mobility)])
        sessions.append(
            WorkoutSession(
                day=day,
                focus=label,
                exercises=[
                    WorkoutExercise(
                        exercise_id=e.id, name=e.name, prescription=e.prescription, video_query=e.video_query
                    )
                    for e in chosen
                ],
            )
        )

    notes = [
        "Warm up for 5 minutes (easy cardio + dynamic stretches) before every session.",
        "Progress by adding 1-2 reps or a little weight each week while form stays clean.",
        "Visible abs depend mostly on body-fat level, so the meal plan matters as much as core work.",
        "Stop and get medical advice if an exercise causes pain (not just effort).",
    ]
    if p.training.sport_days:
        notes.append(f"No hard leg or conditioning work the day before {', '.join(p.training.sport_days)} (sport day).")
    rest = [d for d in DAYS if d not in days]
    return WorkoutPlan(sessions=sessions, rest_days=rest, notes=notes)
