import json, base64
from config import NATS_URL, NATS_PREFIX, CONNECT_TIMEOUT, REQUEST_TIMEOUT

NATS_SERVER = NATS_URL
SUBJECT_MATCH = f"{NATS_PREFIX}.match"


def sub_game(game_id, *parts):
    return ".".join([NATS_PREFIX, "game", game_id, *parts])


def encode_state(state):
    return base64.b64encode(json.dumps(state).encode()).decode()


def decode_state(data):
    return json.loads(base64.b64decode(data).decode())
