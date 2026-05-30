import json, base64, hashlib, hmac, time
from config import NATS_URL, NATS_PREFIX, CONNECT_TIMEOUT, REQUEST_TIMEOUT

NATS_SERVER = NATS_URL
SUBJECT_MATCH = f"{NATS_PREFIX}.match"
SUBJECT_ADMIN_LIST = f"{NATS_PREFIX}.admin.list_games"
SUBJECT_ADMIN_STOP = f"{NATS_PREFIX}.admin.stop"
SUBJECT_ADMIN_KICK = f"{NATS_PREFIX}.admin.kick"
SUBJECT_ADMIN_JOIN = f"{NATS_PREFIX}.admin.join"

# Auth: HMAC-SHA256 with time-based nonce (±5s tolerance)
AUTH_TOLERANCE = 5


def sub_game(game_id, *parts):
    return ".".join([NATS_PREFIX, "game", game_id, *parts])


def encode_msg(data):
    """Encode a dict to base64 bytes for NATS publish/respond."""
    return base64.b64encode(json.dumps(data).encode())


def decode_msg(raw):
    """Decode base64 bytes from NATS into a dict."""
    if isinstance(raw, memoryview):
        raw = bytes(raw)
    return json.loads(base64.b64decode(raw).decode())


def sign_request(payload, password):
    """Sign a payload dict with HMAC-SHA256. Returns payload with auth fields added."""
    nonce = str(int(time.time()))
    token = hmac.HMAC(password.encode(), nonce.encode(), hashlib.sha256).hexdigest()
    payload["_nonce"] = nonce
    payload["_token"] = token
    return payload


def verify_auth(data, password):
    """Verify HMAC auth fields in a decoded message. Returns True if valid."""
    nonce = data.get("_nonce")
    token = data.get("_token")
    if not nonce or not token:
        return False
    # Check time drift
    try:
        req_time = int(nonce)
    except (ValueError, TypeError):
        return False
    if abs(time.time() - req_time) > AUTH_TOLERANCE:
        return False
    # Verify HMAC
    expected = hmac.HMAC(password.encode(), nonce.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(token, expected)


# State encoding returns bytes (consistent with encode_msg)
encode_state = lambda state: base64.b64encode(json.dumps(state).encode())
decode_state = decode_msg
