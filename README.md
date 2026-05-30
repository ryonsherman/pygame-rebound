# REBOUND

A 4-player artillery battle game built with Python and Pygame. Players control castles in the four corners of an arena and fire bouncing projectiles at each other. Each castle has 9 bricks (2 HP each), a cannon, and a shield. Last castle standing wins.

## Quick Start

```bash
pip install pygame
make game
```

Or run directly:

```bash
python game.py        # Play the game
python server.py      # Host multiplayer backend
```

Select difficulty on the menu screen, then press Enter or click START.

## Controls

| Key | Action |
|-----|--------|
| Mouse move | Aim cannon |
| Left click | Fire |
| Space (hold) | Raise shield |
| M | Toggle mute |
| Q | Return to menu |
| Left/Right arrows | Select difficulty (menu) |
| Down arrow | Select Online (menu) |
| Up arrow | Back to difficulty (menu) |
| Enter | Start game (menu) |

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
- Cannon aim is clamped to the outward-facing quadrant (cannot aim behind the castle)

### Projectiles
- Fired from the cannon muzzle at speed scaled by difficulty
- Ball inherits tangential momentum from cannon rotation at the moment of firing (sling effect)
- Max projectiles on screen varies by difficulty (oldest removed when exceeded)
- Bounce off walls (max bounces varies by difficulty, shrinking each time)
- Bounce off other projectiles (elastic collision, no shrink or bounce count)
- Destroyed on hitting a castle brick
- Bounce off grey obstacles (proper reflection off surface normals)

### Physics
- Sub-stepped movement: ball advances in increments no larger than its radius per sub-step, preventing tunneling through obstacles
- Obstacle collision uses true circle-vs-rectangle detection with normal-based reflection
- Wall clamping after every sub-step ensures balls never escape the arena

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

## Difficulty Scaling

| Parameter | Easy | Medium | Hard |
|-----------|------|--------|------|
| Ball speed | ×0.9 | ×1.0 | ×1.1 |
| Max bounces | 3 | 4 | 5 |
| Max balls in play | 15 | 18 | 21 |
| Ball shrink per bounce | ×0.75 | ×0.80 | ×0.85 |
| Ball slowdown per bounce | ×0.84 | ×0.88 | ×0.92 |
| AI fire rate (frames) | 99–198 | 60–150 | 27–81 |
| AI aim spread | 60° | 35° | 15° |
| AI rotation speed | 0.02 rad/f | 0.04 rad/f | 0.06 rad/f |
| AI sling threshold | 0.05 rad | 0.12 rad | 0.20 rad |
| AI shield detection | 100px | 140px | 180px |
| AI prediction frames | 30 | 45 | 60 |

## Project Structure

```
rebound-game/
├── game.py              # Entry point — play the game
├── server.py            # Multiplayer server entry point
├── config.py            # All gameplay constants
├── Makefile             # make game / make server
├── sounds/              # .ogg sound files + pitch-shifted variants
├── src/
│   ├── engine.py        # Pure game logic — no Pygame, dict-based state
│   ├── game_client.py   # Thin client bridging input/rendering to engine
│   ├── menu.py          # Difficulty/mode selection screen
│   ├── renderer.py      # All Pygame drawing from state dict
│   ├── sounds.py        # Sound loader/player — event-driven playback
│   └── nats_common.py   # NATS messaging helpers for multiplayer
└── tests/
    ├── test_wall_escape.py   # Physics tunneling/overlap tests
    ├── test_obstacles.py     # Obstacle collision analysis
    └── test_nats.py          # Multiplayer messaging tests
```

## Architecture

### Engine Design

`src/engine.py` contains all game logic with zero Pygame dependencies:
- `GameEngine` — manages the game state update loop
- `AIController` — AI decision-making (per-player)
- Pure dict-based state for trivial JSON serialization (designed for network play)

The engine processes input via `handle_input({player_idx: {...}})` and advances one frame per `update()` call. State is read via `get_state()`, which returns a trivially serializable dict.

### Rendering

`src/renderer.py` takes the engine's state dict and draws the current frame using `pygame.draw` primitives. Cannons have a flat tip (muzzle) and a rounded grey base.

### Sound System

`src/sounds.py` lazy-initializes `pygame.mixer` on first play. Each sound event has an original `.ogg` file plus `_h.ogg` (+15% pitch) and `_l.ogg` (-15% pitch) variants. One is picked randomly per event. Volume scales with projectile radius (linear 0.2–1.0), with a 1.3× boost for human players.

## AI

Each AI opponent operates independently with its own target selection, aim planning, and shield logic:

- **Targeting**: Picks a random alive enemy, retargets every 15–45 frames (randomized) and on each shot
- **Aiming**: Always uses bounce shots (never direct) — plans bounces off walls, center-cross obstacles, or player blockade bricks
- **Rotation**: Smoothly rotates toward the aim angle at a rate determined by difficulty
- **Sling shots**: AI fires while still rotating toward target (within a threshold), adding tangential momentum to the ball for curved trajectories
- **Shield**: Predictively raises shield based on incoming projectile trajectory and proximity; holds for at least 10 frames to prevent flickering

## Development

### Headless Testing

The engine can run without rendering for automated testing:

```python
from src.engine import GameEngine
e = GameEngine(difficulty="medium", human_players=[])
while not e.game_over:
    e.update()
print(f"Winner: P{e.winner}")
```

### Running Tests

```bash
python tests/test_wall_escape.py
python tests/test_obstacles.py
```

### Debug Mode

Set `engine.DEBUG = True` to enable structured physics tracing (`[WALL]`, `[OBS]`, `[BLK]`, `[FIRE]`, `[DEATH]` lines in stdout).

### Adding Features

- Game logic changes go in `src/engine.py`
- Visual changes go in `src/renderer.py`
- New constants go in `config.py`
- New sound events: add to `src/sounds.py` and call `_emit_sound()` in the engine

## Requirements

- Python 3.10+
- Pygame 2.6+

## License

MIT. Sound effects are CC0 from [Kenney](https://kenney.nl/).
