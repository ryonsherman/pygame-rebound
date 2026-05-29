import math
import random
from config import (
    ARENA_RECT, CASTLE_SIZE, BRICK_SIZE, BRICKS_PER_CASTLE,
    FIRE_COOLDOWN, SHIELD_DURATION, SHIELD_COOLDOWN, SHIELD_RADIUS,
    PROJECTILE_RADIUS, PROJECTILE_SPEED, MAX_PROJECTILES, MAX_BLOCKADES,
)

def _sound_vol(p):
    return max(0.2, min(1.0, p["radius"] / PROJECTILE_RADIUS))

DEBUG = False

def _clamp_aim(owner, mx, my, cx, cy):
    ax, ay, aw, ah = ARENA_RECT
    if owner == 0:
        mx = max(ax, min(mx, cx - 1))
        my = max(ay, min(my, cy - 1))
    elif owner == 1:
        mx = max(cx + 1, min(mx, ax + aw))
        my = max(cy + 1, min(my, ay + ah))
    elif owner == 2:
        mx = max(ax, min(mx, cx - 1))
        my = max(cy + 1, min(my, ay + ah))
    else:
        mx = max(cx + 1, min(mx, ax + aw))
        my = max(ay, min(my, cy - 1))
    return mx, my

def _corner_positions():
    ax, ay, aw, ah = ARENA_RECT
    m = 4
    return [
        (ax + aw - CASTLE_SIZE - m, ay + ah - CASTLE_SIZE - m),
        (ax + m, ay + m),
        (ax + aw - CASTLE_SIZE - m, ay + m),
        (ax + m, ay + ah - CASTLE_SIZE - m),
    ]

def _init_bricks(cx, cy):
    cols = int(BRICKS_PER_CASTLE ** 0.5)
    rows = (BRICKS_PER_CASTLE + cols - 1) // cols
    total_w = cols * BRICK_SIZE
    total_h = rows * BRICK_SIZE
    ox = cx + (CASTLE_SIZE - total_w) // 2
    oy = cy + (CASTLE_SIZE - total_h) // 2
    # counter-clockwise from top-right, center last
    order = [(0, 2), (1, 2), (2, 2), (2, 1), (2, 0), (1, 0), (0, 0), (0, 1), (1, 1)]
    bricks = []
    for r, c in order:
        bx = ox + c * BRICK_SIZE
        by = oy + r * BRICK_SIZE
        bricks.append({"alive": True, "hp": 2, "rect": (bx, by, BRICK_SIZE, BRICK_SIZE)})
    return bricks

_ball_id_counter = 0

def _make_projectile(x, y, angle, owner, color_idx, speed):
    global _ball_id_counter
    _ball_id_counter += 1
    return {
        "x": x, "y": y,
        "vx": math.cos(angle) * speed,
        "vy": math.sin(angle) * speed,
        "owner": owner,
        "color_idx": color_idx,
        "alive": True,
        "radius": PROJECTILE_RADIUS,
        "bounces": 0,
        "bounce_cooldown": 0,
        "ball_cd": 0,
        "id": _ball_id_counter,
    }

def _random_blockade_pos(owner):
    ax, ay, aw, ah = ARENA_RECT
    cx = ax + aw // 2
    cy = ay + ah // 2
    bw = BRICK_SIZE * 2
    margin = CASTLE_SIZE
    positions = _corner_positions()
    c_x, c_y = positions[owner]
    if owner == 1:
        min_x = c_x + CASTLE_SIZE + margin
        min_y = c_y + CASTLE_SIZE + margin
        max_x = cx - bw
        max_y = cy - bw
    elif owner == 0:
        min_x = cx + BRICK_SIZE
        min_y = cy + BRICK_SIZE
        max_x = c_x - margin - bw
        max_y = c_y - margin - bw
    elif owner == 2:
        min_x = cx + BRICK_SIZE
        min_y = c_y + CASTLE_SIZE + margin
        max_x = c_x - margin - bw
        max_y = cy - bw
    else:
        min_x = c_x + CASTLE_SIZE + margin
        min_y = cy + BRICK_SIZE
        max_x = cx - bw
        max_y = c_y - margin - bw
    if min_x >= max_x or min_y >= max_y:
        return None
    x = random.randint(int(min_x), int(max_x))
    y = random.randint(int(min_y), int(max_y))
    return (x, y)

def _make_blockade(x, y):
    return {
        "alive": True,
        "bricks": [
            {"alive": True, "rect": (x, y, BRICK_SIZE, BRICK_SIZE)},
            {"alive": True, "rect": (x + BRICK_SIZE, y, BRICK_SIZE, BRICK_SIZE)},
            {"alive": True, "rect": (x, y + BRICK_SIZE, BRICK_SIZE, BRICK_SIZE)},
            {"alive": True, "rect": (x + BRICK_SIZE, y + BRICK_SIZE, BRICK_SIZE, BRICK_SIZE)},
        ],
    }

COLOR_LETTERS = ["R", "B", "G", "Y"]
OBSTACLE_COLOR = (100, 100, 110)

def _init_obstacles():
    ax, ay, aw, ah = ARENA_RECT
    cx = ax + aw // 2
    cy = ay + ah // 2
    bs = BRICK_SIZE
    m = 3
    obs = []

    for i in range(4):
        obs.append({"rect": (cx - bs // 2, ay + m + i * bs, bs, bs), "zone": "edge"})
        obs.append({"rect": (cx - bs // 2, ay + ah - m - (i + 1) * bs, bs, bs), "zone": "edge"})
        obs.append({"rect": (ax + m + i * bs, cy - bs // 2, bs, bs), "zone": "edge"})
        obs.append({"rect": (ax + aw - m - (i + 1) * bs, cy - bs // 2, bs, bs), "zone": "edge"})

    for i in range(-2, 3):
        obs.append({"rect": (cx + i * bs - bs // 2, cy - bs // 2, bs, bs), "zone": "center"})

    for i in range(-2, 3):
        if i == 0:
            continue
        obs.append({"rect": (cx - bs // 2, cy + i * bs - bs // 2, bs, bs), "zone": "center"})

    return obs

def _push_out_of_rect(p, rx, ry, rw, rh):
    cx = max(rx, min(p["x"], rx + rw))
    cy = max(ry, min(p["y"], ry + rh))
    dx = p["x"] - cx
    dy = p["y"] - cy
    if dx * dx + dy * dy >= p["radius"] * p["radius"]:
        return False
    overlap_x = p["radius"] - abs(dx) if abs(dx) < p["radius"] else p["radius"]
    overlap_y = p["radius"] - abs(dy) if abs(dy) < p["radius"] else p["radius"]
    if overlap_x < overlap_y:
        if dx >= 0:
            p["x"] = cx + p["radius"]
        else:
            p["x"] = cx - p["radius"]
    else:
        if dy >= 0:
            p["y"] = cy + p["radius"]
        else:
            p["y"] = cy - p["radius"]
    return True

class AIController:
    def __init__(self, owner_idx, difficulty="medium", obstacles=None):
        self.owner = owner_idx
        self.obstacles = obstacles or []
        self.set_difficulty(difficulty)
        self.fire_timer = random.randint(*self.fire_interval)
        self.retarget_timer = 0
        self.target = None
        self.aim_offset = (0, 0)
        ax, ay, aw, ah = ARENA_RECT
        arena_cx, arena_cy = ax + aw // 2, ay + ah // 2
        positions = _corner_positions()
        cx, cy = positions[owner_idx]
        ccx = cx + CASTLE_SIZE // 2
        ccy = cy + CASTLE_SIZE // 2
        self.current_angle = math.atan2(arena_cy - ccy, arena_cx - ccx)
        self.aim_point = None
        self.shield_hold = 0
        self.sling_state = None  # None, "winding", or "sweeping"
        self.sling_dir = 0
        self.sling_overshoot = 0

    def set_difficulty(self, difficulty):
        if difficulty == "easy":
            self.fire_interval = (90, 180)
            self.aim_spread = 60
            self.shield_range = 100
            self.prediction_frames = 30
            self.rot_speed = 0.02
            self.bounce_chance = 0.1
            self.obstacle_awareness = 0.3
            self.sling_chance = 0.1
            self.sling_speed = 0.08
        elif difficulty == "hard":
            self.fire_interval = (30, 90)
            self.aim_spread = 15
            self.shield_range = 180
            self.prediction_frames = 60
            self.rot_speed = 0.06
            self.bounce_chance = 0.4
            self.obstacle_awareness = 1.0
            self.sling_chance = 0.5
            self.sling_speed = 0.15
        else:
            self.fire_interval = (60, 150)
            self.aim_spread = 35
            self.shield_range = 140
            self.prediction_frames = 45
            self.rot_speed = 0.04
            self.bounce_chance = 0.25
            self.obstacle_awareness = 0.8
            self.sling_chance = 0.3
            self.sling_speed = 0.10

    @staticmethod
    def _segments_intersect(x1, y1, x2, y2, x3, y3, x4, y4):
        def ccw(ax, ay, bx, by, cx, cy):
            return (cy - ay) * (bx - ax) > (by - ay) * (cx - ax)
        return (ccw(x1, y1, x3, y3, x4, y4) != ccw(x2, y2, x3, y3, x4, y4) and
                ccw(x1, y1, x2, y2, x3, y3) != ccw(x1, y1, x2, y2, x4, y4))

    def _line_intersects_rect(self, x1, y1, x2, y2, rect):
        rx, ry, rw, rh = rect
        if rx <= x1 <= rx + rw and ry <= y1 <= ry + rh:
            return True
        if rx <= x2 <= rx + rw and ry <= y2 <= ry + rh:
            return True
        if self._segments_intersect(x1, y1, x2, y2, rx, ry, rx, ry + rh):
            return True
        if self._segments_intersect(x1, y1, x2, y2, rx + rw, ry, rx + rw, ry + rh):
            return True
        if self._segments_intersect(x1, y1, x2, y2, rx, ry, rx + rw, ry):
            return True
        if self._segments_intersect(x1, y1, x2, y2, rx, ry + rh, rx + rw, ry + rh):
            return True
        return False

    def _angle_in_quadrant(self, aim_angle):
        if self.owner == 0:
            return -math.pi <= aim_angle <= -math.pi / 2
        if self.owner == 1:
            return 0 <= aim_angle <= math.pi / 2
        if self.owner == 2:
            return math.pi / 2 <= aim_angle <= math.pi
        return -math.pi / 2 <= aim_angle <= 0

    def _line_blocked(self, x1, y1, x2, y2, exclude=None):
        for obs in self.obstacles:
            if exclude is not None and obs["rect"] == exclude:
                continue
            if self._line_intersects_rect(x1, y1, x2, y2, obs["rect"]):
                return True
        return False

    def _eval_brick_bounce(self, mx, my, tx, ty, rx, ry, rw, rh):
        bcx = rx + rw / 2
        bcy = ry + rh / 2
        faces = []
        if tx < bcx:
            faces.append(("right", rx + rw))
        elif tx > bcx:
            faces.append(("left", rx))
        if ty < bcy:
            faces.append(("bottom", ry + rh))
        elif ty > bcy:
            faces.append(("top", ry))

        for face_name, face_pos in faces:
            if face_name in ("left", "right"):
                wx = 2 * face_pos - tx
                wy = ty
            else:
                wx = tx
                wy = 2 * face_pos - ty
            if self._line_blocked(mx, my, wx, wy, exclude=(rx, ry, rw, rh)):
                continue
            if not self._angle_in_quadrant(math.atan2(wy - my, wx - mx)):
                continue
            if face_name in ("left", "right"):
                if abs(wx - mx) < 0.01:
                    continue
                t = (face_pos - mx) / (wx - mx)
                hit_y = my + t * (wy - my)
                if ry <= hit_y <= ry + rh:
                    return (wx, wy)
            else:
                if abs(wy - my) < 0.01:
                    continue
                t = (face_pos - my) / (wy - my)
                hit_x = mx + t * (wx - mx)
                if rx <= hit_x <= rx + rw:
                    return (wx, wy)
        return None

    def _find_bounce_point(self, mx, my, tx, ty, castles):
        ax, ay, aw, ah = ARENA_RECT
        candidates = []

        dx, dy = tx - mx, ty - my
        if abs(dx) >= abs(dy):
            primary = "left" if dx > 0 else "right"
            sec_a = "top" if dy > 0 else "bottom"
            sec_b = "bottom" if dy > 0 else "top"
            wall_order = [primary, sec_a, sec_b]
        else:
            primary = "top" if dy > 0 else "bottom"
            sec_a = "left" if dx > 0 else "right"
            sec_b = "right" if dx > 0 else "left"
            wall_order = [primary, sec_a, sec_b]

        for wall in wall_order:
            if wall == "left":
                wx, wy = 2 * ax - tx, ty
            elif wall == "right":
                wx, wy = 2 * (ax + aw) - tx, ty
            elif wall == "top":
                wx, wy = tx, 2 * ay - ty
            else:
                wx, wy = tx, 2 * (ay + ah) - ty
            if self._line_blocked(mx, my, wx, wy):
                continue
            if not self._angle_in_quadrant(math.atan2(wy - my, wx - mx)):
                continue
            candidates.append((wx, wy, 0))

        for obs in self.obstacles:
            if obs.get("zone") != "center":
                continue
            result = self._eval_brick_bounce(mx, my, tx, ty, *obs["rect"])
            if result:
                candidates.append((*result, 1))

        for c in castles:
            for blockade in c["blockades"]:
                if not blockade["alive"]:
                    continue
                for brick in blockade["bricks"]:
                    if not brick["alive"]:
                        continue
                    result = self._eval_brick_bounce(mx, my, tx, ty, *brick["rect"])
                    if result:
                        candidates.append((*result, 2))

        if not candidates:
            return None
        candidates.sort(key=lambda x: x[2])
        return (candidates[0][0], candidates[0][1])

    def _pick_aim_point(self, target_center, my_center, castles):
        tx = target_center[0] + self.aim_offset[0]
        ty = target_center[1] + self.aim_offset[1]

        aim = self._find_bounce_point(my_center[0], my_center[1], tx, ty, castles)
        if aim is not None:
            self.aim_point = aim
        else:
            self.aim_point = (tx, ty)

    def update(self, castles, projectiles):
        my_castle = castles[self.owner]
        if not my_castle["alive"]:
            return

        alive_targets = [
            (c["center"], c["owner"]) for c in castles
            if c["alive"] and c["owner"] != self.owner
        ]
        if not alive_targets:
            return

        self.retarget_timer -= 1
        if (self.target is None or
            not castles[self.target]["alive"] or
            self.retarget_timer <= 0 or
            self.fire_timer <= 0):
            chosen = random.choice(alive_targets)
            self.target = chosen[1]
            self.aim_offset = (random.randint(-self.aim_spread, self.aim_spread),
                               random.randint(-self.aim_spread, self.aim_spread))
            self.retarget_timer = random.randint(15, 45)
            self._pick_aim_point(chosen[0], my_castle["center"], castles)
            print(f"{COLOR_LETTERS[self.owner]} → targeting {COLOR_LETTERS[self.target]} (bounce)")

        if self.aim_point:
            cx, cy = my_castle["center"]
            ax, ay = _clamp_aim(self.owner, self.aim_point[0], self.aim_point[1], cx, cy)
            dx = ax - cx
            dy = ay - cy
            target_angle = math.atan2(dy, dx)
            diff = target_angle - self.current_angle
            diff = math.atan2(math.sin(diff), math.cos(diff))

            if self.sling_state == "winding":
                # Wind up: rotate away from target
                self.current_angle += self.sling_dir * self.rot_speed
                self.sling_overshoot -= self.rot_speed
                if self.sling_overshoot <= 0:
                    self.sling_state = "sweeping"
            elif self.sling_state == "sweeping":
                # Sweep through target at sling speed
                self.current_angle -= self.sling_dir * self.sling_speed
                # Check if we've crossed the target angle
                new_diff = target_angle - self.current_angle
                new_diff = math.atan2(math.sin(new_diff), math.cos(new_diff))
                if abs(new_diff) < self.sling_speed * 1.5:
                    # Fire now while sweeping through
                    self.current_angle = target_angle
                    self.sling_state = None
                    if not my_castle["shield"]["active"]:
                        self._fire(my_castle)
                        print(f"{COLOR_LETTERS[self.owner]} → sling-fired at {COLOR_LETTERS[self.target]}")
                        self.fire_timer = random.randint(*self.fire_interval)
            else:
                # Normal rotation toward target
                if abs(diff) < self.rot_speed:
                    self.current_angle = target_angle
                else:
                    self.current_angle += self.rot_speed if diff > 0 else -self.rot_speed

        my_castle["cannon_angle"] = self.current_angle

        self.fire_timer -= 1
        if self.fire_timer <= 0 and self.sling_state is None:
            if not my_castle["shield"]["active"] and self.aim_point is not None:
                # Decide whether to sling or fire normally
                if random.random() < self.sling_chance:
                    # Start sling: wind up in random direction
                    self.sling_dir = random.choice([-1, 1])
                    self.sling_overshoot = random.uniform(0.15, 0.4)
                    self.sling_state = "winding"
                else:
                    self._fire(my_castle)
                    print(f"{COLOR_LETTERS[self.owner]} → fired at {COLOR_LETTERS[self.target]}")
                    self.fire_timer = random.randint(*self.fire_interval)
            else:
                self.fire_timer = random.randint(*self.fire_interval)

        threat = False
        threat_from = None
        threat_frames = None
        cx, cy = my_castle["center"]
        for p in projectiles:
            if not p["alive"]:
                continue
            dx = p["x"] - cx
            dy = p["y"] - cy
            dist_sq = dx * dx + dy * dy
            if dist_sq > self.shield_range * self.shield_range:
                continue
            if dist_sq < 60 * 60:
                threat = True
                threat_from = p["owner"]
                threat_frames = 0
                break
            speed = math.hypot(p["vx"], p["vy"])
            if speed < 1:
                continue
            t = -(dx * p["vx"] + dy * p["vy"]) / (speed * speed)
            t = max(0, min(t, self.prediction_frames))
            close_x = p["x"] + p["vx"] * t
            close_y = p["y"] + p["vy"] * t
            close_dx = close_x - cx
            close_dy = close_y - cy
            if close_dx * close_dx + close_dy * close_dy < 55 * 55:
                threat = True
                threat_from = p["owner"]
                threat_frames = int(t)
                break

        if threat:
            if not my_castle["shield"]["active"] and my_castle["shield"]["cooldown_timer"] <= 0:
                threat_label = f"{COLOR_LETTERS[threat_from]}" if threat_from is not None else "reflected"
                if threat_frames and threat_frames > 0:
                    print(f"{COLOR_LETTERS[self.owner]} → shield UP ({threat_label}'s shot in ~{threat_frames}f)")
                else:
                    print(f"{COLOR_LETTERS[self.owner]} → shield UP ({threat_label} close)")
                my_castle["shield"]["active"] = True
                my_castle["shield"]["timer"] = SHIELD_DURATION
            self.shield_hold = 10
        elif self.shield_hold > 0:
            self.shield_hold -= 1
        else:
            if my_castle["shield"]["active"]:
                print(f"{COLOR_LETTERS[self.owner]} → shield DOWN (threat passed)")
                my_castle["shield"]["active"] = False

    def _fire(self, castle):
        castle["fire_request"] = self.current_angle

class GameEngine:
    def __init__(self, difficulty="hard", human_players=None):
        self.difficulty = difficulty
        speed_mult = {"easy": 0.9, "medium": 1.0, "hard": 1.1}.get(difficulty, 1.0)
        self.projectile_speed = PROJECTILE_SPEED * speed_mult
        self.projectiles = []
        self.castles = self._init_castles()
        if human_players is None:
            human_players = [0]
        self.human_players = set(human_players)
        self.obstacles = _init_obstacles()
        self.ai = [AIController(i, difficulty, self.obstacles) for i in range(4) if i not in self.human_players]
        self.frame = 0
        self.game_over = False
        self.winner = None
        self.sound_events = []

    def _init_castles(self):
        positions = _corner_positions()
        ax, ay, aw, ah = ARENA_RECT
        arena_cx = ax + aw // 2
        arena_cy = ay + ah // 2
        castles = []
        for i, (cx, cy) in enumerate(positions):
            ccx = cx + CASTLE_SIZE // 2
            ccy = cy + CASTLE_SIZE // 2
            castles.append({
                "owner": i,
                "alive": True,
                "rect": (cx, cy, CASTLE_SIZE, CASTLE_SIZE),
                "center": (ccx, ccy),
                "bricks": _init_bricks(cx, cy),
                "cannon_angle": math.atan2(arena_cy - ccy, arena_cx - ccx),
                "prev_cannon_angle": math.atan2(arena_cy - ccy, arena_cx - ccx),
                "cannon_cooldown": 0,
                "shield": {"active": False, "timer": 0, "cooldown_timer": 0},
                "fire_request": None,
                "blockades": [],
                "stats": {"hits": 0, "blocks": 0},
            })
        return castles

    def _emit_sound(self, event_type, base_vol, owner=None):
        vol = min(1.0, base_vol * (1.3 if owner is not None and owner in self.human_players else 1.0))
        self.sound_events.append({"type": event_type, "volume": vol})

    def handle_input(self, player_inputs):
        if self.game_over:
            return
        for player_idx, inp in player_inputs.items():
            if player_idx not in self.human_players:
                continue
            castle = self.castles[player_idx]
            if not castle["alive"]:
                continue

            mx = inp.get("mouse_x", 0)
            my = inp.get("mouse_y", 0)
            cx, cy = castle["center"]
            mx, my = _clamp_aim(player_idx, mx, my, cx, cy)
            castle["cannon_angle"] = math.atan2(my - cy, mx - cx)

            if inp.get("space", False):
                s = castle["shield"]
                if s["cooldown_timer"] <= 0:
                    s["active"] = True
                    s["timer"] = SHIELD_DURATION
            else:
                castle["shield"]["active"] = False

            if inp.get("click", False) and not castle["shield"]["active"]:
                castle["fire_request"] = castle["cannon_angle"]

    def update(self):
        self.sound_events.clear()
        if self.game_over:
            return

        self.frame += 1

        for c in self.castles:
            if not c["alive"]:
                continue
            # Track angular velocity for cannon sling
            angle_diff = c["cannon_angle"] - c["prev_cannon_angle"]
            # Normalize to [-pi, pi]
            if angle_diff > math.pi:
                angle_diff -= 2 * math.pi
            elif angle_diff < -math.pi:
                angle_diff += 2 * math.pi
            c["angular_vel"] = angle_diff
            c["prev_cannon_angle"] = c["cannon_angle"]

            if c["cannon_cooldown"] > 0:
                c["cannon_cooldown"] -= 1
            s = c["shield"]
            if s["active"]:
                s["timer"] -= 1
                if s["timer"] <= 0:
                    s["active"] = False
            if s["cooldown_timer"] > 0:
                s["cooldown_timer"] -= 1
            fr = c["fire_request"]
            if fr is not None:
                cx, cy = c["center"]
                h = CASTLE_SIZE / 2
                cf = math.cos(fr)
                sf = math.sin(fr)
                if abs(cf) < 1e-6:
                    tx = float('inf')
                else:
                    tx = h / abs(cf)
                if abs(sf) < 1e-6:
                    ty = float('inf')
                else:
                    ty = h / abs(sf)
                dist = min(tx, ty) + PROJECTILE_RADIUS + 1
                px = cx + math.cos(fr) * dist
                py = cy + math.sin(fr) * dist
                projectile = _make_projectile(px, py, fr, c["owner"], c["owner"], self.projectile_speed)
                # Add cannon sling momentum (tangential velocity at tip)
                omega = c.get("angular_vel", 0)
                tip_speed = omega * dist
                # Tangential direction is perpendicular to the cannon angle
                projectile["vx"] += -math.sin(fr) * tip_speed
                projectile["vy"] += math.cos(fr) * tip_speed
                self.projectiles.append(projectile)
                c["cannon_cooldown"] = FIRE_COOLDOWN
                c["fire_request"] = None
                self._emit_sound("cannon_fire", 1.0, c["owner"])
                if DEBUG:
                    print(f"[FIRE] id:{projectile['id']} owner:{COLOR_LETTERS[c['owner']]} "
                          f"pos:({px:.1f},{py:.1f}) angle:{math.degrees(fr):.0f} "
                          f"v:({projectile['vx']:.1f},{projectile['vy']:.1f})")

        for ai in self.ai:
            ai.update(self.castles, self.projectiles)

        for p in self.projectiles:
            if p["ball_cd"] > 0:
                p["ball_cd"] -= 1
            self._update_projectile(p)

        for p in self.projectiles:
            if not p["alive"]:
                continue
            for c in self.castles:
                if not c["alive"]:
                    continue
                if c["shield"]["active"]:
                    dx = p["x"] - c["center"][0]
                    dy = p["y"] - c["center"][1]
                    if dx * dx + dy * dy < SHIELD_RADIUS * SHIELD_RADIUS:
                        self._reflect_projectile(p)
                        c["shield"]["active"] = False
                        c["shield"]["cooldown_timer"] = SHIELD_COOLDOWN
                        if p["owner"] != c["owner"]:
                            c["stats"]["blocks"] += 1
                        self._emit_sound("shield_reflect", _sound_vol(p), p["owner"])
                        if p["owner"] != c["owner"]:
                            self._spawn_blockade(c)
                        break

        for p in self.projectiles:
            if not p["alive"]:
                continue
            for c in self.castles:
                if not c["alive"]:
                    continue
                rx, ry, rw, rh = c["rect"]
                if rx <= p["x"] <= rx + rw and ry <= p["y"] <= ry + rh:
                    self._damage_castle(c, p, p["owner"])
                    break

        for i in range(len(self.projectiles)):
            for j in range(i + 1, len(self.projectiles)):
                a, b = self.projectiles[i], self.projectiles[j]
                if not a["alive"] or not b["alive"]:
                    continue
                if a["ball_cd"] > 0 or b["ball_cd"] > 0:
                    continue
                dx = a["x"] - b["x"]
                dy = a["y"] - b["y"]
                if dx * dx + dy * dy < (a["radius"] + b["radius"]) ** 2:
                    self._bounce_balls(a, b)
                    a["ball_cd"] = 8
                    b["ball_cd"] = 8
                    owner = a["owner"] if a["owner"] in self.human_players else b["owner"]
                    self._emit_sound("ball_collision", max(_sound_vol(a), _sound_vol(b)), owner)

        self._check_blockade_hits()

        for c in self.castles:
            c["blockades"] = [b for b in c["blockades"] if any(br["alive"] for br in b["bricks"])]
            for b in c["blockades"]:
                b["alive"] = any(br["alive"] for br in b["bricks"])

        self.projectiles = [p for p in self.projectiles if p["alive"]]

        while len(self.projectiles) > MAX_PROJECTILES:
            removed = self.projectiles.pop(0)
            if DEBUG:
                print(f"[CULL] id:{removed['id']} owner:{COLOR_LETTERS[removed['owner']]} "
                      f"pos:({removed['x']:.1f},{removed['y']:.1f}) "
                      f"b:{removed['bounces']} r:{removed['radius']}")

        alive = [c for c in self.castles if c["alive"]]
        if len(alive) <= 1 and not self.game_over:
            self.game_over = True
            self.winner = alive[0]["owner"] if alive else None

    def _update_projectile(self, p):
        if p["bounce_cooldown"] > 0:
            p["bounce_cooldown"] -= 1

        ax, ay, aw, ah = ARENA_RECT
        r = p["radius"]
        bounced = False

        # Sub-step: move in increments no larger than radius to prevent tunneling
        speed = math.hypot(p["vx"], p["vy"])
        num_steps = max(1, math.ceil(speed / r))
        step_vx = p["vx"] / num_steps
        step_vy = p["vy"] / num_steps

        for _ in range(num_steps):
            p["x"] += step_vx
            p["y"] += step_vy

            # Wall bounces
            if p["x"] - r < ax:
                p["x"] = ax + r
                p["vx"] = abs(p["vx"])
                step_vx = abs(step_vx)
                bounced = True
            elif p["x"] + r > ax + aw:
                p["x"] = ax + aw - r
                p["vx"] = -abs(p["vx"])
                step_vx = -abs(step_vx)
                bounced = True
            if p["y"] - r < ay:
                p["y"] = ay + r
                p["vy"] = abs(p["vy"])
                step_vy = abs(step_vy)
                bounced = True
            elif p["y"] + r > ay + ah:
                p["y"] = ay + ah - r
                p["vy"] = -abs(p["vy"])
                step_vy = -abs(step_vy)
                bounced = True

            # Obstacle collisions
            for _ in range(5):
                any_hit = False
                for obs in self.obstacles:
                    rx, ry, rw, rh = obs["rect"]
                    cx = max(rx, min(p["x"], rx + rw))
                    cy = max(ry, min(p["y"], ry + rh))
                    dx = p["x"] - cx
                    dy = p["y"] - cy
                    dist_sq = dx * dx + dy * dy
                    if dist_sq >= r * r:
                        continue
                    any_hit = True
                    # Push out and reflect
                    if dist_sq == 0:
                        # Center inside rect — push out along shorter axis
                        push_left = p["x"] - rx
                        push_right = rx + rw - p["x"]
                        push_up = p["y"] - ry
                        push_down = ry + rh - p["y"]
                        min_push = min(push_left, push_right, push_up, push_down)
                        if min_push == push_left:
                            p["x"] = rx - r
                            p["vx"] = -abs(p["vx"])
                            step_vx = -abs(step_vx)
                        elif min_push == push_right:
                            p["x"] = rx + rw + r
                            p["vx"] = abs(p["vx"])
                            step_vx = abs(step_vx)
                        elif min_push == push_up:
                            p["y"] = ry - r
                            p["vy"] = -abs(p["vy"])
                            step_vy = -abs(step_vy)
                        else:
                            p["y"] = ry + rh + r
                            p["vy"] = abs(p["vy"])
                            step_vy = abs(step_vy)
                    else:
                        dist = math.sqrt(dist_sq)
                        nx = dx / dist
                        ny = dy / dist
                        p["x"] = cx + nx * r
                        p["y"] = cy + ny * r
                        # Reflect velocity along normal
                        dot = p["vx"] * nx + p["vy"] * ny
                        if dot < 0:
                            p["vx"] -= 2 * dot * nx
                            p["vy"] -= 2 * dot * ny
                            step_vx = p["vx"] / num_steps
                            step_vy = p["vy"] / num_steps
                    bounced = True
                    self._emit_sound("bounce", _sound_vol(p), p["owner"])
                if not any_hit:
                    break

            # Re-clamp to walls after obstacle push
            if p["x"] - r < ax:
                p["x"] = ax + r
                p["vx"] = abs(p["vx"])
                step_vx = abs(step_vx)
            elif p["x"] + r > ax + aw:
                p["x"] = ax + aw - r
                p["vx"] = -abs(p["vx"])
                step_vx = -abs(step_vx)
            if p["y"] - r < ay:
                p["y"] = ay + r
                p["vy"] = abs(p["vy"])
                step_vy = abs(step_vy)
            elif p["y"] + r > ay + ah:
                p["y"] = ay + ah - r
                p["vy"] = -abs(p["vy"])
                step_vy = -abs(step_vy)

        if bounced:
            p["bounces"] += 1
            if DEBUG:
                print(f"  [WALL] id:{p['id']} {p['x']:.1f},{p['y']:.1f} "
                      f"spd:{math.hypot(p['vx'],p['vy']):.1f} dir:({p['vx']:.1f},{p['vy']:.1f}) "
                      f"r:{p['radius']} b:{p['bounces']} "
                      f"owner:{COLOR_LETTERS[p['owner']]}")
            if p["bounces"] >= 3:
                p["alive"] = False
                if DEBUG:
                    print(f"[DEATH] id:{p['id']} cause:max_wall_bounces owner:{COLOR_LETTERS[p['owner']]}")
            elif p["bounce_cooldown"] <= 0:
                p["radius"] = max(2, int(p["radius"] * 0.8))
                p["vx"] *= 0.88
                p["vy"] *= 0.88
                p["bounce_cooldown"] = 15

    def _reflect_projectile(self, p):
        angle = math.radians(
            (math.degrees(math.atan2(p["vy"], p["vx"])) + 180 + random.choice([-60, 60])) % 360
        )
        spd = math.hypot(p["vx"], p["vy"])
        p["vx"] = math.cos(angle) * spd
        p["vy"] = math.sin(angle) * spd
        p["bounces"] += 1
        if p["bounces"] >= 3:
            p["alive"] = False
            if DEBUG:
                print(f"[DEATH] id:{p['id']} cause:shield_reflect_bounce owner:{COLOR_LETTERS[p['owner']]}")
        elif p["bounce_cooldown"] <= 0:
            p["radius"] = max(2, int(p["radius"] * 0.8))
            p["vx"] *= 0.88
            p["vy"] *= 0.88
            p["bounce_cooldown"] = 15

    def _bounce_balls(self, a, b):
        dx = a["x"] - b["x"]
        dy = a["y"] - b["y"]
        dist = math.hypot(dx, dy)
        if dist < 1:
            return
        nx = dx / dist
        ny = dy / dist
        overlap = (a["radius"] + b["radius"] - dist) / 2
        a["x"] += nx * overlap
        a["y"] += ny * overlap
        b["x"] -= nx * overlap
        b["y"] -= ny * overlap
        dvx = a["vx"] - b["vx"]
        dvy = a["vy"] - b["vy"]
        dot = dvx * nx + dvy * ny
        a["vx"] -= dot * nx
        a["vy"] -= dot * ny
        b["vx"] += dot * nx
        b["vy"] += dot * ny

    def _spawn_blockade(self, castle):
        if len(castle["blockades"]) >= MAX_BLOCKADES:
            return
        existing = castle["blockades"]
        for _ in range(20):
            pos = _random_blockade_pos(castle["owner"])
            if pos is None:
                return
            bx, by = pos
            new_rects = [
                (bx, by, BRICK_SIZE, BRICK_SIZE),
                (bx + BRICK_SIZE, by, BRICK_SIZE, BRICK_SIZE),
                (bx, by + BRICK_SIZE, BRICK_SIZE, BRICK_SIZE),
                (bx + BRICK_SIZE, by + BRICK_SIZE, BRICK_SIZE, BRICK_SIZE),
            ]
            gap = BRICK_SIZE
            overlap = False
            for blockade in existing:
                for brick in blockade["bricks"]:
                    rx, ry, rw, rh = brick["rect"]
                    for nx, ny, nw, nh in new_rects:
                        if nx < rx + rw + gap and rx - gap < nx + nw and ny < ry + rh + gap and ry - gap < ny + nh:
                            overlap = True
                            break
                    if overlap:
                        break
                if overlap:
                    break
            if not overlap:
                castle["blockades"].append(_make_blockade(*pos))
                return

    def _check_blockade_hits(self):
        for p in self.projectiles:
            if not p["alive"]:
                continue
            hit_any = False
            ox, oy = p["x"], p["y"]
            hit_blockade_keys = set()
            for _ in range(10):
                any_overlap = False
                for ci, c in enumerate(self.castles):
                    for bi, blockade in enumerate(c["blockades"]):
                        for brick in blockade["bricks"]:
                            if not brick["alive"]:
                                continue
                            rx, ry, rw, rh = brick["rect"]
                            if _push_out_of_rect(p, rx, ry, rw, rh):
                                any_overlap = True
                                hit_any = True
                                brick["alive"] = False
                                hit_blockade_keys.add((ci, bi))
                if not any_overlap:
                    break
            if hit_any:
                dx, dy = p["x"] - ox, p["y"] - oy
                if dx != 0:
                    p["vx"] = abs(p["vx"]) if dx > 0 else -abs(p["vx"])
                if dy != 0:
                    p["vy"] = abs(p["vy"]) if dy > 0 else -abs(p["vy"])
                if DEBUG:
                    dstr = f"dx={dx:+.1f} dy={dy:+.1f}" if dx != 0 or dy != 0 else "dx=0 dy=0"
                    print(f"  [BLK] id:{p['id']} {p['x']:.1f},{p['y']:.1f} "
                          f"spd:{math.hypot(p['vx'],p['vy']):.1f} dir:({p['vx']:.1f},{p['vy']:.1f}) "
                          f"{dstr} r:{p['radius']} b:{p['bounces']} "
                          f"keys:{len(hit_blockade_keys)} "
                          f"owner:{COLOR_LETTERS[p['owner']]}")
                p["bounces"] += 1
                if p["bounces"] >= 3:
                    p["alive"] = False
                    if DEBUG:
                        print(f"[DEATH] id:{p['id']} cause:blockade_bounce owner:{COLOR_LETTERS[p['owner']]}")
                elif p["bounce_cooldown"] <= 0:
                    p["radius"] = max(2, int(p["radius"] * 0.8))
                    p["vx"] *= 0.88
                    p["vy"] *= 0.88
                    p["bounce_cooldown"] = 15
                self._emit_sound("bounce", _sound_vol(p), p["owner"])
                for ci, bi in hit_blockade_keys:
                    blockade = self.castles[ci]["blockades"][bi]
                    remaining = sum(1 for b in blockade["bricks"] if b["alive"])
                    tag = "blockade destroyed" if remaining == 0 else "blockade hit"
                    attacker = f"{COLOR_LETTERS[p['owner']]}" if p["owner"] is not None else "reflected"
                    print(f"{COLOR_LETTERS[ci]} → {tag} by {attacker} ({remaining} blocks left)")
                    vol = _sound_vol(p)
                    event = "blockade_destroyed" if remaining == 0 else "blockade_hit"
                    self._emit_sound(event, vol, p["owner"])

    def _damage_castle(self, castle, projectile, attacker):
        if attacker is not None:
            self.castles[attacker]["stats"]["hits"] += 1
        for brick in castle["bricks"]:
            if brick["alive"]:
                brick["hp"] -= 1
                destroyed = brick["hp"] <= 0
                if destroyed:
                    brick["alive"] = False
                projectile["alive"] = False
                if DEBUG:
                    print(f"[DEATH] id:{projectile['id']} cause:castle_hit "
                          f"owner:{COLOR_LETTERS[projectile['owner']]} target:{COLOR_LETTERS[castle['owner']]}")
                remaining = sum(1 for b in castle["bricks"] if b["alive"])
                tag = " destroyed" if destroyed else " cracked"
                attacker_tag = f"{COLOR_LETTERS[attacker]}" if attacker is not None else "reflected"
                print(f"{COLOR_LETTERS[castle['owner']]} → HIT by {attacker_tag}{tag} ({remaining} blocks left)")
                event = "brick_destroy" if destroyed else "brick_crack"
                self._emit_sound(event, _sound_vol(projectile), attacker)
                if remaining == 0:
                    self._emit_sound("castle_collapse", 1.0)
                    castle["alive"] = False
                    removed_ids = [p["id"] for p in self.projectiles if p["owner"] == castle["owner"]]
                    self.projectiles = [p for p in self.projectiles if p["owner"] != castle["owner"]]
                    if DEBUG and removed_ids:
                        print(f"[DEATH] ids:{removed_ids} cause:castle_collapse owner:{COLOR_LETTERS[castle['owner']]}")
                    print(f"{COLOR_LETTERS[castle['owner']]} → OUT")
                    alive = [c for c in self.castles if c["alive"]]
                    if len(alive) == 1:
                        self.game_over = True
                        self.winner = alive[0]["owner"]
                        self._emit_sound("victory", 1.0)
                        print(f"{COLOR_LETTERS[self.winner]} → VICTORY!")
                return

    def get_state(self):
        return {
            "castles": [{
                "owner": c["owner"],
                "alive": c["alive"],
                "center": c["center"],
                "rect": c["rect"],
                "cannon_angle": c["cannon_angle"],
                "cannon_cooldown": c["cannon_cooldown"],
                "shield": dict(c["shield"]),
                "bricks": [dict(b) for b in c["bricks"]],
                "blockades": [{
                    "alive": b["alive"],
                    "bricks": [dict(br) for br in b["bricks"]],
                } for b in c["blockades"]],
                "stats": dict(c["stats"]),
                "human": c["owner"] in self.human_players or c["owner"] == 0,
            } for c in self.castles],
            "projectiles": [{
                "x": p["x"], "y": p["y"],
                "vx": p["vx"], "vy": p["vy"],
                "radius": p["radius"],
                "owner": p["owner"],
                "color_idx": p["color_idx"],
                "alive": p["alive"],
            } for p in self.projectiles],
            "obstacles": [dict(o) for o in self.obstacles],
            "game_over": self.game_over,
            "winner": self.winner,
            "sound_events": list(self.sound_events),
        }
