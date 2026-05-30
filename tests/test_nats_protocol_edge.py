"""Tests for NATS protocol error handling (TESTS.md #43-49)."""
import base64
import json
import time
import pytest
from src.nats_common import encode_msg, decode_msg, encode_state, sign_request, verify_auth


class TestDecodeErrors:
    """#43-45: decode_msg error cases."""

    def test_invalid_base64(self):
        """#43: Invalid base64 should raise."""
        with pytest.raises(Exception):
            decode_msg(b"not-valid-base64!!!")

    def test_valid_base64_invalid_json(self):
        """#44: Valid base64 but invalid JSON should raise."""
        bad = base64.b64encode(b"not json {{{")
        with pytest.raises(Exception):
            decode_msg(bad)

    def test_empty_bytes(self):
        """#45: Empty bytes should raise (can't base64 decode empty to valid JSON)."""
        with pytest.raises(Exception):
            decode_msg(b"")


class TestVerifyAuthEdge:
    """#46: verify_auth nonce not an integer."""

    def test_nonce_not_integer(self):
        """#46: Non-integer nonce should fail verification."""
        data = {"_nonce": "not_a_number", "_token": "abc"}
        assert not verify_auth(data, "secret")

    def test_nonce_none(self):
        """Nonce as None should fail."""
        data = {"_nonce": None, "_token": "abc"}
        assert not verify_auth(data, "secret")


class TestSignRequestMutation:
    """#47: sign_request mutates input dict."""

    def test_mutates_in_place(self):
        """#47: sign_request adds _nonce and _token to the same dict."""
        payload = {"action": "test"}
        result = sign_request(payload, "secret")
        assert result is payload  # Same object
        assert "_nonce" in payload
        assert "_token" in payload


class TestOversizedPayload:
    """#48: Oversized payloads."""

    def test_large_payload_encodes(self):
        """#48: >1MB JSON encodes without crash (performance check)."""
        big_data = {"data": "x" * (1024 * 1024)}
        encoded = encode_msg(big_data)
        decoded = decode_msg(encoded)
        assert decoded == big_data


class TestEncodeStateAlias:
    """#49: encode_state vs encode_msg equivalence."""

    def test_functionally_equivalent(self):
        """#49: encode_state and encode_msg produce same output for same input."""
        data = {"castles": [], "projectiles": [], "game_over": False}
        assert encode_state(data) == encode_msg(data)
