"""Tests for Menu (TESTS.md #80-85). Uses mocked pygame."""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_pygame_menu():
    """Mock pygame for menu tests."""
    pg = MagicMock()
    pg.MOUSEMOTION = 4
    pg.MOUSEBUTTONDOWN = 5
    pg.KEYDOWN = 2
    pg.K_RETURN = 13
    pg.K_LEFT = 276
    pg.K_RIGHT = 275
    pg.K_UP = 273
    pg.K_DOWN = 274
    with patch.dict("sys.modules", {"pygame": pg, "pygame.font": pg.font}):
        pg.font.SysFont = MagicMock(return_value=MagicMock(
            render=MagicMock(return_value=MagicMock(
                get_rect=MagicMock(return_value=MagicMock(center=(0, 0))),
                get_width=MagicMock(return_value=100),
            ))
        ))
        pg.Rect = lambda *a: MagicMock(
            collidepoint=MagicMock(return_value=False),
            center=(a[0] + a[2]//2, a[1] + a[3]//2) if len(a) == 4 else (0, 0),
        )
        yield pg


class TestKeyboardNavigation:
    """#80: Keyboard navigation."""

    def test_left_decreases_col(self, mock_pygame_menu):
        """#80: LEFT key decreases difficulty column."""
        from src.menu import Menu
        pg = mock_pygame_menu
        m = Menu()
        m._col = 2  # hard
        event = MagicMock()
        event.type = pg.KEYDOWN
        event.key = pg.K_LEFT
        m.handle_event(event)
        assert m._col == 1

    def test_right_increases_col(self, mock_pygame_menu):
        """#80: RIGHT key increases difficulty column."""
        from src.menu import Menu
        pg = mock_pygame_menu
        m = Menu()
        m._col = 0
        event = MagicMock()
        event.type = pg.KEYDOWN
        event.key = pg.K_RIGHT
        m.handle_event(event)
        assert m._col == 1

    def test_down_switches_to_online(self, mock_pygame_menu):
        """#80: DOWN key switches to online row."""
        from src.menu import Menu
        pg = mock_pygame_menu
        m = Menu()
        m._row = 0
        event = MagicMock()
        event.type = pg.KEYDOWN
        event.key = pg.K_DOWN
        m.handle_event(event)
        assert m._row == 1
        assert m.mode == "online"

    def test_up_switches_from_online(self, mock_pygame_menu):
        """#80: UP key switches from online back to difficulty."""
        from src.menu import Menu
        pg = mock_pygame_menu
        m = Menu()
        m._row = 1
        m._col = 1
        event = MagicMock()
        event.type = pg.KEYDOWN
        event.key = pg.K_UP
        m.handle_event(event)
        assert m._row == 0
        assert m.mode == "medium"


class TestMouseClick:
    """#81, #82: Mouse clicks on mode buttons and START."""

    def test_mode_button_click(self, mock_pygame_menu):
        """#81: Clicking a mode button selects that mode."""
        from src.menu import Menu
        pg = mock_pygame_menu
        m = Menu()
        # Manually set mode_rects to have collidepoint return True for index 0
        rect = MagicMock()
        rect.collidepoint = MagicMock(return_value=True)
        m.mode_rects = [rect, MagicMock(collidepoint=MagicMock(return_value=False)),
                        MagicMock(collidepoint=MagicMock(return_value=False)),
                        MagicMock(collidepoint=MagicMock(return_value=False))]
        m.start_rect = MagicMock(collidepoint=MagicMock(return_value=False))
        event = MagicMock()
        event.type = pg.MOUSEBUTTONDOWN
        event.button = 1
        event.pos = (100, 240)
        m.handle_event(event)
        assert m.mode == "easy"

    def test_start_click_returns_mode(self, mock_pygame_menu):
        """#82: Clicking START returns the current mode."""
        from src.menu import Menu
        pg = mock_pygame_menu
        m = Menu()
        m.mode = "hard"
        m.mode_rects = [MagicMock(collidepoint=MagicMock(return_value=False)) for _ in range(4)]
        m.start_rect = MagicMock(collidepoint=MagicMock(return_value=True))
        event = MagicMock()
        event.type = pg.MOUSEBUTTONDOWN
        event.button = 1
        event.pos = (512, 380)
        result = m.handle_event(event)
        assert result == "hard"


class TestOnlineMode:
    """#83: Online mode returns correct payload."""

    def test_online_returns_dict(self, mock_pygame_menu):
        """#83: Online mode returns {"online": True}."""
        from src.menu import Menu
        pg = mock_pygame_menu
        m = Menu()
        m.mode = "online"
        event = MagicMock()
        event.type = pg.KEYDOWN
        event.key = pg.K_RETURN
        result = m.handle_event(event)
        assert result == {"online": True}


class TestHoverState:
    """#84: Hover state tracking."""

    def test_hover_sets_index(self, mock_pygame_menu):
        """#84: MOUSEMOTION over a button sets hover_idx."""
        from src.menu import Menu
        pg = mock_pygame_menu
        m = Menu()
        rect = MagicMock()
        rect.collidepoint = MagicMock(return_value=True)
        m.mode_rects = [MagicMock(collidepoint=MagicMock(return_value=False)),
                        rect,
                        MagicMock(collidepoint=MagicMock(return_value=False)),
                        MagicMock(collidepoint=MagicMock(return_value=False))]
        m.start_rect = MagicMock(collidepoint=MagicMock(return_value=False))
        event = MagicMock()
        event.type = pg.MOUSEMOTION
        event.pos = (200, 240)
        m.handle_event(event)
        assert m.hover_idx == 1


class TestSyncMode:
    """#85: _sync_mode logic."""

    def test_sync_mode_row0(self, mock_pygame_menu):
        """#85: _sync_mode with row=0 uses col index."""
        from src.menu import Menu
        m = Menu()
        m._row = 0
        m._col = 0
        m._sync_mode()
        assert m.mode == "easy"
        m._col = 2
        m._sync_mode()
        assert m.mode == "hard"

    def test_sync_mode_row1_online(self, mock_pygame_menu):
        """#85: _sync_mode with row=1 sets online."""
        from src.menu import Menu
        m = Menu()
        m._row = 1
        m._sync_mode()
        assert m.mode == "online"
