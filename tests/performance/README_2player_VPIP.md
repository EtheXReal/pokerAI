# Understanding VPIP in 2-Player Poker

## Summary

The styled players' VPIP targets (e.g., Fish 58%, Maniac 75%) represent their **strategic VPIP** - how often they choose to play when given the opportunity. However, their **realized VPIP** in actual games will be lower due to opponent folding preflop.

## The Math

### Example: Fish (58% Target VPIP) vs TAG Opponent

In our 500-hand test:

| Position | Hands | TAG Action | Fish Gets Decision? | Fish VPIP When Acting |
|----------|-------|------------|---------------------|-----------------------|
| Button (SB) | 250 | N/A | Yes | 144/250 = **57.6%** ✓ |
| BB | 250 | Fold 66% | No (165 hands) | N/A |
| BB | 250 | Raise 28% | Yes (71 hands) | 38/71 = **53.5%** ✓ |
| BB | 250 | Limp 6% | Yes (14 hands) | 5/14 = 35.7% |

**When Fish gets to act**: 187 VPIP / 335 opportunities = **55.8% strategic VPIP** ✓

**Realized VPIP** (what stats show): 187 VPIP / 500 hands = **37.4%**

## Why Realized VPIP is Lower

In 2-player poker:
1. You're always in a blind (50% Button/SB, 50% BB)
2. When opponent folds from Button, you win blinds without making a decision
3. These "free win" hands count as hands played but not VPIP opportunities
4. With a tight opponent (TAG folds 66% from Button), you get **fewer chances** to demonstrate your 58% VPIP

## Validation

| Opponent Type | Strategic VPIP | Realized VPIP | Difference |
|---------------|----------------|---------------|------------|
| Fish | 58% (target) | 55.8% (when acting) | 37.4% (overall) | ✓ Correct |
| Maniac | 75% (target) | ~73% (when acting) | 48.4% (overall) | ✓ Correct |
| Calling Station | 65% (target) | ~62% (when acting) | 44.4% (overall) | ✓ Correct |

## Conclusion

The "low VPIP" is **not a bug** - it's correct 2-player poker dynamics. The styled players ARE using their target VPIP ranges when they get opportunities, but realized VPIP is lower because opponents fold preflop, denying them chances to play.

To see true VPIP targets, test against an opponent who never folds (100% VPIP), or measure VPIP only when the player gets to make a decision.

## Code Fix Applied

We fixed the styled players to properly handle 2-player poker by:
1. Detecting heads-up games (`is_heads_up = num_active_players == 2`)
2. Using appropriate "facing raise" ranges in heads-up (much wider than multi-player)
3. Example for Fish: facing raise range increased from 10% (multi-player) to 55% (heads-up)

This ensures the players maintain their target VPIP *when they get opportunities to act*.
