import math
import pygame
from config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, ARENA_RECT, CASTLE_SIZE,
    BRICK_COLORS, CASTLE_COLORS, CANNON_COLORS,
    PROJECTILE_COLORS, SHIELD_COLOR, SHIELD_RADIUS,
    CANNON_LENGTH, CANNON_WIDTH,
    BG_COLOR, ARENA_COLOR, ARENA_WALL_COLOR,
)

def draw_game(screen, state, my_slot=None, difficulty="medium"):
    screen.fill(BG_COLOR)
    draw_arena(screen, state)
    draw_title(screen)
    for c in state["castles"]:
        draw_castle(screen, c, my_slot)
    for c in state["castles"]:
        for blockade in c.get("blockades", []):
            draw_blockade(screen, blockade, c["owner"])
    draw_stats(screen, state["castles"])
    for p in state["projectiles"]:
        if p["alive"]:
            draw_projectile(screen, p)
    if state.get("game_over"):
        draw_game_over(screen, state)
    # Draw aim line for human player based on difficulty
    if my_slot is not None:
        for c in state["castles"]:
            if c["owner"] == my_slot and c.get("human"):
                draw_aim_line(screen, c, difficulty)

def draw_game_direct(screen, engine, my_slot=None):
    """Render directly from engine state without copying — used in local mode."""
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
    for p in engine.projectiles:
        if p["alive"]:
            draw_projectile(screen, p)
    if engine.game_over:
        _draw_game_over_direct(screen, engine)
    # Draw aim line for human player based on difficulty
    if my_slot is not None:
        for c in engine.castles:
            if c["owner"] == my_slot and c["owner"] in engine.human_players:
                draw_aim_line(screen, c, engine.difficulty)

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


def draw_aim_line(screen, castle, difficulty):
    """Draw aim line from cannon tip showing aim direction.
    
    Easy: solid bright line
    Medium: fainter line (50% alpha)
    Hard: no line
    """
    if difficulty == "hard":
        return
    
    center = castle["center"]
    angle = castle["cannon_angle"]
    owner = castle["owner"]
    
    # Start from cannon tip (same calculation as draw_cannon)
    start_dist = CASTLE_SIZE // 2 + 6 + CANNON_LENGTH
    sx = center[0] + math.cos(angle) * start_dist
    sy = center[1] + math.sin(angle) * start_dist
    
    # Line extends 120 pixels from cannon tip
    line_length = 120
    ex = sx + math.cos(angle) * line_length
    ey = sy + math.sin(angle) * line_length
    
    if difficulty == "easy":
        # Full brightness, solid line
        color = (255, 255, 100)  # Bright yellow
        alpha = 255
    else:  # medium
        # Fainter, semi-transparent
        color = (200, 200, 80)
        alpha = 128
    
    # Create surface with alpha for transparency
    line_surface = pygame.Surface((int(abs(ex - sx)) + 4, int(abs(ey - sy)) + 4), pygame.SRCALPHA)
    pygame.draw.line(line_surface, (*color, alpha), (2, 2), 
                     (2 + int(ex - sx), 2 + int(ey - sy)), 2)
    screen.blit(line_surface, (int(sx) - 2, int(sy) - 2))

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
