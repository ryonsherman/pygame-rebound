"""Shared fixtures for rebound-game tests."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pytest
from src.engine import GameEngine


@pytest.fixture
def engine_hard():
    """All-AI hard difficulty engine."""
    return GameEngine(difficulty="hard", human_players=[])


@pytest.fixture
def engine_medium():
    """All-AI medium difficulty engine."""
    return GameEngine(difficulty="medium", human_players=[])


@pytest.fixture
def engine_easy():
    """All-AI easy difficulty engine."""
    return GameEngine(difficulty="easy", human_players=[])


@pytest.fixture
def engine_human():
    """Engine with player 0 as human."""
    return GameEngine(difficulty="medium", human_players=[0])
