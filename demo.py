#!/usr/bin/env python3
"""Demo runner — plays the rehearsed Demo Day conversation against the real API.

    export ANTHROPIC_API_KEY=sk-ant-...
    python demo.py                # scripted run
    python demo.py --interactive  # chat freely
"""

from __future__ import annotations

import sys

from tripsmart.agent import TripSmartAgent
from tripsmart.memory import Memory

CYAN, GREEN, GREY, YELLOW, RESET = "\033[36m", "\033[32m", "\033[90m", "\033[33m", "\033[0m"

SCRIPT = [
    "Mình muốn đi Bangkok cuối tháng 8, budget 8 triệu, 2 người",
    "Từ TP.HCM, 28/08 đến 31/08",
    "Mình đi với con nhỏ 4 tuổi thì cần chuẩn bị gì?",
    "Đặt lựa chọn đầu tiên đi",
]

# Off-script questions worth rehearsing — these exercise the "answer directly"
# path and the domestic-travel rule rather than the booking loop.
EXTRAS = [
    "Tôi tham gia buổi hòa nhạc tại sân vận động Mỹ Đình Hà Nội, tôi nên ở chỗ nào để tiện cho việc di chuyển",
    "Tìm khách sạn gần sân Mỹ Đình cho tôi",
]


def main() -> int:
    interactive = "--interactive" in sys.argv

    # Fresh in-memory DB so demo runs are reproducible.
    memory = Memory(":memory:")
    agent = TripSmartAgent(memory=memory)
    user_id = "demo-user"

    def turn(msg: str) -> None:
        print(f"\n{CYAN}👤 User:{RESET} {msg}")
        result = agent.handle_message(user_id, msg)
        if result.blocked:
            print(f"{YELLOW}[guard: {result.blocked}]{RESET}")
        if result.reply:
            print(f"{GREEN}🤖 TripSmart:{RESET} {result.reply}")
        if result.card:
            print(f"{GREY}[card] {result.card}{RESET}")

    if interactive:
        print("Interactive mode. Type a message, or 'exit' to quit.\n")
        while True:
            try:
                line = input("👤 You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line or line.lower() == "exit":
                break
            turn(line)
    else:
        for msg in SCRIPT:
            turn(msg)
        if "--extras" in sys.argv:
            print(f"\n{GREY}--- off-script questions ---{RESET}")
            for msg in EXTRAS:
                turn(msg)
        print("\n--- usage today ---")
        print(memory.usage_today(user_id))
        print("\n--- stored preferences ---")
        print(memory.get_preferences(user_id))

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"\nDemo failed: {exc}")
        import os

        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("Hint: ANTHROPIC_API_KEY is not set.")
        raise SystemExit(1)
