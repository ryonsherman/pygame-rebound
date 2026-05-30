# Tests

Reference for AI agents working on this codebase. Describes what each test file covers and why.

## Running

```bash
make tests       # Everything that doesn't need a NATS server (184 tests, ~26s)
make tests-nats  # Integration tests requiring live NATS + game server (18 tests, ~10s)
```

## Test Files

### `conftest.py`
Shared pytest fixtures providing pre-configured `GameEngine` instances at each difficulty level plus a human-controlled variant. Used by most engine/gameplay tests.

---

### `test_engine_physics.py` — Core Physics
Verifies the physics simulation is correct and robust:
- **Wall bounce containment**: Projectiles stay inside the arena over 3000 frames
- **Bounce count tracking**: Counter increments on each wall hit
- **Max bounces**: Projectile dies after exceeding difficulty bounce limit
- **Sub-stepping**: Fast projectiles (speed 8) don't tunnel through 14px bricks
- **Obstacle collision**: Projectiles don't get stuck inside obstacles (2000-frame stress)
- **Ball-ball elastic collision**: Overlapping balls separate correctly
- **Ball collision cooldown**: Same pair can't re-collide for 8 frames
- **Radius shrink floor**: Radius never drops below 2px (5000-frame stress)

### `test_engine_physics_edge.py` — Physics Edge Cases
Corner cases that could cause crashes or escapes:
- **Simultaneous X+Y bounce**: Ball hitting an exact corner bounces correctly
- **All 4 arena corners**: Parametrized test — ball placed at each corner stays contained
- **Zero-speed projectile**: vx=0, vy=0 doesn't crash (num_steps = max(1,...))
- **Center inside obstacle**: When dist_sq == 0, push_out_of_rect still works
- **Overlapping many obstacles**: Iteration cap (5) prevents infinite loops
- **Post-obstacle re-clamp**: After being pushed out of obstacle, ball is re-clamped to arena
- **Multiple obstacle collisions same sub-step**: Reflection is correct
- **Nearly-coincident balls**: dist < 1 triggers early return (no division by zero)
- **Bounce cooldown prevents shrink**: Rapid bounces don't over-shrink
- **Projectile culling**: When exceeding max_projectiles, oldest is removed (FIFO)
- **Game over draw**: 0 alive castles (winner=None) doesn't crash
- **Angular velocity normalization**: Cannon angle wraps correctly across ±π

---

### `test_engine_gameplay.py` — Game Mechanics
Verifies gameplay rules work as designed:
- **Fire cooldown**: Can't fire again until cooldown expires
- **Shield activation**: Space key raises shield
- **Shield deactivation**: Releasing space drops shield
- **Shield expiry**: Shield times out after max duration
- **Shield reflection**: Projectile bounces off active shield
- **Brick 2-hit destruction**: First hit cracks, second destroys
- **Castle death**: Castle marked dead when all bricks gone
- **Owner projectile cleanup**: Dead player's projectiles are removed
- **Win condition**: game_over=True when 1 castle remains
- **Dead castle input ignored**: Dead players can't fire or shield
- **Cannon sling**: Firing while cannon rotates adds tangential momentum
- **Blockade cap**: Can't exceed max blockades per castle

### `test_game_client.py` — Client Logic
Tests game client behavior without pygame:
- **Shield cooldown guard**: Can't re-activate shield during cooldown
- **Non-human input ignored**: Engine rejects input from non-human slots
- **Click edge detection**: Only fires on mouse-down transition (not hold)
- **Game over timer**: 30-second auto-return logic
- **NATS connect failure**: Connection error handled gracefully
- **Match returns not-ok**: Server rejection handled
- **State queue backpressure**: Full queue drops stale states

---

### `test_ai_controller.py` — AI Basics
Core AI behavior:
- **Targets alive castles only**: AI won't aim at dead castles
- **Retargets on death**: Picks new target when current target dies
- **No fire during shield**: AI doesn't waste ammo while shielding
- **Hard fires faster**: Hard difficulty has shorter fire intervals
- **Hard has better aim**: Hard difficulty has tighter angle spread

### `test_ai_logic.py` — AI Internals
Deep AI logic verification:
- **Early returns**: AI does nothing when all targets dead or own castle dead
- **_segments_intersect**: Geometry helper — intersecting, non-intersecting, miss, collinear cases
- **_line_intersects_rect**: Hit, miss, and endpoint-inside cases
- **_angle_in_quadrant**: All 4 owners have correct quadrant bounds
- **_line_blocked**: Detects obstacles blocking line of fire
- **_eval_brick_bounce**: Returns bounce point or None when blocked
- **_find_bounce_point**: Wall order by direction, obstacle zone filtering, blockade bounce, no-candidates fallback
- **_pick_aim_point**: Falls back to direct aim when no bounce found
- **AI sling firing**: Fires within sling_threshold of target angle
- **Shield hold countdown**: Timer decrements correctly
- **Shield deactivation**: Releases when threat passes
- **Threat detection**: Slow projectiles (speed < 1) ignored; closest approach triggers shield
- **Medium difficulty values**: Verify else-branch defaults

---

### `test_difficulty_scaling.py` — Difficulty Parameters
Parametrized verification that config values are correct:
- max_bounces: easy=3, medium=4, hard=5
- max_projectiles: easy=15, medium=18, hard=21
- bounce_shrink: easy=0.75, medium=0.80, hard=0.85
- bounce_slowdown: easy=0.84, medium=0.88, hard=0.92
- Pacing: hard games complete faster than easy

---

### `test_nats_protocol.py` — Network Protocol
Core protocol correctness:
- **Encode/decode roundtrip**: Simple dict, empty dict, unicode
- **Encode returns bytes**: Type check
- **Decode handles memoryview**: NATS delivers memoryview, not bytes
- **State serialization roundtrip**: Full engine state survives encode→decode
- **State size reasonable**: Serialized state < 16KB
- **HMAC auth**: Sign and verify happy path
- **Wrong password fails**: Verification rejects bad password
- **Missing fields fails**: Incomplete auth data rejected
- **Expired nonce fails**: Stale timestamp rejected (>5s drift)
- **Tampered token fails**: Modified payload rejected
- **Subject construction**: Format strings produce correct NATS subjects

### `test_nats_protocol_edge.py` — Protocol Error Handling
Malformed input handling:
- **Invalid base64**: Raises on garbage input
- **Valid base64, invalid JSON**: Raises on non-JSON content
- **Empty bytes**: Handled gracefully
- **Nonce not integer**: verify_auth rejects non-numeric nonce
- **Nonce None**: verify_auth rejects null nonce
- **sign_request mutates in-place**: Documents the behavior (adds nonce+token to input dict)
- **Oversized payload**: Large dict still encodes (no arbitrary limits)
- **encode_state alias**: Functionally equivalent to encode_msg

---

### `test_server.py` — Server Room Logic
Server-side room lifecycle (unit tests, no NATS needed):
- **Last player leaves during countdown**: Room closes
- **Countdown expires with no real players (non-admin)**: Room finishes
- **Concurrent matchmaking**: Second request for full room gets None
- **Input edge cases**: Slot out of range, slot not in players, malformed subject, decode failure — all handled without crash
- **Leave decode failure**: No crash
- **Room tick exception**: Doesn't kill the server
- **Room cleanup delay**: Finished room removed after 5 seconds
- **Server stop mid-game**: Graceful shutdown
- **Admin join open slot**: Direct assignment without kicking

### `test_nats_integration.py` — Live NATS Integration
**Requires**: `make nats` + `make server` running.

End-to-end multiplayer protocol testing:
- **Connect/disconnect**: Basic NATS connectivity, pub/sub, no-responders
- **Matchmaking**: Room assignment, multiple players fill room, invalid difficulty defaults
- **Input/state loop**: Send input → receive 20Hz state broadcast, lobby status at 2Hz
- **Admin auth**: Valid auth succeeds, invalid password rejected, missing auth rejected, kick nonexistent game
- **Bot lifecycle**: Bot joins and receives kicked notification, bot leave updates slot
- **Room lifecycle**: Room fills and starts, real players leave → room closes, admin_created persists, admin join kicks highest slot

---

### `test_bot_client.py` — Bot Client State Machine
Bot client behavior in isolation (mocked NATS):
- **State is None**: No crash before first state received
- **Slot out of range**: Defensive check prevents index error
- **Castle dead**: Bot stops sending input
- **Game over**: Stops run loop
- **stop() method**: Sets running=False
- **Disconnect cleanup**: drain() called on exit

---

### `test_config.py` — Config & ColorProxy
Lazy color proxy (avoids pygame import at config load time):
- **__iter__**: Returns RGBA tuple
- **__getitem__**: Index access works
- **__len__**: Returns 4
- **__repr__**: Readable string output
- **__eq__ and __hash__**: Comparison and dict key usage
- **Lazy resolution**: Importing config doesn't trigger pygame.init()
- **Color() factory**: Returns _ColorProxy instance

---

### `test_renderer.py` — Renderer (mocked pygame)
Rendering logic without a real display:
- **Both render paths callable**: draw_game and draw_game_direct don't crash
- **Dead castle early return**: Dead castles not drawn
- **Cracked brick**: hp=1 uses different color than hp=2
- **Dead blockade skip**: Filtered from rendering
- **Shield inactive**: Nothing drawn when shield is off
- **Crown requires human flag**: Only drawn for human=True castles
- **Stats position**: Top vs bottom layout based on owner
- **Game over None winner**: Renders "Draw!" text
- **Font caching**: Same font object returned on repeated calls

### `test_menu.py` — Menu (mocked pygame)
Menu navigation logic:
- **Keyboard left/right**: Changes difficulty column
- **Keyboard down/up**: Switches between local and online rows
- **Mouse click mode button**: Selects difficulty
- **Mouse click START**: Returns selected mode config
- **Online mode**: Returns `{"online": True}` dict
- **Hover state**: Mouse position sets hover index
- **_sync_mode**: Row 0 syncs to difficulty, row 1 syncs to online

### `test_sounds.py` — Sound System (mocked pygame.mixer)
Sound loading and playback:
- **Already initialized**: Second init() is a no-op
- **Mixer init failure**: Graceful fallback, no crash
- **Legacy string event format**: Backwards compatibility
- **No sound files exist**: No crash
- **No available channel**: Skips gracefully
- **Variant loading**: Random selection from multiple .ogg files per event

### `test_admin.py` — Admin Shell (mocked)
Admin CLI logic:
- **_fix_terminal**: Repairs termios settings without crash
- **_signed**: With and without password produces correct payload
- **_check_game**: Prefix matching, ambiguous prefix rejection, exact match
- **cmd_bots**: Spawns 4 bot clients
- **cmd_join**: Requires game ID argument
- **cmd_spectate**: Subscribes to state subject
- **Unknown command**: Shows error message
