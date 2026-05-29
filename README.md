# REBOUND

A 4-player artillery battle game built with Python and Pygame. Players control castles in the four corners of an arena and fire bouncing projectiles at each other. Each castle has 9 bricks (2 HP each), a cannon, and a shield. Last castle standing wins.

## Quick Start

```bash
pip install pygame
python main.py
```

Select difficulty on the menu screen, then click START or press Enter.

## Controls

| Key | Action |
|-----|--------|
| Mouse move | Aim cannon |
| Left click | Fire |
| Space (hold) | Raise shield |
| M | Toggle mute |
| Q | Return to menu |
| Ctrl+C | Quit |

## Game Rules

### Arena
- 1024×768 window with a 904×648 arena centered at (60, 60)
- Quadrant dividing lines mark each player's territory
- Indestructible grey obstacles: a center `+` cross (9 bricks) and 4-brick barriers at quadrant-line/wall intersections (16 bricks)

### Castles
- 4 castles, one per corner: Red (bottom-right), Blue (top-left), Green (top-right), Yellow (bottom-left)
- Each castle has a 3×3 grid of bricks (9 total), each brick has 2 HP
- First hit cracks the brick (darkens + shows `+`), second hit destroys it
- Castle is destroyed when all bricks are destroyed
- Cannon aim is clamped to the outward-facing quadrant

### Projectiles
- Fired from the cannon muzzle at 8 px/frame
- Max 15 projectiles on screen at once (oldest removed)
- Bounce off walls (up to 3 bounces, shrinking each time: radius ×0.8, speed ×0.88)
- Bounce off other projectiles (elastic collision, no shrink or bounce count)
- Destroyed on hitting a castle brick
- Bounce off grey obstacles (no shrink, no bounce count, full speed preserved)

### Shield
- Circular shield centered on the castle (radius 50px)
- Reflects incoming projectiles randomly (±60° from reverse direction)
- Goes on cooldown (180 frames) only when hit
- Reflecting an enemy projectile spawns a 2×2 blockade in the defender's quadrant (max 4 per castle)
- Reflecting your own projectile does not spawn a blockade or count as a block
- Shield-reflected balls keep the original shooter's owner

### Blockades
- 2×2 brick blocks placed randomly in the defender's quadrant
- Each brick has 1 HP (destroyed on first hit)
- Bricks must be at least CASTLE_SIZE (60px) from the castle and 1 brick-width apart
- Persist after their castle is destroyed — still block projectiles and render
- Projectile bounces off on hit (wall-style physics: shrink, slow, bounce count)

### Scoring
- H (Hits) and B (Blocks) counters displayed above/below each castle
- Hits: every time a projectile damages a castle brick
- Blocks: every time a projectile is reflected by an active shield

## Architecture

### Files

| File | Purpose |
|------|---------|
| `main.py` | Entry point — menu → game loop, handles window and frame clock |
| `menu.py` | Difficulty selection screen (Easy/Medium/Hard) |
| `game.py` | Thin client — bridges Pygame input/rendering to engine |
| `engine.py` | Pure game logic — no Pygame imports, dict-based state, serializable |
| `renderer.py` | All Pygame drawing — takes state dict, renders frame |
| `config.py` | Constants (colors, sizes, speeds, limits) |
| `sounds.py` | Sound loader/player — lazy Pygame mixer init, event-driven playback |
| `sounds/` | 7 base `.ogg` sound files + 14 pitch-shifted variants (+15%, -15%) |

### Engine Design

`engine.py` contains all game logic with zero Pygame dependencies:
- `GameEngine` — manages the game state update loop
- `AIController` — AI decision-making (per-player)
- Pure dict-based state for trivial JSON serialization (designed for network play)

The engine processes input via `handle_input({player_idx: {...}})` and advances one frame per `update()` call. State is read via `get_state()`, which returns a trivially serializable dict.

### Rendering

`renderer.py` takes the engine's state dict and draws the current frame using `pygame.draw` primitives. This separation means the rendering client can run remotely once a network layer is added.

### Sound System

`sounds.py` lazy-initializes `pygame.mixer` on first play. Each sound event has an original `.ogg` file plus `_h.ogg` (+15% pitch) and `_l.ogg` (-15% pitch) variants. One is picked randomly per event. Volume scales with projectile radius (linear 0.2–1.0), with a 1.3× boost for human players.

## AI

Each AI opponent operates independently with its own target selection, aim planning, and shield logic:

- **Targeting**: Picks a random alive enemy, retargets every 15–45 frames (randomized) and on each shot
- **Aiming**: Always uses bounce shots (never direct) — plans bounces off walls (priority 0), center-cross obstacles (priority 1), or player blockade bricks (priority 2)
- **Rotation**: Smoothly rotates toward the aim angle at a rate determined by difficulty
- **Shield**: Predictively raises shield based on incoming projectile trajectory and proximity; holds for at least 10 frames to prevent flickering
- **Difficulty Tiers**:
  | Parameter | Easy | Medium | Hard |
  |---|---|---|---|
  | Fire interval (frames) | 90–180 | 60–150 | 30–90 |
  | Aim spread (°) | ±15 | ±10 | ±5 |
  | Shield range (frames until impact) | 60 | 120 | 180 |
  | Prediction (frames) | 30 | 60 | 90 |
  | Rotation speed (°/frame) | 1.5 | 2.5 | 4.0 |
  | Obstacle awareness | 30% | 80% | 100% |

## Configuration

All gameplay constants are in `config.py`:

- **Window**: 1024×768, 60 FPS
- **Arena**: 904×648, 60px padding
- **Castle**: 60×60, 9 bricks (14×14 each)
- **Cannon**: 24px long, 8px wide
- **Projectile**: radius 6, speed 8 px/frame
- **Shield**: radius 50, duration 60 frames, cooldown 180 frames
- **Fire cooldown**: 30 frames
- **Max projectiles**: 15
- **Max blockades**: 4 per castle

## Development

### Headless Testing

The engine can run without rendering for automated testing:

```python
from engine import GameEngine
e = GameEngine(difficulty="medium", human_players=[])
while not e.game_over:
    e.update()
print(f"Winner: P{e.winner}")
```

### Debug Mode

Set `engine.DEBUG = True` to enable structured physics tracing (`[WALL]`, `[OBS]`, `[BLK]`, `[FIRE]`, `[DEATH]` lines in stdout).

### Adding Features

- Game logic changes go in `engine.py`
- Visual changes go in `renderer.py`
- New constants go in `config.py`
- New sound events add a function in `sounds.py` and call `_emit_sound()` in `engine.py`

## Roadmap

- Visual effects (explosions, shield flash)
- Network multiplayer (WebSocket/TCP server + remote client)
- Real-time headless simulation controls

## Requirements

- Python 3.10+
- Pygame 2.6+
- SDL2_mixer (for sound — `brew install sdl2_mixer` on macOS)

## License

MIT. Sound effects are CC0 from [Kenney](https://kenney.nl/).
