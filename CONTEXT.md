# Rebound — Project Context

A 4-player castle battle game built with Pygame and networked multiplayer via NATS.

## Overview

Each player owns a castle in one corner of the arena. Castles have a rotating cannon that fires projectiles. Projectiles bounce off walls, obstacles, and each other. When a projectile hits a castle's bricks, those bricks are destroyed. Last castle standing wins.

The game supports local single-player (you vs 3 AI) and online multiplayer (4 humans, or any mix of humans and bots connected via NATS).

## Architecture

```
game.py          — Client entrypoint (Pygame window, menu, input, rendering)
server.py        — Multiplayer server (authoritative game state, NATS pub/sub)
admin.py         — Admin shell (interactive CLI for managing games/bots)
config.py        — All constants (gameplay, network, colors, dimensions)
Makefile         — make game / make server [pass] / make nats / make spectate / make admin [pass]

src/
  engine.py      — Core game logic: GameEngine + AIController
  game_client.py — Thin wrapper bridging input/rendering to engine (local mode)
  bot_client.py  — NATS bot client: runs AIController, sends inputs to server
  nats_common.py — NATS helpers: encode/decode, subjects, auth signing
  renderer.py    — All Pygame drawing (castles, projectiles, obstacles, HUD)
  menu.py        — Main menu (difficulty selection, online option)
  sounds.py      — Sound effect loader

tests/
  test_wall_escape.py
  test_obstacles.py
  test_nats.py
  test_difficulty_pacing.py
```

## How It Works

### Local Mode
- `game.py` creates a `GameEngine` with `human_players=[0]`
- Player 0 is mouse-controlled, slots 1-3 are AI
- Engine runs at 60fps, renderer draws state each frame

### Online Mode
- `server.py` hosts rooms; engine runs server-side with `human_players=set()`
- All connected clients (humans and bots) are "human" to the engine (external input)
- Clients send `{mouse_x, mouse_y, click, space}` to `rebound.game.<id>.input.<slot>`
- Server broadcasts state at 20Hz to `rebound.game.<id>.state`
- Server broadcasts status at 2Hz to `rebound.game.<id>.status`

### Matchmaking
- Client sends `{difficulty}` to `rebound.match`, server assigns room/slot
- Bot clients send `{difficulty, bot: true, admin_bot: true/false}`
- Room auto-starts when all 4 slots are filled
- If countdown (30s) expires, room starts with available players + server-side AI
- Rooms without any `real_players` at start time are closed (unless `admin_created`)

### Admin Shell
- Connects to NATS, authenticates via HMAC-SHA256 signed requests
- Commands: `games`, `bots [diff]`, `spectate [id]`, `join [id]`, `kick <id> <slot>`, `stop`
- `bots` spawns 4 bot clients into a match, marks room as `admin_created`
- `join` kicks the highest-numbered slot and takes over (same castle health)
- Uses `prompt_toolkit` for async input

## Key Design Decisions

### Server Authority
The server is the sole source of truth. Clients only send inputs. The server runs the physics engine and broadcasts state. This prevents cheating and ensures consistency.

### AI Controller Management
- The engine creates AI controllers for all 4 slots at init
- AI only updates slots NOT in `human_players` (guard: `if ai.owner not in self.human_players`)
- `engine.add_ai(slot)` — spawns AI for a slot (player leaves mid-game)
- `engine.remove_ai(slot)` — removes AI for a slot (player joins mid-game)
- AI takeover preserves castle health — no reset

### Real Players vs Bot Clients
- `room.players` — all connected clients (bots + humans)
- `room.real_players` — only actual human players
- `room.admin_created` — room was created via admin `bots` command
- Crowns in renderer only show for `real_players`
- Room closes if all real players leave (unless `admin_created`)

### Bot Kicked Handling
- Server publishes to `rebound.game.<id>.kicked.<slot>` when a slot is kicked
- Bot clients subscribe and stop their input loop on receiving this message
- This prevents a kicked bot from overwriting the new player's inputs

## Physics

- **Sub-stepping**: projectiles advance in increments ≤ radius per sub-step (prevents tunneling at speed 8 with 14px bricks)
- **Obstacle collision**: circle-vs-rectangle with normal-based reflection
- **Ball-ball collision**: elastic, 8-frame cooldown between same pair
- **Cannon sling**: projectile inherits tangential velocity from cannon rotation at fire time
- **Arena**: `ARENA_RECT=(60,60,904,648)`, centered in 1024x768 window

## Difficulty Scaling

| Parameter | Easy | Medium | Hard |
|-----------|------|--------|------|
| Fire interval | 99-198 | 60-150 | 27-81 |
| Max bounces | 3 | 4 | 5 |
| Max projectiles | 15 | 18 | 21 |
| Shrink/bounce | 0.75 | 0.80 | 0.85 |
| Slowdown/bounce | 0.84 | 0.88 | 0.92 |
| Match duration | ~4.8 min | ~3.4 min | ~1.2 min |

## Network Protocol

- Transport: NATS (nats://127.0.0.1:4222)
- All payloads: base64-encoded JSON
- Subjects use prefix `rebound` (configurable in config.py)
- Admin auth: HMAC-SHA256 with time-based nonce (±5s tolerance)
- Server password passed as `sys.argv[1]` (optional for both server and admin)

### Subject Map
```
rebound.match                      — matchmaking request/response
rebound.game.<id>.state            — game state broadcast (20Hz)
rebound.game.<id>.status           — lobby status broadcast (2Hz)
rebound.game.<id>.input.<slot>     — player input
rebound.game.<id>.leave            — player leave notification
rebound.game.<id>.kicked.<slot>    — kick notification to specific slot
rebound.admin.list                 — list active games
rebound.admin.stop                 — stop server
rebound.admin.kick                 — kick a player
rebound.admin.join                 — admin join a game
```

## Running

```bash
# Start NATS server
make nats

# Start game server (with optional password)
make server mypassword

# Start game client
make game

# Spectate a local single-player game
make spectate

# Start admin shell (with optional password)
make admin mypassword
```

## Debug Mode

Set `REBOUND_DEBUG=1` to enable verbose engine logging (fire events, collisions, deaths). AI-controlled slots show `:AI` suffix (e.g. `G:AI`), humans show plain color letter.

## Common Pitfalls

- `config.py` imports `pygame.Color` at module level, which triggers pygame init and may corrupt terminal settings. `_fix_terminal()` in admin.py repairs this.
- The engine creates all 4 AI controllers at init regardless of `human_players`. The guard in `update()` prevents them from running for human slots. Don't remove this guard.
- `assign_slot(bot=True)` vs `assign_slot(bot=False)` determines whether the slot shows a crown. Bot clients must pass `bot=True`.
- Pygame window cleanup on macOS requires `set_mode((1,1))` + `display.quit()` + `quit()` sequence.
- The `%: @:` catch-all in Makefile silently swallows unknown targets (needed for arg passing via `$(filter-out)`).
