"""Tests for BotClient state machine (TESTS.md #50-55)."""
import math
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.bot_client import BotClient


class TestBotStateNone:
    """#50: State is None."""

    @pytest.mark.asyncio
    async def test_no_crash_when_state_none(self):
        """#50: Bot with state=None should not publish any input."""
        bot = BotClient(difficulty="medium")
        bot.nc = MagicMock()
        bot.nc.is_connected = True
        bot.nc.drain = AsyncMock()
        bot.nc.publish = AsyncMock()
        bot.state = None
        bot.game_id = "test"
        bot.slot = 0
        bot.ai = MagicMock()
        bot._running = True
        # Manually run one iteration by triggering game_over after first loop
        async def stop_after_one(*a, **kw):
            bot._running = False
        bot.nc.drain.side_effect = stop_after_one
        # Set state to None, then set game_over to stop
        bot.state = None
        # Run will exit immediately since state is None and we stop it
        import asyncio
        bot._running = True
        # Use a task with timeout
        async def run_briefly():
            bot._running = True
            # After a small sleep, stop
            await asyncio.sleep(0.05)
            bot._running = False
        task = asyncio.create_task(run_briefly())
        await bot.run(tick_hz=60)
        task.cancel()
        # No publish should have been called (state was None)
        bot.nc.publish.assert_not_called()


class TestBotSlotOutOfRange:
    """#51: Slot >= len(castles)."""

    @pytest.mark.asyncio
    async def test_slot_out_of_range(self):
        """#51: If slot >= len(castles), bot skips input (no publish)."""
        bot = BotClient(difficulty="medium")
        bot.nc = MagicMock()
        bot.nc.is_connected = True
        bot.nc.drain = AsyncMock()
        bot.nc.publish = AsyncMock()
        bot.slot = 5
        bot.game_id = "test"
        bot.ai = MagicMock()
        bot.state = {"castles": [{} for _ in range(4)], "projectiles": [], "game_over": False}
        bot._running = True
        import asyncio
        async def stop_soon():
            await asyncio.sleep(0.05)
            bot._running = False
        task = asyncio.create_task(stop_soon())
        await bot.run(tick_hz=60)
        task.cancel()
        # No publish because slot >= len(castles)
        bot.nc.publish.assert_not_called()


class TestBotCastleDead:
    """#52: Castle dead — bot stops sending."""

    @pytest.mark.asyncio
    async def test_dead_castle_no_input(self):
        """#52: Bot with dead castle skips input (no publish)."""
        bot = BotClient(difficulty="medium")
        bot.nc = MagicMock()
        bot.nc.is_connected = True
        bot.nc.drain = AsyncMock()
        bot.nc.publish = AsyncMock()
        bot.slot = 0
        bot.game_id = "test"
        bot.ai = MagicMock()
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
        bot._running = True
        import asyncio
        async def stop_soon():
            await asyncio.sleep(0.05)
            bot._running = False
        task = asyncio.create_task(stop_soon())
        await bot.run(tick_hz=60)
        task.cancel()
        # No publish because castle is dead
        bot.nc.publish.assert_not_called()


class TestBotGameOver:
    """#53: game_over stops loop."""

    @pytest.mark.asyncio
    async def test_game_over_stops_running(self):
        """#53: game_over flag causes bot to stop and drain."""
        bot = BotClient(difficulty="medium")
        bot.nc = MagicMock()
        bot.nc.is_connected = True
        bot.nc.drain = AsyncMock()
        bot.nc.publish = AsyncMock()
        bot.state = {"game_over": True}
        bot.game_id = "test"
        bot.slot = 0
        bot.ai = MagicMock()
        await bot.run(tick_hz=60)
        assert not bot._running
        bot.nc.drain.assert_called_once()


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
