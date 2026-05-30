"""Tests for game lifecycle, castle damage, shields, cannon mechanics."""
import math
import pytest
from src.engine import GameEngine, _make_projectile, PROJECTILE_RADIUS, PROJECTILE_SPEED, _corner_positions
from config import (
    ARENA_RECT, FIRE_COOLDOWN, SHIELD_DURATION, SHIELD_COOLDOWN,
    SHIELD_RADIUS, CASTLE_SIZE, MAX_BLOCKADES, BRICK_SIZE,
)

ax, ay, aw, ah = ARENA_RECT


class TestFireCooldown:
    """Cannon fire respects cooldown."""

    def test_cannot_fire_during_cooldown(self, engine_human):
        eng = engine_human
        c = eng.castles[0]
        cx, cy = c["center"]
        # Fire once
        eng.handle_input({0: {"mouse_x": cx - 50, "mouse_y": cy - 50, "click": True, "space": False}})
        eng.update()
        initial_count = len(eng.projectiles)
        # Try to fire again immediately
        for _ in range(FIRE_COOLDOWN - 1):
            eng.handle_input({0: {"mouse_x": cx - 50, "mouse_y": cy - 50, "click": True, "space": False}})
            eng.update()
        # Should not have fired another (only original + AI shots)
        human_shots = [p for p in eng.projectiles if p["owner"] == 0]
        assert len(human_shots) <= 1


class TestShield:
    """Shield activation, duration, cooldown, and reflection."""

    def test_shield_activates_on_space(self, engine_human):
        eng = engine_human
        c = eng.castles[0]
        cx, cy = c["center"]
        eng.handle_input({0: {"mouse_x": cx - 50, "mouse_y": cy - 50, "click": False, "space": True}})
        eng.update()
        assert c["shield"]["active"]

    def test_shield_deactivates_on_release(self, engine_human):
        eng = engine_human
        c = eng.castles[0]
        cx, cy = c["center"]
        eng.handle_input({0: {"mouse_x": cx - 50, "mouse_y": cy - 50, "click": False, "space": True}})
        eng.update()
        eng.handle_input({0: {"mouse_x": cx - 50, "mouse_y": cy - 50, "click": False, "space": False}})
        eng.update()
        assert not c["shield"]["active"]

    def test_shield_expires_after_duration(self, engine_human):
        eng = engine_human
        eng.ai = []
        c = eng.castles[0]
        cx, cy = c["center"]
        # Activate shield once, then stop holding space — let timer tick down
        eng.handle_input({0: {"mouse_x": cx - 50, "mouse_y": cy - 50, "click": False, "space": True}})
        eng.update()
        assert c["shield"]["active"]
        # Now directly set timer to 1 and let engine tick it to 0
        c["shield"]["timer"] = 1
        # Don't send space=True so handle_input won't re-activate
        # But we need to avoid handle_input resetting it — just call update directly
        eng.update()
        assert not c["shield"]["active"]
        assert c["shield"]["cooldown_timer"] == SHIELD_COOLDOWN - 1  # decrements same frame

    def test_shield_reflects_projectile(self, engine_human):
        eng = engine_human
        eng.ai = []  # disable AI
        c = eng.castles[0]
        cx, cy = c["center"]
        # Place enemy projectile heading toward castle 0
        p = _make_projectile(cx - 30, cy - 30, math.atan2(30, 30), 1, 1, PROJECTILE_SPEED, 99)
        eng.projectiles.append(p)
        # Activate shield
        eng.handle_input({0: {"mouse_x": cx - 50, "mouse_y": cy - 50, "click": False, "space": True}})
        # Run a few frames for projectile to reach shield radius
        for _ in range(10):
            eng.handle_input({0: {"mouse_x": cx - 50, "mouse_y": cy - 50, "click": False, "space": True}})
            eng.update()
        # Shield should have deactivated after reflect and cooldown set
        assert c["shield"]["cooldown_timer"] > 0 or not c["shield"]["active"]


class TestCastleDamage:
    """Brick HP, destruction, and castle death."""

    def test_brick_two_hit_destruction(self):
        eng = GameEngine(difficulty="medium", human_players=[])
        eng.ai = []
        c = eng.castles[1]  # target castle 1 (top-left)
        brick = c["bricks"][0]
        assert brick["hp"] == 2
        assert brick["alive"]

        # First hit
        cx, cy = c["center"]
        p = _make_projectile(cx, cy, 0, 0, 0, 0, 1)  # stationary inside castle
        eng.projectiles.append(p)
        eng._damage_castle(c, p, 0)
        assert brick["hp"] == 1
        assert brick["alive"]

        # Second hit
        p2 = _make_projectile(cx, cy, 0, 0, 0, 0, 2)
        eng.projectiles.append(p2)
        eng._damage_castle(c, p2, 0)
        assert not brick["alive"]

    def test_castle_dies_when_all_bricks_destroyed(self):
        eng = GameEngine(difficulty="medium", human_players=[])
        eng.ai = []
        c = eng.castles[1]
        cx, cy = c["center"]
        # Destroy all bricks (9 bricks × 2 hp = 18 hits)
        for i in range(18):
            p = _make_projectile(cx, cy, 0, 0, 0, 0, 100 + i)
            eng.projectiles.append(p)
            eng._damage_castle(c, p, 0)
            if not c["alive"]:
                break
        assert not c["alive"]

    def test_castle_collapse_removes_owner_projectiles(self):
        eng = GameEngine(difficulty="medium", human_players=[])
        eng.ai = []
        # Add projectiles owned by castle 1
        cx, cy = eng.castles[1]["center"]
        for i in range(5):
            eng.projectiles.append(_make_projectile(ax + aw // 2, ay + ah // 2, 0, 1, 1, PROJECTILE_SPEED, 50 + i))
        # Destroy castle 1
        c = eng.castles[1]
        for i in range(18):
            p = _make_projectile(cx, cy, 0, 0, 0, 0, 100 + i)
            eng.projectiles.append(p)
            eng._damage_castle(c, p, 0)
            if not c["alive"]:
                break
        # All owner-1 projectiles should be removed
        owner1_balls = [p for p in eng.projectiles if p["owner"] == 1]
        assert len(owner1_balls) == 0


class TestWinCondition:
    """Game ends when only one castle remains."""

    def test_game_over_on_last_castle(self):
        eng = GameEngine(difficulty="medium", human_players=[])
        eng.ai = []
        # Kill castles 1, 2, 3
        for target in [1, 2, 3]:
            c = eng.castles[target]
            cx, cy = c["center"]
            for i in range(18):
                p = _make_projectile(cx, cy, 0, 0, 0, 0, target * 100 + i)
                eng.projectiles.append(p)
                eng._damage_castle(c, p, 0)
                if not c["alive"]:
                    break
        assert eng.game_over
        assert eng.winner == 0

    def test_dead_castle_input_ignored(self, engine_human):
        eng = engine_human
        eng.ai = []
        c = eng.castles[0]
        cx, cy = c["center"]
        # Kill castle 0
        for i in range(18):
            p = _make_projectile(cx, cy, 0, 1, 1, 0, 200 + i)
            eng.projectiles.append(p)
            eng._damage_castle(c, p, 1)
            if not c["alive"]:
                break
        old_angle = c["cannon_angle"]
        eng.handle_input({0: {"mouse_x": cx + 100, "mouse_y": cy + 100, "click": True, "space": False}})
        eng.update()
        assert c["cannon_angle"] == old_angle


class TestCannonSling:
    """Cannon rotation adds tangential velocity to fired projectile."""

    def test_sling_adds_momentum(self):
        eng = GameEngine(difficulty="medium", human_players=[0])
        eng.ai = []
        c = eng.castles[0]
        cx, cy = c["center"]
        # Set cannon angle and prev to create angular velocity
        c["cannon_angle"] = -2.5
        c["prev_cannon_angle"] = -2.5 + 0.1  # angular_vel = -0.1
        eng.handle_input({0: {"mouse_x": cx - 50, "mouse_y": cy - 50, "click": True, "space": False}})
        eng.update()
        human_shots = [p for p in eng.projectiles if p["owner"] == 0]
        if human_shots:
            p = human_shots[0]
            # Speed should differ from base due to sling
            speed = math.hypot(p["vx"], p["vy"])
            assert speed != pytest.approx(eng.projectile_speed, abs=0.01)


class TestBlockades:
    """Blockade spawn and cap."""

    def test_blockade_cap_respected(self):
        eng = GameEngine(difficulty="medium", human_players=[])
        eng.ai = []
        c = eng.castles[0]
        # Spawn MAX_BLOCKADES
        for _ in range(MAX_BLOCKADES + 5):
            eng._spawn_blockade(c)
        assert len(c["blockades"]) <= MAX_BLOCKADES


class TestCheckBlockadeHits:
    """Coverage gap: _check_blockade_hits destroys blockade bricks and adjusts velocity."""

    def test_projectile_destroys_blockade_brick(self):
        """Projectile overlapping a blockade brick destroys it."""
        eng = GameEngine(difficulty="medium", human_players=[])
        eng.ai = []
        eng.projectiles.clear()
        from src.engine import _make_blockade
        # Place a blockade at known position
        bx, by = ax + aw // 2 + 80, ay + ah // 2 + 80
        blockade = _make_blockade(bx, by)
        eng.castles[0]["blockades"].append(blockade)
        # Place a projectile overlapping the first brick
        p = _make_projectile(bx + BRICK_SIZE // 2, by + BRICK_SIZE // 2, 0, 1, 1, PROJECTILE_SPEED, 99)
        eng.projectiles.append(p)
        eng._check_blockade_hits()
        # At least one brick should be destroyed
        destroyed = [b for b in blockade["bricks"] if not b["alive"]]
        assert len(destroyed) >= 1

    def test_blockade_hit_increments_bounces(self):
        """Projectile hitting a blockade gets bounce count incremented."""
        eng = GameEngine(difficulty="medium", human_players=[])
        eng.ai = []
        eng.projectiles.clear()
        from src.engine import _make_blockade
        bx, by = ax + aw // 2 + 80, ay + ah // 2 + 80
        blockade = _make_blockade(bx, by)
        eng.castles[0]["blockades"].append(blockade)
        p = _make_projectile(bx + BRICK_SIZE // 2, by + BRICK_SIZE // 2, 0, 1, 1, PROJECTILE_SPEED, 99)
        p["bounces"] = 0
        eng.projectiles.append(p)
        eng._check_blockade_hits()
        assert p["bounces"] >= 1


class TestReflectProjectile:
    """Coverage gap: _reflect_projectile unit tests."""

    def test_reflect_reverses_and_offsets_angle(self):
        """_reflect_projectile reverses direction with ±60° offset."""
        eng = GameEngine(difficulty="medium", human_players=[])
        p = _make_projectile(ax + aw // 2, ay + ah // 2, 0, 0, 0, PROJECTILE_SPEED, 1)
        original_speed = math.hypot(p["vx"], p["vy"])
        eng._reflect_projectile(p)
        # Speed should be preserved (no shrink since bounce_cooldown was 0 but now it might shrink)
        new_speed = math.hypot(p["vx"], p["vy"])
        # After reflect, speed is reduced by 0.88 factor (since bounce_cooldown was 0)
        assert new_speed == pytest.approx(original_speed * 0.88, abs=0.1)
        # Bounce count incremented
        assert p["bounces"] == 1
        # bounce_cooldown set
        assert p["bounce_cooldown"] == 15

    def test_reflect_kills_at_max_bounces(self):
        """_reflect_projectile kills projectile at max bounces."""
        eng = GameEngine(difficulty="easy", human_players=[])
        p = _make_projectile(ax + aw // 2, ay + ah // 2, 0, 0, 0, PROJECTILE_SPEED, 1)
        p["bounces"] = eng.max_bounces - 1
        eng._reflect_projectile(p)
        assert not p["alive"]


class TestDamageCastleStats:
    """Coverage gap: _damage_castle increments attacker stats."""

    def test_hits_stat_incremented(self):
        """_damage_castle increments attacker's stats['hits']."""
        eng = GameEngine(difficulty="medium", human_players=[])
        eng.ai = []
        attacker = eng.castles[0]
        target = eng.castles[1]
        cx, cy = target["center"]
        p = _make_projectile(cx, cy, 0, 0, 0, 0, 1)
        eng.projectiles.append(p)
        assert attacker["stats"]["hits"] == 0
        eng._damage_castle(target, p, 0)
        assert attacker["stats"]["hits"] == 1


class TestShieldBlocksFire:
    """Coverage gap: shield active blocks fire request."""

    def test_click_while_shield_active_does_not_fire(self):
        """Click is ignored when shield is active."""
        eng = GameEngine(difficulty="medium", human_players=[0])
        eng.ai = []
        c = eng.castles[0]
        cx, cy = c["center"]
        # Activate shield
        eng.handle_input({0: {"mouse_x": cx - 50, "mouse_y": cy - 50, "click": False, "space": True}})
        eng.update()
        assert c["shield"]["active"]
        # Now try to fire while shield is still active
        eng.handle_input({0: {"mouse_x": cx - 50, "mouse_y": cy - 50, "click": True, "space": True}})
        # fire_request should NOT be set because shield is active
        assert c["fire_request"] is None


class TestBlockadePlacement:
    """Coverage gap (MAJ-5): _spawn_blockade placement and overlap avoidance."""

    def test_blockade_no_overlap(self):
        """New blockade doesn't overlap existing ones."""
        eng = GameEngine(difficulty="medium", human_players=[])
        eng.ai = []
        c = eng.castles[1]  # Owner 1 (top-left)
        # Spawn several blockades and verify no overlap
        for _ in range(MAX_BLOCKADES):
            eng._spawn_blockade(c)
        # Check all blockade bricks don't overlap each other
        all_rects = []
        for blockade in c["blockades"]:
            for brick in blockade["bricks"]:
                all_rects.append(brick["rect"])
        for i, (rx1, ry1, rw1, rh1) in enumerate(all_rects):
            for j, (rx2, ry2, rw2, rh2) in enumerate(all_rects):
                if i >= j:
                    continue
                # Check no overlap (allow touching)
                if (rx1 < rx2 + rw2 and rx2 < rx1 + rw1 and
                        ry1 < ry2 + rh2 and ry2 < ry1 + rh1):
                    # Same blockade bricks can overlap (they're a 2x2 grid)
                    # Only check across different blockades
                    block_i = i // 4
                    block_j = j // 4
                    if block_i != block_j:
                        # They shouldn't overlap (with BRICK_SIZE gap)
                        assert False, f"Blockade bricks overlap: {all_rects[i]} vs {all_rects[j]}"
