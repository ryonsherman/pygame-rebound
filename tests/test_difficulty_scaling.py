"""Tests for difficulty scaling parameters and match pacing."""
import random
import pytest
from src.engine import GameEngine


class TestDifficultyParams:
    """Difficulty settings produce correct engine parameters."""

    @pytest.mark.parametrize("diff,expected_bounces", [
        ("easy", 3), ("medium", 4), ("hard", 5),
    ])
    def test_max_bounces(self, diff, expected_bounces):
        eng = GameEngine(difficulty=diff, human_players=[])
        assert eng.max_bounces == expected_bounces

    @pytest.mark.parametrize("diff,expected_max", [
        ("easy", 15), ("medium", 18), ("hard", 21),
    ])
    def test_max_projectiles(self, diff, expected_max):
        eng = GameEngine(difficulty=diff, human_players=[])
        assert eng.max_projectiles == expected_max

    @pytest.mark.parametrize("diff,expected_shrink", [
        ("easy", 0.75), ("medium", 0.8), ("hard", 0.85),
    ])
    def test_bounce_shrink(self, diff, expected_shrink):
        eng = GameEngine(difficulty=diff, human_players=[])
        assert eng.bounce_shrink == expected_shrink

    @pytest.mark.parametrize("diff,expected_slow", [
        ("easy", 0.84), ("medium", 0.88), ("hard", 0.92),
    ])
    def test_bounce_slowdown(self, diff, expected_slow):
        eng = GameEngine(difficulty=diff, human_players=[])
        assert eng.bounce_slowdown == expected_slow


class TestDifficultyPacing:
    """Hard games should complete faster than easy games."""

    def test_hard_faster_than_easy(self):
        """Run 2 trials each with seeded RNG and confirm hard avg < easy avg frames."""
        def run(diff, n=2):
            frames = []
            for i in range(n):
                random.seed(42 + i)
                eng = GameEngine(difficulty=diff, human_players=[])
                while not eng.game_over and eng.frame < 6000:
                    eng.update()
                frames.append(eng.frame)
            return sum(frames) / len(frames)

        hard_avg = run("hard")
        easy_avg = run("easy")
        # Hard should finish faster (fewer frames)
        assert hard_avg < easy_avg
