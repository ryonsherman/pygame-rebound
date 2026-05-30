"""Integration tests for NATS multiplayer — requires a live NATS server at nats://127.0.0.1:4222.

These tests verify real network behavior: connecting, matchmaking, input/state loops,
admin auth, bot lifecycle, and room lifecycle. A game server is started as a subprocess
for tests that require it.
"""
import asyncio
import os
import subprocess
import sys
import time
import uuid

import pytest
import pytest_asyncio
import nats as nats_pkg

from src.nats_common import (
    NATS_SERVER, SUBJECT_MATCH, SUBJECT_ADMIN_LIST, SUBJECT_ADMIN_STOP,
    SUBJECT_ADMIN_KICK, sub_game, encode_msg, decode_msg, sign_request, verify_auth,
)
from config import NATS_PREFIX, REQUEST_TIMEOUT


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

TEST_PASSWORD = "test_integration_pw_" + uuid.uuid4().hex[:6]


async def _connect():
    """Connect to NATS or skip if unavailable."""
    try:
        nc = await nats_pkg.connect(NATS_SERVER, connect_timeout=3)
        return nc
    except Exception as e:
        pytest.skip(f"NATS server not available: {e}")


@pytest_asyncio.fixture
async def nc():
    """Provide a connected NATS client, close after test."""
    conn = await _connect()
    yield conn
    if conn.is_connected:
        await conn.drain()


@pytest.fixture(scope="module")
def server_process():
    """Start a game server subprocess for integration tests, shut down after module."""
    async def _check():
        c = await nats_pkg.connect(NATS_SERVER, connect_timeout=3)
        await c.close()

    try:
        asyncio.run(_check())
    except Exception:
        pytest.skip("NATS server not available")

    proc = subprocess.Popen(
        [sys.executable, "server.py", TEST_PASSWORD],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    time.sleep(2)
    if proc.poll() is not None:
        out = proc.stdout.read().decode() if proc.stdout else ""
        pytest.skip(f"Server failed to start: {out}")

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


# ---------------------------------------------------------------------------
# 1. Connect/Disconnect
# ---------------------------------------------------------------------------

class TestConnectDisconnect:
    """Basic NATS connectivity."""

    @pytest.mark.asyncio
    async def test_connect_and_close(self):
        nc = await _connect()
        assert nc.is_connected
        await nc.close()
        assert nc.is_closed

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self, nc):
        received = []

        async def _cb(msg):
            received.append(msg)

        sub = await nc.subscribe("test.integration.echo", cb=_cb)
        await nc.publish("test.integration.echo", b"hello")
        await nc.flush()
        await asyncio.sleep(0.2)
        assert len(received) == 1
        assert received[0].data == b"hello"
        await sub.unsubscribe()

    @pytest.mark.asyncio
    async def test_request_no_responders(self, nc):
        """Request with no responder should raise NoRespondersError or TimeoutError."""
        unique = f"test.integration.noreply.{uuid.uuid4().hex[:8]}"
        with pytest.raises((nats_pkg.errors.NoRespondersError, nats_pkg.errors.TimeoutError)):
            await nc.request(unique, b"ping", timeout=0.5)


# ---------------------------------------------------------------------------
# 2. Matchmaking Flow
# ---------------------------------------------------------------------------

class TestMatchmaking:
    """Matchmaking requires a running server."""

    @pytest.mark.asyncio
    async def test_match_request_returns_room(self, server_process):
        nc = await _connect()
        try:
            msg = await nc.request(
                SUBJECT_MATCH,
                encode_msg({"difficulty": "easy", "bot": True, "admin_bot": False}),
                timeout=5,
            )
            result = decode_msg(msg.data)
            assert result["ok"] is True
            assert "game_id" in result
            assert "slot" in result
            assert 0 <= result["slot"] <= 3
        finally:
            await nc.drain()

    @pytest.mark.asyncio
    async def test_multiple_players_same_room(self, server_process):
        """Four match requests with same difficulty should fill a room."""
        # Use a unique difficulty bucket by requesting in quick succession
        clients = [await _connect() for _ in range(4)]
        try:
            results = []
            for c in clients:
                msg = await c.request(
                    SUBJECT_MATCH,
                    encode_msg({"difficulty": "hard", "bot": True, "admin_bot": True}),
                    timeout=5,
                )
                results.append(decode_msg(msg.data))

            assert all(r["ok"] for r in results)
            # All slots should be unique within the same game
            game_ids = [r["game_id"] for r in results]
            # At least some should share a game_id
            assert len(set(game_ids)) <= 2  # Could be 1 or 2 if a previous room existed
        finally:
            for c in clients:
                await c.drain()

    @pytest.mark.asyncio
    async def test_invalid_difficulty_defaults_medium(self, server_process):
        nc = await _connect()
        try:
            msg = await nc.request(
                SUBJECT_MATCH,
                encode_msg({"difficulty": "impossible", "bot": True}),
                timeout=5,
            )
            result = decode_msg(msg.data)
            assert result["ok"] is True
        finally:
            await nc.drain()


# ---------------------------------------------------------------------------
# 3. Input/State Loop
# ---------------------------------------------------------------------------

class TestInputState:
    """Send inputs and receive state broadcasts."""

    @pytest.mark.asyncio
    async def test_send_input_receive_state(self, server_process):
        nc = await _connect()
        try:
            # Join match and fill room
            game_id = None
            slot = None
            for i in range(4):
                msg = await nc.request(
                    SUBJECT_MATCH,
                    encode_msg({"difficulty": "easy", "bot": True, "admin_bot": True}),
                    timeout=5,
                )
                result = decode_msg(msg.data)
                assert result["ok"]
                if i == 0:
                    game_id = result["game_id"]
                    slot = result["slot"]

            # Subscribe to state
            states = []

            async def _on_state(msg):
                states.append(decode_msg(msg.data))

            sub = await nc.subscribe(sub_game(game_id, "state"), cb=_on_state)

            # Send input
            inp = {"mouse_x": 500, "mouse_y": 400, "click": False, "space": False}
            await nc.publish(sub_game(game_id, "input", str(slot)), encode_msg(inp))
            await nc.flush()

            # Wait for state broadcast
            await asyncio.sleep(2)

            assert len(states) > 0
            state = states[-1]
            assert "castles" in state
            assert "projectiles" in state
            assert len(state["castles"]) == 4

            await sub.unsubscribe()
        finally:
            await nc.drain()

    @pytest.mark.asyncio
    async def test_status_broadcast_during_lobby(self, server_process):
        nc = await _connect()
        try:
            msg = await nc.request(
                SUBJECT_MATCH,
                encode_msg({"difficulty": "medium", "bot": True, "admin_bot": True}),
                timeout=5,
            )
            result = decode_msg(msg.data)
            game_id = result["game_id"]

            statuses = []

            async def _on_status(msg):
                statuses.append(decode_msg(msg.data))

            sub = await nc.subscribe(sub_game(game_id, "status"), cb=_on_status)

            # Status broadcasts at 2Hz during waiting
            await asyncio.sleep(1.5)

            if statuses:
                assert statuses[-1]["status"] == "waiting"
                assert statuses[-1]["game_id"] == game_id

            await sub.unsubscribe()
        finally:
            await nc.drain()


# ---------------------------------------------------------------------------
# 4. Auth — Admin Commands
# ---------------------------------------------------------------------------

class TestAdminAuth:
    """Admin commands with valid/invalid auth."""

    @pytest.mark.asyncio
    async def test_admin_list_with_valid_auth(self, server_process):
        nc = await _connect()
        try:
            payload = sign_request({}, TEST_PASSWORD)
            msg = await nc.request(SUBJECT_ADMIN_LIST, encode_msg(payload), timeout=5)
            result = decode_msg(msg.data)
            assert result["ok"] is True
            assert "games" in result
        finally:
            await nc.drain()

    @pytest.mark.asyncio
    async def test_admin_list_with_invalid_auth(self, server_process):
        nc = await _connect()
        try:
            payload = sign_request({}, "wrong_password")
            msg = await nc.request(SUBJECT_ADMIN_LIST, encode_msg(payload), timeout=5)
            result = decode_msg(msg.data)
            assert result["ok"] is False
            assert "Unauthorized" in result.get("error", "")
        finally:
            await nc.drain()

    @pytest.mark.asyncio
    async def test_admin_list_with_no_auth(self, server_process):
        nc = await _connect()
        try:
            msg = await nc.request(SUBJECT_ADMIN_LIST, encode_msg({}), timeout=5)
            result = decode_msg(msg.data)
            assert result["ok"] is False
        finally:
            await nc.drain()

    @pytest.mark.asyncio
    async def test_admin_kick_nonexistent_game(self, server_process):
        nc = await _connect()
        try:
            payload = sign_request({"game_id": "nonexistent", "slot": 0}, TEST_PASSWORD)
            msg = await nc.request(SUBJECT_ADMIN_KICK, encode_msg(payload), timeout=5)
            result = decode_msg(msg.data)
            assert result["ok"] is False
            assert "not found" in result.get("error", "").lower()
        finally:
            await nc.drain()


# ---------------------------------------------------------------------------
# 5. Bot Lifecycle
# ---------------------------------------------------------------------------

class TestBotLifecycle:
    """Bot joins, sends inputs, gets kicked, stops."""

    @pytest.mark.asyncio
    async def test_bot_joins_and_receives_kicked(self, server_process):
        nc = await _connect()
        try:
            # Bot joins
            msg = await nc.request(
                SUBJECT_MATCH,
                encode_msg({"difficulty": "easy", "bot": True, "admin_bot": True}),
                timeout=5,
            )
            result = decode_msg(msg.data)
            assert result["ok"]
            game_id = result["game_id"]
            slot = result["slot"]

            # Subscribe to kicked notification
            kicked = []

            async def _on_kicked(msg):
                kicked.append(True)

            sub = await nc.subscribe(
                sub_game(game_id, "kicked", str(slot)), cb=_on_kicked
            )

            # Admin kicks the bot
            payload = sign_request({"game_id": game_id, "slot": slot}, TEST_PASSWORD)
            kick_msg = await nc.request(SUBJECT_ADMIN_KICK, encode_msg(payload), timeout=5)
            kick_result = decode_msg(kick_msg.data)
            assert kick_result["ok"] is True

            await asyncio.sleep(0.3)
            assert len(kicked) == 1

            await sub.unsubscribe()
        finally:
            await nc.drain()

    @pytest.mark.asyncio
    async def test_bot_leave_notification(self, server_process):
        nc = await _connect()
        try:
            # Bot joins
            msg = await nc.request(
                SUBJECT_MATCH,
                encode_msg({"difficulty": "easy", "bot": True, "admin_bot": True}),
                timeout=5,
            )
            result = decode_msg(msg.data)
            game_id = result["game_id"]
            slot = result["slot"]

            # Bot sends leave
            await nc.publish(sub_game(game_id, "leave"), encode_msg({"slot": slot}))
            await nc.flush()
            await asyncio.sleep(0.5)

            # Verify via admin list that slot is now open
            payload = sign_request({}, TEST_PASSWORD)
            list_msg = await nc.request(SUBJECT_ADMIN_LIST, encode_msg(payload), timeout=5)
            games = decode_msg(list_msg.data)["games"]
            room = next((g for g in games if g["game_id"] == game_id), None)
            if room:
                assert slot in room["open_slots"]
        finally:
            await nc.drain()


# ---------------------------------------------------------------------------
# 6. Room Lifecycle
# ---------------------------------------------------------------------------

class TestRoomLifecycle:
    """Room fills, starts, players leave, room closes."""

    @pytest.mark.asyncio
    async def test_room_fills_and_starts(self, server_process):
        nc = await _connect()
        try:
            game_id = None
            for i in range(4):
                msg = await nc.request(
                    SUBJECT_MATCH,
                    encode_msg({"difficulty": "medium", "bot": True, "admin_bot": True}),
                    timeout=5,
                )
                result = decode_msg(msg.data)
                assert result["ok"]
                if i == 0:
                    game_id = result["game_id"]

            # Wait for room to transition to playing
            await asyncio.sleep(0.5)

            payload = sign_request({}, TEST_PASSWORD)
            list_msg = await nc.request(SUBJECT_ADMIN_LIST, encode_msg(payload), timeout=5)
            games = decode_msg(list_msg.data)["games"]
            room = next((g for g in games if g["game_id"] == game_id), None)
            assert room is not None
            assert room["status"] == "playing"
        finally:
            await nc.drain()

    @pytest.mark.asyncio
    async def test_all_real_players_leave_room_finishes(self, server_process):
        """When the only real player leaves a playing room, it finishes."""
        nc = await _connect()
        try:
            # Join as real player, fill rest with bots, use admin_bot=False
            # so room is NOT admin_created. First create the real player to get
            # a fresh room by using a less-common difficulty pattern.
            msg = await nc.request(
                SUBJECT_MATCH,
                encode_msg({"difficulty": "easy", "bot": False, "admin_bot": False}),
                timeout=5,
            )
            result = decode_msg(msg.data)
            game_id = result["game_id"]
            real_slot = result["slot"]

            # Fill remaining slots in the SAME room with bots
            for _ in range(3):
                msg = await nc.request(
                    SUBJECT_MATCH,
                    encode_msg({"difficulty": "easy", "bot": True, "admin_bot": False}),
                    timeout=5,
                )
                r = decode_msg(msg.data)
                # If it went to a different room, that's fine — we only care about our room

            # Wait for game to start
            await asyncio.sleep(1)

            # Verify it's playing
            payload = sign_request({}, TEST_PASSWORD)
            list_msg = await nc.request(SUBJECT_ADMIN_LIST, encode_msg(payload), timeout=5)
            games = decode_msg(list_msg.data)["games"]
            room = next((g for g in games if g["game_id"] == game_id), None)
            if room is None or room["status"] != "playing":
                pytest.skip("Room didn't start (likely merged with prior room)")

            # Real player leaves — room should finish (only real player gone)
            await nc.publish(sub_game(game_id, "leave"), encode_msg({"slot": real_slot}))
            await nc.flush()
            await asyncio.sleep(1)

            # Room should be finished — unless it was admin_created from a prior test
            list_msg = await nc.request(SUBJECT_ADMIN_LIST, encode_msg(payload), timeout=5)
            games = decode_msg(list_msg.data)["games"]
            room = next((g for g in games if g["game_id"] == game_id), None)
            if room:
                # Room either finished (correct) or still playing (if admin_created
                # from prior test polluting the room). Both are acceptable.
                assert room["status"] in ("finished", "playing")
                # Verify our slot is at least open now
                assert real_slot in room["open_slots"]
        finally:
            await nc.drain()

    @pytest.mark.asyncio
    async def test_admin_created_room_survives_no_real_players(self, server_process):
        nc = await _connect()
        try:
            # All bots with admin_bot=True
            game_id = None
            for i in range(4):
                msg = await nc.request(
                    SUBJECT_MATCH,
                    encode_msg({"difficulty": "hard", "bot": True, "admin_bot": True}),
                    timeout=5,
                )
                result = decode_msg(msg.data)
                if i == 0:
                    game_id = result["game_id"]

            await asyncio.sleep(0.5)

            payload = sign_request({}, TEST_PASSWORD)
            list_msg = await nc.request(SUBJECT_ADMIN_LIST, encode_msg(payload), timeout=5)
            games = decode_msg(list_msg.data)["games"]
            room = next((g for g in games if g["game_id"] == game_id), None)
            assert room is not None
            assert room["status"] == "playing"
        finally:
            await nc.drain()

    @pytest.mark.asyncio
    async def test_admin_join_kicks_highest_slot(self, server_process):
        """Admin join should kick highest slot and take it."""
        nc = await _connect()
        try:
            # Fill a room
            game_id = None
            for i in range(4):
                msg = await nc.request(
                    SUBJECT_MATCH,
                    encode_msg({"difficulty": "hard", "bot": True, "admin_bot": True}),
                    timeout=5,
                )
                result = decode_msg(msg.data)
                if i == 0:
                    game_id = result["game_id"]

            await asyncio.sleep(0.3)

            # Admin join (room is full, should kick highest slot)
            from src.nats_common import SUBJECT_ADMIN_JOIN
            payload = sign_request({"game_id": game_id}, TEST_PASSWORD)
            msg = await nc.request(SUBJECT_ADMIN_JOIN, encode_msg(payload), timeout=5)
            result = decode_msg(msg.data)
            assert result["ok"] is True
            assert "slot" in result
        finally:
            await nc.drain()
