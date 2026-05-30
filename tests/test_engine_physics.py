"""Tests for physics engine: wall bounces, sub-stepping, obstacle collisions, ball-ball."""
import math
import pytest
from src.engine import GameEngine, _make_projectile, PROJECTILE_RADIUS, PROJECTILE_SPEED
from config import ARENA_RECT


ax, ay, aw, ah = ARENA_RECT


class TestWallBounce:
    """Projectiles must stay within arena bounds and bounce off walls."""

    def test_projectile_stays_in_arena(self, engine_hard):
        """Run 1000 frames, all projectiles must remain within arena."""
        eng = engine_hard
        for _ in range(1000):
            eng.update()
            for p in eng.projectiles:
                r = p["radius"]
                assert p["x"] - r >= ax, f"Ball escaped left: x={p['x']}, r={r}"
                assert p["x"] + r <= ax + aw, f"Ball escaped right: x={p['x']}, r={r}"
                assert p["y"] - r >= ay, f"Ball escaped top: y={p['y']}, r={r}"
                assert p["y"] + r <= ay + ah, f"Ball escaped bottom: y={p['y']}, r={r}"

    def test_wall_bounce_increments_bounce_count(self):
        """A projectile heading directly at a wall should bounce and increment count."""
        eng = GameEngine(difficulty="medium", human_players=[])
        eng.projectiles.clear()
        eng.ai = []
        # Projectile heading straight left toward the left wall
        p = _make_projectile(ax + 20, ay + ah // 2, math.pi, 0, 0, PROJECTILE_SPEED, 99)
        eng.projectiles.append(p)
        for _ in range(10):
            eng.update()
        assert p["bounces"] >= 1

    def test_max_bounces_kills_projectile(self):
        """A projectile at max_bounces-1 should die on next bounce."""
        eng = GameEngine(difficulty="easy", human_players=[])
        eng.projectiles.clear()
        eng.ai = []
        p = _make_projectile(ax + 10, ay + ah // 2, math.pi, 0, 0, PROJECTILE_SPEED, 99)
        p["bounces"] = eng.max_bounces - 1
        eng.projectiles.append(p)
        for _ in range(5):
            eng.update()
        assert not p["alive"]


class TestSubStepping:
    """Sub-stepping prevents tunneling through obstacles."""

    def test_fast_projectile_no_tunnel(self):
        """A fast projectile should not pass through arena walls."""
        eng = GameEngine(difficulty="hard", human_players=[])
        eng.projectiles.clear()
        eng.ai = []
        # Very fast projectile aimed at right wall
        p = _make_projectile(ax + aw - 30, ay + ah // 2, 0, 0, 0, PROJECTILE_SPEED * 3, 99)
        eng.projectiles.append(p)
        eng.update()
        assert p["x"] + p["radius"] <= ax + aw


class TestObstacleCollision:
    """Projectiles should bounce off obstacles without getting stuck."""

    def test_no_projectile_stuck_in_obstacle(self, engine_hard):
        """After 800 frames, no alive projectile should overlap an obstacle."""
        eng = engine_hard
        for _ in range(800):
            eng.update()
        for p in eng.projectiles:
            r = p["radius"]
            for obs in eng.obstacles:
                if "rect" in obs:
                    rx, ry, rw, rh = obs["rect"]
                elif "corners" in obs:
                    corners = obs["corners"]
                    min_x = min(c[0] for c in corners)
                    max_x = max(c[0] for c in corners)
                    min_y = min(c[1] for c in corners)
                    max_y = max(c[1] for c in corners)
                    rx, ry, rw, rh = min_x, min_y, max_x - min_x, max_y - min_y
                else:
                    continue
                cx = max(rx, min(p["x"], rx + rw))
                cy = max(ry, min(p["y"], ry + rh))
                dx = p["x"] - cx
                dy = p["y"] - cy
                # Allow 1px tolerance for floating point
                assert dx * dx + dy * dy >= (r - 1) ** 2, (
                    f"Ball {p['id']} stuck in obstacle at ({p['x']:.1f},{p['y']:.1f})"
                )


class TestBallBallCollision:
    """Elastic ball-ball collisions."""

    def test_overlapping_balls_separate(self):
        """Two overlapping projectiles should be pushed apart."""
        eng = GameEngine(difficulty="medium", human_players=[])
        eng.projectiles.clear()
        eng.ai = []
        a = _make_projectile(ax + aw // 2, ay + ah // 2, 0, 0, 0, PROJECTILE_SPEED, 1)
        b = _make_projectile(ax + aw // 2 + 3, ay + ah // 2, math.pi, 1, 1, PROJECTILE_SPEED, 2)
        a["ball_cd"] = 0
        b["ball_cd"] = 0
        eng.projectiles.extend([a, b])
        eng.update()
        dist = math.hypot(a["x"] - b["x"], a["y"] - b["y"])
        assert dist >= a["radius"] + b["radius"] - 1

    def test_ball_collision_cooldown(self):
        """After collision, ball_cd should be set to 8."""
        eng = GameEngine(difficulty="medium", human_players=[])
        eng.projectiles.clear()
        eng.ai = []
        # Place balls overlapping (distance 2 < radius*2=12) with zero velocity
        # so they don't move apart before collision check
        a = _make_projectile(ax + aw // 2, ay + ah // 2, 0, 0, 0, 0, 1)
        b = _make_projectile(ax + aw // 2 + 2, ay + ah // 2, math.pi, 1, 1, 0, 2)
        a["vx"], a["vy"] = 1, 0
        b["vx"], b["vy"] = -1, 0
        a["ball_cd"] = 0
        b["ball_cd"] = 0
        eng.projectiles.extend([a, b])
        eng.update()
        # Balls were overlapping so collision must have occurred
        assert a["ball_cd"] == 8
        assert b["ball_cd"] == 8


class TestProjectileShrink:
    """Projectile radius shrinks on bounce but never below 2."""

    def test_radius_never_below_2(self, engine_hard):
        """After many frames, no projectile radius should be < 2."""
        eng = engine_hard
        for _ in range(2000):
            eng.update()
            for p in eng.projectiles:
                assert p["radius"] >= 2
