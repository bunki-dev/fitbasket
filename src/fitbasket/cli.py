"""Chat with FitBasket in the terminal: `fitbasket` (uses LLM_PROVIDER, default offline)."""

from __future__ import annotations

import argparse

from .agent.agent import FitBasketAgent
from .agent.providers.base import get_provider
from .store import UserState


def main() -> None:
    parser = argparse.ArgumentParser(description="FitBasket CLI")
    parser.add_argument("--provider", help="offline | anthropic | azure (default: $LLM_PROVIDER or offline)")
    parser.add_argument("--blank", action="store_true", help="start with an empty profile instead of the demo one")
    parser.add_argument("-m", "--message", help="send one message and exit")
    args = parser.parse_args()

    agent = FitBasketAgent(get_provider(args.provider))
    state = UserState() if args.blank else UserState.demo()
    history = []
    print(f"FitBasket ({agent.provider.name}: {agent.provider.model}). Ctrl+C to quit.\n")

    def turn(text: str) -> None:
        nonlocal history
        res = agent.run(state, text, history)
        history = res.history
        tools = ", ".join(e.name + ("" if e.ok else " (error)") for e in res.tool_events) or "none"
        print(
            f"\nFitBasket: {res.reply}\n  [tools: {tools} | {res.latency_ms:.0f} ms | "
            f"{res.usage.input_tokens}+{res.usage.output_tokens} tokens]\n"
        )

    if args.message:
        turn(args.message)
        return
    try:
        while True:
            text = input("You: ").strip()
            if text:
                turn(text)
    except (KeyboardInterrupt, EOFError):
        print()


if __name__ == "__main__":
    main()
