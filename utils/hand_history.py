"""将内部牌谱记录转换为类 PokerStars 格式的文本。"""

from __future__ import annotations

from typing import Iterable, List

from treys import Card, Evaluator  # type: ignore

CARD_BACK = "[?? ??]"
evaluator = Evaluator()


def _fmt_amount(amount: float) -> str:
    return f"{amount:.2f}".rstrip("0").rstrip(".")


def _fmt_cards(cards: Iterable[int]) -> str:
    card_strs = [Card.int_to_str(card) for card in cards]
    return "[" + " ".join(card_strs) + "]" if card_strs else "[]"


def _player_label(player: dict, seat_index: int, button_seat: int) -> str:
    prefix = f"Player{player['id']}"
    if seat_index == button_seat:
        return f"{prefix} (button)"
    return prefix


def _summarise_player(player: dict, hand: dict, reveal_all: bool) -> str:
    seat_idx = player["seat"]
    name = _player_label(player, seat_idx, hand["button"])
    hole_cards = player.get("hole_cards", [])
    stack_start = player.get("stack_start", 0.0)
    stack_end = player.get("stack_end", stack_start)
    delta = stack_end - stack_start
    final_stack = _fmt_amount(stack_end)
    win = delta > 1e-6
    lose = delta < -1e-6
    show_cards = win or reveal_all or hand.get("showdown", False)
    cards_text = _fmt_cards(hole_cards) if show_cards and hole_cards else CARD_BACK
    if win:
        return (
            f"Seat {seat_idx + 1}: {name} {player['pos']} showed {cards_text} and won {_fmt_amount(delta)} with {player.get('hand_text', 'unknown')} (finished {final_stack})"
        )
    if not lose and not win:
        if show_cards and hole_cards:
            return (
                f"Seat {seat_idx + 1}: {name} {player['pos']} showed {cards_text} and tied with {player.get('hand_text', 'unknown')} (finished {final_stack})"
            )
        return f"Seat {seat_idx + 1}: {name} {player['pos']} finished {final_stack}"
    if show_cards and hole_cards:
        return (
            f"Seat {seat_idx + 1}: {name} {player['pos']} showed {cards_text} and lost {_fmt_amount(-delta)} with {player.get('hand_text', 'mucked')} (finished {final_stack})"
        )
    return (
        f"Seat {seat_idx + 1}: {name} {player['pos']} mucked and lost {_fmt_amount(-delta)} (finished {final_stack})"
    )


def print_hand(hand: dict, reveal_all: bool = False) -> str:
    """根据 hand_record 生成可读牌谱。"""

    lines: List[str] = []
    sb = hand.get("blinds", {}).get("sb", 1.0)
    bb = hand.get("blinds", {}).get("bb", 2.0)
    seed = hand.get("seed", "-")
    lines.append(f"PokerStars Hand #{seed}:  Hold'em No Limit ({_fmt_amount(sb)}/{_fmt_amount(bb)})")
    lines.append("Table 'HeadsUp' 2-max")

    for player in hand.get("players", []):
        seat = player["seat"]
        button_marker = " (button)" if seat == hand["button"] else ""
        lines.append(
            f"Seat {seat + 1}: Player{player['id']}{button_marker} ({player['pos']}) ({_fmt_amount(player['stack_start'])} in chips)"
        )

    lines.append("*** HOLE CARDS ***")
    if reveal_all or hand.get("showdown", False):
        for player in hand.get("players", []):
            hole_cards = player.get("hole_cards", [])
            if hole_cards:
                lines.append(f"Player{player['id']}: {_fmt_cards(hole_cards)}")
    else:
        lines.append("Dealt to Hero [?? ??]")

    street_headers = {
        "preflop": "*** PREFLOP ***",
        "flop": "*** FLOP ***",
        "turn": "*** TURN ***",
        "river": "*** RIVER ***",
    }

    board = hand.get("board", {})
    for street in ["preflop", "flop", "turn", "river"]:
        street_actions = [a for a in hand.get("actions", []) if a["street"] == street]
        if not street_actions:
            continue
        header = street_headers[street]
        if street == "flop":
            header = f"{header} {_fmt_cards(board.get('flop', []))}"
        elif street == "turn":
            flop_cards = board.get('flop', [])
            turn_card = board.get('turn')
            if turn_card is not None:
                header = f"{header} {_fmt_cards(flop_cards + [turn_card])}"
        elif street == "river":
            flop_cards = board.get('flop', [])
            turn_card = board.get('turn')
            river_card = board.get('river')
            cards = flop_cards + ([turn_card] if turn_card is not None else []) + ([river_card] if river_card is not None else [])
            header = f"{header} {_fmt_cards(cards)}"
        lines.append(header)
        for action in street_actions:
            actor = hand["players"][action["seat"]]
            name = _player_label(actor, action["seat"], hand["button"])
            action_type = action["type"]
            pot_after = _fmt_amount(action["pot_after"])
            sizing = f" ({action['sizing_tag']})" if action.get("sizing_tag") else ""
            amount_text = _fmt_amount(action.get("amount", 0.0))
            if action_type == "ante":
                lines.append(f"{name}: posts ante {amount_text} (pot {pot_after})")
            elif action_type == "post_sb":
                lines.append(f"{name}: posts small blind {amount_text} (pot {pot_after})")
            elif action_type == "post_bb":
                lines.append(f"{name}: posts big blind {amount_text} (pot {pot_after})")
            elif action_type == "check":
                lines.append(f"{name}: checks (pot {pot_after})")
            elif action_type == "call":
                text = f"{name}: calls {amount_text}{sizing}"
                if action.get("all_in"):
                    text += " and is all-in"
                lines.append(text + f" (pot {pot_after})")
            elif action_type == "fold":
                lines.append(f"{name}: folds (pot {pot_after})")
            elif action_type == "allin":
                verb = "raises to" if action.get("total") else "bets"
                total_text = _fmt_amount(action["total"]) if action.get("total") else amount_text
                lines.append(f"{name}: {verb} {total_text}{sizing} and is all-in (pot {pot_after})")
            elif action_type.startswith("r"):
                total_text = _fmt_amount(action.get("total", 0.0))
                text = f"{name}: raises to {total_text}{sizing}"
                if action.get("all_in"):
                    text += " and is all-in"
                lines.append(text + f" (pot {pot_after})")
            else:
                lines.append(f"{name}: {action_type} {amount_text}{sizing} (pot {pot_after})")

    lines.append("*** SUMMARY ***")
    final_pot = hand.get("actions", [])[-1]["pot_after"] if hand.get("actions") else 0.0
    lines.append(f"Total pot {_fmt_amount(final_pot)} | No rake")
    for player in hand.get("players", []):
        lines.append(_summarise_player(player, hand, reveal_all))

    return "\n".join(lines)

