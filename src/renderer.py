import math
import os
import pygame
from config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, ARENA_RECT, CASTLE_SIZE,
    BRICK_COLORS, CASTLE_COLORS, CANNON_COLORS,
    PROJECTILE_COLORS, SHIELD_COLOR, SHIELD_RADIUS,
    CANNON_LENGTH, CANNON_WIDTH,
    BG_COLOR, ARENA_COLOR, ARENA_WALL_COLOR,
)

DEBUG = os.environ.get("REBOUND_DEBUG", "0") == "1"

def draw_game(screen, state, my_slot=None, aim_mode="multiplayer"):
    """Render game state.
    
    aim_mode controls aim line visibility:
    - 'spectate': show all players' lines (medium style, no clamp)
    - 'multiplayer': show only own line (medium style, clamped)
    - 'admin': show own line (easy) + others (medium, no clamp)
    """
    screen.fill(BG_COLOR)
    draw_arena(screen, state)
    draw_title(screen)
    for c in state["castles"]:
        draw_castle(screen, c, my_slot)
    for c in state["castles"]:
        for blockade in c.get("blockades", []):
            draw_blockade(screen, blockade, c["owner"])
    draw_stats(screen, state["castles"])
    
    # Collect all blockades as obstacles for ray casting
    all_blockades = []
    for c in state["castles"]:
        for blockade in c.get("blockades", []):
            if blockade.get("alive"):
                for brick in blockade.get("bricks", []):
                    if brick.get("alive"):
                        all_blockades.append({"rect": brick["rect"]})
    hit_objects = state.get("obstacles", []) + all_blockades
    
    # Draw aim lines (behind projectiles)
    if aim_mode == "spectate":
        # Show all lines (medium style, no clamp)
        for c in state["castles"]:
            if c["alive"]:
                draw_aim_line(screen, c, "medium", hit_objects, clamp_to_quadrant=False)
    elif aim_mode == "spectate_no_lines":
        # No aim lines
        pass
    elif aim_mode == "multiplayer":
        # Show only own line (medium style, clamped)
        if my_slot is not None:
            for c in state["castles"]:
                if c["owner"] == my_slot and c.get("human"):
                    draw_aim_line(screen, c, "medium", hit_objects, clamp_to_quadrant=True)
    elif aim_mode == "admin":
        # Show own line (easy) + others (medium, no clamp)
        if my_slot is not None:
            for c in state["castles"]:
                if c["alive"]:
                    style = "easy" if c["owner"] == my_slot else "medium"
                    draw_aim_line(screen, c, style, hit_objects, clamp_to_quadrant=False)
    
    # Draw projectiles on top of aim lines
    for p in state["projectiles"]:
        if p["alive"]:
            draw_projectile(screen, p)
    
    if state.get("game_over"):
        draw_game_over(screen, state)

def draw_game_direct(screen, engine, my_slot=None, aim_mode="multiplayer"):
    """Render directly from engine state without copying — used in local mode.
    
    aim_mode controls aim line visibility:
    - 'spectate': show all players' lines (medium style, no clamp)
    - 'multiplayer': show only own line (medium style, clamped)
    - 'admin': show own line (easy) + others (medium, no clamp)
    - 'single_player': show only human player line based on engine.difficulty
                       (easy=no clamp, medium=clamped, hard=none)
    """
    screen.fill(BG_COLOR)
    # Draw arena with obstacles read directly
    ax, ay, aw, ah = ARENA_RECT
    pygame.draw.rect(screen, ARENA_COLOR, (ax, ay, aw, ah))
    pygame.draw.rect(screen, ARENA_WALL_COLOR, (ax, ay, aw, ah), 3)
    cx, cy = ax + aw // 2, ay + ah // 2
    pygame.draw.line(screen, ARENA_WALL_COLOR, (cx, ay + 1), (cx, ay + ah - 1), 1)
    pygame.draw.line(screen, ARENA_WALL_COLOR, (ax + 1, cy), (ax + aw - 1, cy), 1)
    for o in engine.obstacles:
        pygame.draw.rect(screen, (100, 100, 110), o["rect"])
        pygame.draw.rect(screen, (0, 0, 0), o["rect"], 1)

    draw_title(screen)
    for c in engine.castles:
        if not c["alive"]:
            continue
        # Synthesize human flag inline
        _c_view = c
        _c_view_human = c["owner"] in engine.human_players
        center = c["center"]
        owner = c["owner"]
        base_color = CASTLE_COLORS[owner]
        r = pygame.Rect(center[0] - CASTLE_SIZE // 2, center[1] - CASTLE_SIZE // 2,
                        CASTLE_SIZE, CASTLE_SIZE)
        pygame.draw.rect(screen, base_color, r, 2)
        for brick in c["bricks"]:
            draw_brick(screen, brick, owner)
        draw_cannon(screen, center, c["cannon_angle"], owner)
        draw_shield(screen, center, c["shield"])
        if _c_view_human:
            draw_crown(screen, center, owner == my_slot)
    for c in engine.castles:
        for blockade in c.get("blockades", []):
            if not blockade["alive"]:
                continue
            draw_blockade(screen, blockade, c["owner"])
    draw_stats(screen, engine.castles)
    
    # Collect all blockades as obstacles for ray casting
    all_blockades = []
    for c in engine.castles:
        for blockade in c.get("blockades", []):
            if blockade.get("alive"):
                for brick in blockade.get("bricks", []):
                    if brick.get("alive"):
                        all_blockades.append({"rect": brick["rect"]})
    hit_objects = engine.obstacles + all_blockades
    
    # Draw aim lines (behind projectiles)
    if aim_mode == "spectate":
        # Show all lines (medium style, no clamp)
        for c in engine.castles:
            if c["alive"]:
                draw_aim_line(screen, c, "medium", hit_objects, clamp_to_quadrant=False)
    elif aim_mode == "spectate_no_lines":
        # No aim lines
        pass
    elif aim_mode == "multiplayer":
        # Show only own line (medium style, clamped)
        if my_slot is not None:
            for c in engine.castles:
                if c["owner"] == my_slot and c["owner"] in engine.human_players:
                    draw_aim_line(screen, c, "medium", hit_objects, clamp_to_quadrant=True)
    elif aim_mode == "admin":
        # Show own line (easy) + others (medium, no clamp)
        if my_slot is not None:
            for c in engine.castles:
                if c["alive"]:
                    style = "easy" if c["owner"] == my_slot else "medium"
                    draw_aim_line(screen, c, style, hit_objects, clamp_to_quadrant=False)
    elif aim_mode == "single_player":
        # Show human player line based on difficulty
        # easy: no clamp; medium: clamped; hard: none
        if my_slot is not None:
            for c in engine.castles:
                if c["owner"] == my_slot and c["owner"] in engine.human_players:
                    clamp = (engine.difficulty == "medium")
                    draw_aim_line(screen, c, engine.difficulty, hit_objects, clamp_to_quadrant=clamp)
    
    # Draw projectiles on top of aim lines
    for p in engine.projectiles:
        if p["alive"]:
            draw_projectile(screen, p)
    
    if engine.game_over:
        _draw_game_over_direct(screen, engine)

def _draw_game_over_direct(screen, engine):
    w = engine.winner
    font = _get_font(60)
    color = CASTLE_COLORS[w] if w is not None else (200, 200, 200)
    text = font.render(f"{WINNER_NAMES[w]} Wins!", True, color)
    ax, ay, aw, ah = ARENA_RECT
    rect = text.get_rect(center=(ax + aw // 2, ay + ah // 2))
    screen.blit(text, rect)

# Pre-computed cracked brick colors (brick at hp=1)
BRICK_CRACKED_COLORS = [tuple(max(0, c - 60) for c in color) for color in BRICK_COLORS]

def draw_arena(screen, state):
    ax, ay, aw, ah = ARENA_RECT
    pygame.draw.rect(screen, ARENA_COLOR, (ax, ay, aw, ah))
    pygame.draw.rect(screen, ARENA_WALL_COLOR, (ax, ay, aw, ah), 3)
    cx, cy = ax + aw // 2, ay + ah // 2
    pygame.draw.line(screen, ARENA_WALL_COLOR, (cx, ay + 1), (cx, ay + ah - 1), 1)
    pygame.draw.line(screen, ARENA_WALL_COLOR, (ax + 1, cy), (ax + aw - 1, cy), 1)
    for o in state.get("obstacles", []):
        pygame.draw.rect(screen, (100, 100, 110), o["rect"])
        pygame.draw.rect(screen, (0, 0, 0), o["rect"], 1)

def draw_title(screen):
    font = _get_font(30)
    text = font.render("REBOUND", True, ARENA_WALL_COLOR)
    rect = text.get_rect(center=(WINDOW_WIDTH // 2, 20))
    screen.blit(text, rect)

def draw_castle(screen, castle, my_slot=None):
    if not castle["alive"]:
        return
    center = castle["center"]
    owner = castle["owner"]
    base_color = CASTLE_COLORS[owner]
    r = pygame.Rect(center[0] - CASTLE_SIZE // 2, center[1] - CASTLE_SIZE // 2,
                    CASTLE_SIZE, CASTLE_SIZE)
    pygame.draw.rect(screen, base_color, r, 2)
    for brick in castle["bricks"]:
        draw_brick(screen, brick, owner)
    draw_cannon(screen, center, castle["cannon_angle"], owner)
    draw_shield(screen, center, castle["shield"])
    if castle.get("human"):
        draw_crown(screen, center, owner == my_slot)

def draw_brick(screen, brick, owner):
    if not brick["alive"]:
        return
    rx, ry, rw, rh = brick["rect"]
    if brick["hp"] == 2:
        pygame.draw.rect(screen, BRICK_COLORS[owner], brick["rect"])
    else:
        color = BRICK_CRACKED_COLORS[owner]
        pygame.draw.rect(screen, color, brick["rect"])
        cx = rx + rw // 2
        cy = ry + rh // 2
        s = rw // 3
        pygame.draw.line(screen, (20, 20, 20), (cx, cy - s), (cx, cy + s), 2)
        pygame.draw.line(screen, (20, 20, 20), (cx - s, cy), (cx + s, cy), 2)
    pygame.draw.rect(screen, (0, 0, 0), brick["rect"], 1)

def draw_blockade(screen, blockade, owner):
    if not blockade["alive"]:
        return
    color = CASTLE_COLORS[owner]
    for brick in blockade["bricks"]:
        if not brick["alive"]:
            continue
        pygame.draw.rect(screen, color, brick["rect"])
        pygame.draw.rect(screen, (0, 0, 0), brick["rect"], 1)

def draw_cannon(screen, center, angle, owner):
    half = CASTLE_SIZE // 2
    cx, cy = center
    mount = (int(cx + math.cos(angle) * (half + 2)),
             int(cy + math.sin(angle) * (half + 2)))
    start_dist = half + 6
    sx = cx + math.cos(angle) * start_dist
    sy = cy + math.sin(angle) * start_dist
    ex = sx + math.cos(angle) * CANNON_LENGTH
    ey = sy + math.sin(angle) * CANNON_LENGTH
    color = CANNON_COLORS[owner]
    # Flat tip, rounded grey base
    hw = CANNON_WIDTH / 2
    perp_x = -math.sin(angle) * hw
    perp_y = math.cos(angle) * hw
    points = [
        (sx + perp_x, sy + perp_y),
        (sx - perp_x, sy - perp_y),
        (ex - perp_x, ey - perp_y),
        (ex + perp_x, ey + perp_y),
    ]
    pygame.draw.polygon(screen, color, points)
    pygame.draw.circle(screen, (120, 120, 120), (int(sx), int(sy)), CANNON_WIDTH // 2 + 2)


def _ray_cast_to_boundary(cx, cy, angle, owner, obstacles, clamp_to_quadrant):
    """Cast a ray from cannon and return the hit point.
    
    Checks collision with arena walls, obstacles (barricades), and blockades.
    Returns (ex, ey) - the endpoint where the ray hits.
    """
    ax, ay, aw, ah = ARENA_RECT
    arena_cx, arena_cy = ax + aw // 2, ay + ah // 2
    
    # Ray direction
    dx = math.cos(angle)
    dy = math.sin(angle)
    
    # Find intersection with all 4 arena walls
    t_values = []
    
    # Left wall (x = ax)
    if dx != 0:
        t = (ax - cx) / dx
        if t > 0:
            y = cy + t * dy
            if ay <= y <= ay + ah:
                t_values.append(t)
    
    # Right wall (x = ax + aw)
    if dx != 0:
        t = (ax + aw - cx) / dx
        if t > 0:
            y = cy + t * dy
            if ay <= y <= ay + ah:
                t_values.append(t)
    
    # Top wall (y = ay)
    if dy != 0:
        t = (ay - cy) / dy
        if t > 0:
            x = cx + t * dx
            if ax <= x <= ax + aw:
                t_values.append(t)
    
    # Bottom wall (y = ay + ah)
    if dy != 0:
        t = (ay + ah - cy) / dy
        if t > 0:
            x = cx + t * dx
            if ax <= x <= ax + aw:
                t_values.append(t)
    
    # Check quadrant boundary if clamped
    if clamp_to_quadrant:
        if owner == 0:  # Bottom-right, can aim where x > arena_cx AND y > arena_cy
            if dx < 0:  # aiming left, check if crosses vertical center line
                t = (arena_cx - 1 - cx) / dx
                if t > 0:
                    y = cy + t * dy
                    if arena_cy + 1 <= y <= ay + ah:  # y must be in bottom half
                        t_values.append(t)
            if dy < 0:  # aiming up, check if crosses horizontal center line
                t = (arena_cy - 1 - cy) / dy
                if t > 0:
                    x = cx + t * dx
                    if arena_cx + 1 <= x <= ax + aw:  # x must be in right half
                        t_values.append(t)
        elif owner == 1:  # Top-left, can aim where x < arena_cx AND y < arena_cy
            if dx > 0:  # aiming right, check if crosses vertical center line
                t = (arena_cx + 1 - cx) / dx
                if t > 0:
                    y = cy + t * dy
                    if ay <= y <= arena_cy - 1:  # y must be in top half
                        t_values.append(t)
            if dy > 0:  # aiming down, check if crosses horizontal center line
                t = (arena_cy + 1 - cy) / dy
                if t > 0:
                    x = cx + t * dx
                    if ax <= x <= arena_cx - 1:  # x must be in left half
                        t_values.append(t)
        elif owner == 2:  # Top-right, can aim where x > arena_cx AND y < arena_cy
            if dx < 0:  # aiming left, check if crosses vertical center line
                t = (arena_cx - 1 - cx) / dx
                if t > 0:
                    y = cy + t * dy
                    if ay <= y <= arena_cy - 1:  # y must be in top half
                        t_values.append(t)
            if dy > 0:  # aiming down, check if crosses horizontal center line
                t = (arena_cy + 1 - cy) / dy
                if t > 0:
                    x = cx + t * dx
                    if arena_cx + 1 <= x <= ax + aw:  # x must be in right half
                        t_values.append(t)
        else:  # owner == 3, Bottom-left, can aim where x < arena_cx AND y > arena_cy
            if dx > 0:  # aiming right, check if crosses vertical center line
                t = (arena_cx + 1 - cx) / dx
                if t > 0:
                    y = cy + t * dy
                    if arena_cy + 1 <= y <= ay + ah:  # y must be in bottom half
                        t_values.append(t)
            if dy < 0:  # aiming up, check if crosses horizontal center line
                t = (arena_cy - 1 - cy) / dy
                if t > 0:
                    x = cx + t * dx
                    if ax <= x <= arena_cx - 1:  # x must be in left half
                        t_values.append(t)
    
    # Check collision with obstacles (barricades and blockades)
    for obs in obstacles:
        rx, ry, rw, rh = obs["rect"]
        # Proper ray-AABB intersection using slab method
        t_enter = 0.0
        t_exit = float('inf')
        
        # X slab
        if abs(dx) < 0.0001:
            # Ray is parallel to x slab
            if cx < rx or cx > rx + rw:
                continue
        else:
            t1 = (rx - cx) / dx
            t2 = (rx + rw - cx) / dx
            t_enter = max(t_enter, min(t1, t2))
            t_exit = min(t_exit, max(t1, t2))
        
        # Y slab
        if abs(dy) < 0.0001:
            # Ray is parallel to y slab
            if cy < ry or cy > ry + rh:
                continue
        else:
            t1 = (ry - cy) / dy
            t2 = (ry + rh - cy) / dy
            t_enter = max(t_enter, min(t1, t2))
            t_exit = min(t_exit, max(t1, t2))
        
        # Check if ray intersects this obstacle
        if t_enter <= t_exit and t_exit > 0:
            t_hit = max(0, t_enter)
            if t_hit > 0 and (not t_values or t_hit < min(t_values)):
                # Validate hit point
                hx = cx + t_hit * dx
                hy = cy + t_hit * dy
                if rx - 0.1 <= hx <= rx + rw + 0.1 and ry - 0.1 <= hy <= ry + rh + 0.1:
                    t_values.append(t_hit)
    
    if t_values:
        t = min(t_values)  # Closest intersection
        if DEBUG:
            print(f"       [RAY] P{owner}: hit at t={t:.2f}, walls={len([tv for tv in t_values if tv < 1000])}, obstacles checked={len(obstacles)}")
        return cx + t * dx, cy + t * dy
    
    if DEBUG:
        print(f"       [RAY] P{owner}: NO HIT (fallback), walls={len(t_values)}, obstacles={len(obstacles)}")
    # Fallback: return a point far away
    return cx + dx * 1000, cy + dy * 1000


def draw_aim_line(screen, castle, style, obstacles, clamp_to_quadrant=False, fade=False):
    """Draw aim line from cannon tip showing where projectile will hit.
    
    style: 'easy' (solid), 'medium' (faint), 'hard' (none)
    obstacles: list of obstacle rects to check for collisions
    clamp_to_quadrant: if True, line stops at quadrant boundary
    fade: unused for now (easy and medium both use solid lines)
    """
    if style == "hard":
        return
    
    center = castle["center"]
    angle = castle["cannon_angle"]
    owner = castle["owner"]
    
    # Start from cannon tip (same calculation as draw_cannon)
    start_dist = CASTLE_SIZE // 2 + 6 + CANNON_LENGTH
    sx = center[0] + math.cos(angle) * start_dist
    sy = center[1] + math.sin(angle) * start_dist
    
    # Cast ray to find actual hit point
    ex, ey = _ray_cast_to_boundary(sx, sy, angle, owner, obstacles, clamp_to_quadrant)
    
    if DEBUG:
        print(f"[AIM] P{owner}: style={style}, clamp={clamp_to_quadrant}")
        print(f"       cannon_angle={angle:.3f}, start=({sx:.1f}, {sy:.1f}), end=({ex:.1f}, {ey:.1f})")
    
    if style == "easy":
        # Bright yellow - easy to see
        color = (255, 255, 100)
    else:  # medium
        # Dimmer yellow - harder to see
        color = (150, 150, 60)
    
    # Draw line directly on screen
    pygame.draw.line(screen, color, (int(sx), int(sy)), (int(ex), int(ey)), 2)

# Pre-rendered shield surfaces (created on first use)
_shield_outline = None
_shield_tint = None

def _get_shield_surfaces():
    global _shield_outline, _shield_tint
    if _shield_outline is None:
        _shield_outline = pygame.Surface((SHIELD_RADIUS * 2, SHIELD_RADIUS * 2), pygame.SRCALPHA)
        pygame.draw.circle(_shield_outline, SHIELD_COLOR, (SHIELD_RADIUS, SHIELD_RADIUS), SHIELD_RADIUS, 3)
        _shield_tint = pygame.Surface((SHIELD_RADIUS * 2, SHIELD_RADIUS * 2), pygame.SRCALPHA)
        _shield_tint.set_alpha(40)
        pygame.draw.circle(_shield_tint, (80, 180, 255), (SHIELD_RADIUS, SHIELD_RADIUS), SHIELD_RADIUS)
    return _shield_outline, _shield_tint

def draw_shield(screen, center, shield):
    if not shield["active"]:
        return
    cx, cy = center
    outline, tint = _get_shield_surfaces()
    screen.blit(tint, (cx - SHIELD_RADIUS, cy - SHIELD_RADIUS))
    screen.blit(outline, (cx - SHIELD_RADIUS, cy - SHIELD_RADIUS))

# Pre-rendered crown surfaces (defined=True and defined=False variants)
_crown_cache = {}

def draw_crown(screen, center, defined=True):
    cx, cy = center
    cy -= CASTLE_SIZE // 2 + 6
    if defined not in _crown_cache:
        s = pygame.Surface((30, 16), pygame.SRCALPHA)
        pts = [(4, 14), (0, 8), (7, 4), (10, 10), (15, 0), (20, 10), (23, 4), (30, 8), (26, 14)]
        if defined:
            pygame.draw.polygon(s, (255, 215, 0, 200), pts)
            pygame.draw.polygon(s, (200, 160, 0, 240), pts, 2)
        else:
            pygame.draw.polygon(s, (200, 180, 80, 120), pts)
            pygame.draw.polygon(s, (255, 215, 0, 180), pts, 1)
        _crown_cache[defined] = s
    screen.blit(_crown_cache[defined], (cx - 15, cy))

def draw_projectile(screen, p):
    pygame.draw.circle(screen, PROJECTILE_COLORS[p["color_idx"]],
                       (int(p["x"]), int(p["y"])), p["radius"])

WINNER_NAMES = ["Red", "Blue", "Green", "Yellow"]

# Cached font helper to avoid repeated SysFont allocation
_font_cache = {}
def _get_font(size):
    if size not in _font_cache:
        _font_cache[size] = pygame.font.SysFont(None, size)
    return _font_cache[size]

def draw_stats(screen, castles):
    ax, ay, aw, ah = ARENA_RECT
    font = _get_font(20)
    for c in castles:
        h = c["stats"]["hits"]
        b = c["stats"]["blocks"]
        owner = c["owner"]
        color = BRICK_COLORS[owner]
        cx, _ = c["center"]
        if owner in (1, 2):
            y = ay - 40
        else:
            y = ay + ah + 8
        screen.blit(font.render(f"H:{h}", True, color), (cx - 18, y))
        screen.blit(font.render(f"B:{b}", True, color), (cx - 18, y + 18))

def draw_game_over(screen, state):
    w = state["winner"]
    font = _get_font(60)
    color = CASTLE_COLORS[w] if w is not None else (200, 200, 200)
    text = font.render(f"{WINNER_NAMES[w]} Wins!", True, color)
    ax, ay, aw, ah = ARENA_RECT
    rect = text.get_rect(center=(ax + aw // 2, ay + ah // 2))
    screen.blit(text, rect)
