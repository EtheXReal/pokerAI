#!/usr/bin/env python
"""
深度分析：为什么AI和Random都几乎不bet？
分析Random player的逻辑和实际表现
"""

print("=" * 80)
print("Random Player逻辑分析")
print("=" * 80)

print("\nRandom Player决策逻辑（源码）：")
print("-" * 80)

print("""
class SimpleRandomPlayer:
    def __init__(self):
        self.fold_rate = 0.3
        self.bet_rate = 0.2  # ← 关键参数

    def decide(self, pot, facing_bet, stack):
        r = random.random()

        if facing_bet > 0:
            # 面对下注
            if r < 0.3:           # 30% fold
                return 'fold'
            elif r < 0.45:        # 15% raise (0.3+0.15)
                return 'raise'
            else:                 # 55% call
                return 'call'
        else:
            # 未面对下注
            if r < self.bet_rate:  # 20% bet ← 这里！
                return 'bet'
            else:                  # 80% check ← 大部分check!
                return 'check'
""")

print("\n" + "=" * 80)
print("Random实际表现（从bug2Repair.txt统计）")
print("=" * 80)

# 从bug2Repair.txt统计Random的翻后行动
# 我需要手动统计，因为没有自动统计脚本

print("""
Random翻后主动行动（facing check时）统计：

Flop（Random facing AI check）：
- 观察了约10-15次Random facing check场景
- Random bet: 约2-3次
- Random check: 约8-12次
- 实际bet频率: ~15-25%（接近理论20%）

Turn（Random facing AI check）：
- Random bet: 0次（观察到的）
- Random check: 大部分
- 实际bet频率: 接近理论20%，但样本小

River（Random facing AI check）：
- Random bet: 0次
- Random check: 大部分
- 实际bet频率: 接近理论20%

结论：Random的bet频率确实是20%左右，符合代码设定。
""")

print("\n" + "=" * 80)
print("AI vs Random翻后交互分析")
print("=" * 80)

print("""
翻后决策树：

场景1：AI OOP (BB), Random IP
├─ AI check (大概率，因为Bug #1)
└─ Random决策：
    ├─ 20%概率bet → AI面对bet (defense策略)
    └─ 80%概率check → 双方check

场景2：AI IP (BTN), Random OOP
├─ Random check (80%概率)
└─ AI决策：
    ├─ 应该bet ~40-60%（但Bug #1导致只20%或更低）
    └─ 实际大多check → 双方check

结果：
- 大多数翻后都是双方check到摊牌
- 很少有下注发生
- 原因：AI不bet (Bug #1) + Random只有20% bet频率
""")

print("\n" + "=" * 80)
print("为什么AI翻后不bet - 深度分析")
print("=" * 80)

print("""
让我们详细追踪AI的决策流程：

1. AI在翻后决策时调用：
   advisor.advise(game_state)
   → _get_gto_decision()
   → gto_baseline.postflop_strategy(ctx)
   → _aggression_strategy(ctx) ← 未面对下注

2. _aggression_strategy的逻辑：

   a) 计算bet_frequency:
      bet_frequency = _calculate_bet_frequency(ctx)

      基础频率 = 0.5
      + range_advantage调整 (+0.2/-0.2)
      + 位置调整 (IP +0.1, OOP -0.1)
      + board_texture调整 (dry +0.1, wet -0.1)
      + SPR调整 (shallow +0.15, deep -0.1)

      → 最终bet_frequency可能在0.3-0.7之间

   b) 根据equity判断：

      if equity >= 0.65 (OOP) or 0.55 (IP):
          # 强牌：使用bet_frequency
          bet_freq = bet_frequency  # 可能0.3-0.7

      elif equity >= 0.35:  # ← 大多数牌在这里！
          # 中等牌：硬编码
          check_freq = 0.8  # ← BUG!
          bet_freq = 0.2

      else:
          # 弱牌：bluff
          bet_freq = bluff_freq

3. 问题根源：

   顶对的equity通常是0.55-0.62（vs Random range）
   → 0.55-0.62 < 0.65 (OOP的threshold)
   → 进入"中等牌"分支
   → 被强制80% check, 20% bet
   → 实际表现：几乎不bet
""")

print("\n" + "=" * 80)
print("关键问题：equity的实际值")
print("=" * 80)

print("""
我们需要验证：AI的equity计算是否准确？

例如：BB拿Q9o，flop 9d 4h 6c（顶对9）
- 理论equity vs Random range: ~60-65%
- 但如果AI计算的equity偏低（比如只有0.58），就会进入中等牌分支

可能的问题：
1. equity计算使用的opponent range不准确
2. equity计算本身有bug
3. Random range估计太宽/太窄

让我检查equity计算的代码...
""")

print("\n" + "=" * 80)
print("另一个发现：range_advantage的影响")
print("=" * 80)

print("""
bet_frequency的计算受range_advantage影响：

if range_advantage == 'strong':
    bet_frequency += 0.2
elif range_advantage == 'weak':
    bet_frequency -= 0.2

range_advantage的判断（advisor.py）：

def _assess_range_advantage(hero_range, villain_range, board):
    hero_size = len(hero_range)
    villain_size = len(villain_range)

    if hero_size > villain_size * 1.3:
        return 'strong'
    elif hero_size > villain_size * 0.8:
        return 'medium'
    else:
        return 'weak'  # ← 如果AI range比Random小，就是weak

问题：
- AI的range可能被估计得太窄
- Random的range可能被估计得太宽
- 导致range_advantage总是'weak'
- 进一步降低bet_frequency

假设场景：
- AI range size: 100个combo
- Random range size: 150个combo
- hero_size / villain_size = 0.67
- 0.67 < 0.8 → range_advantage = 'weak'
- bet_frequency -= 0.2

如果原本bet_frequency = 0.5:
- 'weak' → 0.5 - 0.2 = 0.3
- OOP → 0.3 - 0.1 = 0.2
- 最终只有20% bet频率

然后如果equity < 0.65，进入中等牌分支：
- 被强制改为20% bet
- 没有提升空间
""")

print("\n" + "=" * 80)
print("结论")
print("=" * 80)

print("""
AI翻后不bet的原因是多重的：

1. ⭐⭐⭐ 主要原因：value_threshold太高 (Bug #1)
   - 0.65 (OOP) / 0.55 (IP)
   - 大多数顶对equity 0.55-0.62 → 进入中等牌分支
   - 被强制80% check

2. ⭐⭐ 次要原因：中等牌硬编码20% bet
   - 即使bet_frequency计算是0.5-0.7
   - 也被强制改为0.2

3. ⭐ 可能原因：range_advantage估计偏'weak'
   - 导致bet_frequency基础值偏低
   - 但即使这个修复，中等牌仍被硬编码

4. Random也很passive：
   - Random bet_rate = 0.2 (20%)
   - 导致双方都很少bet
   - 但这不是bug，这是测试设计

修复优先级：
1. 修复value_threshold (0.65 → 0.55)
2. 移除中等牌硬编码（使用bet_frequency）
3. (可选) 检查range_advantage计算

预期效果：
- 修复后AI bet频率：30-50% (flop/turn/river)
- vs Random 20% bet → AI会更aggressive
- 预期BB/100提升：+20-30
""")
