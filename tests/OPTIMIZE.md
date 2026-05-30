# Test Suite Optimization Report

**Date**: 2026-05-27
**Before**: 193 tests in ~21s
**After**: 193 tests in ~8.6s (59% faster)

## Summary

The test suite was dominated by a single test (`test_hard_faster_than_easy`) that consumed 80% of execution time by running 6 full game simulations to 12,000 frames. Several physics tests also ran more frames than necessary to validate their invariants. Reducing frame counts while preserving test semantics yielded a 59% speedup.

## Critical Optimizations

### [OPT-1] Reduce difficulty pacing test simulation length

**File**: `test_difficulty_scaling.py:42-56`
**Impact**: 16.8s → ~5.5s

The test ran 3 trials × 2 difficulties × 12,000 frame cap = potential 72,000 frames. Hard games typically end by frame ~1,200 and easy games by ~4,800. A 6,000 frame cap with 2 trials still validates the invariant (hard < easy) with large margin.

- Reduced trials from 3 to 2
- Reduced frame cap from 12,000 to 6,000

### [OPT-2] Reduce physics wall-escape test frames

**File**: `test_engine_physics.py:14-24`
**Impact**: 1.26s → ~0.4s

3,000 frames was excessive for validating wall containment. Projectiles reach all walls within 100 frames. 1,000 frames provides ample coverage with multiple bounces per projectile.

### [OPT-3] Reduce projectile shrink test frames

**File**: `test_engine_physics.py:128-134`
**Impact**: 0.96s → ~0.4s

Reduced from 5,000 to 2,000 frames. Projectiles hit max bounces and die well before 2,000 frames; the invariant (radius ≥ 2) is fully exercised.

### [OPT-4] Reduce obstacle-stuck test frames

**File**: `test_engine_physics.py:69-85`
**Impact**: 0.87s → ~0.35s

Reduced from 2,000 to 800 frames. Obstacle collisions occur within the first 50-100 frames.

## Major Optimizations

### [OPT-5] Reduce stress test frame cap

**File**: `test_game_state.py:120-126`
**Impact**: 0.77s → ~0.4s

Reduced cap from 30,000 to 12,000. Hard games end by ~1,200 frames on average. 12,000 is still 10× the expected duration.

## Minor Optimizations (not applied — low ROI)

- **Shared `engine_hard` across physics tests**: The conftest fixture is function-scoped (correct — tests mutate engine state). Sharing would require deep-copying, negating savings.
- **Parallelization**: Tests are CPU-bound (game physics). `pytest-xdist` would help on multi-core but adds dependency complexity. The suite is now fast enough at ~8.5s.
- **Import cost**: `config.py` uses `_ColorProxy` to defer pygame init — already optimized. No pygame import occurs during test collection.
- **Bot client sleep-based tests** (0.05s each): Could use `asyncio.sleep(0)` but the 50ms is needed for the async loop to tick.
