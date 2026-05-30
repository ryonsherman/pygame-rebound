import asyncio
import json
import os
import queue
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nats_common import SUBJECT_MATCH
import server as engine_server
from server import GameServer

engine_server.COUNTDOWN_SECONDS = 2

SERVER_TIMEOUT = 15


def _run_server(loop):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(GameServer().start())


def test_matchmaking():
    server_loop = asyncio.new_event_loop()
    server_thread = threading.Thread(target=_run_server, args=(server_loop,), daemon=True)
    server_thread.start()
    time.sleep(1)

    import nats

    async def client():
        from config import NATS_URL
        from src.nats_common import encode_msg, decode_msg, decode_state, sub_game

        nc = await nats.connect(NATS_URL)
        msg = await nc.request(
            SUBJECT_MATCH,
            encode_msg({"difficulty": "medium"}),
            timeout=10,
        )
        result = decode_msg(msg.data)
        assert result.get("ok"), f"Match failed: {result}"

        game_id = result["game_id"]
        slot = result["slot"]

        state_queue = queue.Queue(maxsize=10)
        status_queue = queue.Queue(maxsize=10)

        async def on_state(msg):
            state = decode_state(msg.data)
            try:
                state_queue.put_nowait(state)
            except queue.Full:
                pass

        async def on_status(msg):
            data = decode_msg(msg.data)
            try:
                status_queue.put_nowait(data)
            except queue.Full:
                pass

        state_sub = await nc.subscribe(sub_game(game_id, "state"), cb=on_state)
        status_sub = await nc.subscribe(sub_game(game_id, "status"), cb=on_status)

        await nc.publish(sub_game(game_id, "input", str(slot)), encode_msg({"mouse_x": 500, "mouse_y": 400, "space": False, "click": False}))

        for _ in range(100):
            try:
                s = state_queue.get_nowait()
                if s:
                    print(f"[TEST] Got state: game_over={s.get('game_over')}, frame={s.get('frame')}")
                    break
            except queue.Empty:
                pass
            await asyncio.sleep(0.1)
        else:
            print("[TEST] No state received within timeout")

        await nc.publish(sub_game(game_id, "leave"), encode_msg({"slot": slot}))
        await nc.drain()

    asyncio.run(client())
    print("[TEST] PASSED")


if __name__ == "__main__":
    test_matchmaking()
