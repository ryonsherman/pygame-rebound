"""Tests for NATS protocol: encode/decode, auth signing/verification, state serialization."""
import time
import math
import pytest
from src.nats_common import (
    encode_msg, decode_msg, encode_state, decode_state,
    sign_request, verify_auth, sub_game, SUBJECT_MATCH,
)
from src.engine import GameEngine


class TestEncodeDecode:
    """Message encoding/decoding roundtrip."""

    def test_roundtrip_simple(self):
        data = {"hello": "world", "num": 42, "nested": {"a": [1, 2, 3]}}
        assert decode_msg(encode_msg(data)) == data

    def test_roundtrip_empty(self):
        assert decode_msg(encode_msg({})) == {}

    def test_roundtrip_unicode(self):
        data = {"emoji": "🎮", "jp": "ゲーム"}
        assert decode_msg(encode_msg(data)) == data

    def test_encode_returns_bytes(self):
        result = encode_msg({"x": 1})
        assert isinstance(result, bytes)

    def test_decode_handles_memoryview(self):
        raw = encode_msg({"key": "val"})
        mv = memoryview(raw)
        assert decode_msg(mv) == {"key": "val"}


class TestStateSerialize:
    """Full game state encode/decode roundtrip."""

    def test_state_roundtrip(self):
        eng = GameEngine(difficulty="medium", human_players=[])
        for _ in range(100):
            eng.update()
        state = eng.get_state()
        decoded = decode_state(encode_state(state))
        assert decoded["game_over"] == state["game_over"]
        assert decoded["winner"] == state["winner"]
        assert len(decoded["castles"]) == 4
        assert len(decoded["projectiles"]) == len(state["projectiles"])

    def test_state_size_reasonable(self):
        """State JSON should be < 16KB for network send at 20Hz."""
        eng = GameEngine(difficulty="hard", human_players=[])
        for _ in range(500):
            eng.update()
        state = eng.get_state()
        encoded = encode_state(state)
        assert len(encoded) < 16384


class TestAuth:
    """HMAC-SHA256 signing and verification."""

    def test_sign_and_verify(self):
        payload = {"action": "stop"}
        signed = sign_request(payload, "secret123")
        assert verify_auth(signed, "secret123")

    def test_wrong_password_fails(self):
        payload = {"action": "stop"}
        signed = sign_request(payload, "secret123")
        assert not verify_auth(signed, "wrong_password")

    def test_missing_fields_fails(self):
        assert not verify_auth({}, "secret123")
        assert not verify_auth({"_nonce": "123"}, "secret123")
        assert not verify_auth({"_token": "abc"}, "secret123")

    def test_expired_nonce_fails(self):
        payload = {"action": "test"}
        signed = sign_request(payload, "secret123")
        # Tamper with nonce to be old
        signed["_nonce"] = str(int(time.time()) - 100)
        assert not verify_auth(signed, "secret123")

    def test_tampered_token_fails(self):
        payload = {"action": "test"}
        signed = sign_request(payload, "secret123")
        signed["_token"] = "deadbeef" * 8
        assert not verify_auth(signed, "secret123")


class TestSubjects:
    """NATS subject construction."""

    def test_sub_game_format(self):
        assert sub_game("abc123", "state") == "rebound.game.abc123.state"
        assert sub_game("abc123", "input", "0") == "rebound.game.abc123.input.0"

    def test_subject_match(self):
        assert SUBJECT_MATCH == "rebound.match"
