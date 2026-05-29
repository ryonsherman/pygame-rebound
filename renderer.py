import math
import pygame
from config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, ARENA_RECT, CASTLE_SIZE,
    BRICK_COLORS, CASTLE_COLORS, CANNON_COLORS,
    PROJECTILE_COLORS, SHIELD_COLOR, SHIELD_RADIUS,
    CANNON_LENGTH, CANNON_WIDTH,
    BG_COLOR, ARENA_COLOR, ARENA_WALL_COLOR,
)

def draw_game(screen, state):
    screen.fill(BG_COLOR)
    draw_arena(screen, state)
    for c in state["castles"]:
        draw_castle(screen, c)
    draw_stats(screen, state["castles"])
    for p in state["projectiles"]:
        if p["alive"]:
            draw_projectile(screen, p)
    if state.get("game_over"):
        draw_game_over(screen, state)

def draw_arena(screen, state):
    ax, ay, aw, ah = ARENA_RECT
    pygame.draw.rect(screen, ARENA_COLOR, (ax, ay, aw, ah))
    pygame.draw.rect(screen, ARENA_WALL_COLOR, (ax, ay, aw, ah), 3)
    cx, cy = ax + aw // 2, ay + ah // 2
    pygame.draw.line(screen, ARENA_WALL_COLOR, (cx, ay), (cx, ay + ah), 1)
    pygame.draw.line(screen, ARENA_WALL_COLOR, (ax, cy), (ax + aw, cy), 1)
    for o in state.get("obstacles", []):
        pygame.draw.rect(screen, (100, 100, 110), o["rect"])
        pygame.draw.rect(screen, (0, 0, 0), o["rect"], 1)

def draw_castle(screen, castle):
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
    for blockade in castle.get("blockades", []):
        draw_blockade(screen, blockade, owner)
    draw_cannon(screen, center, castle["cannon_angle"], owner)
    draw_shield(screen, center, castle["shield"])

def draw_brick(screen, brick, owner):
    if not brick["alive"]:
        return
    rx, ry, rw, rh = brick["rect"]
    if brick["hp"] == 2:
        pygame.draw.rect(screen, BRICK_COLORS[owner], brick["rect"])
    else:
        color = tuple(max(0, c - 60) for c in BRICK_COLORS[owner])
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
    pygame.draw.circle(screen, (120, 120, 120), mount, 6)
    pygame.draw.line(screen, color, (sx, sy), (ex, ey), CANNON_WIDTH)
    pygame.draw.circle(screen, color, (int(ex), int(ey)), CANNON_WIDTH // 2)

def draw_shield(screen, center, shield):
    if not shield["active"]:
        return
    cx, cy = center
    s = pygame.Surface((SHIELD_RADIUS * 2, SHIELD_RADIUS * 2), pygame.SRCALPHA)
    pygame.draw.circle(s, SHIELD_COLOR, (SHIELD_RADIUS, SHIELD_RADIUS), SHIELD_RADIUS, 3)
    alpha_tint = pygame.Surface((SHIELD_RADIUS * 2, SHIELD_RADIUS * 2), pygame.SRCALPHA)
    alpha_tint.set_alpha(40)
    pygame.draw.circle(alpha_tint, (80, 180, 255), (SHIELD_RADIUS, SHIELD_RADIUS), SHIELD_RADIUS)
    screen.blit(alpha_tint, (cx - SHIELD_RADIUS, cy - SHIELD_RADIUS))
    screen.blit(s, (cx - SHIELD_RADIUS, cy - SHIELD_RADIUS))

def draw_projectile(screen, p):
    pygame.draw.circle(screen, PROJECTILE_COLORS[p["color_idx"]],
                       (int(p["x"]), int(p["y"])), p["radius"])

WINNER_NAMES = ["Red", "Blue", "Green", "Yellow"]

def draw_stats(screen, castles):
    font = pygame.font.SysFont(None, 20)
    ax, ay, aw, ah = ARENA_RECT
    for c in castles:
        if not c["alive"]:
            continue
        h = c["stats"]["hits"]
        b = c["stats"]["blocks"]
        owner = c["owner"]
        color = CASTLE_COLORS[owner]
        cx, cy = c["center"]
        if owner in (0, 2):
            x = ax + aw + 6
        else:
            x = ax - 56
        screen.blit(font.render(f"H:{h}", True, color), (x, cy - 16))
        screen.blit(font.render(f"B:{b}", True, color), (x, cy))

def draw_game_over(screen, state):
    w = state["winner"]
    font = pygame.font.SysFont(None, 60)
    color = CASTLE_COLORS[w] if w is not None else (200, 200, 200)
    text = font.render(f"{WINNER_NAMES[w]} Wins!", True, color)
    ax, ay, aw, ah = ARENA_RECT
    rect = text.get_rect(center=(ax + aw // 2, ay + ah // 2))
    screen.blit(text, rect)
