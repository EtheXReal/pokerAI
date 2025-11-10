#!/usr/bin/env python
"""
评估器性能基准测试
测试不同采样数下的耗时和精度
"""
import time
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from env.evaluator import hand_strength, effective_hand_strength
from treys import Card

def benchmark_hs():
    """测试Hand Strength性能"""
    print("=== Hand Strength Benchmark ===")

    # 典型场景：翻牌圈
    hole = [Card.new('As'), Card.new('Kd')]
    board = [Card.new('Ah'), Card.new('Ts'), Card.new('3c')]

    for nsamples in [100, 300, 500, 1000, 2000]:
        times = []
        for _ in range(5):  # 5次取平均
            start = time.perf_counter()
            hs = hand_strength(hole, board, nsamples=nsamples)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        avg_time = sum(times) / len(times)
        print(f"nsamples={nsamples:4d}: {avg_time*1000:6.1f}ms (HS={hs:.3f})")

def benchmark_ehs():
    """测试Effective Hand Strength性能"""
    print("\n=== Effective Hand Strength Benchmark ===")

    # 典型场景：翻牌圈（需要计算潜力）
    hole = [Card.new('Qc'), Card.new('Qh')]
    board = [Card.new('Ah'), Card.new('Ts'), Card.new('3c')]

    for nsamples in [100, 300, 500, 1000]:
        times = []
        for _ in range(3):  # EHS更慢，少测几次
            start = time.perf_counter()
            ehs = effective_hand_strength(hole, board, nsamples=nsamples)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        avg_time = sum(times) / len(times)
        print(f"nsamples={nsamples:4d}: {avg_time*1000:6.1f}ms (EHS={ehs:.3f})")

def benchmark_full_decision():
    """模拟完整决策流程"""
    print("\n=== Full Decision Benchmark ===")

    hole = [Card.new('As'), Card.new('Kd')]
    board = [Card.new('Ah'), Card.new('Ts'), Card.new('3c')]

    start = time.perf_counter()

    # 模拟决策：需要快速评估
    hs = hand_strength(hole, board, nsamples=300)
    ehs = effective_hand_strength(hole, board, nsamples=300)

    # 简单策略判断
    if ehs > 0.7:
        action = "r100"
    elif ehs > 0.5:
        action = "r66"
    elif hs > 0.4:
        action = "call"
    else:
        action = "fold"

    elapsed = time.perf_counter() - start
    print(f"Total time: {elapsed*1000:.1f}ms")
    print(f"Decision: {action} (HS={hs:.3f}, EHS={ehs:.3f})")
    print(f"Within 20s budget: {'✓' if elapsed < 20 else '✗'}")

if __name__ == '__main__':
    benchmark_hs()
    benchmark_ehs()
    benchmark_full_decision()
