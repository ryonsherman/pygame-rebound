"""
Bot client: connects to NATS, joins a match, and sends AI-generated
inputs to the server. Runs its own AIController to produce realistic
mouse/click/space inputs at 60Hz.
"""
import asyncio
import json
import math
import random

import nats

from src.engine import AIController, _corner_positions, _clamp_aim, ARENA_RECT
from src.nats_common import (
    NATS_SERVER, CONNECT_TIMEOUT, REQUEST_TIMEOUT,
    SUBJECT_MATCH, sub_game, encode_msg, decode_msg, decode_state,
)


class BotClient:
    def __init__(self, difficulty="medium", name="bot", admin=False):
        self.difficulty = difficulty
        self.name = name
        self.admin = admin
        self.nc = None
        self.game_id = None
        self.slot = None
        self.ai = None
        self.state = None
        self._running = False
        self._state_sub = None
        # Track firing independently since server state doesn't include fire_request
        self._fire_this_tick = False

    async def connect_and_match(self):
        self.nc = await nats.connect(NATS_SERVER, connect_timeout=CONNECT_TIMEOUT)
        msg = await self.nc.request(
            SUBJECT_MATCH,
            encode_msg({"difficulty": self.difficulty, "bot": True, "admin_bot": self.admin}),
            timeout=REQUEST_TIMEOUT,
        )
        result = decode_msg(msg.data)
        if not result.get("ok"):
            raise RuntimeError(f"[{self.name}] Match failed: {result}")

        self.game_id = result["game_id"]
        self.slot = result["slot"]
        print(f"[{self.name}] Joined game {self.game_id} as slot {self.slot}")

        # Subscribe to state
        subj = sub_game(self.game_id, "state")
        self._state_sub = await self.nc.subscribe(subj, cb=self._on_state)

        # Subscribe to kicked notification
        kicked_subj = sub_game(self.game_id, "kicked", str(self.slot))
        await self.nc.subscribe(kicked_subj, cb=self._on_kicked)

        # AI controller initialized when we receive first state (need obstacles)
        self.ai = None
        return result

    async def _on_state(self, msg):
        try:
            self.state = decode_state(msg.data)
        except Exception:
            pass

    async def _on_kicked(self, msg):
        print(f"[{self.name}] Kicked from game")
        self._running = False

    async def run(self, tick_hz=60):
        """Main loop: generate AI input and send to server at tick_hz."""
        self._running = True
        interval = 1.0 / tick_hz

        try:
            while self._running:
                if self.state and not self.state.get("game_over", False):
                    # Initialize AI with obstacles on first state
                    if self.ai is None:
                        obstacles = self.state.get("obstacles", [])
                        self.ai = AIController(self.slot, self.difficulty, obstacles)
                    
                    castles = self.state.get("castles", [])
                    projectiles = self.state.get("projectiles", [])

                    if self.slot < len(castles) and castles[self.slot].get("alive"):
                        # Patch: give castle a fire_request field for AI to write to
                        my_castle = castles[self.slot]
                        my_castle["fire_request"] = None

                        # Update AI targeting and rotation
                        self.ai.update(castles, projectiles)

                        # Read what the AI decided
                        cx, cy = my_castle["center"]
                        angle = self.ai.current_angle
                        aim_x = cx + math.cos(angle) * 300
                        aim_y = cy + math.sin(angle) * 300

                        fire = my_castle.get("fire_request") is not None
                        use_shield = self.ai.shield_hold > 0

                        inp = {
                            "mouse_x": int(aim_x),
                            "mouse_y": int(aim_y),
                            "click": fire,
                            "space": use_shield,
                        }

                        subj = sub_game(self.game_id, "input", str(self.slot))
                        await self.nc.publish(subj, encode_msg(inp))

                elif self.state and self.state.get("game_over", False):
                    self._running = False
                    break

                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass
        finally:
            print(f"[{self.name}] Stopped, disconnecting")
            if self.nc.is_connected:
                await self.nc.drain()

    def stop(self):
        self._running = False
