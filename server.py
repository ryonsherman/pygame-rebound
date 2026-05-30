import asyncio
import json
import uuid
import time
import nats
from src.nats_common import (
    NATS_SERVER, CONNECT_TIMEOUT, SUBJECT_MATCH,
    PREFIX, sub_game, encode_state, decode_state,
)
from src.engine import GameEngine

COUNTDOWN_SECONDS = 120
STATE_HZ = 20
STATUS_HZ = 2


class GameRoom:
    def __init__(self, game_id, difficulty, nc):
        self.game_id = game_id
        self.difficulty = difficulty
        self.nc = nc
        self.engine = GameEngine(difficulty=difficulty, human_players=set())
        self.players = {}
        self.open_slots = set(range(4))
        self.status = "waiting"
        self.input_buffers = {}
        self.frame = 0
        self.created_at = time.time()

    def assign_slot(self):
        if not self.open_slots:
            return None
        slot = min(self.open_slots)
        self.open_slots.remove(slot)
        self.players[slot] = True
        self.engine.human_players.add(slot)
        return slot

    def handle_input(self, slot, data):
        self.input_buffers.setdefault(slot, []).append(data)

    def handle_leave(self, slot):
        if slot in self.players:
            del self.players[slot]
            self.open_slots.add(slot)
            self.engine.human_players.discard(slot)
            print(f"[ROOM {self.game_id}] Player slot {slot} disconnected")

    def countdown_remaining(self):
        return max(0, int(COUNTDOWN_SECONDS - (time.time() - self.created_at)))

    async def publish_status(self):
        data = {
            "game_id": self.game_id,
            "difficulty": self.difficulty,
            "status": self.status,
            "players": len(self.players),
            "open_slots": len(self.open_slots),
            "countdown": self.countdown_remaining() if self.status == "waiting" else 0,
        }
        await self.nc.publish(sub_game(self.game_id, "status"), json.dumps(data).encode())

    async def tick(self, frame):
        self.frame = frame

        if self.status == "waiting":
            if frame % (60 // STATUS_HZ) == 0:
                await self.publish_status()

            if self.countdown_remaining() <= 0:
                self.status = "playing"
                print(f"[ROOM {self.game_id}] Game started — {len(self.players)} human, "
                      f"{4 - len(self.players)} AI")

        elif self.status == "playing":
            buffers = self.input_buffers
            self.input_buffers = {}
            for slot, inputs in buffers.items():
                if slot in self.players and inputs:
                    self.engine.handle_input({slot: inputs[-1]})

            self.engine.update()

            if frame % (60 // STATE_HZ) == 0:
                state = self.engine.get_state()
                await self.nc.publish(sub_game(self.game_id, "state"), encode_state(state).encode())

                if self.engine.game_over:
                    self.status = "finished"
                    print(f"[ROOM {self.game_id}] Game over — "
                          f"{['Red','Blue','Green','Yellow'][self.engine.winner]} wins")


class GameServer:
    def __init__(self):
        self.nc = None
        self.rooms = {}
        self.frame = 0
        self._match_sub = None
        self.pending_matches = []

    async def start(self):
        print("[SERVER] Connecting to NATS...")
        self.nc = await nats.connect(NATS_SERVER, connect_timeout=CONNECT_TIMEOUT)
        print(f"[SERVER] Connected — {self.nc.connected_url}")

        self._match_sub = await self.nc.subscribe(SUBJECT_MATCH, cb=self._on_match)
        await self.nc.subscribe(f"{PREFIX}.game.*.input.>", cb=self._on_input)
        await self.nc.subscribe(f"{PREFIX}.game.*.leave", cb=self._on_leave)
        print("[SERVER] Matchmaking active — waiting for players...")

        while True:
            self.frame += 1

            await self._process_pending_matches()

            finished = []
            for gid, room in list(self.rooms.items()):
                if room.status == "finished":
                    if room.frame > 0 and (self.frame - room.frame) > 60 * 5:
                        finished.append(gid)
                    continue
                try:
                    await room.tick(self.frame)
                except Exception as e:
                    print(f"[ROOM {gid}] Error: {e}")

            for gid in finished:
                del self.rooms[gid]
                print(f"[ROOM {gid}] Removed")

            await asyncio.sleep(1 / 60)

    async def _process_pending_matches(self):
        matches = self.pending_matches
        self.pending_matches = []
        for msg, difficulty in matches:
            try:
                # Try to fill an existing waiting room first
                placed = False
                for room in self.rooms.values():
                    if room.status == "waiting" and room.difficulty == difficulty and room.open_slots:
                        slot = room.assign_slot()
                        print(f"[MATCH] Player → room {room.game_id} (slot {slot}, {len(room.players)}/4)")
                        await msg.respond(json.dumps({
                            "ok": True, "game_id": room.game_id, "slot": slot,
                        }).encode())
                        placed = True
                        break

                if not placed:
                    gid = uuid.uuid4().hex[:8]
                    room = GameRoom(gid, difficulty, self.nc)
                    slot = room.assign_slot()
                    self.rooms[gid] = room
                    print(f"[MATCH] New room {gid} — first player (slot {slot})")
                    await msg.respond(json.dumps({
                        "ok": True, "game_id": gid, "slot": slot,
                    }).encode())
            except Exception as e:
                print(f"[MATCH] Setup error: {e}")
                try:
                    await msg.respond(json.dumps({"ok": False, "error": str(e)}).encode())
                except Exception:
                    pass

    async def _on_match(self, msg):
        try:
            data = json.loads(msg.data.decode())
            difficulty = data.get("difficulty", "medium")
            self.pending_matches.append((msg, difficulty))
        except Exception as e:
            print(f"[MATCH] Error: {e}")
            try:
                await msg.respond(json.dumps({"ok": False, "error": str(e)}).encode())
            except Exception:
                pass

    async def _on_input(self, msg):
        try:
            parts = msg.subject.split(".")
            game_id = parts[2]
            slot = int(parts[4])
            room = self.rooms.get(game_id)
            if room and slot in room.players:
                data = json.loads(msg.data.decode())
                room.handle_input(slot, data)
        except Exception:
            pass

    async def _on_leave(self, msg):
        try:
            parts = msg.subject.split(".")
            game_id = parts[2]
            data = json.loads(msg.data.decode())
            slot = data.get("slot")
            room = self.rooms.get(game_id)
            if room and slot is not None:
                room.handle_leave(slot)
        except Exception:
            pass


def main():
    asyncio.run(GameServer().start())


if __name__ == "__main__":
    main()
