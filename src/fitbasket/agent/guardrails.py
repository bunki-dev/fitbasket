"""Input guardrails that run before the model sees a message.

They are cheap, deterministic and conservative: they block only what must never reach
the planner (oversized input, requests for dangerously low intakes, crisis signals) and
otherwise attach flags the trace and the evals can see. Allergy, diet and budget rules are
enforced inside the tools, so they hold no matter what the model does.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MAX_INPUT_CHARS = 4000

_INJECTION = re.compile(
    r"ignore (all |the )?(previous|prior|above) (instructions|rules)|system prompt|you are now|"
    r"developer mode|jailbreak|disregard (your|the) (rules|instructions)",
    re.I,
)
_VERY_LOW_INTAKE = re.compile(r"\b([1-9]\d{2})\s*(k?cals?|calories?)\b", re.I)  # 100-999 kcal/day
_DISORDERED = re.compile(
    r"starv(e|ing) myself|purg(e|ing)|make myself (sick|throw up)|stop eating|not eat(ing)? for \d+ days|"
    r"eating disorder|anorexi|bulimi",
    re.I,
)
_SELF_HARM = re.compile(r"kill myself|end my life|suicid|self[- ]harm|hurt myself", re.I)

SUPPORT_MESSAGE = (
    "I'm really glad you told me, and I don't want to give you a plan that could hurt you. "
    "Please talk to someone who can help properly: your GP, or the Butterfly Foundation helpline on "
    "1800 33 4673 for eating and body-image concerns. If you're in crisis or thinking about harming "
    "yourself, call Lifeline on 13 11 14 or 000 in an emergency. I'm happy to help with balanced "
    "meals and gentle training whenever you're ready."
)
LOW_INTAKE_MESSAGE = (
    "I can't build a plan that low. Very low daily intakes aren't safe without medical supervision and "
    "tend to cost muscle, energy and training performance. I can set up a moderate deficit that still "
    "gets you lean, with plenty of protein. Want me to do that?"
)


@dataclass
class GuardrailResult:
    allowed: bool
    message: str
    flags: list[str] = field(default_factory=list)
    response: str | None = None  # canned reply when blocked


def check_input(text: str) -> GuardrailResult:
    flags: list[str] = []
    if len(text) > MAX_INPUT_CHARS:
        return GuardrailResult(
            False, text, ["too_long"], f"That message is too long. Please keep it under {MAX_INPUT_CHARS} characters."
        )
    if _SELF_HARM.search(text) or _DISORDERED.search(text):
        return GuardrailResult(False, text, ["wellbeing"], SUPPORT_MESSAGE)
    # A daily intake under 1000 kcal ("600 calories a day", "eat 800 cals"), but not "burn 500 calories"
    # or "a 300 calorie snack".
    if _VERY_LOW_INTAKE.search(text) and not re.search(r"\bburn|snack|workout|session", text, re.I):
        if re.search(r"\b(a|per) day\b|daily|diet|\beat(ing)?\b|only", text, re.I):
            return GuardrailResult(False, text, ["unsafe_intake"], LOW_INTAKE_MESSAGE)
    if _INJECTION.search(text):
        flags.append("possible_prompt_injection")
    return GuardrailResult(True, text, flags)
