"""命令行人工测试脚本，可与环境/AI 交互验证下注与买入逻辑。

运行示例：
    python scripts/manual_play.py --players 3 --seed 123 --hands 2 --hero-buyin 50000
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path
import sys
from typing import Optional

from treys import Card  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from env.engine import HeadsUpPokerEnv
from utils.hand_history import print_hand

EPS = 1e-6
TABLE_SB = 500.0
TABLE_BB = 1000.0
BUYIN_RANGE = (10_000.0, 200_000.0)
AI_BANKROLL = 1_000_000.0


def format_cards(cards: list[int]) -> str:
    return " ".join(Card.int_to_str(card) for card in cards) if cards else "--"


def fmt_chips(amount: float) -> str:
    if abs(amount) >= 1000:
        value = amount / 1000.0
        text = f"{value:.1f}".rstrip("0").rstrip(".")
        return f"{text}k"
    return f"{amount:.0f}"


def show_prompt(state: dict) -> None:
    board = state.get("board_cards", [])
    recent = state.get("last_actions", [])
    print("-" * 64)
    print(
        f"Street: {state['street']} | Pot: {fmt_chips(state['pot'])} | ToCall: {fmt_chips(state['to_call'])}"
    )
    print(
        f"Hero Stack/Bankroll: {fmt_chips(state['hero_stack'])} / {fmt_chips(state.get('hero_bankroll', 0.0))}"
    )
    print(f"Board: {' '.join(board) if board else '--'}")
    print(f"Your cards: {format_cards(state.get('hole_cards', []))}")
    if recent:
        print("最近动作：")
        for action in recent:
            actor = action.get("actor")
            action_type = action.get("action")
            size = action.get("size", 0.0)
            print(f"  {actor}: {action_type} ({fmt_chips(size)})")
    print("可输入：fold/call/check/allin/bet X/raise X，例如 'bet 12' 或 'raise 30'")


def parse_user_action(text: str, to_call: float) -> tuple[str, Optional[float]]:
    parts = text.strip().split()
    if not parts:
        raise ValueError("需要输入动作。")
    action = parts[0].lower()
    amount = float(parts[1]) if len(parts) > 1 else None
    if action == "bet" and to_call > EPS:
        action = "raise"
    if action == "check" and to_call > EPS:
        action = "call"
    return action, amount


def ai_policy(rng: random.Random, legal_mask: list[bool]) -> int:
    candidates = [idx for idx, flag in enumerate(legal_mask) if flag]
    if not candidates:
        raise RuntimeError("AI 找不到合法动作。")
    return rng.choice(candidates)


def print_table_state(env: HeadsUpPokerEnv, hero_seat: int) -> None:
    print("\n座位信息：")
    for player in env.players:
        label = "You" if player.seat_id == hero_seat else f"P{player.seat_id}"
        stack_txt = fmt_chips(player.stack)
        bank_txt = fmt_chips(player.bankroll)
        print(
            f"  Seat {player.seat_id}: {label} | Stack {stack_txt} | Bankroll {bank_txt}"
        )


def handle_ai_action(env: HeadsUpPokerEnv, seat: int) -> None:
    if not env.hand_record["actions"]:
        return
    action = env.hand_record["actions"][-1]
    actor = action.get("type")
    amount = action.get("amount", 0.0)
    total = action.get("total")
    size = total if total is not None else amount
    print(
        f"[AI Seat {seat}] {actor} ({fmt_chips(size)})"
    )


def prompt_rebuy(env: HeadsUpPokerEnv, hero_seat: int) -> bool:
    while True:
        cmd = input("输入 'buy 金额' 补码，回车继续，或输入 quit 退出: ").strip()
        if not cmd:
            return True
        lowered = cmd.lower()
        if lowered == "quit":
            return False
        if lowered.startswith("buy"):
            parts = cmd.split()
            if len(parts) != 2:
                print("格式：buy 50000")
                continue
            try:
                amount = float(parts[1])
            except ValueError:
                print("金额必须为数字。")
                continue
            try:
                invested = env.rebuy_player(hero_seat, amount)
                player = env.players[hero_seat]
                print(
                    f"补码成功：+{fmt_chips(invested)}，当前 Stack={fmt_chips(player.stack)}，Bankroll={fmt_chips(player.bankroll)}"
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[错误] {exc}")
        else:
            print("未知指令。")


def run_manual(
    seed: int,
    n_players: int,
    hero_seat: int,
    hero_bankroll: float,
    hero_buyin: float,
    hands: int,
) -> None:
    rng = random.Random(seed + 99)
    bankrolls = [AI_BANKROLL for _ in range(n_players)]
    bankrolls[hero_seat] = hero_bankroll
    env = HeadsUpPokerEnv(
        blinds=(TABLE_SB, TABLE_BB),
        ante=0.0,
        num_players=n_players,
        buyin_range=BUYIN_RANGE,
        initial_bankroll=AI_BANKROLL,
        bankrolls=bankrolls,
    )
    env.set_player_buyin(hero_seat, hero_buyin, apply_blind=False)

    for hand_idx in range(hands):
        state, legal = env.reset(seed=seed + hand_idx)
        print_table_state(env, hero_seat)
        done = False
        while not done:
            seat = env.current_player
            if seat == hero_seat:
                show_prompt(state)
                while True:
                    try:
                        user_input = input("你的动作> ")
                    except EOFError:
                        print("\n输入结束，默认弃牌。")
                        user_input = "fold"
                    try:
                        action, amount = parse_user_action(user_input, state["to_call"])
                        state, legal, _, done, _ = env.step_command(action, amount)
                        break
                    except Exception as exc:  # noqa: BLE001
                        print(f"[错误] {exc}")
            else:
                action_idx = ai_policy(rng, legal)
                state, legal, _, done, _ = env.step(action_idx)
                handle_ai_action(env, seat)

        hand_record = env.get_hand_record()
        print("\n=== 手牌回放 ===")
        print(print_hand(hand_record, reveal_all=True))
        hero = env.players[hero_seat]
        print(
            f"手牌结束：Hero stack={fmt_chips(hero.stack)}, bankroll={fmt_chips(hero.bankroll)}"
        )
        if hand_idx < hands - 1:
            if not prompt_rebuy(env, hero_seat):
                break


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="手动测试 CLI，可与环境/AI 对局。")
    parser.add_argument("--seed", type=int, default=42, help="环境种子，保证复现。")
    parser.add_argument(
        "--players", type=int, default=2, help="桌上玩家数（含人类），范围 2-5。"
    )
    parser.add_argument("--hero-seat", type=int, default=0, help="人类所在的座位 ID。")
    parser.add_argument(
        "--hero-bankroll",
        type=float,
        default=AI_BANKROLL,
        help="人类初始场外筹码（默认 1M）。",
    )
    parser.add_argument(
        "--hero-buyin",
        type=float,
        default=BUYIN_RANGE[1],
        help="开局买入筹码，范围 10k-200k。",
    )
    parser.add_argument(
        "--hands", type=int, default=1, help="本次交互要打多少手牌。"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if not (2 <= args.players <= 5):
        raise SystemExit("players 必须在 2~5 范围。")
    if not (0 <= args.hero_seat < args.players):
        raise SystemExit("hero-seat 必须在座位范围内。")
    run_manual(
        seed=args.seed,
        n_players=args.players,
        hero_seat=args.hero_seat,
        hero_bankroll=args.hero_bankroll,
        hero_buyin=args.hero_buyin,
        hands=args.hands,
    )
