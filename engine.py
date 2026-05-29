import math
import random
from config import (
    ARENA_RECT, CASTLE_SIZE, BRICK_SIZE, BRICKS_PER_CASTLE,
    FIRE_COOLDOWN, SHIELD_DURATION, SHIELD_COOLDOWN, SHIELD_RADIUS,
    PROJECTILE_RADIUS, PROJECTILE_SPEED, MAX_PROJECTILES, MAX_BLOCKADES,
)

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
    bricks = []
    for i in range(BRICKS_PER_CASTLE):
        r = i // cols
        c = i % cols
        bx = ox + c * BRICK_SIZE
        by = oy + r * BRICK_SIZE
        bricks.append({"alive": True, "hp": 2, "rect": (bx, by, BRICK_SIZE, BRICK_SIZE)})
    return bricks

def _make_projectile(x, y, angle, owner, color_idx):
    return {
        "x": x, "y": y,
        "vx": math.cos(angle) * PROJECTILE_SPEED,
        "vy": math.sin(angle) * PROJECTILE_SPEED,
        "owner": owner,
        "color_idx": color_idx,
        "alive": True,
        "radius": PROJECTILE_RADIUS,
        "bounces": 0,
        "bounce_cooldown": 0,
        "ball_cd": 0,
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
    m = 4
    obs = []

    for i in range(4):
        obs.append({"rect": (cx - bs // 2, ay + m + i * bs, bs, bs)})
        obs.append({"rect": (cx - bs // 2, ay + ah - m - (i + 1) * bs, bs, bs)})
        obs.append({"rect": (ax + m + i * bs, cy - bs // 2, bs, bs)})
        obs.append({"rect": (ax + aw - m - (i + 1) * bs, cy - bs // 2, bs, bs)})

    for i in range(-2, 3):
        obs.append({"rect": (cx + i * bs - bs // 2, cy - bs // 2, bs, bs)})

    for i in range(-2, 3):
        if i == 0:
            continue
        obs.append({"rect": (cx - bs // 2, cy + i * bs - bs // 2, bs, bs)})

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
        self.current_angle = 0
        self.aim_point = None
        self.shield_hold = 0

    def set_difficulty(self, difficulty):
        if difficulty == "easy":
            self.fire_interval = (90, 180)
            self.aim_spread = 60
            self.shield_range = 100
            self.prediction_frames = 30
            self.rot_speed = 0.02
            self.bounce_chance = 0.1
            self.obstacle_awareness = 0.3
        elif difficulty == "hard":
            self.fire_interval = (30, 90)
            self.aim_spread = 15
            self.shield_range = 180
            self.prediction_frames = 60
            self.rot_speed = 0.06
            self.bounce_chance = 0.4
            self.obstacle_awareness = 1.0
        else:
            self.fire_interval = (60, 150)
            self.aim_spread = 35
            self.shield_range = 140
            self.prediction_frames = 45
            self.rot_speed = 0.04
            self.bounce_chance = 0.25
            self.obstacle_awareness = 0.8

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

    def _line_blocked(self, x1, y1, x2, y2):
        for obs in self.obstacles:
            if self._line_intersects_rect(x1, y1, x2, y2, obs["rect"]):
                return True
        return False

    def _pick_aim_point(self, target_center, my_center):
        tx = target_center[0] + self.aim_offset[0]
        ty = target_center[1] + self.aim_offset[1]

        direct_blocked = self._line_blocked(my_center[0], my_center[1], tx, ty)
        use_bounce = False

        if direct_blocked and random.random() < self.obstacle_awareness:
            use_bounce = True
        elif random.random() < self.bounce_chance:
            use_bounce = True

        if use_bounce:
            ax, ay, aw, ah = ARENA_RECT
            wall = random.choice(["left", "right", "top", "bottom"])
            if wall == "left":
                tx = 2 * ax - tx
            elif wall == "right":
                tx = 2 * (ax + aw) - tx
            elif wall == "top":
                ty = 2 * ay - ty
            else:
                ty = 2 * (ay + ah) - ty
            if direct_blocked:
                print(f"{COLOR_LETTERS[self.owner]} → obstacle blocked, bounce via {wall}")

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
            self._pick_aim_point(chosen[0], my_castle["center"])
            tag = "bounce shot via " if self.aim_point and (
                self.aim_point[0] < ARENA_RECT[0] or
                self.aim_point[0] > ARENA_RECT[0] + ARENA_RECT[2] or
                self.aim_point[1] < ARENA_RECT[1] or
                self.aim_point[1] > ARENA_RECT[1] + ARENA_RECT[3]
            ) else ""
            print(f"{COLOR_LETTERS[self.owner]} → targeting {COLOR_LETTERS[self.target]} ({tag}{COLOR_LETTERS[chosen[1]]})")

        if self.aim_point:
            cx, cy = my_castle["center"]
            ax, ay = _clamp_aim(self.owner, self.aim_point[0], self.aim_point[1], cx, cy)
            dx = ax - cx
            dy = ay - cy
            target_angle = math.atan2(dy, dx)
            diff = target_angle - self.current_angle
            diff = math.atan2(math.sin(diff), math.cos(diff))
            if abs(diff) < self.rot_speed:
                self.current_angle = target_angle
            else:
                self.current_angle += self.rot_speed if diff > 0 else -self.rot_speed

        my_castle["cannon_angle"] = self.current_angle

        self.fire_timer -= 1
        if self.fire_timer <= 0:
            if not my_castle["shield"]["active"]:
                self._fire(my_castle)
                print(f"{COLOR_LETTERS[self.owner]} → fired at {COLOR_LETTERS[self.target]}")
            self.fire_timer = random.randint(*self.fire_interval)

        threat = False
        threat_from = None
        threat_frames = None
        cx, cy = my_castle["center"]
        for p in projectiles:
            if not p["alive"] or p["owner"] == self.owner:
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
                "cannon_angle": 0.0,
                "cannon_cooldown": 0,
                "shield": {"active": False, "timer": 0, "cooldown_timer": 0},
                "fire_request": None,
                "blockades": [],
                "stats": {"hits": 0, "blocks": 0},
            })
        return castles

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
        if self.game_over:
            return

        self.frame += 1
        self.sound_events.clear()

        for c in self.castles:
            if not c["alive"]:
                continue
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
                half = CASTLE_SIZE // 2
                dist = half + 3
                cx, cy = c["center"]
                px = cx + math.cos(fr) * dist
                py = cy + math.sin(fr) * dist
                projectile = _make_projectile(px, py, fr, c["owner"], c["owner"])
                self.projectiles.append(projectile)
                c["cannon_cooldown"] = FIRE_COOLDOWN
                c["fire_request"] = None
                self.sound_events.append("cannon_fire")

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
                        c["stats"]["blocks"] += 1
                        self.sound_events.append("shield_reflect")
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
                    self.sound_events.append("ball_collision")

        self._check_blockade_hits()

        for c in self.castles:
            c["blockades"] = [b for b in c["blockades"] if any(br["alive"] for br in b["bricks"])]
            for b in c["blockades"]:
                b["alive"] = any(br["alive"] for br in b["bricks"])

        self.projectiles = [p for p in self.projectiles if p["alive"]]

        while len(self.projectiles) > MAX_PROJECTILES:
            self.projectiles.pop(0)

        alive = [c for c in self.castles if c["alive"]]
        if len(alive) <= 1 and not self.game_over:
            self.game_over = True
            self.winner = alive[0]["owner"] if alive else None

    def _update_projectile(self, p):
        p["x"] += p["vx"]
        p["y"] += p["vy"]
        if p["bounce_cooldown"] > 0:
            p["bounce_cooldown"] -= 1

        ax, ay, aw, ah = ARENA_RECT
        bounced = False
        if p["x"] - p["radius"] < ax:
            p["x"] = ax + p["radius"]
            p["vx"] = -p["vx"]
            bounced = True
        elif p["x"] + p["radius"] > ax + aw:
            p["x"] = ax + aw - p["radius"]
            p["vx"] = -p["vx"]
            bounced = True
        if p["y"] - p["radius"] < ay:
            p["y"] = ay + p["radius"]
            p["vy"] = -p["vy"]
            bounced = True
        elif p["y"] + p["radius"] > ay + ah:
            p["y"] = ay + ah - p["radius"]
            p["vy"] = -p["vy"]
            bounced = True

        obstacle_hit = False
        for obs in self.obstacles:
            rx, ry, rw, rh = obs["rect"]
            ox, oy = p["x"], p["y"]
            if _push_out_of_rect(p, rx, ry, rw, rh):
                if p["x"] != ox:
                    p["vx"] = -p["vx"]
                if p["y"] != oy:
                    p["vy"] = -p["vy"]
                obstacle_hit = True
                break
        if obstacle_hit:
            for obs in self.obstacles:
                rx, ry, rw, rh = obs["rect"]
                _push_out_of_rect(p, rx, ry, rw, rh)
            self.sound_events.append("bounce")

        if bounced:
            p["bounces"] += 1
            self.sound_events.append("bounce")
            if p["bounces"] >= 3:
                p["alive"] = False
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
        p["owner"] = None
        p["bounces"] += 1
        if p["bounces"] >= 3:
            p["alive"] = False
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
            overlap = False
            for blockade in existing:
                for brick in blockade["bricks"]:
                    rx, ry, rw, rh = brick["rect"]
                    for nx, ny, nw, nh in new_rects:
                        if nx < rx + rw and rx < nx + nw and ny < ry + rh and ry < ny + nh:
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
            for c in self.castles:
                for blockade in c["blockades"]:
                    if not blockade["alive"]:
                        continue
                    for brick in blockade["bricks"]:
                        if not brick["alive"]:
                            continue
                        rx, ry, rw, rh = brick["rect"]
                        if rx <= p["x"] <= rx + rw and ry <= p["y"] <= ry + rh:
                            brick["alive"] = False
                            p["alive"] = False
                            remaining = sum(1 for b in blockade["bricks"] if b["alive"])
                            tag = "blockade destroyed" if remaining == 0 else "blockade hit"
                            attacker = f"{COLOR_LETTERS[p['owner']]}" if p["owner"] is not None else "reflected"
                            print(f"{COLOR_LETTERS[c['owner']]} → {tag} by {attacker} ({remaining} blocks left)")
                            if remaining == 0:
                                self.sound_events.append("blockade_destroyed")
                            else:
                                self.sound_events.append("blockade_hit")
                            return

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
                remaining = sum(1 for b in castle["bricks"] if b["alive"])
                tag = " destroyed" if destroyed else " cracked"
                attacker_tag = f"{COLOR_LETTERS[attacker]}" if attacker is not None else "reflected"
                print(f"{COLOR_LETTERS[castle['owner']]} → HIT by {attacker_tag}{tag} ({remaining} blocks left)")
                if destroyed:
                    self.sound_events.append("brick_destroy")
                else:
                    self.sound_events.append("brick_crack")
                if remaining == 0:
                    self.sound_events.append("castle_collapse")
                    castle["alive"] = False
                    self.projectiles = [p for p in self.projectiles if p["owner"] != castle["owner"]]
                    print(f"{COLOR_LETTERS[castle['owner']]} → OUT")
                    alive = [c for c in self.castles if c["alive"]]
                    if len(alive) == 1:
                        self.game_over = True
                        self.winner = alive[0]["owner"]
                        self.sound_events.append("victory")
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
