"""Tests for Sounds (TESTS.md #86-91). Uses mocked pygame.mixer."""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_mixer():
    """Mock pygame and pygame.mixer."""
    pg = MagicMock()
    pg.mixer = MagicMock()
    pg.mixer.init = MagicMock()
    pg.mixer.Sound = MagicMock(return_value=MagicMock())
    pg.mixer.find_channel = MagicMock(return_value=MagicMock())
    with patch.dict("sys.modules", {"pygame": pg, "pygame.mixer": pg.mixer}):
        # Reset sounds module state
        import src.sounds as sounds_mod
        sounds_mod._initialized = False
        sounds_mod._sounds = {}
        yield pg, sounds_mod


class TestInitAlreadyInitialized:
    """#86: init() when already initialized."""

    def test_noop_on_second_call(self, mock_mixer):
        """#86: Second init() call is a no-op."""
        pg, sounds = mock_mixer
        sounds._initialized = True
        sounds.init()
        # mixer.init should not be called again
        pg.mixer.init.assert_not_called()


class TestInitFailure:
    """#87: mixer init failure."""

    def test_graceful_fallback(self, mock_mixer):
        """#87: If mixer.init raises, no crash."""
        pg, sounds = mock_mixer
        sounds._initialized = False
        pg.mixer.init.side_effect = Exception("No audio device")
        # Re-import won't work easily, so test the logic directly
        # The init() catches Exception and returns
        sounds.init()
        # Should not crash, _initialized remains False or True depending on code flow
        # In actual code, it returns before setting _initialized = True


class TestLegacyStringEvent:
    """#88: String event format (legacy)."""

    def test_string_event_handled(self, mock_mixer):
        """#88: play_sound_events handles string event format."""
        pg, sounds = mock_mixer
        sounds._initialized = True
        sounds._sounds = {"bounce": [MagicMock()]}
        channel = MagicMock()
        pg.mixer.find_channel.return_value = channel
        # Legacy format: event is a plain string
        sounds.play_sound_events({"sound_events": ["bounce"]})
        channel.play.assert_called_once()


class TestNoSoundFiles:
    """#89: No sound files exist."""

    def test_no_crash_empty_sounds(self, mock_mixer):
        """#89: play_sound_events with no loaded sounds does nothing."""
        pg, sounds = mock_mixer
        sounds._initialized = True
        sounds._sounds = {}
        # Should not crash
        sounds.play_sound_events({"sound_events": [{"type": "bounce", "volume": 1.0}]})


class TestNoAvailableChannel:
    """#90: No available channel."""

    def test_skips_when_no_channel(self, mock_mixer):
        """#90: If find_channel returns None, skips gracefully."""
        pg, sounds = mock_mixer
        sounds._initialized = True
        sounds._sounds = {"bounce": [MagicMock()]}
        pg.mixer.find_channel.return_value = None
        # Should not crash
        sounds.play_sound_events({"sound_events": [{"type": "bounce", "volume": 1.0}]})


class TestVariantLoading:
    """#91: Sound variant selection."""

    def test_random_variant_selection(self, mock_mixer):
        """#91: Multiple variants are randomly selected."""
        pg, sounds = mock_mixer
        sounds._initialized = True
        v1 = MagicMock()
        v2 = MagicMock()
        sounds._sounds = {"bounce": [v1, v2]}
        channel = MagicMock()
        pg.mixer.find_channel.return_value = channel
        sounds.play_sound_events({"sound_events": [{"type": "bounce", "volume": 1.0}]})
        # One of the variants was played
        played = channel.play.call_args[0][0]
        assert played in (v1, v2)
