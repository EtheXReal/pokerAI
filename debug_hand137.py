#!/usr/bin/env python3
"""Debug Hand #137 specifically"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from poker_env import PokerGame, GameConfig, Player, PlayerAction, GameState
from advisor_v2.analysis.range_engine import RangeEngine
from advisor_v2.analysis.equity_engine import EquityEngine
from advisor_v2.analysis.board_analyzer import BoardAnalyzer
from advisor_v2.strategy.gto_strategy import GTOStrategy
from advisor_v2.integration.decision_integrator import DecisionIntegrator
import random


class RandomPlayer(Player):
    """随机策略玩家"""
    def decide(self, game_state: GameState) -> PlayerAction:
        """简单的随机决策"""
        rand = random.random()

        if game_state.to_call <= 0:
            # 无需跟注，check或bet
            if rand < 0.5:
                return PlayerAction(action='check', amount=0)
            else:
                # 小注bet
                bet_amount = game_state.pot * 0.6
                return PlayerAction(action='bet', amount=bet_amount)
        else:
            # 需要跟注
            if rand < 0.2:
                return PlayerAction(action='fold', amount=0)
            elif rand < 0.5:
                return PlayerAction(action='call', amount=game_state.to_call)
            else:
                # raise
                raise_amount = game_state.facing_bet * 5
                return PlayerAction(action='raise', amount=raise_amount)


class AdvisorV2Player(Player):
    """使用AdvisorV2的AI玩家"""
    def __init__(self, name: str, seat: int, stack: float):
        super().__init__(name, seat, stack)
        self.range_engine = RangeEngine()
        self.equity_engine = EquityEngine()
        self.board_analyzer = BoardAnalyzer()
        self.gto_strategy = GTOStrategy()
        self.integrator = DecisionIntegrator(
            range_engine=self.range_engine,
            equity_engine=self.equity_engine,
            board_analyzer=self.board_analyzer,
            strategy=self.gto_strategy
        )

    def decide(self, game_state: GameState) -> PlayerAction:
        try:
            from advisor.strategy_engine import GameState as AdvisorGameState
            advisor_game_state = AdvisorGameState(
                street=game_state.street,
                position=game_state.position,
                is_in_position=game_state.is_in_position,
                hero_hand=game_state.hand,
                pot_size=game_state.pot,
                effective_stack=game_state.effective_stack,
                hero_stack=game_state.hero_stack,
                board=game_state.board,
                facing_bet=game_state.facing_bet,
                bet_to_call=game_state.to_call
            )
            decision_trace = self.integrator.decide(advisor_game_state)

            # 简化决策逻辑
            if game_state.to_call > 0:
                if random.random() < 0.5:
                    return PlayerAction(action='call', amount=game_state.to_call)
                else:
                    return PlayerAction(action='fold', amount=0)
            else:
                return PlayerAction(action='check', amount=0)
        except:
            if game_state.to_call > 0:
                return PlayerAction(action='fold', amount=0)
            else:
                return PlayerAction(action='check', amount=0)


# 创建玩家
players = [
    AdvisorV2Player("AI", 0, 100.0),
    RandomPlayer("Random_1", 1, 80.0),
    RandomPlayer("Random_2", 2, 150.0),
]

config = GameConfig(
    num_players=3,
    starting_stack=100.0,
    small_blind=0.5,
    big_blind=1.0,
    verbose=False,  # Disable for cleaner output
    debug=False
)

game = PokerGame(players, config)

initial_stacks = {"AI": 100.0, "Random_1": 80.0, "Random_2": 150.0}

# Run hands 136-138
seed = 42

for hand_num in range(136, 139):
    btn_seat = (hand_num - 1) % 3

    print("="*80)
    print(f"Hand #{hand_num} - BTN: {players[btn_seat].name} (seat {btn_seat})")
    print("="*80)
    print()

    # 重置筹码
    players[0].reset_for_new_hand(initial_stacks["AI"])
    players[1].reset_for_new_hand(initial_stacks["Random_1"])
    players[2].reset_for_new_hand(initial_stacks["Random_2"])

    result = game.play_hand(hand_num, btn_seat, seed + hand_num, reset_stacks=False)

    print()
    print(f"Result: Pot={result.pot:.2f}BB")
    print(f"Profits: AI={result.player_profits[0]:.2f}BB, "
          f"R1={result.player_profits[1]:.2f}BB, "
          f"R2={result.player_profits[2]:.2f}BB")
    print(f"Sum: {sum(result.player_profits):.2f}BB")
    print(f"Invested: AI={players[0].invested:.2f}BB, "
          f"R1={players[1].invested:.2f}BB, "
          f"R2={players[2].invested:.2f}BB")
    print(f"Total invested: {sum(p.invested for p in players):.2f}BB")
    print()
