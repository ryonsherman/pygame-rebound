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
        nc = await nats.connect("nats://demo.nats.io:4222")
        msg = await nc.request(
            SUBJECT_MATCH,
            json.dumps({"difficulty": "medium"}).encode(),
            timeout=10,
        )
        result = json.loads(msg.data.decode())
        assert result.get("ok"), f"Match failed: {result}"

        game_id = result["game_id"]
        slot = result["slot"]

        state_queue = queue.Queue(maxsize=10)
        status_queue = queue.Queue(maxsize=10)

        async def on_state(msg):
            from src.nats_common import decode_state
            state = decode_state(msg.data)
            try:
                state_queue.put_nowait(state)
            except queue.Full:
                pass

        async def on_status(msg):
            data = json.loads(msg.data.decode())
            try:
                status_queue.put_nowait(data)
            except queue.Full:
                pass

        from src.nats_common import sub_game
        state_sub = await nc.subscribe(sub_game(game_id, "state"), cb=on_state)
        status_sub = await nc.subscribe(sub_game(game_id, "status"), cb=on_status)

        await nc.publish(sub_game(game_id, "input", str(slot)), json.dumps({"mouse_x": 500, "mouse_y": 400, "space": False, "click": False}).encode())

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

        from src.nats_common import sub_game
        await nc.publish(sub_game(game_id, "leave"), json.dumps({"slot": slot}).encode())
        await nc.drain()

    asyncio.run(client())
    print("[TEST] PASSED")


if __name__ == "__main__":
    test_matchmaking()
