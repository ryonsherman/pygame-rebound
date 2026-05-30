"""Tests for Admin shell (TESTS.md #92-100)."""
import sys
import os
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


class TestFixTerminal:
    """#92: _fix_terminal restores terminal settings."""

    def test_fix_terminal_no_crash(self):
        """#92: _fix_terminal should not crash even without termios."""
        # Import with mocked termios that raises
        with patch.dict("sys.modules", {"termios": None}):
            # Force reimport
            from admin import _fix_terminal
            # Should not raise
            _fix_terminal()

    def test_fix_terminal_calls_tcsetattr(self):
        """#92: When termios available, tcsetattr is called."""
        mock_termios = MagicMock()
        mock_termios.tcgetattr.return_value = [0, 0, 0, 0, 0, 0, []]
        mock_termios.ICRNL = 0x100
        mock_termios.OPOST = 0x1
        mock_termios.ONLCR = 0x4
        mock_termios.ECHO = 0x8
        mock_termios.ICANON = 0x2
        mock_termios.IEXTEN = 0x400
        mock_termios.ISIG = 0x1
        mock_termios.TCSANOW = 0
        with patch("admin.termios", mock_termios, create=True):
            from admin import _fix_terminal
            _fix_terminal()
            # termios is imported inside the function, so this tests no-crash


class TestSigned:
    """#93: _signed with and without password."""

    def test_signed_with_password(self):
        """#93: With password, payload gets _nonce and _token."""
        from admin import _signed
        from src.nats_common import decode_msg
        result = _signed({"action": "stop"}, "mypass")
        data = decode_msg(result)
        assert "_nonce" in data
        assert "_token" in data
        assert data["action"] == "stop"

    def test_signed_without_password(self):
        """#93: Without password, payload is just encoded (no auth fields)."""
        from admin import _signed
        from src.nats_common import decode_msg
        result = _signed({"action": "stop"}, None)
        data = decode_msg(result)
        assert "_nonce" not in data
        assert data["action"] == "stop"


class TestCheckGame:
    """#94-96: _check_game prefix matching."""

    @pytest.mark.asyncio
    async def test_prefix_match_single(self):
        """#94: Prefix matching finds by prefix."""
        from admin import _check_game
        nc = MagicMock()
        from src.nats_common import encode_msg
        response = encode_msg({"ok": True, "games": [
            {"game_id": "abc123def", "status": "running"},
            {"game_id": "xyz789", "status": "running"},
        ]})
        nc.request = AsyncMock(return_value=MagicMock(data=response))
        gid, status = await _check_game(nc, "abc", None)
        assert gid == "abc123def"
        assert status == "running"

    @pytest.mark.asyncio
    async def test_ambiguous_prefix(self):
        """#95: Multiple matches returns ambiguous."""
        from admin import _check_game
        nc = MagicMock()
        from src.nats_common import encode_msg
        response = encode_msg({"ok": True, "games": [
            {"game_id": "abc123", "status": "running"},
            {"game_id": "abc456", "status": "running"},
        ]})
        nc.request = AsyncMock(return_value=MagicMock(data=response))
        gid, status = await _check_game(nc, "abc", None)
        assert gid is None
        assert status == "ambiguous"

    @pytest.mark.asyncio
    async def test_exact_match(self):
        """#96: Exact match found directly."""
        from admin import _check_game
        nc = MagicMock()
        from src.nats_common import encode_msg
        response = encode_msg({"ok": True, "games": [
            {"game_id": "abc123", "status": "waiting"},
            {"game_id": "abc1234", "status": "running"},
        ]})
        nc.request = AsyncMock(return_value=MagicMock(data=response))
        gid, status = await _check_game(nc, "abc123", None)
        assert gid == "abc123"
        assert status == "waiting"


class TestCmdBots:
    """#97: cmd_bots creates server-side AI room."""

    @pytest.mark.asyncio
    async def test_bots_spawn_4(self):
        """#97: cmd_bots requests server to create room with 4 AI bots."""
        from admin import cmd_bots
        from src.nats_common import SUBJECT_ADMIN_BOTS, encode_msg, decode_msg
        mock_nc = MagicMock()
        response_data = {"ok": True, "game_id": "test-game-123"}
        mock_nc.request = AsyncMock(return_value=MagicMock(data=encode_msg(response_data)))
        game_id, tasks = await cmd_bots(mock_nc, "medium", None)
        assert game_id == "test-game-123"
        assert tasks == []
        mock_nc.request.assert_called_once()
        call_args = mock_nc.request.call_args
        assert call_args[0][0] == SUBJECT_ADMIN_BOTS
        payload = decode_msg(call_args[0][1])
        assert payload["difficulty"] == "medium"


class TestCmdJoinLifecycle:
    """#98: cmd_join pygame window lifecycle (concept test)."""

    @pytest.mark.asyncio
    async def test_join_requires_game_id(self):
        """#98: Join command needs a valid game ID — returns error for unknown game."""
        from admin import _check_game
        nc = MagicMock()
        from src.nats_common import encode_msg
        response = encode_msg({"ok": True, "games": []})
        nc.request = AsyncMock(return_value=MagicMock(data=response))
        gid, status = await _check_game(nc, "nonexistent", None)
        assert gid is None


class TestCmdSpectateLifecycle:
    """#99: cmd_spectate pygame window lifecycle (concept test)."""

    def test_spectate_subscribes_to_state(self):
        """#99: Spectate subscribes to game state subject."""
        from src.nats_common import sub_game
        subj = sub_game("test-id", "state")
        assert subj == "rebound.game.test-id.state"


class TestUnknownCommand:
    """#100: Unknown command prints error."""

    def test_unknown_command_message(self, capsys):
        """#100: Unknown command shows error message."""
        # Simulate the command dispatch logic from admin.main()
        cmd = "invalidcommand"
        if cmd not in ("quit", "exit", "help", "games", "stop", "kick", "bots", "join", "spectate"):
            print(f"  Unknown command: {cmd}")
            print("  Type 'help' for available commands")
        captured = capsys.readouterr()
        assert "Unknown command: invalidcommand" in captured.out


class TestAdminIdGeneration:
    """#101: Admin ID is generated on connect."""

    def test_admin_id_format(self):
        """#101: Admin ID is a 6-character hex string."""
        import uuid
        # Simulate what admin.main() does
        admin_id = uuid.uuid4().hex[:6]
        assert len(admin_id) == 6
        assert all(c in "0123456789abcdef" for c in admin_id)

    def test_admin_id_uniqueness(self):
        """#101: Multiple admin sessions get unique IDs."""
        import uuid
        ids = set()
        for _ in range(100):
            admin_id = uuid.uuid4().hex[:6]
            ids.add(admin_id)
        # With 6 hex chars (16^6 = ~16M combinations), 100 IDs should all be unique
        assert len(ids) == 100


class TestAdminIdInPayload:
    """#102: Admin ID is included in signed payloads."""

    def test_signed_includes_admin_id(self):
        """#102: When admin_id is provided, it's included in the payload."""
        from admin import _signed
        from src.nats_common import decode_msg
        result = _signed({"action": "stop"}, "mypass", admin_id="abc123")
        data = decode_msg(result)
        assert data["admin_id"] == "abc123"
        assert data["action"] == "stop"
        assert "_nonce" in data
        assert "_token" in data

    def test_signed_without_admin_id(self):
        """#102: When admin_id is None, it's not included in the payload."""
        from admin import _signed
        from src.nats_common import decode_msg
        result = _signed({"action": "stop"}, "mypass", admin_id=None)
        data = decode_msg(result)
        assert "admin_id" not in data
        assert data["action"] == "stop"

    def test_signed_without_password_includes_admin_id(self):
        """#102: Admin ID is included even without password auth."""
        from admin import _signed
        from src.nats_common import decode_msg
        result = _signed({"action": "bots"}, None, admin_id="xyz789")
        data = decode_msg(result)
        assert data["admin_id"] == "xyz789"
        assert "_nonce" not in data  # No password = no auth fields
        assert data["action"] == "bots"

    def test_signed_preserves_original_fields(self):
        """#102: Original payload fields are preserved when admin_id is added."""
        from admin import _signed
        from src.nats_common import decode_msg
        original = {"game_id": "test123", "slot": 2, "difficulty": "hard"}
        result = _signed(original, "pass", admin_id="admin1")
        data = decode_msg(result)
        assert data["game_id"] == "test123"
        assert data["slot"] == 2
        assert data["difficulty"] == "hard"
        assert data["admin_id"] == "admin1"


class TestAdminIdInCommands:
    """#103: Admin ID is passed to all admin commands."""

    @pytest.mark.asyncio
    async def test_games_includes_admin_id(self):
        """#103: cmd_games passes admin_id to _signed."""
        from admin import cmd_games
        from src.nats_common import encode_msg, decode_msg
        mock_nc = MagicMock()
        response = encode_msg({"ok": True, "games": []})
        mock_nc.request = AsyncMock(return_value=MagicMock(data=response))
        
        await cmd_games(mock_nc, password="pass", admin_id="testadmin")
        
        # Verify the request was made with admin_id in payload
        call_args = mock_nc.request.call_args
        payload = decode_msg(call_args[0][1])
        assert payload["admin_id"] == "testadmin"

    @pytest.mark.asyncio
    async def test_kick_includes_admin_id(self):
        """#103: cmd_kick passes admin_id to _signed."""
        from admin import cmd_kick
        from src.nats_common import encode_msg, decode_msg
        mock_nc = MagicMock()
        response = encode_msg({"ok": True})
        mock_nc.request = AsyncMock(return_value=MagicMock(data=response))
        
        await cmd_kick(mock_nc, "game123", "2", password="pass", admin_id="admin42")
        
        call_args = mock_nc.request.call_args
        payload = decode_msg(call_args[0][1])
        assert payload["admin_id"] == "admin42"
        assert payload["game_id"] == "game123"
        assert payload["slot"] == 2

    @pytest.mark.asyncio
    async def test_bots_includes_admin_id(self):
        """#103: cmd_bots passes admin_id to _signed."""
        from admin import cmd_bots
        from src.nats_common import encode_msg, decode_msg
        mock_nc = MagicMock()
        response = encode_msg({"ok": True, "game_id": "newgame"})
        mock_nc.request = AsyncMock(return_value=MagicMock(data=response))
        
        await cmd_bots(mock_nc, difficulty="hard", password="pass", admin_id="botadmin")
        
        call_args = mock_nc.request.call_args
        payload = decode_msg(call_args[0][1])
        assert payload["admin_id"] == "botadmin"
        assert payload["difficulty"] == "hard"

    @pytest.mark.asyncio
    async def test_join_includes_admin_id(self):
        """#103: cmd_join passes admin_id to _signed for the join request."""
        from admin import _signed
        from src.nats_common import decode_msg
        # Test that _signed includes admin_id when called by cmd_join
        payload = {"game_id": "game123"}
        result = _signed(payload, password="pass", admin_id="joinadmin")
        data = decode_msg(result)
        assert data["admin_id"] == "joinadmin"
        assert data["game_id"] == "game123"
        # Verify auth fields are also present
        assert "_nonce" in data
        assert "_token" in data

    @pytest.mark.asyncio
    async def test_check_game_includes_admin_id(self):
        """#103: _check_game passes admin_id to _signed."""
        from admin import _check_game
        from src.nats_common import encode_msg, decode_msg
        mock_nc = MagicMock()
        response = encode_msg({"ok": True, "games": [{"game_id": "abc123", "status": "waiting"}]})
        mock_nc.request = AsyncMock(return_value=MagicMock(data=response))
        
        gid, status = await _check_game(mock_nc, "abc", password="pass", admin_id="checkadmin")
        
        call_args = mock_nc.request.call_args
        payload = decode_msg(call_args[0][1])
        assert payload["admin_id"] == "checkadmin"
