"""
可视化AI的盈亏曲线
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import matplotlib.pyplot as plt
import pandas as pd

# Read profit curve data
data_file = os.path.join(os.path.dirname(__file__), "../../test_results/profit_curve.csv")

if not os.path.exists(data_file):
    print(f"❌ 数据文件不存在: {data_file}")
    print(f"请先运行: python analyze_long_run.py")
    sys.exit(1)

df = pd.read_csv(data_file)

# Create figure with 2 subplots
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

# Plot 1: Cumulative profit curve
ax1.plot(df['hand_num'], df['cumulative_profit'], linewidth=2, color='#2196F3')
ax1.axhline(y=0, color='red', linestyle='--', alpha=0.5, linewidth=1)
ax1.axvline(x=30, color='orange', linestyle='--', alpha=0.7, linewidth=1.5, label='Exploit开始应用 (手30)')
ax1.fill_between(df['hand_num'], 0, df['cumulative_profit'],
                  where=(df['cumulative_profit'] >= 0), alpha=0.3, color='green', label='盈利区域')
ax1.fill_between(df['hand_num'], 0, df['cumulative_profit'],
                  where=(df['cumulative_profit'] < 0), alpha=0.3, color='red', label='亏损区域')

ax1.set_xlabel('手数', fontsize=12)
ax1.set_ylabel('累计盈亏 (BB)', fontsize=12)
ax1.set_title('AI vs MANIAC 盈亏曲线 (400手)', fontsize=14, fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.legend(loc='best')

# Annotate key points
final_profit = df['cumulative_profit'].iloc[-1]
hand_30_profit = df[df['hand_num'] == 30]['cumulative_profit'].values[0]
max_profit = df['cumulative_profit'].max()
max_profit_hand = df[df['cumulative_profit'] == max_profit]['hand_num'].values[0]
min_profit = df['cumulative_profit'].min()
min_profit_hand = df[df['cumulative_profit'] == min_profit]['hand_num'].values[0]

ax1.annotate(f'手30: {hand_30_profit:+.1f}BB',
             xy=(30, hand_30_profit), xytext=(50, hand_30_profit + 200),
             arrowprops=dict(arrowstyle='->', color='orange', lw=1.5),
             fontsize=10, bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7))

ax1.annotate(f'最高点 (手{max_profit_hand:.0f}): {max_profit:+.1f}BB',
             xy=(max_profit_hand, max_profit), xytext=(max_profit_hand + 50, max_profit - 300),
             arrowprops=dict(arrowstyle='->', color='green', lw=1.5),
             fontsize=10, bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgreen', alpha=0.7))

ax1.annotate(f'最低点 (手{min_profit_hand:.0f}): {min_profit:+.1f}BB',
             xy=(min_profit_hand, min_profit), xytext=(min_profit_hand + 50, min_profit + 300),
             arrowprops=dict(arrowstyle='->', color='red', lw=1.5),
             fontsize=10, bbox=dict(boxstyle='round,pad=0.5', facecolor='lightcoral', alpha=0.7))

ax1.annotate(f'终点 (手400): {final_profit:+.1f}BB',
             xy=(400, final_profit), xytext=(350, final_profit + 200),
             arrowprops=dict(arrowstyle='->', color='blue', lw=1.5),
             fontsize=10, bbox=dict(boxstyle='round,pad=0.5', facecolor='lightblue', alpha=0.7))

# Plot 2: Per-hand profit (滑动平均)
window = 20
df['profit_ma'] = df['profit'].rolling(window=window, min_periods=1).mean()

ax2.bar(df['hand_num'], df['profit'], alpha=0.3, color='gray', label='每手盈亏')
ax2.plot(df['hand_num'], df['profit_ma'], linewidth=2, color='#FF5722', label=f'{window}手滑动平均')
ax2.axhline(y=0, color='black', linestyle='-', alpha=0.5, linewidth=1)
ax2.axvline(x=30, color='orange', linestyle='--', alpha=0.7, linewidth=1.5)

ax2.set_xlabel('手数', fontsize=12)
ax2.set_ylabel('单手盈亏 (BB)', fontsize=12)
ax2.set_title(f'每手盈亏分布 ({window}手滑动平均)', fontsize=14, fontweight='bold')
ax2.grid(True, alpha=0.3)
ax2.legend(loc='best')

plt.tight_layout()

# Save figure
output_file = os.path.join(os.path.dirname(__file__), "../../test_results/profit_curve.png")
plt.savefig(output_file, dpi=150, bbox_inches='tight')
print(f"✅ 盈亏曲线已保存到: {output_file}")

# Calculate statistics
print(f"\n📊 统计数据:")
print(f"  总手数: {len(df)}")
print(f"  最终盈亏: {final_profit:+.1f}BB")
print(f"  BB/100: {(final_profit / len(df)) * 100:+.1f}")
print(f"  最大盈利: {max_profit:+.1f}BB (手{max_profit_hand:.0f})")
print(f"  最大亏损: {min_profit:+.1f}BB (手{min_profit_hand:.0f})")
print(f"  手30盈亏: {hand_30_profit:+.1f}BB")
print(f"  手30后盈亏: {final_profit - hand_30_profit:+.1f}BB")

# Phase analysis
phase1 = df[df['hand_num'] <= 30]
phase2 = df[(df['hand_num'] > 30) & (df['hand_num'] <= 100)]
phase3 = df[df['hand_num'] > 100]

print(f"\n📈 分阶段分析:")
print(f"  前30手 (GTO): {phase1['profit'].sum():+.1f}BB, BB/100={phase1['profit'].sum()/30*100:+.1f}")
print(f"  31-100手: {phase2['profit'].sum():+.1f}BB, BB/100={phase2['profit'].sum()/70*100:+.1f}")
print(f"  101-400手: {phase3['profit'].sum():+.1f}BB, BB/100={phase3['profit'].sum()/300*100:+.1f}")

# Show plot
plt.show()
