import asyncio
import json
import os
import queue
import subprocess
import sys
import threading
import time

import nats
import pygame

from config import WINDOW_WIDTH, WINDOW_HEIGHT, FPS, BG_COLOR, NATS_NAME, LOBBY_COUNTDOWN
from src.game_client import Game
from src.menu import Menu
from src.renderer import draw_game, _get_font
from src.sounds import play_sound_events

from src.nats_common import (
    NATS_SERVER, CONNECT_TIMEOUT, REQUEST_TIMEOUT, SUBJECT_MATCH,
    sub_game, encode_msg, decode_msg, decode_state,
)


class NATSClient:
    def __init__(self):
        self._loop = None
        self._thread = None
        self._nc = None
        self.state_queue = queue.Queue(maxsize=10)
        self.status_queue = queue.Queue(maxsize=10)
        self.game_id = None
        self.slot = None
        self._input_sub = None
        self._state_sub = None
        self._status_sub = None

    def start(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def connect_and_match(self, difficulty):
        future = asyncio.run_coroutine_threadsafe(
            self._do_connect_and_match(difficulty), self._loop
        )
        return future.result(timeout=REQUEST_TIMEOUT + 5)

    async def _do_connect_and_match(self, difficulty):
        self._nc = await nats.connect(NATS_SERVER, name=NATS_NAME)
        msg = await self._nc.request(
            SUBJECT_MATCH,
            encode_msg({"difficulty": difficulty}),
            timeout=REQUEST_TIMEOUT,
        )
        result = decode_msg(msg.data)
        if result.get("ok"):
            self.game_id = result["game_id"]
            self.slot = result["slot"]
            await self._subscribe_game()
        return result

    async def _subscribe_game(self):
        state_subj = sub_game(self.game_id, "state")
        self._state_sub = await self._nc.subscribe(state_subj, cb=self._on_state)

        status_subj = sub_game(self.game_id, "status")
        self._status_sub = await self._nc.subscribe(status_subj, cb=self._on_status)

    async def _on_state(self, msg):
        try:
            state = decode_state(msg.data)
            self.state_queue.put_nowait(state)
        except queue.Full:
            pass
        except Exception:
            pass

    async def _on_status(self, msg):
        try:
            data = decode_msg(msg.data)
            self.status_queue.put_nowait(data)
        except queue.Full:
            pass
        except Exception:
            pass

    @property
    def is_connected(self):
        return self._nc is not None and self._nc.is_connected

    def send_input(self, inp):
        if self._nc and self.game_id is not None and self.slot is not None:
            subj = sub_game(self.game_id, "input", str(self.slot))
            asyncio.run_coroutine_threadsafe(
                self._nc.publish(subj, encode_msg(inp)), self._loop
            )

    def send_leave(self):
        if self._nc and self.game_id is not None and self.slot is not None:
            subj = sub_game(self.game_id, "leave")
            asyncio.run_coroutine_threadsafe(
                self._nc.publish(subj, encode_msg({"slot": self.slot})), self._loop
            )

    def close(self):
        if self._nc and self._loop:
            future = asyncio.run_coroutine_threadsafe(self._nc.drain(), self._loop)
            try:
                future.result(timeout=3)
            except Exception:
                # Drain failed — force close the connection
                try:
                    asyncio.run_coroutine_threadsafe(self._nc.close(), self._loop).result(timeout=2)
                except Exception:
                    pass
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=3)


WHITE = (255, 255, 255)


def _raise_window():
    """Bring the pygame window to front (macOS)."""
    try:
        pid = os.getpid()
        subprocess.Popen([
            "osascript", "-e",
            f'tell application "System Events" to set frontmost of '
            f'the first process whose unix id is {pid} to true'
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


class App:
    def __init__(self, spectate=False):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        _raise_window()
        pygame.display.set_caption("Rebound")
        self.clock = pygame.time.Clock()
        self.menu = Menu()
        self.game = None
        self.nats = None
        self.state = "menu"
        self.spectate = spectate
        self.error_msg = None
        self.error_timer = 0
        self.prev_mouse_down = False
        self.muted = True
        self.latest_state = None
        self.game_over_timer = 0
        self.waiting_deadline = None
        self.waiting_players = 1

    def run(self):
        while True:
            dt = self.clock.tick(FPS)
            result = self._handle_events()
            if result == "quit":
                break
            self._update(dt)
            self._draw()
            pygame.display.flip()
        pygame.quit()
        sys.exit(0)

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_q, pygame.K_ESCAPE):
                if self.state == "menu":
                    return "quit"
                if self.state in ("game", "remote_game", "waiting"):
                    if self.nats:
                        self.nats.send_leave()
                        self.nats.close()
                        self.nats = None
                    self.state = "menu"
                    self.game = None
                    self.latest_state = None
                    self.error_msg = None
                    continue
            if event.type == pygame.KEYDOWN and event.key == pygame.K_m:
                self.muted = not self.muted

            if self.state == "game":
                self.game.handle_event(event)
            elif self.state == "menu":
                result = self.menu.handle_event(event)
                if result:
                    if isinstance(result, dict) and result.get("online"):
                        self._start_online()
                    else:
                        self.game = Game(self.screen, result, spectate=self.spectate)
                        self.state = "game"
        return None

    def _disconnect_to_menu(self, msg):
        """Return to main menu on server disconnect."""
        if self.nats:
            self.nats.close()
            self.nats = None
        self.state = "menu"
        self.game = None
        self.latest_state = None
        self.error_msg = msg
        self.error_timer = 180

    def _start_online(self):
        self.error_msg = None
        self.nats = NATSClient()
        self.nats.start()
        try:
            result = self.nats.connect_and_match("medium")
            if result.get("ok"):
                self.state = "waiting"
                self.waiting_deadline = time.time() + LOBBY_COUNTDOWN
                print(f"[CLIENT] Joined game {result['game_id']} as player {result['slot']}")
            else:
                self.error_msg = result.get("error", "Matchmaking failed")
                self.error_timer = 180
                self.nats.close()
                self.nats = None
        except Exception as e:
            self.error_msg = f"Could not connect: {e}"
            self.error_timer = 180
            if self.nats:
                self.nats.close()
                self.nats = None

    def _update(self, dt):
        if self.state == "waiting":
            if self.nats and not self.nats.is_connected:
                self._disconnect_to_menu("Server disconnected")
                return
            # Update countdown from status messages
            status = self._drain_queue(self.nats.status_queue)
            if status:
                countdown = status.get("countdown", LOBBY_COUNTDOWN)
                self.waiting_deadline = time.time() + countdown
                self.waiting_players = status.get("players", self.waiting_players)
            # Check if game started (state arriving)
            state = self._drain_queue(self.nats.state_queue)
            if state is not None:
                self.latest_state = state
                self.state = "remote_game"

        elif self.state == "remote_game":
            if self.nats and not self.nats.is_connected:
                self._disconnect_to_menu("Server disconnected")
                return
            state = self._drain_queue(self.nats.state_queue)
            if state is not None:
                self.latest_state = state
            self._send_local_input()
            if self.latest_state and self.latest_state.get("game_over"):
                self.game_over_timer += 1
                if self.game_over_timer >= FPS * 30:
                    if self.nats:
                        self.nats.close()
                        self.nats = None
                    self.state = "menu"
                    self.game = None
                    self.latest_state = None
                    self.game_over_timer = 0

        elif self.state == "game":
            self.game.update(dt)
            if self.game and self.game.engine.game_over:
                self.game_over_timer += 1
                if self.game_over_timer >= FPS * 30:
                    self.state = "menu"
                    self.game = None
                    self.game_over_timer = 0

        if self.error_timer > 0:
            self.error_timer -= 1
            if self.error_timer == 0:
                self.error_msg = None

    def _send_local_input(self):
        mx, my = pygame.mouse.get_pos()
        keys = pygame.key.get_pressed()
        buttons = pygame.mouse.get_pressed()
        clicked = buttons[0] and not self.prev_mouse_down
        self.prev_mouse_down = buttons[0]

        self.nats.send_input({
            "mouse_x": mx,
            "mouse_y": my,
            "space": keys[pygame.K_SPACE],
            "click": clicked,
        })

    def _draw(self):
        if self.state == "menu":
            self.menu.draw(self.screen)
            if self.error_msg:
                text = _get_font(28).render(self.error_msg, True, (220, 80, 80))
                rect = text.get_rect(center=(WINDOW_WIDTH // 2, 520))
                self.screen.blit(text, rect)

        elif self.state == "waiting":
            self.screen.fill(BG_COLOR)
            text = _get_font(40).render(f"Waiting for players... {self.waiting_players}/4", True, (200, 200, 220))
            rect = text.get_rect(center=(WINDOW_WIDTH // 2, 300))
            self.screen.blit(text, rect)

            remaining = max(0, int(self.waiting_deadline - time.time())) if self.waiting_deadline else LOBBY_COUNTDOWN
            mins, secs = divmod(remaining, 60)
            timer = _get_font(60).render(f"{mins}:{secs:02d}", True, (160, 160, 200))
            trect = timer.get_rect(center=(WINDOW_WIDTH // 2, 360))
            self.screen.blit(timer, trect)

            hint = _get_font(24).render(
                "Press Q to cancel.", True, (100, 100, 120)
            )
            hrect = hint.get_rect(center=(WINDOW_WIDTH // 2, 420))
            self.screen.blit(hint, hrect)

            if self.muted:
                muted_text = _get_font(24).render("MUTED", True, (200, 200, 200))
                self.screen.blit(muted_text, (10, 10))

        elif self.state == "remote_game":
            if self.latest_state:
                if not self.muted:
                    play_sound_events(self.latest_state)
                draw_game(self.screen, self.latest_state, my_slot=self.nats.slot)
                if self.latest_state.get("game_over"):
                    remaining = max(0, 30 - self.game_over_timer // FPS)
                    hint = _get_font(24).render(f"Returning to menu in {remaining}s — Press Q to return now", True, (120, 120, 140))
                    self.screen.blit(hint, (WINDOW_WIDTH // 2 - 160, WINDOW_HEIGHT - 30))
            else:
                self.screen.fill(BG_COLOR)
            if self.muted:
                muted_text = _get_font(24).render("MUTED", True, (200, 200, 200))
                self.screen.blit(muted_text, (10, 10))

        elif self.state == "game":
            self.screen.fill(BG_COLOR)
            self.game.draw(self.screen)

    @staticmethod
    def _drain_queue(q):
        result = None
        while True:
            try:
                result = q.get_nowait()
            except queue.Empty:
                break
        return result


if __name__ == "__main__":
    try:
        App(spectate="--spectate" in sys.argv).run()
    except (KeyboardInterrupt, SystemExit):
        pygame.quit()
        sys.exit(0)
