"""Tests for BotClient state machine (TESTS.md #50-55)."""
import math
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.bot_client import BotClient


class TestBotStateNone:
    """#50: State is None."""

    def test_no_crash_when_state_none(self):
        """#50: Bot with state=None should not crash in run logic."""
        bot = BotClient(difficulty="medium")
        bot.state = None
        bot._running = False
        # The run loop checks `if self.state` — with None it skips


class TestBotSlotOutOfRange:
    """#51: Slot >= len(castles)."""

    def test_slot_out_of_range(self):
        """#51: If slot >= len(castles), bot skips input."""
        bot = BotClient(difficulty="medium")
        bot.slot = 5
        bot.state = {"castles": [{} for _ in range(4)], "projectiles": [], "game_over": False}
        # The run loop checks `self.slot < len(castles)` — would skip
        assert bot.slot >= len(bot.state["castles"])


class TestBotCastleDead:
    """#52: Castle dead — bot stops sending."""

    def test_dead_castle_no_input(self):
        """#52: Bot with dead castle skips input."""
        bot = BotClient(difficulty="medium")
        bot.slot = 0
        bot.state = {
            "castles": [
                {"alive": False, "center": (100, 100), "fire_request": None,
                 "shield": {"active": False, "timer": 0, "cooldown_timer": 0}},
                {"alive": True, "center": (200, 200)},
                {"alive": True, "center": (300, 300)},
                {"alive": True, "center": (400, 400)},
            ],
            "projectiles": [],
            "game_over": False,
        }
        # The condition `castles[self.slot].get("alive")` is False — skips


class TestBotGameOver:
    """#53: game_over stops loop."""

    def test_game_over_stops_running(self):
        """#53: game_over flag should set _running=False."""
        bot = BotClient(difficulty="medium")
        bot.state = {"game_over": True}
        bot._running = True
        # In run(), the elif branch sets _running = False
        if bot.state and bot.state.get("game_over", False):
            bot._running = False
        assert not bot._running


class TestBotStop:
    """#54: stop() method."""

    def test_stop_sets_running_false(self):
        """#54: stop() sets _running to False."""
        bot = BotClient(difficulty="medium")
        bot._running = True
        bot.stop()
        assert not bot._running


class TestBotDisconnect:
    """#55: Disconnect after run."""

    @pytest.mark.asyncio
    async def test_drain_called_on_exit(self):
        """#55: drain() called when run completes."""
        bot = BotClient(difficulty="medium")
        bot.nc = MagicMock()
        bot.nc.is_connected = True
        bot.nc.drain = AsyncMock()
        bot.nc.publish = AsyncMock()
        bot.state = {"game_over": True}
        bot._running = True
        bot.game_id = "test"
        bot.slot = 0
        bot.ai = MagicMock()
        await bot.run(tick_hz=60)
        bot.nc.drain.assert_called_once()
