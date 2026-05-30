"""
Admin shell for the Rebound game server.
Connects to NATS and provides interactive management commands.

Usage: python manage.py
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nats
from src.nats_common import (
    NATS_SERVER, CONNECT_TIMEOUT, REQUEST_TIMEOUT,
    SUBJECT_ADMIN_LIST, SUBJECT_ADMIN_STOP, SUBJECT_ADMIN_KICK,
    SUBJECT_ADMIN_JOIN, SUBJECT_MATCH, sub_game, encode_msg, decode_msg, decode_state,
    sign_request,
)


def _fix_terminal():
    """Restore terminal settings that pygame/SDL may have broken."""
    try:
        import termios
        fd = sys.stdin.fileno()
        attrs = termios.tcgetattr(fd)
        attrs[0] |= termios.ICRNL
        attrs[1] |= termios.OPOST | termios.ONLCR
        attrs[3] |= termios.ECHO | termios.ICANON | termios.IEXTEN | termios.ISIG
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
    except (ImportError, OSError):
        pass


def _raise_window():
    """Bring the pygame window to front (macOS)."""
    try:
        import subprocess
        pid = os.getpid()
        subprocess.Popen([
            "osascript", "-e",
            f'tell application "System Events" to set frontmost of '
            f'the first process whose unix id is {pid} to true'
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

HELP_TEXT = """
Commands:
  games          List active games
  join <id>      Join a game as a player (takes an open slot)
  spectate <id>  Watch a game (opens pygame window)
  bots [diff]    Spawn 4 bots into a match (default: medium)
  kick <id> <s>  Kick player in slot <s> from game <id>
  stop           Gracefully stop the server
  help           Show this help
  quit / exit    Exit admin shell
""".strip()


def _signed(payload, password):
    """Sign a payload if password is set, then encode for NATS."""
    if password:
        payload = sign_request(payload, password)
    return encode_msg(payload) if payload else b""


async def cmd_games(nc, password=None):
    msg = await nc.request(SUBJECT_ADMIN_LIST, _signed({}, password), timeout=REQUEST_TIMEOUT)
    data = decode_msg(msg.data)
    if not data.get("ok"):
        print(f"  Error: {data.get('error')}")
        return
    games = data.get("games", [])
    if not games:
        print("  No active games.")
        return
    for g in games:
        slots_str = ",".join(str(s) for s in g["slots"])
        print(f"  {g['game_id']}  {g['status']:8s}  {g['difficulty']:6s}  "
              f"players:[{slots_str}]  frame:{g['frame']}")


async def _check_game(nc, game_id, password=None):
    """Return (full_game_id, status) tuple. Supports prefix matching.
    Returns (None, None) if not found, (None, 'ambiguous') if multiple matches."""
    msg = await nc.request(SUBJECT_ADMIN_LIST, _signed({}, password), timeout=REQUEST_TIMEOUT)
    data = decode_msg(msg.data)
    if not data.get("ok"):
        return None, None
    games = data.get("games", [])
    # Exact match first
    for g in games:
        if g["game_id"] == game_id:
            return g["game_id"], g["status"]
    # Prefix match
    matches = [g for g in games if g["game_id"].startswith(game_id)]
    if len(matches) == 1:
        return matches[0]["game_id"], matches[0]["status"]
    if len(matches) > 1:
        return None, "ambiguous"
    return None, None


async def cmd_stop(nc, password=None):
    msg = await nc.request(SUBJECT_ADMIN_STOP, _signed({}, password), timeout=REQUEST_TIMEOUT)
    data = decode_msg(msg.data)
    if not data.get("ok"):
        print(f"  Error: {data.get('error')}")
        return
    print(f"  {data.get('message', 'Done')}")


async def cmd_kick(nc, game_id, slot, password=None):
    payload = {"game_id": game_id, "slot": int(slot)}
    msg = await nc.request(SUBJECT_ADMIN_KICK, _signed(payload, password), timeout=REQUEST_TIMEOUT)
    data = decode_msg(msg.data)
    if data.get("ok"):
        print(f"  Kicked slot {slot} from {game_id}")
    else:
        print(f"  Error: {data.get('error')}")


async def cmd_join(nc, game_id, password=None):
    """Join a game as a human player, replacing a bot if needed."""
    payload = {"game_id": game_id}
    msg = await nc.request(SUBJECT_ADMIN_JOIN, _signed(payload, password), timeout=REQUEST_TIMEOUT)
    data = decode_msg(msg.data)
    if not data.get("ok"):
        print(f"  Error: {data.get('error')}")
        return

    slot = data["slot"]
    print(f"  Joined game {game_id} as slot {slot} — press Q/Esc to leave")

    import pygame
    import math
    from config import WINDOW_WIDTH, WINDOW_HEIGHT, FPS, BG_COLOR
    from src.renderer import draw_game
    from src.sounds import play_sound_events

    os.environ["SDL_VIDEO_WINDOW_POS"] = "center"
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption(f"Rebound — Player {slot} in {game_id}")
    _raise_window()
    clock = pygame.time.Clock()

    latest_state = None
    muted = True

    async def on_state(msg):
        nonlocal latest_state
        try:
            latest_state = decode_state(msg.data)
        except Exception:
            pass

    sub = await nc.subscribe(sub_game(game_id, "state"), cb=on_state)
    input_subj = sub_game(game_id, "input", str(slot))

    running = True
    while running:
        if not nc.is_connected:
            break

        click = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_q, pygame.K_ESCAPE):
                    running = False
                if event.key == pygame.K_m:
                    muted = not muted
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                click = True

        if not running:
            break

        mouse_x, mouse_y = pygame.mouse.get_pos()
        space = pygame.key.get_pressed()[pygame.K_SPACE]

        inp = {
            "mouse_x": mouse_x,
            "mouse_y": mouse_y,
            "click": click,
            "space": bool(space),
        }
        await nc.publish(input_subj, encode_msg(inp))

        if latest_state:
            if not muted:
                play_sound_events(latest_state)
            draw_game(screen, latest_state, my_slot=slot)
            fps_text = pygame.font.SysFont(None, 24).render(f"{int(clock.get_fps())} fps", True, (200, 200, 200))
            screen.blit(fps_text, (WINDOW_WIDTH - fps_text.get_width() - 10, 10))
            if muted:
                screen.blit(pygame.font.SysFont(None, 24).render("MUTED", True, (200, 200, 200)), (10, 10))
            if latest_state.get("game_over"):
                running = False
        else:
            screen.fill(BG_COLOR)
            font = pygame.font.SysFont(None, 32)
            screen.blit(font.render("Waiting for state...", True, (150, 150, 170)),
                        (WINDOW_WIDTH // 2 - 100, WINDOW_HEIGHT // 2))

        pygame.display.flip()
        clock.tick(FPS)
        await asyncio.sleep(0)

    # Leave the game
    await nc.publish(sub_game(game_id, "leave"), encode_msg({"slot": slot}))
    await sub.unsubscribe()
    pygame.display.set_mode((1, 1))
    pygame.display.quit()
    pygame.quit()
    _fix_terminal()
    print(f"  Left game {game_id}.")


async def cmd_bots(nc, difficulty="medium"):
    from src.bot_client import BotClient
    print(f"  Spawning 4 bots ({difficulty})...")
    bots = [BotClient(difficulty=difficulty, name=f"bot-{i}", admin=True) for i in range(4)]
    for bot in bots:
        await bot.connect_and_match()

    game_id = bots[0].game_id
    print(f"  All bots joined game {game_id}")
    print(f"  Bots running — use 'spectate {game_id}' to watch")

    # Run bots concurrently in background tasks
    tasks = [asyncio.create_task(bot.run()) for bot in bots]
    return game_id, tasks


async def cmd_spectate(nc, game_id):
    """Subscribe to state and render in pygame."""
    print(f"  Spectating game {game_id} — press Q/Esc to stop")

    import pygame
    from config import WINDOW_WIDTH, WINDOW_HEIGHT, FPS, BG_COLOR
    from src.renderer import draw_game
    from src.sounds import play_sound_events

    os.environ["SDL_VIDEO_WINDOW_POS"] = "center"
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption(f"Rebound — Spectating {game_id}")
    _raise_window()
    clock = pygame.time.Clock()

    latest_state = None
    muted = True

    async def on_state(msg):
        nonlocal latest_state
        try:
            latest_state = decode_state(msg.data)
        except Exception:
            pass

    sub = await nc.subscribe(sub_game(game_id, "state"), cb=on_state)

    running = True
    while running:
        if not nc.is_connected:
            break

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_q, pygame.K_ESCAPE):
                    running = False
                if event.key == pygame.K_m:
                    muted = not muted

        if latest_state:
            if not muted:
                play_sound_events(latest_state)
            draw_game(screen, latest_state, my_slot=None)
            fps_text = pygame.font.SysFont(None, 24).render(f"{int(clock.get_fps())} fps", True, (200, 200, 200))
            screen.blit(fps_text, (WINDOW_WIDTH - fps_text.get_width() - 10, 10))
            if muted:
                screen.blit(pygame.font.SysFont(None, 24).render("MUTED", True, (200, 200, 200)), (10, 10))
        else:
            screen.fill(BG_COLOR)
            font = pygame.font.SysFont(None, 32)
            screen.blit(font.render("Waiting for state...", True, (150, 150, 170)),
                        (WINDOW_WIDTH // 2 - 100, WINDOW_HEIGHT // 2))

        pygame.display.flip()
        clock.tick(FPS)
        await asyncio.sleep(0)  # yield to event loop for NATS callbacks

    await sub.unsubscribe()
    pygame.display.set_mode((1, 1))
    pygame.display.quit()
    pygame.quit()
    _fix_terminal()
    print("  Spectator closed.")


async def main():
    password = sys.argv[1] if len(sys.argv) > 1 else None

    print("Connecting to NATS...")
    nc = await nats.connect(NATS_SERVER, connect_timeout=CONNECT_TIMEOUT)
    print(f"Connected — {nc.connected_url.geturl()}")

    # Verify auth immediately
    try:
        msg = await nc.request(SUBJECT_ADMIN_LIST, _signed({}, password), timeout=REQUEST_TIMEOUT)
        data = decode_msg(msg.data)
        if not data.get("ok"):
            print(f"Error: {data.get('error')}")
            await nc.drain()
            return
    except Exception as e:
        print(f"Error: {e}")
        await nc.drain()
        return

    print("Authenticated." if password else "Connected (no password required).")
    print(HELP_TEXT)
    print()

    bot_tasks = []
    last_game_id = None

    from prompt_toolkit import PromptSession
    from prompt_toolkit.patch_stdout import patch_stdout
    session = PromptSession()

    try:
        while True:
            with patch_stdout():
                try:
                    line = await session.prompt_async("admin> ")
                except EOFError:
                    break
                except KeyboardInterrupt:
                    break
            line = line.strip()

            parts = line.split()
            if not parts:
                continue

            cmd = parts[0].lower()

            if cmd in ("quit", "exit"):
                break
            elif cmd == "help":
                print(HELP_TEXT)
            elif cmd == "games":
                await cmd_games(nc, password)
            elif cmd == "stop":
                await cmd_stop(nc, password)
                break
            elif cmd == "kick":
                if len(parts) < 3:
                    print("  Usage: kick <game_id> <slot>")
                else:
                    gid, status = await _check_game(nc, parts[1], password)
                    if status == "ambiguous":
                        print(f"  Ambiguous ID '{parts[1]}' — be more specific.")
                    elif status == "finished":
                        print(f"  Game {gid} is over.")
                    elif gid is None:
                        print(f"  Game '{parts[1]}' not found.")
                    else:
                        await cmd_kick(nc, gid, parts[2], password)
            elif cmd == "bots":
                if last_game_id:
                    print(f"  Bot game already running: {last_game_id}")
                else:
                    diff = parts[1] if len(parts) > 1 else "medium"
                    game_id, tasks = await cmd_bots(nc, diff)
                    last_game_id = game_id
                    bot_tasks.extend(tasks)
            elif cmd == "join":
                gid_input = parts[1] if len(parts) > 1 else last_game_id
                if not gid_input:
                    print("  Usage: join <game_id>")
                else:
                    gid, status = await _check_game(nc, gid_input, password)
                    if status == "ambiguous":
                        print(f"  Ambiguous ID '{gid_input}' — be more specific.")
                    elif status == "finished":
                        print(f"  Game {gid} is over.")
                    elif gid is None:
                        print(f"  Game '{gid_input}' not found.")
                    else:
                        await cmd_join(nc, gid, password)
            elif cmd == "spectate":
                gid_input = parts[1] if len(parts) > 1 else last_game_id
                if not gid_input:
                    print("  Usage: spectate <game_id>")
                else:
                    gid, status = await _check_game(nc, gid_input, password)
                    if status == "ambiguous":
                        print(f"  Ambiguous ID '{gid_input}' — be more specific.")
                    elif status == "finished":
                        print(f"  Game {gid} is over.")
                    elif gid is None:
                        print(f"  Game '{gid_input}' not found.")
                    else:
                        await cmd_spectate(nc, gid)
            else:
                print(f"  Unknown command: {cmd}")
                print("  Type 'help' for available commands")

    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        for t in bot_tasks:
            t.cancel()
        if nc.is_connected:
            await nc.drain()
        print("\nDisconnected.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
