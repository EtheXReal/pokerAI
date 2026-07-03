#!/usr/bin/env python
"""
1v1 人机对战服务器（本地，零第三方依赖）

用法:
    python webplay/server.py [--port 8000] [--no-exploit]

浏览器打开 http://127.0.0.1:8000 与 AI 单挑。
- 每手牌双方重置为100BB，累计盈亏计分
- AI 使用完整决策管线（分析→GTO→exploit），并实时对"你"建模
- 每手结束后可查看 AI 的决策推理（DecisionTrace）与它对你的分类
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
import queue
import threading
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from poker_env import PokerGame, GameConfig, Player, PlayerAction
from poker_env.utils import round_amount
from advisor.integration.poker_env_adapter import AdvisorEnvPlayer


class HumanPlayer(Player):
    """人类玩家：decide()阻塞等待网页提交动作"""

    def __init__(self, name, seat, stack, session):
        super().__init__(name, seat, stack)
        self.session = session

    def decide(self, game_state):
        # 发布当前局面，等待人类动作
        with self.session.lock:
            self.session.pending = game_state
        action = self.session.action_queue.get()  # 阻塞
        with self.session.lock:
            self.session.pending = None
        return action


class Session:
    """一局人机对战会话"""

    def __init__(self, use_exploit=True):
        self.lock = threading.Lock()
        self.action_queue = queue.Queue()
        self.pending = None          # 等待人类决策时的GameState
        self.hand_thread = None
        self.hand_num = 0
        self.last_result = None
        self.results = []
        self.human_total = 0.0
        self.error = None

        self.human = HumanPlayer("You", seat=0, stack=100.0, session=self)
        self.ai = AdvisorEnvPlayer("AI", seat=1, stack=100.0,
                                   use_exploit=use_exploit, keep_traces=True)
        self.ai.villain_id = "You"
        self.players = [self.human, self.ai]
        self.game = PokerGame(self.players, GameConfig(
            num_players=2, starting_stack=100.0,
            small_blind=0.5, big_blind=1.0, verbose=False))

    # ---------- 对局控制 ----------

    def hand_active(self):
        return self.hand_thread is not None and self.hand_thread.is_alive()

    def start_hand(self):
        if self.hand_active():
            return False
        self.error = None
        self.ai.start_hand()
        btn_seat = self.hand_num % 2
        num = self.hand_num
        self.hand_num += 1

        def run():
            try:
                result = self.game.play_hand(hand_num=num, btn_seat=btn_seat)
                with self.lock:
                    self.last_result = result
                    self.results.append(result)
                    self.human_total += result.player_profits[0]
                self.ai.observe_hand(result, self.players)
            except Exception as e:
                import traceback
                traceback.print_exc()
                with self.lock:
                    self.error = str(e)

        self.hand_thread = threading.Thread(target=run, daemon=True)
        self.hand_thread.start()
        return True

    def submit_action(self, action, amount):
        """校验并提交人类动作"""
        with self.lock:
            gs = self.pending
        if gs is None:
            return "当前不是你的回合"

        to_call = gs.to_call or 0.0
        stack = gs.hero_stack
        action = (action or '').lower()

        if action == 'fold':
            pa = PlayerAction('fold', 0.0)
        elif action == 'check':
            if to_call > 0.01:
                return f"面对{to_call:.1f}BB下注不能check"
            pa = PlayerAction('check', 0.0)
        elif action == 'call':
            if to_call <= 0.01:
                return "无人下注，请用check"
            pa = PlayerAction('call', 0.0)
        elif action == 'bet':
            if to_call > 0.01:
                return "面对下注请用raise"
            amt = round_amount(max(1.0, min(float(amount or 0), stack)))
            if stack - amt < 1.0:
                amt = stack
            pa = PlayerAction('bet', amt)
        elif action == 'raise':
            if to_call <= 0.01 and gs.street != 'preflop':
                return "无人下注，请用bet"
            # 前端传"加注到"总额 → poker_env需要超出call的增量
            raise_to = float(amount or 0)
            increment = round_amount(raise_to - (gs.facing_bet or 0.0))
            max_inc = stack - to_call
            increment = max(0.5, min(increment, max_inc))
            if max_inc - increment < 1.0:
                increment = max_inc
            pa = PlayerAction('raise', round_amount(increment))
        elif action == 'allin':
            if to_call > 0.01:
                pa = PlayerAction('raise', round_amount(stack - to_call))
            else:
                pa = PlayerAction('bet', round_amount(stack))
        else:
            return f"未知动作: {action}"

        self.action_queue.put(pa)
        return None

    # ---------- 状态快照 ----------

    def snapshot(self):
        with self.lock:
            pending = self.pending
            result = self.last_result
            error = self.error
            human_total = self.human_total
            n_results = len(self.results)

        active = self.hand_active()
        state = {
            'session': {
                'hands_played': n_results,
                'human_total': round(human_total, 2),
                'bb100': round(human_total / n_results * 100, 1) if n_results else 0.0,
            },
            'hand_active': active,
            'your_turn': pending is not None,
            'error': error,
        }

        if pending is not None:
            gs = pending
            state['table'] = {
                'street': gs.street,
                'board': [str(c) for c in gs.board] if gs.board else [],
                'your_cards': [str(c) for c in gs.hand.cards],
                'pot': round(gs.pot, 2),
                'your_stack': round(gs.hero_stack, 2),
                'to_call': round(gs.to_call, 2),
                'facing_bet': round(gs.facing_bet, 2),
                'min_raise_to': round(gs.min_raise, 2),
                'position': gs.position,
                'log': [f"[{a.street}] {a.player_name}: {a.action}"
                        for a in getattr(gs, 'hand_actions', [])],
            }

        if result is not None and not active:
            stats, ptype = self.ai.get_villain_model()

            def split_cards(s):
                # "AsKh" → ["As", "Kh"]
                s = (s or '').replace(' ', '')
                return [s[i:i + 2] for i in range(0, len(s), 2)]

            state['last_hand'] = {
                'hand_num': result.hand_num + 1,
                'board': (result.flop or []) + ([result.turn] if result.turn else [])
                         + ([result.river] if result.river else []),
                'your_cards': split_cards(result.player_hands[0]),
                'ai_cards': split_cards(result.player_hands[1]) if result.showdown else None,
                'showdown': result.showdown,
                'winners': [self.players[s].name for s in result.winner_seats],
                'pot': round(result.pot, 2),
                'your_profit': round(result.player_profits[0], 2),
                'hand_strengths': result.hand_strengths if result.showdown else None,
                'log': [f"[{a.street}] {a.player_name}: {a.action}" for a in result.actions],
                'ai_insight': {
                    'ai_reasoning': [
                        {
                            'street': t.metadata.get('street', '?'),
                            'action': t.selected_action.action if t.selected_action else '?',
                            'gto': {k: round(v, 2) for k, v in
                                    t.gto_decision.action_distribution.items()} if t.gto_decision else {},
                            'reasoning': (t.final_decision.reasoning or '')[:160],
                            'exploit': t.metadata.get('exploit_reasoning'),
                        }
                        for t in self.ai.hand_traces
                    ],
                    'you_classified_as': ptype.value if ptype else '样本不足',
                    'your_vpip': round(stats.vpip, 2) if stats else None,
                    'your_af': round(stats.af, 2) if stats else None,
                    'hands_observed': stats.hands_played if stats else 0,
                },
            }

        return state


SESSION = None
USE_EXPLOIT = True
INDEX_PATH = os.path.join(os.path.dirname(__file__), 'index.html')


class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # 静默访问日志

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ('/', '/index.html'):
            with open(INDEX_PATH, 'rb') as f:
                body = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == '/api/state':
            self._json(SESSION.snapshot())
        else:
            self._json({'error': 'not found'}, 404)

    def do_POST(self):
        global SESSION
        length = int(self.headers.get('Content-Length') or 0)
        payload = json.loads(self.rfile.read(length) or b'{}') if length else {}

        if self.path == '/api/new_hand':
            ok = SESSION.start_hand()
            self._json({'ok': ok})
        elif self.path == '/api/action':
            err = SESSION.submit_action(payload.get('action'), payload.get('amount'))
            self._json({'ok': err is None, 'error': err})
        elif self.path == '/api/reset':
            SESSION = Session(use_exploit=USE_EXPLOIT)
            self._json({'ok': True})
        else:
            self._json({'error': 'not found'}, 404)


def main():
    global SESSION, USE_EXPLOIT
    parser = argparse.ArgumentParser(description='1v1人机对战服务器')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--no-exploit', action='store_true', help='AI只用纯GTO（不针对你调整）')
    args = parser.parse_args()

    USE_EXPLOIT = not args.no_exploit
    SESSION = Session(use_exploit=USE_EXPLOIT)

    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'🃏 人机对战: http://127.0.0.1:{args.port}  (AI exploit={"开" if USE_EXPLOIT else "关"})')
    print('   Ctrl+C 停止')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
