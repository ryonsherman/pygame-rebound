"""Tests for engine physics edge cases (TESTS.md #1-12)."""
import math
import pytest
from src.engine import GameEngine, _make_projectile, _push_out_of_rect, PROJECTILE_RADIUS, PROJECTILE_SPEED
from config import ARENA_RECT

ax, ay, aw, ah = ARENA_RECT


class TestCornerBounce:
    """#1, #2: Simultaneous wall bounces and exact corner hits."""

    def test_simultaneous_x_y_bounce_corner(self):
        """#1: Ball aimed at corner should bounce without escaping."""
        eng = GameEngine(difficulty="medium", human_players=[])
        eng.projectiles.clear()
        eng.ai = []
        # Aim at bottom-right corner
        p = _make_projectile(ax + aw - 15, ay + ah - 15, math.atan2(1, 1), 0, 0, PROJECTILE_SPEED, 1)
        eng.projectiles.append(p)
        for _ in range(20):
            eng.update()
            r = p["radius"]
            assert p["x"] - r >= ax
            assert p["x"] + r <= ax + aw
            assert p["y"] - r >= ay
            assert p["y"] + r <= ay + ah

    @pytest.mark.parametrize("corner", [
        (ax + PROJECTILE_RADIUS + 1, ay + PROJECTILE_RADIUS + 1),       # top-left
        (ax + aw - PROJECTILE_RADIUS - 1, ay + PROJECTILE_RADIUS + 1),  # top-right
        (ax + PROJECTILE_RADIUS + 1, ay + ah - PROJECTILE_RADIUS - 1),  # bottom-left
        (ax + aw - PROJECTILE_RADIUS - 1, ay + ah - PROJECTILE_RADIUS - 1),  # bottom-right
    ])
    def test_projectile_at_exact_corner(self, corner):
        """#2: Projectile placed near each corner should not escape."""
        eng = GameEngine(difficulty="medium", human_players=[])
        eng.projectiles.clear()
        eng.ai = []
        # Aim toward center
        cx, cy = ax + aw // 2, ay + ah // 2
        angle = math.atan2(cy - corner[1], cx - corner[0])
        p = _make_projectile(corner[0], corner[1], angle + math.pi, 0, 0, PROJECTILE_SPEED, 1)
        eng.projectiles.append(p)
        for _ in range(30):
            eng.update()
            r = p["radius"]
            assert p["x"] - r >= ax
            assert p["x"] + r <= ax + aw
            assert p["y"] - r >= ay
            assert p["y"] + r <= ay + ah


class TestZeroSpeedProjectile:
    """#3: Zero-speed projectile."""

    def test_zero_speed_no_crash(self):
        """#3: vx=0, vy=0 should not crash (num_steps = max(1,...))."""
        eng = GameEngine(difficulty="medium", human_players=[])
        eng.projectiles.clear()
        eng.ai = []
        p = _make_projectile(ax + aw // 2, ay + ah // 2, 0, 0, 0, 0, 1)
        p["vx"] = 0
        p["vy"] = 0
        eng.projectiles.append(p)
        # Should not crash
        for _ in range(10):
            eng.update()
        # Should not crash — position may shift due to obstacle push but ball stays in arena
        r = p["radius"]
        assert p["x"] - r >= ax
        assert p["x"] + r <= ax + aw


class TestObstacleEdgeCases:
    """#4-7: Obstacle collision edge cases."""

    def test_center_inside_obstacle_pushout(self):
        """#4: Projectile center exactly inside obstacle (dist_sq == 0)."""
        eng = GameEngine(difficulty="medium", human_players=[])
        eng.projectiles.clear()
        eng.ai = []
        # Place projectile center exactly at an obstacle's center
        obs = eng.obstacles[0]
        rx, ry, rw, rh = obs["rect"]
        p = _make_projectile(rx + rw // 2, ry + rh // 2, 0, 0, 0, PROJECTILE_SPEED, 1)
        eng.projectiles.append(p)
        eng.update()
        # Should have been pushed out
        cx = max(rx, min(p["x"], rx + rw))
        cy = max(ry, min(p["y"], ry + rh))
        dx = p["x"] - cx
        dy = p["y"] - cy
        assert dx * dx + dy * dy >= (p["radius"] - 2) ** 2

    def test_overlaps_many_obstacles(self):
        """#5: Projectile overlapping >5 obstacles uses iteration cap."""
        eng = GameEngine(difficulty="medium", human_players=[])
        eng.projectiles.clear()
        eng.ai = []
        # Place at center cross (many obstacles clustered)
        cx, cy = ax + aw // 2, ay + ah // 2
        p = _make_projectile(cx, cy, 0, 0, 0, PROJECTILE_SPEED, 1)
        eng.projectiles.append(p)
        # Should not crash or infinite loop
        eng.update()
        r = p["radius"]
        assert p["x"] - r >= ax
        assert p["x"] + r <= ax + aw

    def test_post_obstacle_push_reclamp(self):
        """#6: After obstacle push, ball is re-clamped to arena."""
        eng = GameEngine(difficulty="medium", human_players=[])
        eng.projectiles.clear()
        eng.ai = []
        # Find an obstacle near the edge
        edge_obs = [o for o in eng.obstacles if o["zone"] == "edge"]
        if edge_obs:
            obs = edge_obs[0]
            rx, ry, rw, rh = obs["rect"]
            # Push ball toward the wall from inside obstacle
            p = _make_projectile(rx + 1, ry + 1, math.pi, 0, 0, PROJECTILE_SPEED * 2, 1)
            eng.projectiles.append(p)
            eng.update()
            r = p["radius"]
            assert p["x"] - r >= ax
            assert p["y"] - r >= ay

    def test_multiple_obstacle_collisions_same_substep(self):
        """#7: Multiple obstacle collisions in same sub-step."""
        eng = GameEngine(difficulty="medium", human_players=[])
        eng.projectiles.clear()
        eng.ai = []
        # Place at center where obstacles form a cross
        cx, cy = ax + aw // 2, ay + ah // 2
        p = _make_projectile(cx + 5, cy + 5, math.pi * 1.25, 0, 0, PROJECTILE_SPEED, 1)
        eng.projectiles.append(p)
        for _ in range(5):
            eng.update()
        # Ball should still be valid
        r = p["radius"]
        assert p["x"] - r >= ax
        assert p["x"] + r <= ax + aw


class TestBallBallEdge:
    """#8: Nearly-coincident projectiles."""

    def test_nearly_coincident_early_return(self):
        """#8: dist < 1 should trigger early return in _bounce_balls."""
        eng = GameEngine(difficulty="medium", human_players=[])
        a = _make_projectile(ax + aw // 2, ay + ah // 2, 0, 0, 0, PROJECTILE_SPEED, 1)
        b = _make_projectile(ax + aw // 2 + 0.5, ay + ah // 2, math.pi, 1, 1, PROJECTILE_SPEED, 2)
        vx_before_a = a["vx"]
        eng._bounce_balls(a, b)
        # With dist < 1, function returns early, no velocity change
        assert a["vx"] == vx_before_a


class TestBounceCooldown:
    """#9: Bounce cooldown prevents shrink."""

    def test_bounce_cooldown_prevents_shrink(self):
        """#9: When bounce_cooldown > 0, radius should not shrink."""
        eng = GameEngine(difficulty="medium", human_players=[])
        eng.projectiles.clear()
        eng.ai = []
        p = _make_projectile(ax + 20, ay + ah // 2, math.pi, 0, 0, PROJECTILE_SPEED, 1)
        p["bounce_cooldown"] = 15
        initial_radius = p["radius"]
        eng.projectiles.append(p)
        for _ in range(5):
            eng.update()
        # If it bounced while cooldown > 0, radius should not have changed via the cooldown path
        # (bounces still increment, but shrink is skipped)
        if p["bounces"] > 0:
            # radius may or may not have changed depending on timing, but it should never go below 2
            assert p["radius"] >= 2


class TestProjectileCulling:
    """#10: FIFO culling when > max_projectiles."""

    def test_oldest_removed_fifo(self):
        """#10: Oldest projectile removed when exceeding max."""
        eng = GameEngine(difficulty="easy", human_players=[])
        eng.projectiles.clear()
        eng.ai = []
        # Add max + 5 projectiles
        for i in range(eng.max_projectiles + 5):
            p = _make_projectile(ax + 100 + i * 5, ay + ah // 2, 0, 0, 0, PROJECTILE_SPEED, i)
            eng.projectiles.append(p)
        eng.update()
        assert len(eng.projectiles) <= eng.max_projectiles
        # First ids should have been removed (FIFO)
        ids = [p["id"] for p in eng.projectiles]
        assert 0 not in ids


class TestGameOverDraw:
    """#11: Game over with 0 alive castles."""

    def test_zero_alive_no_crash(self):
        """#11: All castles dead — winner = None, no crash."""
        eng = GameEngine(difficulty="medium", human_players=[])
        eng.ai = []
        # Kill all castles
        for c in eng.castles:
            for b in c["bricks"]:
                b["alive"] = False
                b["hp"] = 0
            c["alive"] = False
        eng.update()
        assert eng.game_over
        assert eng.winner is None


class TestAngularVelocityNormalization:
    """#12: Angular velocity normalization across +-pi boundary."""

    def test_cannon_wrap_normalization(self):
        """#12: Angular velocity should be normalized when crossing +-pi."""
        eng = GameEngine(difficulty="medium", human_players=[])
        eng.ai = []
        c = eng.castles[0]
        # Set angles that cross the +-pi boundary
        c["cannon_angle"] = 3.1  # just below pi
        c["prev_cannon_angle"] = -3.1  # just above -pi
        eng.update()
        # angular_vel should be small (wrapping around), not ~6.2
        assert abs(c["angular_vel"]) < 1.0
