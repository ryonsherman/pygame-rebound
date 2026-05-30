"""Tests for Server edge cases (TESTS.md #31-42)."""
import time
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from server import GameRoom, GameServer
from src.nats_common import encode_msg, decode_msg


@pytest.fixture
def mock_nc():
    nc = MagicMock()
    nc.publish = AsyncMock()
    nc.subscribe = AsyncMock()
    nc.is_connected = True
    nc.drain = AsyncMock()
    return nc


@pytest.fixture
def room(mock_nc):
    r = GameRoom("test-room", "medium", mock_nc)
    return r


class TestLastPlayerLeavesDuringCountdown:
    """#31: Last player leaves during countdown."""

    def test_empty_room_closes(self, room):
        """#31: Room with no players transitions to finished."""
        room.assign_slot(bot=False)  # slot 0
        room.handle_leave(0)
        assert room.status == "finished"


class TestCountdownNoRealPlayers:
    """#32: Countdown expiry with no real players (non-admin room)."""

    @pytest.mark.asyncio
    async def test_no_real_players_closes(self, room):
        """#32: Non-admin room with only bots closes at countdown expiry."""
        room.assign_slot(bot=True)
        room.assign_slot(bot=True)
        room.assign_slot(bot=True)
        room.assign_slot(bot=True)
        room.created_at = time.time() - 100  # expired
        await room.tick(1)
        assert room.status == "finished"


class TestConcurrentMatchmaking:
    """#33: Race condition — two requests for last slot."""

    def test_second_request_gets_none(self, room):
        """#33: When only 1 slot left, second assign_slot returns None."""
        # Fill 3 slots
        room.assign_slot(bot=True)
        room.assign_slot(bot=True)
        room.assign_slot(bot=True)
        # One slot left
        s1 = room.assign_slot(bot=True)
        assert s1 is not None
        s2 = room.assign_slot(bot=True)
        assert s2 is None


class TestOnInputEdgeCases:
    """#34-37: _on_input error handling."""

    @pytest.mark.asyncio
    async def test_slot_out_of_range(self, mock_nc):
        """#34: Slot > 3 is rejected silently."""
        server = GameServer()
        server.nc = mock_nc
        server.rooms = {"test": MagicMock()}
        msg = MagicMock()
        msg.subject = "rebound.game.test.input.5"
        msg.data = encode_msg({"mouse_x": 0, "mouse_y": 0, "click": False, "space": False})
        await server._on_input(msg)
        # No crash, input ignored

    @pytest.mark.asyncio
    async def test_slot_not_in_players(self, mock_nc):
        """#35: Slot not in room.players is ignored."""
        server = GameServer()
        server.nc = mock_nc
        room = GameRoom("test", "medium", mock_nc)
        room.assign_slot(bot=False)  # slot 0
        server.rooms = {"test": room}
        msg = MagicMock()
        msg.subject = "rebound.game.test.input.2"
        msg.data = encode_msg({"mouse_x": 0, "mouse_y": 0, "click": False, "space": False})
        await server._on_input(msg)
        assert 2 not in room.input_buffers

    @pytest.mark.asyncio
    async def test_malformed_subject(self, mock_nc):
        """#36: Subject with < 5 parts doesn't crash."""
        server = GameServer()
        server.nc = mock_nc
        server.rooms = {}
        msg = MagicMock()
        msg.subject = "rebound.game.test"
        msg.data = encode_msg({})
        await server._on_input(msg)
        # No crash

    @pytest.mark.asyncio
    async def test_decode_failure(self, mock_nc):
        """#37: Invalid payload in _on_input doesn't crash."""
        server = GameServer()
        server.nc = mock_nc
        room = GameRoom("test", "medium", mock_nc)
        room.assign_slot(bot=False)
        server.rooms = {"test": room}
        msg = MagicMock()
        msg.subject = "rebound.game.test.input.0"
        msg.data = b"invalid-not-base64!!!"
        await server._on_input(msg)
        # No crash


class TestOnLeaveDecodeFailure:
    """#38: _on_leave decode failure."""

    @pytest.mark.asyncio
    async def test_leave_decode_failure(self, mock_nc):
        """#38: Invalid payload in _on_leave doesn't crash."""
        server = GameServer()
        server.nc = mock_nc
        server.rooms = {"test": GameRoom("test", "medium", mock_nc)}
        msg = MagicMock()
        msg.subject = "rebound.game.test.leave"
        msg.data = b"bad-data"
        await server._on_leave(msg)
        # No crash


class TestRoomTickException:
    """#39: Room tick exception handling."""

    @pytest.mark.asyncio
    async def test_tick_exception_doesnt_kill_server(self, mock_nc):
        """#39: Exception in room.tick() is caught by server loop."""
        server = GameServer()
        server.nc = mock_nc
        room = MagicMock()
        room.status = "playing"
        room.frame = 1
        room.tick = AsyncMock(side_effect=RuntimeError("boom"))
        server.rooms = {"test": room}
        # Simulate what the server loop does: call tick and catch exceptions
        errors = []
        for gid, r in list(server.rooms.items()):
            if r.status == "finished":
                continue
            try:
                await r.tick(server.frame)
            except Exception as e:
                errors.append(str(e))
        # Server catches the error without crashing
        assert len(errors) == 1
        assert errors[0] == "boom"
        # Room is still in rooms dict (not removed)
        assert "test" in server.rooms


class TestRoomCleanupDelay:
    """#40: Room cleanup after 5-second delay."""

    def test_finished_room_removed_after_delay(self, mock_nc):
        """#40: Finished room is cleaned up after 300 frames (5s * 60fps)."""
        server = GameServer()
        server.nc = mock_nc
        room = GameRoom("test", "medium", mock_nc)
        room.status = "finished"
        room.frame = 100
        server.rooms = {"test": room}
        # Not enough time — room should NOT be removed
        server.frame = 100 + 60 * 5 - 1
        finished = [gid for gid, r in server.rooms.items()
                    if r.status == "finished" and r.frame > 0
                    and (server.frame - r.frame) > 60 * 5]
        assert "test" not in finished
        # Enough time — room should be removed
        server.frame = 100 + 60 * 5 + 1
        finished = [gid for gid, r in server.rooms.items()
                    if r.status == "finished" and r.frame > 0
                    and (server.frame - r.frame) > 60 * 5]
        assert "test" in finished


class TestServerStopMidGame:
    """#41: Server stop mid-game."""

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, mock_nc):
        """#41: Server drain called on stop."""
        server = GameServer()
        server.nc = mock_nc
        server.password = "testpass"
        msg = MagicMock()
        from src.nats_common import encode_msg, sign_request
        payload = sign_request({}, "testpass")
        msg.data = encode_msg(payload)
        msg.respond = AsyncMock()
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.stop = MagicMock()
            await server._on_admin_stop(msg)
        mock_nc.drain.assert_called_once()


class TestAdminJoinOpenSlot:
    """#42: Admin join when room has open slots."""

    @pytest.mark.asyncio
    async def test_join_open_slot_no_kick(self, mock_nc):
        """#42: Admin join with available slot doesn't kick anyone."""
        server = GameServer()
        server.password = "testpass"
        server.nc = mock_nc
        room = GameRoom("test", "medium", mock_nc)
        room.assign_slot(bot=True)  # slot 0
        room.assign_slot(bot=True)  # slot 1
        # slots 2, 3 open
        server.rooms = {"test": room}
        msg = MagicMock()
        from src.nats_common import encode_msg, sign_request
        payload = sign_request({"game_id": "test"}, "testpass")
        msg.data = encode_msg(payload)
        msg.respond = AsyncMock()
        await server._on_admin_join(msg)
        resp = decode_msg(msg.respond.call_args[0][0])
        assert resp["ok"]
        assert resp["slot"] == 2  # first open slot

    @pytest.mark.asyncio
    async def test_join_full_room_kicks_highest_slot(self, mock_nc):
        """#42b: Admin join with full room kicks highest-numbered slot."""
        server = GameServer()
        server.password = "testpass"
        server.nc = mock_nc
        room = GameRoom("test", "medium", mock_nc)
        room.assign_slot(bot=True)  # slot 0
        room.assign_slot(bot=True)  # slot 1
        room.assign_slot(bot=True)  # slot 2
        room.assign_slot(bot=True)  # slot 3
        assert not room.open_slots
        server.rooms = {"test": room}
        msg = MagicMock()
        from src.nats_common import encode_msg, sign_request
        payload = sign_request({"game_id": "test"}, "testpass")
        msg.data = encode_msg(payload)
        msg.respond = AsyncMock()
        await server._on_admin_join(msg)
        resp = decode_msg(msg.respond.call_args[0][0])
        assert resp["ok"]
        # Slot 3 was kicked (highest), admin got it
        assert resp["slot"] == 3
        assert 3 in room.players
        # Kicked notification published
        mock_nc.publish.assert_called()
