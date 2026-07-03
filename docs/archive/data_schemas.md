## Data Schemas

### A. Advisor Input (Env -> Advisor)

```json
{
  "street": "preflop|flop|turn|river",
  "btn_is_hero": true,
  "hero_stack": 120.0,
  "villain_stack": 110.0,
  "pot": 9.0,
  "to_call": 3.0,
  "hero_invested_this_round": 0.0,
  "last_raise_amount": 2.0,
  "min_raise_to": 15.0,
  "max_raise_to": 112.0,
  "board": ["Kh", "7d", "2c"],
  "hero_hole": ["As", "Kd"],
  "last_actions": [
    {"actor": "V", "street": "flop", "action": "bet", "size": 6.0},
    {"actor": "H", "street": "flop", "action": "call", "size": 6.0}
  ],
  "legal_mask": [true, true, true, true, true, true],
  "bb": 1.0,
  "seed": 42
}
```

Key fields:
- `street`: current betting street.
- `btn_is_hero`: whether the button (always SB in HU) is the hero.
- `hero_stack` / `villain_stack`: effective stacks.
- `pot`: pot size before acting; `to_call`: chips needed to call.
- `hero_invested_this_round`: hero contribution this street.
- `last_raise_amount`, `min_raise_to`, `max_raise_to`: raise constraints derived by the engine.
- `board` / `hero_hole`: public cards and hero hole cards (flop empty preflop).
- `last_actions`: optional action trace for UI / logging.
- `legal_mask`: boolean array aligned with `[fold, call, r33, r66, r100, allin]`.
- `bb`: big blind size for context; `seed`: optional shuffle seed.

### B. Advisor Output (Advisor -> Env/UI)

```json
{
  "action": "r66",
  "amount": 12.0,
  "probs": {
    "fold": 0.05,
    "call": 0.25,
    "r33": 0.20,
    "r66": 0.35,
    "r100": 0.05,
    "allin": 0.10
  },
  "ev_hint": {
    "approx_win_prob": 0.62,
    "spr": 3.1
  },
  "rationale": "Dry board + range advantage -> bet 2/3 pot",
  "latency_ms": 4
}
```

Fields:
- `action`: chosen discrete action; `amount`: accompanying bet/raise-to amount.
- `probs`: full action distribution (aligned with action set).
- `ev_hint`: optional win-probability / SPR hints.
- `rationale`: human-readable explanation; `latency_ms`: response latency.

### C. Hand Record (Env -> Logging/Replay)

Schema excerpt:
- `players[]`: `{id, seat, pos, stack_start, stack_end, hole_cards, hand_text}`
- `actions[]`: `{street, seat, actor, type, amount, total, sizing_tag, pot_before, pot_after, all_in}`
- `board`: `{flop: [c1,c2,c3], turn: c4, river: c5}`
- `streets`: `{flop, turn, river}` duplicates board state for quick access.
- `winners[]`: entries with `{seat, amount}` (positive net gain); `showdown`: boolean flag.

Amounts are stored as floats (two-decimal friendly). Cards are treys integers in the raw record; rendering helpers (e.g., `utils.hand_history.print_hand`) convert them to strings and can hide hole cards unless `reveal_all=True`.
