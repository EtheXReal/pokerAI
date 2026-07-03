## Test & Acceptance Checklist

### 1. Smoke (Random Self-Play)
- Command: `python scripts/smoke_env.py --seed 42 [--reveal-all]`
- Expectation: prints a full hand history; terminal rewards and stacks balance (total chips conserved).

### 2. Evaluator Sanity
- Command: `python scripts/check_eval.py`
- Expectation: shows HS/EHS comparison (AA > 99 on K72r) and a showdown where winners/rank text match the evaluator result.

### 3. Walk to Showdown
- Command: `python scripts/walk_showdown.py --seed 7`
- Expectation: deterministic strategy reaches showdown, summary is readable, rewards sum to zero.

### 4. Sizing Rules
- Command: `python scripts/test_r_sizing.py`
- Expectation: asserts pass for `r33`, `r100`, `r200` sizing/tag mapping, each printing "OK".

### 5. Long Random Run (10k Hands)
- Recommendation: loop `scripts/smoke_env.py` or a batch helper to collect >=10,000 hands.
- Expectation: no dead loops or exceptions; derive aggregate stats (average pot, showdown rate, etc.).

All scripts depend only on `treys`, `numpy`, and the current env. Passing the suite confirms the advisor-ready environment baseline.
