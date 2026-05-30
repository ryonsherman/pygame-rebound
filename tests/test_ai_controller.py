"""Tests for AIController behavior."""
import math
import pytest
from src.engine import GameEngine, AIController, _corner_positions, COLOR_LETTERS
from config import ARENA_RECT, CASTLE_SIZE, SHIELD_DURATION


class TestAITargeting:
    """AI picks targets and retargets when target dies."""

    def test_ai_picks_alive_target(self, engine_hard):
        eng = engine_hard
        for _ in range(100):
            eng.update()
        for ai in eng.ai:
            if ai.target is not None:
                assert eng.castles[ai.target]["alive"]

    def test_ai_retargets_on_death(self):
        eng = GameEngine(difficulty="hard", human_players=[])
        # Kill castle 1
        c = eng.castles[1]
        for b in c["bricks"]:
            b["alive"] = False
            b["hp"] = 0
        c["alive"] = False
        # Run frames — AI should not target dead castle
        for _ in range(200):
            eng.update()
        for ai in eng.ai:
            if ai.target is not None:
                assert ai.target != 1


class TestAIShield:
    """AI activates shield when threatened."""

    def test_ai_no_fire_during_shield(self):
        """AI should not fire while its shield is active."""
        eng = GameEngine(difficulty="hard", human_players=[])
        # Force shield active on AI castle 0
        c = eng.castles[0]
        c["shield"]["active"] = True
        c["shield"]["timer"] = SHIELD_DURATION
        ai = next(a for a in eng.ai if a.owner == 0)
        ai.fire_timer = 0  # ready to fire
        ai.update(eng.castles, eng.projectiles)
        # fire_request should NOT have been set
        assert c["fire_request"] is None


class TestAIDifficulty:
    """AI parameters scale with difficulty."""

    def test_hard_fires_faster_than_easy(self):
        hard_ai = AIController(0, "hard")
        easy_ai = AIController(0, "easy")
        assert hard_ai.fire_interval[1] < easy_ai.fire_interval[0]

    def test_hard_has_better_aim(self):
        hard_ai = AIController(0, "hard")
        easy_ai = AIController(0, "easy")
        assert hard_ai.aim_spread < easy_ai.aim_spread
