# Test Plan

## Integration Tests

- [ ] **Fire cooldown enforced** — Verify a castle cannot fire two projectiles within `FIRE_COOLDOWN` frames even if `fire_request` is set every frame.
- [ ] **Shield blocks then goes on cooldown** — Activate shield, hit with projectile, confirm reflect + cooldown timer set to `SHIELD_COOLDOWN` and shield deactivates.
- [ ] **Shield duration auto-expires** — Hold shield active, confirm it deactivates after exactly `SHIELD_DURATION` frames.
- [ ] **Cannon angle clamping per quadrant** — For each owner (0-3), confirm `_clamp_aim` restricts aim to the correct quadrant half-plane.
- [ ] **Blockade spawns on shield reflect** — Reflect an enemy projectile with shield, verify a blockade is added to the castle's blockade list.
- [ ] **MAX_BLOCKADES cap respected** — Fill castle with `MAX_BLOCKADES` blockades, trigger another reflect, confirm no additional blockade is added.
- [ ] **Win condition triggers on last castle** — Destroy all bricks of 3 castles, confirm `game_over=True` and `winner` is the surviving owner.
- [ ] **Castle collapse removes owner's projectiles** — Destroy a castle, confirm all projectiles owned by that castle are removed.
- [ ] **Human input ignored when castle dead** — Kill player's castle, send input, confirm no angle change or fire.
- [ ] **Cannon sling momentum added to projectile** — Rotate cannon rapidly then fire, verify projectile velocity has tangential component beyond base speed.
- [ ] **Server room slot assignment and leave** — Create a `GameRoom`, assign 4 slots, confirm 5th returns `None`; leave a slot and reassign.
- [ ] **Server input buffer uses last input per frame** — Feed multiple inputs to `handle_input`, confirm only the latest is applied per tick.
- [ ] **encode_state / decode_state roundtrip** — Confirm `decode_state(encode_state(state)) == state` for a full `get_state()` snapshot.

## Debug / Regression Tests

- [ ] **Projectile never escapes arena bounds** — Run 5000 frames, assert every alive projectile satisfies `ax+r <= x <= ax+aw-r` (and y).
- [ ] **Projectile max bounces kills ball** — Create a projectile at max bounces - 1, trigger one more wall hit, confirm `alive=False`.
- [ ] **Ball-ball collision separation** — Place two overlapping projectiles, run `_bounce_balls`, confirm they no longer overlap.
- [ ] **Brick HP two-hit destruction** — Fire at a castle brick twice, confirm first hit cracks (hp=1), second destroys (alive=False).
- [ ] **Blockade brick destroyed on projectile hit** — Place blockade in projectile path, confirm brick `alive=False` after collision.
- [ ] **AI fires only when shield is inactive** — Confirm AI `_fire` is never called while `castle["shield"]["active"]` is True.
- [ ] **AI retargets when current target dies** — Kill AI's target castle mid-game, confirm it picks a new alive target next update.
- [ ] **_random_blockade_pos returns None for degenerate arena** — Patch `ARENA_RECT` to tiny size, confirm `None` is returned (no crash).
- [ ] **Shield reflect adds random angle offset** — Reflect a projectile, confirm new angle differs from simple 180-degree reversal.
- [ ] **Projectile radius never drops below 2** — Bounce a projectile many times, confirm radius floors at 2.

## Optimization / Performance Tests

- [ ] **10,000-frame full-AI game completes under N seconds** — Benchmark a hard-difficulty all-AI game for regression in tick cost.
- [ ] **Projectile cap culling performance** — Spawn `max_projectiles + 50` balls, confirm cull runs in O(n) without quadratic blowup.
- [ ] **Obstacle collision loop iteration cap** — Verify inner collision loops do not cause frame spikes by timing individual updates with many projectiles near obstacles.
- [ ] **get_state serialization size** — Snapshot state at peak projectile count, confirm JSON size stays under 16KB for network send at 20Hz.
- [ ] **encode_state throughput** — Measure base64+JSON encode of a full state dict 1000 times, assert < 50ms total.

## Stress Tests

- [ ] **All 4 AI on hard, 30k frames without crash** — Run a full game to completion or cap, confirm no exception or infinite loop.
- [ ] **Simultaneous shield activations by all 4 players** — All castles activate shield same frame with incoming projectiles; no double-reflect or crash.
- [ ] **Max projectiles + max blockades simultaneously** — Fill arena to caps on both, run 1000 frames, confirm no stuck/escaped balls.
- [ ] **Rapid fire with zero cooldown (monkey-patch)** — Set `FIRE_COOLDOWN=0`, spam fire for 500 frames, confirm projectile list stays bounded by `max_projectiles`.
- [ ] **Ball-ball collision storm** — Spawn 20+ projectiles in a small area, run 100 frames, confirm no NaN velocities or infinite positions.
- [ ] **GameRoom with all 4 human slots filled + concurrent input** — Instantiate GameRoom, assign all 4 slots, feed inputs to all, tick 100 frames, confirm valid state output.
