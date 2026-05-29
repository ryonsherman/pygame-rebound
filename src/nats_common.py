import json, base64

NATS_SERVER = "nats://demo.nats.io:4222"
CONNECT_TIMEOUT = 5
REQUEST_TIMEOUT = 10

PREFIX = "rebound"
SUBJECT_MATCH = f"{PREFIX}.match"

def sub_game(game_id, *parts):
    return ".".join([PREFIX, "game", game_id, *parts])

def encode_state(state):
    return base64.b64encode(json.dumps(state).encode()).decode()

def decode_state(data):
    return json.loads(base64.b64decode(data).decode())
