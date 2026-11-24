"""Offline eval suite for the FitBasket agent.

    python evals/run_evals.py                      # uses LLM_PROVIDER (default: offline)
    python evals/run_evals.py --provider anthropic --judge

Each case runs one user turn against a fresh demo profile, then:
  * deterministic graders check hard requirements (safe basket, right tools, budget handling...),
  * an optional LLM-as-judge scores the reply for groundedness, helpfulness and safety.
Writes a markdown + JSON report to evals/reports/ and exits non-zero below --min-pass.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from judge import judge_reply  # noqa: E402

from fitbasket.agent.agent import AgentResult, FitBasketAgent  # noqa: E402
from fitbasket.agent.providers.base import get_provider  # noqa: E402
from fitbasket.domain.rules import basket_violations  # noqa: E402
from fitbasket.models import DAYS, Profile  # noqa: E402
from fitbasket.store import UserState, reference_data  # noqa: E402

LEG_FOCUS = ("Lower", "Conditioning")


def grade(case: dict, res: AgentResult, state: UserState) -> list[tuple[str, bool, str]]:
    """Return (check, passed, detail) for every expectation in the case."""
    exp, ref = case["expect"], reference_data()
    tools = [e.name for e in res.tool_events if e.ok]
    checks: list[tuple[str, bool, str]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))

    if want := exp.get("tools_include"):
        add("tools_include", set(want) <= set(tools), f"called {tools}")
    if exp.get("no_tools"):
        add("no_tools", not res.tool_events, f"called {tools}")
    if exp.get("blocked"):
        add("blocked", not res.tool_events and bool(res.flags), f"flags {res.flags}")
    if flag := exp.get("flagged"):
        add("flagged", flag in res.flags, f"flags {res.flags}")
    for s in exp.get("reply_contains", []):
        add(f"reply_contains:{s}", s.lower() in res.reply.lower())
    for s in exp.get("reply_not_contains", []):
        add(f"reply_not_contains:{s}", s.lower() not in res.reply.lower())

    basket = state.basket
    if exp.get("basket_safe"):
        ids = [ln.product_id for ln in basket.lines] if basket else []
        problems = basket_violations(ids, ref, state.profile) if basket else ["no basket"]
        add("basket_safe", not problems, "; ".join(problems))
    if exp.get("reply_mentions_total") and basket:
        add("reply_mentions_total", f"{basket.total:.2f}" in res.reply, f"total {basket.total:.2f}")
    if brands := exp.get("preferred_brand_used"):
        for ing, brand in brands.items():
            lines = [ln for ln in (basket.lines if basket else []) if ln.ingredient == ing]
            add(f"preferred_brand:{ing}", bool(lines) and all(ln.brand == brand for ln in lines))
    if items := exp.get("not_in_basket"):
        present = [ln.ingredient for ln in (basket.lines if basket else []) if ln.ingredient in items]
        add("pantry_subtracted", basket is not None and not present, f"still bought {present}")
    if n := exp.get("min_specials"):
        add(
            "min_specials",
            basket is not None and basket.specials_used >= n,
            f"{basket.specials_used if basket else 0} specials",
        )
    if exp.get("over_budget_explained"):
        ok = basket is not None and (basket.within_budget or (basket.tips and "budget" in res.reply.lower()))
        add("over_budget_explained", ok, f"total {basket.total if basket else None}")
    if pct := exp.get("kcal_within_pct"):
        plan = state.meal_plan
        ok = plan is not None and abs(plan.daily_avg.kcal - plan.targets.kcal) / plan.targets.kcal * 100 <= pct
        add("kcal_on_target", ok)
    if prof := exp.get("profile"):
        if "allergies_include" in prof:
            add("profile_allergies", set(prof["allergies_include"]) <= set(state.profile.allergies))
        if "weekly_budget" in prof:
            add("profile_budget", state.profile.weekly_budget == prof["weekly_budget"])
    if days := exp.get("no_session_on"):
        sessions = state.workout_plan.sessions if state.workout_plan else []
        add(
            "no_session_on",
            bool(sessions) and not {s.day for s in sessions} & set(days),
            f"{[s.day for s in sessions]}",
        )
    if sport := exp.get("no_legs_before"):
        before = DAYS[(DAYS.index(sport) - 1) % 7]
        sessions = state.workout_plan.sessions if state.workout_plan else []
        add("no_legs_before_sport", all(not (s.day == before and s.focus.startswith(LEG_FOCUS)) for s in sessions))
    return checks


def make_state(case: dict) -> UserState:
    state = UserState.demo()
    if overrides := case.get("profile"):
        state.profile = Profile(**{**state.profile.model_dump(), **overrides})
    if "pantry" in case:
        state.pantry = dict(case["pantry"])
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", help="offline | anthropic | azure")
    parser.add_argument("--judge", action="store_true", help="also score replies with an LLM judge")
    parser.add_argument("--only", help="comma-separated case ids")
    parser.add_argument("--min-pass", type=float, default=0.9, help="fail below this case pass rate")
    args = parser.parse_args()

    cases = json.loads((Path(__file__).parent / "cases.json").read_text())
    if args.only:
        wanted = set(args.only.split(","))
        cases = [c for c in cases if c["id"] in wanted]

    provider = get_provider(args.provider)
    agent = FitBasketAgent(provider)
    judge_provider = provider if args.judge and provider.name != "offline" else None

    rows = []
    for case in cases:
        state = make_state(case)
        res = agent.run(state, case["message"])
        checks = grade(case, res, state)
        judged = judge_reply(judge_provider, case["message"], res) if judge_provider else None
        rows.append(
            {
                "id": case["id"],
                "passed": all(ok for _, ok, _ in checks),
                "checks": [{"check": c, "ok": ok, "detail": d} for c, ok, d in checks],
                "latency_ms": res.latency_ms,
                "input_tokens": res.usage.input_tokens,
                "output_tokens": res.usage.output_tokens,
                "tools": [e.name for e in res.tool_events],
                "judge": judged,
                "reply": res.reply,
            }
        )
        mark = "PASS" if rows[-1]["passed"] else "FAIL"
        print(f"{mark}  {case['id']:<32} {res.latency_ms:>8.0f} ms  " + ", ".join(c for c, ok, _ in checks if not ok))

    passed = sum(r["passed"] for r in rows)
    lat = sorted(r["latency_ms"] for r in rows)
    summary = {
        "provider": provider.name,
        "model": provider.model,
        "cases": len(rows),
        "passed": passed,
        "pass_rate": round(passed / max(len(rows), 1), 3),
        "latency_p50_ms": round(statistics.median(lat), 1) if lat else 0,
        "latency_p95_ms": round(lat[min(len(lat) - 1, int(0.95 * len(lat)))], 1) if lat else 0,
        "tokens_in": sum(r["input_tokens"] for r in rows),
        "tokens_out": sum(r["output_tokens"] for r in rows),
    }
    scored = [r["judge"] for r in rows if r["judge"] and "overall" in r["judge"]]
    if scored:
        summary["judge_mean_overall"] = round(statistics.mean(j["overall"] for j in scored), 2)
    write_reports(summary, rows)
    print(json.dumps(summary, indent=2))
    return 0 if summary["pass_rate"] >= args.min_pass else 1


def write_reports(summary: dict, rows: list[dict]) -> None:
    out = Path(__file__).parent / "reports"
    out.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (out / f"{summary['provider']}-{stamp}.json").write_text(json.dumps({"summary": summary, "cases": rows}, indent=2))
    lines = [
        f"# Eval report: {summary['provider']} ({summary['model']})",
        "",
        f"**{summary['passed']}/{summary['cases']} cases passed** ({summary['pass_rate']:.0%}). "
        f"Latency p50 {summary['latency_p50_ms']} ms, p95 {summary['latency_p95_ms']} ms. "
        f"Tokens {summary['tokens_in']} in / {summary['tokens_out']} out.",
        "",
        "| Case | Result | Failed checks | Judge |",
        "|---|---|---|---|",
    ]
    for r in rows:
        failed = ", ".join(c["check"] for c in r["checks"] if not c["ok"]) or "-"
        judge = r["judge"]["overall"] if r["judge"] and "overall" in r["judge"] else "-"
        lines.append(f"| {r['id']} | {'pass' if r['passed'] else 'FAIL'} | {failed} | {judge} |")
    (out / f"latest-{summary['provider']}.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
