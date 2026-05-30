# Multiplayer Architecture: How Rebound Uses NATS

## Overview

Rebound's multiplayer uses [NATS](https://nats.io) as a lightweight message bus between a single authoritative game server and multiple clients (human players, bot clients, admin tools). The architecture is simple:

- **The server runs the physics.** Clients never simulate — they only send inputs and receive rendered state.
- **NATS provides pub/sub and request/reply.** No custom TCP protocol, no WebSockets, no REST API. Just messages on named subjects.
- **All messages are base64-encoded JSON.** A thin obfuscation layer (not encryption) that prevents casual inspection of traffic on shared NATS servers.

Why NATS? It's fast, tiny, requires zero configuration, supports wildcards for subject routing, and has native request/reply semantics. For a game that needs ~20 state broadcasts per second to a handful of clients, it's perfect — no need for the complexity of gRPC or a custom binary protocol.

## Subject Hierarchy

Every NATS subject starts with a configurable prefix (default: `rebound`). Here's the full map:

```
rebound.
├── match                          Request/reply: matchmaking
├── game.<id>.
│   ├── state                      Server → clients: full game state (20Hz)
│   ├── status                     Server → clients: lobby info (2Hz, waiting only)
│   ├── input.<slot>               Client → server: player input (per-slot)
│   ├── leave                      Client → server: player disconnecting
│   └── kicked.<slot>              Server → specific client: you've been kicked
└── admin.
    ├── list_games                 Request/reply: list active rooms
    ├── stop                       Request/reply: shut down server
    ├── kick                       Request/reply: kick a player
    └── join                       Request/reply: admin takes a slot
```

The `<id>` is an 8-character hex string (e.g. `a3f1bc09`) generated from a UUID when a room is created. The `<slot>` is 0–3, corresponding to the four castle positions (Red, Blue, Green, Yellow).

## Message Format

All messages go through `encode_msg` / `decode_msg`:

```python
# Encoding (publish side)
base64.b64encode(json.dumps(data).encode())   # dict → bytes

# Decoding (subscribe side)
json.loads(base64.b64decode(raw).decode())     # bytes → dict
```

This isn't security — it's a courtesy. If you're running on a shared NATS server (like `demo.nats.io`), raw JSON payloads would be trivially readable by anyone subscribed to `rebound.>`. Base64 adds one layer of "you have to try" without adding latency or complexity.

## Connection Flow

Here's what happens when a player clicks "Online" in the game menu:

```
┌──────────┐                    ┌──────────┐                    ┌──────────┐
│  Client  │                    │   NATS   │                    │  Server  │
└────┬─────┘                    └────┬─────┘                    └────┬─────┘
     │                               │                               │
     │  nats.connect()               │                               │
     │──────────────────────────────>│                               │
     │                               │                               │
     │  REQUEST rebound.match        │                               │
     │  {"difficulty": "medium"}     │                               │
     │──────────────────────────────>│  deliver to server             │
     │                               │──────────────────────────────>│
     │                               │                               │
     │                               │  REPLY                        │
     │                               │  {"ok":true, "game_id":"...", │
     │  response                     │   "slot": 0}                  │
     │<──────────────────────────────│<──────────────────────────────│
     │                               │                               │
     │  SUBSCRIBE rebound.game.<id>.state                            │
     │  SUBSCRIBE rebound.game.<id>.status                           │
     │──────────────────────────────>│                               │
     │                               │                               │
```

The client spins up a dedicated asyncio event loop on a background thread (since the main thread runs Pygame). All NATS operations happen on that thread; game state arrives via a thread-safe queue.

## Matchmaking

Matchmaking uses NATS request/reply — the client sends a request to `rebound.match` and blocks until the server responds.

**Request payload:**
```json
{"difficulty": "medium"}
```

For bot clients, the request also includes:
```json
{"difficulty": "medium", "bot": true, "admin_bot": false}
```

**Server logic:**
1. Try to find an existing room with the same difficulty that has open slots
2. If found → assign the next available slot (lowest number)
3. If not → create a new room with a fresh ID, assign slot 0

**Response:**
```json
{"ok": true, "game_id": "a3f1bc09", "slot": 2}
```

The `bot` flag matters: bot clients don't count as "real players" and don't get the crown icon in the renderer. The `admin_bot` flag marks the room as admin-created, preventing it from auto-closing when no humans are present.

## Lobby / Waiting Phase

Once matched, the client enters the waiting state. The server broadcasts status messages at 2Hz on `rebound.game.<id>.status`:

```json
{
  "game_id": "a3f1bc09",
  "difficulty": "medium",
  "status": "waiting",
  "players": 2,
  "open_slots": 2,
  "countdown": 24
}
```

The game starts when either:
- **All 4 slots are filled** — starts immediately
- **The countdown reaches 0** (default 30 seconds) — starts with available players + server-side AI filling empty slots

If the countdown expires and there are no real (human) players in the room (and it wasn't admin-created), the room is closed instead of started.

The client uses the countdown value from these status broadcasts to display the timer, rather than tracking it locally.

## Gameplay

Once the game starts, two things happen continuously:

### Client → Server: Input (every frame)

Each client publishes to `rebound.game.<id>.input.<slot>`:

```json
{
  "mouse_x": 512,
  "mouse_y": 384,
  "click": false,
  "space": true
}
```

This is raw input — mouse position (for cannon aiming), whether the mouse was clicked this frame (fire), and whether space is held (shield). The server interprets these inputs through its own physics engine.

The server uses wildcard subscription (`rebound.game.*.input.>`) to receive all input for all games. It parses the subject to extract the game ID and slot number.

### Server → Clients: State (20Hz)

The server publishes the full game state to `rebound.game.<id>.state` at 20Hz (every 3 frames of its internal 60fps loop):

```json
{
  "castles": [
    {"owner": 0, "alive": true, "center": [90, 90], "bricks": [...], "human": true, ...},
    ...
  ],
  "projectiles": [
    {"x": 400, "y": 300, "owner": 1, "radius": 5, ...},
    ...
  ],
  "obstacles": [...],
  "game_over": false,
  "winner": null
}
```

The server adds a `"human"` flag to each castle indicating whether it's controlled by a real player (for the crown display). Clients don't simulate anything — they just render this state directly.

### Server Authority

The server is the single source of truth. It:
- Runs the physics engine at 60fps
- Processes the *most recent* input from each slot per tick (earlier inputs in the same tick are discarded)
- Resolves all collisions, projectile bouncing, and brick destruction
- Detects game over conditions

Clients cannot cheat because they never run the simulation. They can only lie about their mouse position or spam clicks, but the server enforces fire cooldowns and physics constraints.

## Player Disconnect / Leave

When a player leaves (presses Q, closes the window, or loses connection):

1. Client publishes to `rebound.game.<id>.leave`:
   ```json
   {"slot": 2}
   ```

2. Server removes the slot from `human_players` and calls `engine.add_ai(slot)` — the AI takes over that castle immediately, preserving its current health.

3. If **all real players** have left and the room isn't admin-created, the room is marked "finished."

4. If a player leaves during the **waiting** phase, their slot returns to the open pool. If the room becomes completely empty, it closes.

The AI takeover is seamless — the castle doesn't reset. The AI picks up wherever the human left off.

## Bot Clients

Bot clients (`src/bot_client.py`) are standalone processes that connect to NATS and play the game using an AI controller. They behave almost identically to human clients, with a few differences:

1. **Matchmaking** — they send `"bot": true` which prevents them from getting the crown icon
2. **Input generation** — instead of reading mouse/keyboard, they run an `AIController` locally and convert its decisions into the same `{mouse_x, mouse_y, click, space}` format
3. **State consumption** — they subscribe to game state to inform their AI decisions (targeting, threat assessment)
4. **Kicked handling** — they subscribe to `rebound.game.<id>.kicked.<slot>` and stop their input loop if kicked

```
┌──────────────────────────────────────────────────┐
│                   Bot Client                      │
│                                                   │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐ │
│  │  State   │────>│    AI    │────>│  Input   │ │
│  │ Receiver │     │Controller│     │ Publisher│ │
│  └──────────┘     └──────────┘     └──────────┘ │
│       ▲                                   │      │
└───────┼───────────────────────────────────┼──────┘
        │              NATS                 │
        │                                   ▼
   game.<id>.state              game.<id>.input.<slot>
```

Bot clients send input at 60Hz (same rate as the server tick), but only when their castle is alive and the game isn't over.

## Admin Commands

The admin shell (`admin.py`) connects to NATS and sends request/reply messages to dedicated admin subjects.

### Authentication

Admin commands use HMAC-SHA256 with a shared password:

```python
nonce = str(int(time.time()))                           # Unix timestamp as string
token = hmac.HMAC(password, nonce, sha256).hexdigest()  # HMAC of the nonce
payload["_nonce"] = nonce
payload["_token"] = token
```

The server verifies:
1. The nonce is within ±5 seconds of the server's clock (prevents replay attacks)
2. The HMAC matches (proves knowledge of the password)

If no password was set on the server, all admin commands are accepted without auth.

### Available Commands

| Command | Subject | Effect |
|---------|---------|--------|
| `games` | `admin.list_games` | Returns list of all active rooms with status, players, frame count |
| `stop` | `admin.stop` | Gracefully shuts down the server |
| `kick <id> <slot>` | `admin.kick` | Removes a player from a slot, publishes kicked notification |
| `join <id>` | `admin.join` | Takes a slot (kicks highest-numbered player if full) |
| `bots [diff]` | Uses `match` | Spawns 4 bot clients into a game, marks room as admin-created |
| `spectate <id>` | Subscribes to `state` | Opens a Pygame window to watch a game (read-only) |

The `join` command is notable: if the room is full, it kicks the highest-numbered slot to make room. The kicked client receives a message on `rebound.game.<id>.kicked.<slot>` and stops sending input.

## Room Lifecycle

```
         ┌─────────────────────────────────────────────────┐
         │                                                 │
         ▼                                                 │
    ┌─────────┐         ┌─────────┐         ┌──────────┐  │
    │ CREATED │────────>│ WAITING │────────>│ PLAYING  │  │
    │         │         │         │         │          │  │
    └─────────┘         └────┬────┘         └────┬─────┘  │
                             │                    │        │
                   empty or  │          game over │        │
                   no humans │          or empty  │        │
                             ▼                    ▼        │
                        ┌──────────┐                      │
                        │ FINISHED │                      │
                        └────┬─────┘                      │
                             │                            │
                             │  after 5 seconds           │
                             ▼                            │
                        ┌──────────┐                      │
                        │ REMOVED  │──────────────────────┘
                        └──────────┘        (memory freed)
```

**Created → Waiting:** Immediate. A room is created in the waiting state when the first player matches and no suitable room exists.

**Waiting → Playing:** When all 4 slots fill OR the 30-second countdown expires (whichever comes first). Empty slots are filled by server-side AI.

**Waiting → Finished:** If the countdown expires with no real players (bots-only room that wasn't admin-created), or if all players leave during the waiting phase.

**Playing → Finished:** When one castle remains (game over), or when all real players disconnect from a non-admin room.

**Finished → Removed:** After 5 seconds of being finished (300 frames at 60fps), the room is deleted from memory. This grace period allows clients to receive the final game-over state.

## Configuration Reference

All network constants live in `config.py`:

| Constant | Default | Purpose |
|----------|---------|---------|
| `NATS_URL` | `nats://127.0.0.1:4222` | NATS server address |
| `NATS_NAME` | `github.ryonsherman/rebound-game` | Client identity string |
| `NATS_PREFIX` | `rebound` | Subject namespace prefix |
| `LOBBY_COUNTDOWN` | `30` | Seconds before auto-start |
| `STATE_HZ` | `20` | State broadcasts per second |
| `STATUS_HZ` | `2` | Lobby status broadcasts per second |
| `CONNECT_TIMEOUT` | `5` | Seconds to wait for NATS connection |
| `REQUEST_TIMEOUT` | `10` | Seconds to wait for request/reply |
