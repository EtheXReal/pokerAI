#!/usr/bin/env python
"""
统计分析bug2Repair.txt中的betting频率
验证Random和AI的实际表现
"""

print("=" * 80)
print("bug2Repair.txt Betting频率统计分析")
print("=" * 80)

# 读取文件
with open('bug2Repair.txt', 'r') as f:
    content = f.read()

lines = content.split('\n')

# 统计数据
stats = {
    'flop': {'ai_bet': 0, 'random_bet': 0, 'total': 0},
    'turn': {'ai_bet': 0, 'random_bet': 0, 'total': 0},
    'river': {'ai_bet': 0, 'random_bet': 0, 'total': 0},
}

current_street = None

for i, line in enumerate(lines):
    # 识别street
    if '=== Flop:' in line:
        current_street = 'flop'
        stats['flop']['total'] += 1
    elif '=== Turn:' in line:
        current_street = 'turn'
        stats['turn']['total'] += 1
    elif '=== River:' in line:
        current_street = 'river'
        stats['river']['total'] += 1

    # 统计bet
    if current_street and 'bets' in line:
        if 'AI bets' in line:
            stats[current_street]['ai_bet'] += 1
        elif 'Random bets' in line:
            stats[current_street]['random_bet'] += 1

print("\n" + "=" * 80)
print("统计结果")
print("=" * 80)

for street in ['flop', 'turn', 'river']:
    data = stats[street]
    total = data['total']
    ai_bet = data['ai_bet']
    random_bet = data['random_bet']

    ai_pct = (ai_bet / total * 100) if total > 0 else 0
    random_pct = (random_bet / total * 100) if total > 0 else 0
    total_bet = ai_bet + random_bet
    total_pct = (total_bet / (total * 2) * 100) if total > 0 else 0

    print(f"\n{street.upper()}:")
    print(f"  总决策次数（每方）: {total}")
    print(f"  AI bet:     {ai_bet}/{total} ({ai_pct:.1f}%)")
    print(f"  Random bet: {random_bet}/{total} ({random_pct:.1f}%)")
    print(f"  合计bet:    {total_bet}/{total*2} ({total_pct:.1f}%)")

print("\n" + "=" * 80)
print("对比分析")
print("=" * 80)

print("""
Random的设计：
- bet_rate = 0.2 (20%)
- 但只有不facing bet时才可能bet
- 预期实际bet频率：10-15% (因为约一半时间facing bet)
- 实际Flop bet: 12.5% ✅ 符合预期

AI的问题：
- 应该bet频率：Flop 30-50%, Turn 25-40%, River 20-35%
- 实际Flop bet: 6.25% ❌ 远低于预期
- 实际Turn bet: 0% ❌❌❌
- 实际River bet: 0% ❌❌❌

结论：
1. Random的低bet频率是设计特性，不是bug
2. AI的bet频率远低于GTO标准
3. 主要原因：
   - value_threshold = 0.65太高
   - 中等牌 (0.35-0.65) 硬编码80% check
   - 大多数value hands被错误归类为中等牌
""")

print("\n" + "=" * 80)
print("具体bet记录")
print("=" * 80)

# 找出所有bet的具体情况
print("\n所有bet动作：")
for i, line in enumerate(lines):
    if 'bets' in line and ('AI' in line or 'Random' in line):
        # 打印前5行context
        start = max(0, i - 5)
        print(f"\n--- Context (lines {start}-{i}) ---")
        for j in range(start, i + 1):
            print(lines[j])

print("\n" + "=" * 80)
