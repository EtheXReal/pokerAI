"""
分析长周期模式的AI表现 - 找出巨额亏损的原因

分析维度：
1. 盈亏曲线 (前30手 vs 31-100手 vs 101-400手)
2. 决策分布 (fold/call/raise频率)
3. Exploit应用情况 (什么时候开始应用，应用了什么调整)
4. 典型失败案例 (输掉最多钱的几手牌)
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Enable debug to see exploit adjustments
os.environ['DEBUG_HYBRID'] = '1'

from poker_env import PokerGame, GameConfig, Player, PlayerAction
from tests.performance.styled_players import create_styled_player
from advisor_v2.integration.decision_integrator import DecisionIntegrator
from advisor_v2.analysis.range_engine import RangeEngine
from advisor_v2.analysis.equity_engine import EquityEngine
from advisor_v2.analysis.board_analyzer import BoardAnalyzer
from advisor_v2.strategy.hybrid_strategy import HybridStrategy
from advisor_v2.integration.utils import convert_game_result_to_hand_history
import random
from collections import defaultdict

# Track decisions and exploits
ai_decisions = []  # [(hand_num, street, action, amount, pot, facing_bet)]
exploit_applications = []  # [(hand_num, player_type, confidence, action_type, alpha)]
hand_results = []  # [(hand_num, profit, cumulative_profit)]

class AnalysisAIPlayer(Player):
    def __init__(self, name, seat, stack, all_players):
        super().__init__(name, seat, stack)
        self.all_players = all_players
        self.range_engine = RangeEngine()
        self.equity_engine = EquityEngine()
        self.board_analyzer = BoardAnalyzer()
        self.hybrid_strategy = HybridStrategy()
        self.integrator = DecisionIntegrator(
            range_engine=self.range_engine,
            equity_engine=self.equity_engine,
            board_analyzer=self.board_analyzer,
            strategy=self.hybrid_strategy
        )
        self.current_hand = None

    def decide(self, game_state):
        # Record decision context
        decision_trace = self.integrator.decide(game_state)
        selected_action = decision_trace.selected_action

        if selected_action:
            ai_decisions.append({
                'hand_num': self.current_hand,
                'street': game_state.street,
                'action': selected_action.action,
                'amount': getattr(selected_action, 'amount', 0),
                'pot': game_state.pot,
                'facing_bet': game_state.to_call,
                'board': str(game_state.board) if hasattr(game_state, 'board') else '',
            })

            # Check if exploit was applied
            if hasattr(decision_trace, 'final_decision') and decision_trace.final_decision:
                key_factors = decision_trace.final_decision.key_factors
                if key_factors and 'strategy' in key_factors:
                    if key_factors['strategy'] == 'HybridStrategy':
                        exploit_applications.append({
                            'hand_num': self.current_hand,
                            'street': game_state.street,
                            'player_type': key_factors.get('exploit_action_type', 'N/A'),
                            'alpha': key_factors.get('exploit_alpha', 0),
                        })

            return PlayerAction(action=selected_action.action, amount=getattr(selected_action, 'amount', 0))
        return PlayerAction(action='fold', amount=0)

    def on_hand_complete(self, game_result):
        try:
            hand_history = convert_game_result_to_hand_history(game_result, self.all_players)
            self.integrator.tracker.update_from_hand(hand_history)
        except:
            pass

# Create players
players = [None, None]
maniac = create_styled_player('maniac', 'MANIAC', 1, 100.0)
players[1] = maniac
ai = AnalysisAIPlayer('AI', 0, 100.0, players)
players[0] = ai

config = GameConfig(
    num_players=2,
    starting_stack=100.0,
    small_blind=0.5,
    big_blind=1.0,
    verbose=False,
    debug=False
)

print("="*80)
print("分析AI vs MANIAC长周期表现 (400手)")
print("="*80)

random.seed(42)
game = PokerGame(players, config)

cumulative_profit = 0.0

# Run 400 hands
for i in range(400):
    ai.current_hand = i + 1
    btn_seat = i % 2
    result = game.play_hand(hand_num=i+1, btn_seat=btn_seat, seed=42+i)

    profit = result.player_profits[0]
    cumulative_profit += profit
    hand_results.append((i+1, profit, cumulative_profit))

    # Print progress every 50 hands
    if (i + 1) % 50 == 0:
        print(f"Hand {i+1}: cumulative profit = {cumulative_profit:+.1f}BB")

print(f"\n{'='*80}")
print(f"📊 分析结果")
print(f"{'='*80}")

# 1. 分阶段盈亏分析
phase1 = [h for h in hand_results if h[0] <= 30]
phase2 = [h for h in hand_results if 30 < h[0] <= 100]
phase3 = [h for h in hand_results if h[0] > 100]

phase1_profit = sum(h[1] for h in phase1)
phase2_profit = sum(h[1] for h in phase2)
phase3_profit = sum(h[1] for h in phase3)

print(f"\n1️⃣ 分阶段盈亏分析:")
print(f"  前30手 (纯GTO建模期): {phase1_profit:+.1f}BB, BB/100={phase1_profit/30*100:+.1f}")
print(f"  31-100手 (Exploit早期): {phase2_profit:+.1f}BB, BB/100={phase2_profit/70*100:+.1f}")
print(f"  101-400手 (Exploit成熟): {phase3_profit:+.1f}BB, BB/100={phase3_profit/300*100:+.1f}")
print(f"  总计: {cumulative_profit:+.1f}BB, BB/100={cumulative_profit/400*100:+.1f}")

# 2. 决策分布分析
print(f"\n2️⃣ 决策分布分析:")
action_counts = defaultdict(int)
for d in ai_decisions:
    action_counts[d['action']] += 1

total_decisions = sum(action_counts.values())
print(f"  总决策次数: {total_decisions}")
for action, count in sorted(action_counts.items(), key=lambda x: -x[1]):
    pct = count / total_decisions * 100
    print(f"    {action}: {count} ({pct:.1f}%)")

# 3. Exploit应用分析
print(f"\n3️⃣ Exploit应用分析:")
print(f"  Exploit调整次数: {len(exploit_applications)}")
if exploit_applications:
    exploit_types = defaultdict(int)
    for e in exploit_applications:
        exploit_types[e['player_type']] += 1

    print(f"  调整类型分布:")
    for etype, count in sorted(exploit_types.items(), key=lambda x: -x[1]):
        print(f"    {etype}: {count}次")

    avg_alpha = sum(e['alpha'] for e in exploit_applications) / len(exploit_applications)
    print(f"  平均Alpha权重: {avg_alpha:.2f}")

# 4. 最大亏损案例
print(f"\n4️⃣ 最大亏损的10手牌:")
worst_hands = sorted(hand_results, key=lambda x: x[1])[:10]
for rank, (hand_num, profit, cumul) in enumerate(worst_hands, 1):
    print(f"  #{rank}. Hand {hand_num}: {profit:+.1f}BB (累计: {cumul:+.1f}BB)")

# 5. 对手建模检查
print(f"\n5️⃣ 对手建模状态 (最终):")
maniac_stats = ai.integrator.tracker.get_stats('MANIAC')
print(f"  Hands: {maniac_stats.hands_played}")
print(f"  VPIP: {maniac_stats.vpip:.1%}")
print(f"  PFR: {maniac_stats.pfr:.1%}")
print(f"  AF: {maniac_stats.af:.2f}")

classification = ai.integrator.classifier.classify(maniac_stats)
print(f"  Classification: {classification.player_type.name}, confidence={classification.confidence:.2f}")

# 6. 生成盈亏曲线数据
print(f"\n6️⃣ 盈亏曲线已保存到 test_results/profit_curve.csv")
output_dir = os.path.join(os.path.dirname(__file__), "../../test_results")
os.makedirs(output_dir, exist_ok=True)

with open(os.path.join(output_dir, "profit_curve.csv"), 'w') as f:
    f.write("hand_num,profit,cumulative_profit\n")
    for hand_num, profit, cumul in hand_results:
        f.write(f"{hand_num},{profit:.2f},{cumul:.2f}\n")

print(f"\n7️⃣ 决策详情已保存到 test_results/ai_decisions.csv")
with open(os.path.join(output_dir, "ai_decisions.csv"), 'w', encoding='utf-8') as f:
    f.write("hand_num,street,action,amount,pot,facing_bet,board\n")
    for d in ai_decisions:
        f.write(f"{d['hand_num']},{d['street']},{d['action']},{d['amount']:.2f},{d['pot']:.2f},{d['facing_bet']:.2f},{d['board']}\n")

print(f"\n✅ 分析完成！")
print(f"\n建议下一步:")
print(f"  1. 查看盈亏曲线：python plot_profit_curve.py")
print(f"  2. 对比前30手 vs 后370手的决策差异")
print(f"  3. 检查最大亏损的手牌详情 (使用--verbose重跑特定seed)")
