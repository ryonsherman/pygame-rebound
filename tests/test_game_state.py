"""Tests for game state, AI management, and engine initialization."""
import pytest
from src.engine import GameEngine, _corner_positions, _clamp_aim, _init_obstacles
from config import ARENA_RECT, CASTLE_SIZE, BRICK_SIZE, BRICKS_PER_CASTLE


class TestInitialization:
    """Engine initializes correctly."""

    def test_four_castles(self, engine_medium):
        assert len(engine_medium.castles) == 4

    def test_all_castles_alive(self, engine_medium):
        for c in engine_medium.castles:
            assert c["alive"]
            assert all(b["alive"] for b in c["bricks"])

    def test_correct_brick_count(self, engine_medium):
        for c in engine_medium.castles:
            assert len(c["bricks"]) == BRICKS_PER_CASTLE

    def test_obstacles_created(self, engine_medium):
        assert len(engine_medium.obstacles) > 0

    def test_no_projectiles_at_start(self, engine_medium):
        assert len(engine_medium.projectiles) == 0


class TestAIManagement:
    """Adding and removing AI controllers."""

    def test_add_ai(self, engine_human):
        eng = engine_human
        assert 0 in eng.human_players
        eng.add_ai(0)
        assert 0 not in eng.human_players
        assert any(ai.owner == 0 for ai in eng.ai)

    def test_remove_ai(self, engine_hard):
        eng = engine_hard
        eng.remove_ai(1)
        assert 1 in eng.human_players
        assert not any(ai.owner == 1 for ai in eng.ai)

    def test_add_ai_no_duplicate(self, engine_hard):
        eng = engine_hard
        count_before = len(eng.ai)
        eng.add_ai(0)  # 0 is already AI
        assert len(eng.ai) == count_before


class TestClampAim:
    """Cannon aim clamping per quadrant."""

    def test_owner0_clamps_upper_left(self):
        """Owner 0 is bottom-right, aim must be toward upper-left."""
        ax, ay, aw, ah = ARENA_RECT
        positions = _corner_positions()
        cx, cy = positions[0]
        ccx = cx + CASTLE_SIZE // 2
        ccy = cy + CASTLE_SIZE // 2
        # Try aiming to the right (invalid for owner 0)
        mx, my = _clamp_aim(0, ccx + 100, ccy + 100, ccx, ccy)
        assert mx < ccx
        assert my < ccy

    def test_owner1_clamps_lower_right(self):
        """Owner 1 is top-left, aim must be toward lower-right."""
        positions = _corner_positions()
        cx, cy = positions[1]
        ccx = cx + CASTLE_SIZE // 2
        ccy = cy + CASTLE_SIZE // 2
        mx, my = _clamp_aim(1, ccx - 100, ccy - 100, ccx, ccy)
        assert mx > ccx
        assert my > ccy


class TestGetState:
    """get_state() returns well-formed data."""

    def test_state_has_required_keys(self, engine_medium):
        eng = engine_medium
        eng.update()
        state = eng.get_state()
        assert "castles" in state
        assert "projectiles" in state
        assert "obstacles" in state
        assert "game_over" in state
        assert "winner" in state
        assert "sound_events" in state

    def test_state_castle_fields(self, engine_medium):
        state = engine_medium.get_state()
        c = state["castles"][0]
        assert "owner" in c
        assert "alive" in c
        assert "cannon_angle" in c
        assert "bricks" in c
        assert "shield" in c
        assert "human" in c

    def test_sound_events_contain_fire_event(self):
        """Sound events include cannon_fire with type and volume after firing."""
        eng = GameEngine(difficulty="medium", human_players=[0])
        eng.ai = []
        c = eng.castles[0]
        cx, cy = c["center"]
        eng.handle_input({0: {"mouse_x": cx - 50, "mouse_y": cy - 50, "click": True, "space": False}})
        eng.update()
        state = eng.get_state()
        fire_events = [e for e in state["sound_events"] if e["type"] == "cannon_fire"]
        assert len(fire_events) == 1
        assert "volume" in fire_events[0]
        assert fire_events[0]["volume"] > 0


class TestStressFullGame:
    """Stress test: run a full AI game without crash."""

    def test_full_hard_game_completes(self):
        eng = GameEngine(difficulty="hard", human_players=[])
        while not eng.game_over and eng.frame < 30000:
            eng.update()
        assert eng.game_over or eng.frame == 30000
        if eng.game_over:
            assert eng.winner in [0, 1, 2, 3]
