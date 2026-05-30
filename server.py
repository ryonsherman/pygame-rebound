import asyncio
import json
import sys
import uuid
import time
import nats
from src.nats_common import (
    NATS_SERVER, SUBJECT_MATCH, SUBJECT_ADMIN_LIST, SUBJECT_ADMIN_STOP,
    SUBJECT_ADMIN_KICK, SUBJECT_ADMIN_JOIN, SUBJECT_ADMIN_KILL, sub_game, encode_msg, decode_msg, encode_state,
    verify_auth, sign_request,
)
from config import NATS_NAME, NATS_PREFIX, LOBBY_COUNTDOWN, STATE_HZ, STATUS_HZ, CONNECT_TIMEOUT
from src.engine import GameEngine

COUNTDOWN_SECONDS = LOBBY_COUNTDOWN


class GameRoom:
    def __init__(self, game_id, difficulty, nc):
        self.game_id = game_id
        self.difficulty = difficulty
        self.nc = nc
        self.engine = GameEngine(difficulty=difficulty, human_players=set())
        self.players = {}
        self.real_players = set()  # slots occupied by actual humans (not bots)
        self.admin_created = False  # set True when room created via admin bots command
        self.open_slots = set(range(4))
        self.status = "waiting"
        self.input_buffers = {}
        self.frame = 0
        self.created_at = time.time()

    def assign_slot(self, bot=False):
        if not self.open_slots:
            return None
        slot = min(self.open_slots)
        self.open_slots.remove(slot)
        self.players[slot] = True
        self.engine.human_players.add(slot)
        if not bot:
            self.real_players.add(slot)
        if self.status == "playing":
            self.engine.remove_ai(slot)
        return slot

    def handle_input(self, slot, data):
        self.input_buffers.setdefault(slot, []).append(data)

    def handle_leave(self, slot):
        if slot in self.players:
            del self.players[slot]
            self.open_slots.add(slot)
            self.real_players.discard(slot)
            self.engine.human_players.discard(slot)
            if self.status == "playing":
                self.engine.add_ai(slot)
                print(f"[ROOM {self.game_id}] Player slot {slot} left — AI takeover")
                if not self.real_players and not self.admin_created:
                    self.status = "finished"
                    print(f"[ROOM {self.game_id}] No real players — closing")
            else:
                print(f"[ROOM {self.game_id}] Player slot {slot} left")
                if not self.players:
                    self.status = "finished"
                    print(f"[ROOM {self.game_id}] Empty room — closing")

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
        await self.nc.publish(sub_game(self.game_id, "status"), encode_msg(data))

    async def tick(self, frame):
        self.frame = frame

        if self.status == "waiting":
            if frame % (60 // STATUS_HZ) == 0:
                await self.publish_status()

            if not self.open_slots or self.countdown_remaining() <= 0:
                if not self.real_players and not self.admin_created:
                    self.status = "finished"
                    print(f"[ROOM {self.game_id}] No real players — closing")
                    return
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
                for c in state["castles"]:
                    c["human"] = c["owner"] in self.real_players
                await self.nc.publish(sub_game(self.game_id, "state"), encode_state(state))

                if self.engine.game_over:
                    self.status = "finished"
                    print(f"[ROOM {self.game_id}] Game over — "
                          f"{['Red','Blue','Green','Yellow'][self.engine.winner]} wins")


class GameServer:
    def __init__(self, password=None):
        self.nc = None
        self.rooms = {}
        self.frame = 0
        self._match_sub = None
        self.pending_matches = []
        self.password = password

    async def start(self):
        print("[SERVER] Connecting to NATS...")
        self.nc = await nats.connect(NATS_SERVER, connect_timeout=CONNECT_TIMEOUT, name=NATS_NAME)
        print(f"[SERVER] Connected — {self.nc.connected_url.geturl()}")

        self._match_sub = await self.nc.subscribe(SUBJECT_MATCH, cb=self._on_match)
        await self.nc.subscribe(SUBJECT_ADMIN_LIST, cb=self._on_admin_list)
        await self.nc.subscribe(SUBJECT_ADMIN_STOP, cb=self._on_admin_stop)
        await self.nc.subscribe(SUBJECT_ADMIN_KICK, cb=self._on_admin_kick)
        await self.nc.subscribe(SUBJECT_ADMIN_JOIN, cb=self._on_admin_join)
        await self.nc.subscribe(SUBJECT_ADMIN_KILL, cb=self._on_admin_kill)
        await self.nc.subscribe(f"{NATS_PREFIX}.game.*.input.>", cb=self._on_input)
        await self.nc.subscribe(f"{NATS_PREFIX}.game.*.leave", cb=self._on_leave)
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
        for msg, difficulty, is_bot, admin_bot in matches:
            try:
                # Try to fill an existing waiting room first
                placed = False
                for room in self.rooms.values():
                    if room.status == "waiting" and room.difficulty == difficulty and room.open_slots:
                        slot = room.assign_slot(bot=is_bot)
                        if admin_bot:
                            room.admin_created = True
                        print(f"[MATCH] Player → room {room.game_id} (slot {slot}, {len(room.players)}/4)")
                        await msg.respond(encode_msg({
                            "ok": True, "game_id": room.game_id, "slot": slot,
                        }))
                        placed = True
                        break

                if not placed:
                    gid = uuid.uuid4().hex[:8]
                    room = GameRoom(gid, difficulty, self.nc)
                    if admin_bot:
                        room.admin_created = True
                    slot = room.assign_slot(bot=is_bot)
                    self.rooms[gid] = room
                    print(f"[MATCH] New room {gid} — first player (slot {slot})")
                    await msg.respond(encode_msg({
                        "ok": True, "game_id": gid, "slot": slot,
                    }))
            except Exception as e:
                print(f"[MATCH] Setup error: {e}")
                try:
                    await msg.respond(encode_msg({"ok": False, "error": str(e)}))
                except Exception:
                    pass

    async def _on_match(self, msg):
        try:
            data = decode_msg(msg.data)
            difficulty = data.get("difficulty", "medium")
            # Validate difficulty to prevent mismatched rooms
            if difficulty not in ("easy", "medium", "hard"):
                difficulty = "medium"
            is_bot = data.get("bot", False)
            admin_bot = data.get("admin_bot", False)
            self.pending_matches.append((msg, difficulty, is_bot, admin_bot))
        except Exception as e:
            print(f"[MATCH] Error: {e}")
            try:
                await msg.respond(encode_msg({"ok": False, "error": str(e)}))
            except Exception:
                pass

    async def _on_input(self, msg):
        try:
            parts = msg.subject.split(".")
            if len(parts) < 5:
                return
            game_id = parts[2]
            slot = int(parts[4])
            if not (0 <= slot <= 3):
                return
            room = self.rooms.get(game_id)
            if room and slot in room.players:
                data = decode_msg(msg.data)
                room.handle_input(slot, data)
        except (ValueError, IndexError):
            pass
        except Exception:
            pass

    async def _on_leave(self, msg):
        try:
            parts = msg.subject.split(".")
            game_id = parts[2]
            data = decode_msg(msg.data)
            slot = data.get("slot")
            room = self.rooms.get(game_id)
            if room and slot is not None:
                room.handle_leave(slot)
        except Exception:
            pass

    def _check_auth(self, msg):
        """Validate admin auth. Returns decoded data if authorized, None otherwise."""
        if not self.password:
            return None  # No password = admin commands disabled
        try:
            data = decode_msg(msg.data)
        except Exception:
            return None
        if verify_auth(data, self.password):
            return data
        return None

    async def _on_admin_list(self, msg):
        if self._check_auth(msg) is None:
            await msg.respond(encode_msg({"ok": False, "error": "Unauthorized"}))
            return
        games = []
        for gid, room in self.rooms.items():
            games.append({
                "game_id": gid,
                "status": room.status,
                "difficulty": room.difficulty,
                "players": len(room.players),
                "slots": sorted(room.players.keys()),
                "open_slots": sorted(room.open_slots),
                "frame": room.frame,
                "admin_created": room.admin_created,
            })
        await msg.respond(encode_msg({"ok": True, "games": games}))

    async def _on_admin_stop(self, msg):
        if self._check_auth(msg) is None:
            await msg.respond(encode_msg({"ok": False, "error": "Unauthorized"}))
            return
        await msg.respond(encode_msg({"ok": True, "message": "Server shutting down"}))
        print("[SERVER] Admin requested shutdown")
        await self.nc.drain()
        asyncio.get_event_loop().stop()

    async def _on_admin_kick(self, msg):
        data = self._check_auth(msg)
        if data is None:
            await msg.respond(encode_msg({"ok": False, "error": "Unauthorized"}))
            return
        try:
            game_id = data.get("game_id")
            slot = data.get("slot")
            room = self.rooms.get(game_id)
            if not room:
                await msg.respond(encode_msg({"ok": False, "error": "Game not found"}))
                return
            if slot not in room.players:
                await msg.respond(encode_msg({"ok": False, "error": "Slot not occupied"}))
                return
            room.handle_leave(slot)
            # Notify the kicked player
            await self.nc.publish(sub_game(game_id, "kicked", str(slot)), b"")
            await msg.respond(encode_msg({"ok": True, "game_id": game_id, "slot": slot}))
            print(f"[ROOM {game_id}] Admin kicked slot {slot}")
        except Exception as e:
            await msg.respond(encode_msg({"ok": False, "error": str(e)}))

    async def _on_admin_join(self, msg):
        data = self._check_auth(msg)
        if data is None:
            await msg.respond(encode_msg({"ok": False, "error": "Unauthorized"}))
            return
        try:
            game_id = data.get("game_id")
            room = self.rooms.get(game_id)
            if not room:
                await msg.respond(encode_msg({"ok": False, "error": "Game not found"}))
                return
            if not room.open_slots:
                # Kick the highest-numbered player slot to make room
                kick_slot = max(room.players.keys())
                room.handle_leave(kick_slot)
                await self.nc.publish(sub_game(game_id, "kicked", str(kick_slot)), b"")
                print(f"[ROOM {game_id}] Replaced slot {kick_slot} for admin join")
            slot = room.assign_slot()
            await msg.respond(encode_msg({"ok": True, "game_id": game_id, "slot": slot}))
            print(f"[ROOM {game_id}] Admin joined as slot {slot}")
        except Exception as e:
            await msg.respond(encode_msg({"ok": False, "error": str(e)}))

    async def _on_admin_kill(self, msg):
        data = self._check_auth(msg)
        if data is None:
            await msg.respond(encode_msg({"ok": False, "error": "Unauthorized"}))
            return
        try:
            game_id = data.get("game_id")
            room = self.rooms.get(game_id)
            if not room:
                await msg.respond(encode_msg({"ok": False, "error": "Game not found"}))
                return
            # Notify all players they're kicked (bots will clean up)
            for slot in list(room.players.keys()):
                room.handle_leave(slot)
                await self.nc.publish(sub_game(game_id, "kicked", str(slot)), b"")
            # Remove the room
            del self.rooms[game_id]
            await msg.respond(encode_msg({"ok": True, "game_id": game_id}))
            print(f"[ROOM {game_id}] Killed by admin")
        except Exception as e:
            await msg.respond(encode_msg({"ok": False, "error": str(e)}))


async def _run():
    password = sys.argv[1] if len(sys.argv) > 1 else None
    server = GameServer(password=password)
    if password:
        print("[SERVER] Admin auth enabled (HMAC-SHA256)")
    else:
        print("[SERVER] WARNING: No admin password — admin commands are disabled")
    try:
        await server.start()
    except asyncio.CancelledError:
        pass
    finally:
        if server.nc and server.nc.is_connected:
            await server.nc.drain()
        print("\n[SERVER] Shut down.")


def main():
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
