import os
import random
import pygame

SOUND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sounds")

_initialized = False
_sounds = {}

def init():
    global _initialized
    if _initialized:
        return
    try:
        import pygame.mixer
        pygame.mixer.init()
    except Exception:
        return
    base_names = {
        "bounce": "bounce",
        "brick_crack": "brick_crack",
        "brick_destroy": "brick_destroy",
        "cannon_fire": "cannon_fire",
        "castle_collapse": "castle_collapse",
        "shield_reflect": "shield_reflect",
        "victory": "victory",
        "blockade_hit": "bounce",
        "blockade_destroyed": "brick_destroy",
    }
    for key, stem in base_names.items():
        variants = [f"{stem}.ogg", f"{stem}_h.ogg", f"{stem}_l.ogg"]
        loaded = []
        for v in variants:
            path = os.path.join(SOUND_DIR, "sounds", v)
            if os.path.exists(path):
                loaded.append(pygame.mixer.Sound(path))
        if loaded:
            _sounds[key] = loaded
    _initialized = True

def play_sound_events(state):
    init()
    if not _sounds:
        return
    for event in state.get("sound_events", []):
        if isinstance(event, str):
            event_type, volume = event, 1.0
        else:
            event_type, volume = event["type"], event.get("volume", 1.0)
        variants = _sounds.get(event_type)
        if variants:
            snd = random.choice(variants)
            ch = pygame.mixer.find_channel()
            if ch:
                ch.set_volume(volume)
                ch.play(snd)
