"""Compare match duration across difficulties to verify scaling.

Runs headless (no rendering) — measures frames to completion.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Suppress pygame output
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from src.engine import GameEngine, DEBUG

TRIALS = 10
MAX_FRAMES = 30000  # cap at 30k frames (~8 min at 60fps)
FPS = 60

def run_trial(difficulty):
    e = GameEngine(difficulty=difficulty, human_players=[])
    while not e.game_over and e.frame < MAX_FRAMES:
        e.update()
    return e.frame

def main():
    # Silence AI print statements
    import builtins
    _print = builtins.print
    builtins.print = lambda *a, **k: None

    results = {}
    for diff in ["easy", "medium", "hard"]:
        frames = []
        for _ in range(TRIALS):
            frames.append(run_trial(diff))
        avg = sum(frames) / len(frames)
        results[diff] = {"avg": avg, "min": min(frames), "max": max(frames), "frames": frames}

    builtins.print = _print

    print(f"{'Difficulty':<10} {'Avg frames':>11} {'Avg time':>10} {'Min':>8} {'Max':>8} {'Timeouts':>9}")
    print("-" * 62)
    for diff in ["easy", "medium", "hard"]:
        r = results[diff]
        timeouts = sum(1 for f in r["frames"] if f >= MAX_FRAMES)
        avg_sec = r["avg"] / FPS
        print(f"{diff:<10} {r['avg']:>11.0f} {avg_sec:>8.1f}s {r['min']:>8} {r['max']:>8} {timeouts:>9}")

    print(f"\n({TRIALS} trials per difficulty, {MAX_FRAMES} frame cap)")
    print("\nExpected: hard < medium < easy (faster fire + more balls = quicker matches)")

    if results["easy"]["avg"] > results["hard"]["avg"]:
        print("PASS: easy avg > hard avg")
    else:
        print("WARN: easy avg <= hard avg (unexpected)")

if __name__ == "__main__":
    main()
