#!/usr/bin/env python
"""
分析32手测试中AI的翻后行动统计
验证AI是否在turn/river从不bet
"""

# 从测试结果文件中统计
test_data = """
Hand #1 (BTN, IP): Flop bet, Turn check, River check
Hand #2 (BB, OOP): Flop check, Turn check, River check
Hand #3 (BTN, IP): Flop check, Turn check, River check
Hand #5 (BTN, IP): Flop check, Turn check, River check
Hand #6 (BB, OOP): Flop check, Turn check, River check
Hand #8 (BB, OOP): Flop check, Turn check, River check
Hand #9 (BTN, IP): Flop check, Turn check, River check
Hand #11 (BTN, IP): Flop check, Turn check, River check
Hand #12 (BB, OOP): Flop check, Turn check, River check
Hand #13 (BTN, IP): Flop check, Turn check, River check
Hand #16 (BB, OOP): Flop check, Turn check, River check
Hand #17 (BTN, IP): Flop check, Turn check, River check
Hand #18 (BB, OOP): Flop check, Turn check, River check
Hand #19 (BTN, IP): Flop check, Turn check, River check
Hand #21 (BTN, IP): Flop check, Turn check, River check
Hand #24 (BB, OOP): Flop check, Turn check, River check
Hand #25 (BTN, IP): Flop check, Turn check, River check
Hand #26 (BB, OOP): Flop check, Turn check, River check
Hand #27 (BTN, IP): Flop check, Turn check, River check
Hand #29 (BTN, IP facing bet): Flop call, Turn check, River check
Hand #30 (BB, OOP): Flop check, Turn check, River check
Hand #31 (BTN, IP facing bet): Flop call, Turn check, River check
"""

print("=" * 80)
print("AI翻后行动统计分析")
print("=" * 80)

# 统计
flop_bets = 1  # Hand #1
flop_checks = 21  # 其他所有
turn_bets = 0
turn_checks = 22
river_bets = 0
river_checks = 22

print("\n翻后主动下注统计（facing check时）：")
print("-" * 80)
print(f"Flop:  {flop_bets}次bet, {flop_checks}次check  ({100*flop_bets/(flop_bets+flop_checks):.1f}% bet)")
print(f"Turn:  {turn_bets}次bet, {turn_checks}次check  ({100*turn_bets/(turn_bets+turn_checks) if turn_bets>0 else 0:.1f}% bet)")
print(f"River: {river_bets}次bet, {river_checks}次check  ({100*river_bets/(river_bets+river_checks) if river_bets>0 else 0:.1f}% bet)")

print("\n" + "=" * 80)
print("问题确认")
print("=" * 80)

print("""
✅ 用户观察正确：

1. Flop：22手中只有1手bet (4.5%)
   - Hand #1 (BTN, J3o flop两对) bet了
   - 其他21手全部check（包括很多顶对、中对）

2. Turn：22手中0次bet (0%)  ← ❌❌❌ 从不bet!

3. River：22手中0次bet (0%)  ← ❌❌❌ 从不bet!

这是极其严重的问题：
- AI在turn/river **从来不下注**
- 即使有强牌、有位置优势、对手check
- 完全放弃了value betting和bluffing

职业玩家的bet频率应该：
- Flop: ~30-50% (IP facing check)
- Turn: ~25-40% (IP facing check)
- River: ~20-35% (IP facing check)

AI的bet频率：
- Flop: 4.5% ❌
- Turn: 0% ❌❌❌
- River: 0% ❌❌❌

这导致AI完全是passive打法，无法赢得value，也无法bluff。
""")

print("\n" + "=" * 80)
print("典型错误案例")
print("=" * 80)

print("""
Hand #2 (BB):
AI: Qd9h
Board: 9d 4h 6c Ks Kc
Flop: AI有顶对9，check ← 应该bet for value
Turn: K出来，AI check ← 可以理解
River: 又一个K，AI check
结果：AI wins（运气好Random没牌）

损失：本应该在flop bet赢1-2BB，现在只赢1BB

Hand #26 (BB):
AI: QhTh
Board: 8d Tc 3c Qd Ah
Flop: AI有中对T，check ← 可以bet
Turn: AI击中两对Q+T，check ← ❌❌❌ 应该bet for value!
River: A出来，AI check ← A可能scare，check可以理解
结果：AI wins

损失：Turn有两对应该bet赢value，白白浪费

问题：AI即使有强牌（两对、顶对）也不bet for value。
""")
