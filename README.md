# 🏰 Rebound

A fast-paced 4-player castle battle game built with Pygame and networked multiplayer via NATS.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Pygame](https://img.shields.io/badge/Pygame-2.x-green)
![NATS](https://img.shields.io/badge/NATS-Multiplayer-purple)

## Screenshots

<!-- TODO: Add screenshots -->

## Overview

Each player owns a castle in one corner of the arena. Castles have a rotating cannon that fires bouncing projectiles. When a projectile hits a castle's bricks, those bricks are destroyed. **Last castle standing wins.**

Projectiles ricochet off walls, obstacles, and each other — creating chaotic chain reactions as the arena fills with bouncing shots. Defensive shields can deflect incoming fire and create blockades to protect your castle.

## Features

- **Local Single-Player** — Battle 3 AI opponents with selectable difficulty (Easy, Medium, Hard)
- **Online Multiplayer** — 4-player matches via NATS with automatic matchmaking
- **AI Bots** — Intelligent AI that aims, fires, and uses shields strategically
- **Admin Tools** — Interactive shell to manage games, spawn bots, spectate, and join mid-match
- **Physics Engine** — Sub-stepped collision detection with elastic ball-ball bouncing
- **Spectator Mode** — Watch AI-vs-AI battles locally

## Gameplay

- 🔴 Red, 🔵 Blue, 🟢 Green, 🟡 Yellow — each player occupies a corner
- Cannons auto-rotate; click to fire a projectile
- Hold **Space** to raise a shield that deflects incoming shots
- Destroy all bricks of an opponent's castle to eliminate them
- Projectiles shrink and slow down with each bounce, then expire
- Random obstacles spawn mid-match to change trajectories

## Installation

### Prerequisites

- Python 3.10+
- [NATS Server](https://nats.io/download/) (for multiplayer only)

### Setup

```bash
# Clone the repository
git clone https://github.com/ryonsherman/pygame-rebound.git
cd pygame-rebound

# Install dependencies
pip install pygame nats-py prompt-toolkit
```

## Running

### Local Play

```bash
make game           # Start the game client (local single-player via menu)
make spectate       # Watch an AI-vs-AI match locally
```

### Online Multiplayer

```bash
# Terminal 1: Start NATS message broker
make nats

# Terminal 2: Start the game server (optional password)
make server
make server mypassword

# Terminal 3+: Start game clients (select "Online" from menu)
make game
```

### Admin Shell

```bash
make admin                 # Connect without password
make admin mypassword      # Connect with server password
```

**Admin commands:**

| Command | Description |
|---------|-------------|
| `games` | List active game rooms |
| `bots [difficulty]` | Spawn 4 bots into a new match |
| `spectate [game_id]` | Open spectator window for a game |
| `join [game_id]` | Join a game (kicks highest slot) |
| `kick <game_id> <slot>` | Kick a player from a slot |
| `stop` | Shut down the server |

## Controls

| Input | Action |
|-------|--------|
| **Mouse movement** | Aim cannon direction |
| **Left click** | Fire projectile |
| **Space (hold)** | Activate shield |
| **Escape** | Quit to menu |

## How Multiplayer Works

Rebound uses a **server-authoritative** architecture:

1. The **server** runs the physics engine and is the sole source of truth
2. **Clients** only send inputs (mouse position, clicks, space)
3. The server broadcasts game state at 20Hz to all connected clients
4. Matchmaking fills rooms of 4 players; unfilled slots get AI after a 30-second countdown
5. All communication is via [NATS](https://nats.io) pub/sub with base64-encoded JSON payloads

## Difficulty Levels

| Parameter | Easy | Medium | Hard |
|-----------|------|--------|------|
| Fire rate | Slow | Moderate | Fast |
| Max bounces | 3 | 4 | 5 |
| Max projectiles | 15 | 18 | 21 |
| Bounce decay | High | Medium | Low |
| Match duration | ~5 min | ~3.5 min | ~1.5 min |

## Configuration

All constants are defined in [`config.py`](config.py):

| Category | Key Settings |
|----------|-------------|
| **Window** | 1024×768 at 60 FPS |
| **Arena** | 904×648 centered with 60px padding |
| **Castles** | 3×3 grid of 14px bricks |
| **Projectiles** | 6px radius, speed 8 px/frame |
| **Shield** | 50px radius, 3-second cooldown |
| **Network** | `nats://127.0.0.1:4222`, 20Hz state broadcast |
| **Lobby** | 30-second countdown before match starts |

## Debug Mode

```bash
REBOUND_DEBUG=1 make game
REBOUND_DEBUG=1 make server
```

Enables verbose logging of fire events, collisions, and eliminations. AI-controlled slots display with an `:AI` suffix in the HUD (e.g., `G:AI`).

## Project Structure

```
rebound-game/
├── game.py              # Client entrypoint (window, menu, input, rendering)
├── server.py            # Multiplayer server (authoritative state, NATS pub/sub)
├── admin.py             # Admin shell (interactive CLI for game management)
├── config.py            # All constants (gameplay, network, colors, dimensions)
├── Makefile             # Build/run targets
├── CONTEXT.md           # Detailed architecture documentation
│
├── src/
│   ├── engine.py        # Core game logic: GameEngine + AIController
│   ├── game_client.py   # Local-mode bridge (input → engine → renderer)
│   ├── bot_client.py    # NATS bot client (AI input → server)
│   ├── nats_common.py   # NATS helpers (encode/decode, subjects, auth)
│   ├── renderer.py      # All Pygame drawing (castles, projectiles, HUD)
│   ├── menu.py          # Main menu (difficulty, online option)
│   └── sounds.py        # Sound effect loader
│
└── tests/
    ├── test_wall_escape.py
    ├── test_obstacles.py
    ├── test_nats.py
    └── test_difficulty_pacing.py
```

## Disclaimer

**Personal Project Notice:** This is a personal hobby project created for learning and experimentation purposes only. The name "Rebound" and game concept are used without claim to any existing trademarks or copyrights. No infringement is intended. If you hold rights to similar concepts and have concerns, please reach out via GitHub issues rather than legal action.

## License

MIT License — see [LICENSE](LICENSE) for details.
