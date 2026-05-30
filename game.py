import asyncio
import json
import queue
import sys
import threading
import time

import nats
import pygame

from config import WINDOW_WIDTH, WINDOW_HEIGHT, FPS, BG_COLOR, NATS_NAME
from src.game_client import Game
from src.menu import Menu
from src.renderer import draw_game
from src.sounds import play_sound_events

from src.nats_common import (
    NATS_SERVER, CONNECT_TIMEOUT, REQUEST_TIMEOUT, SUBJECT_MATCH,
    sub_game, encode_state, decode_state,
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
            json.dumps({"difficulty": difficulty}).encode(),
            timeout=REQUEST_TIMEOUT,
        )
        result = json.loads(msg.data.decode())
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
            data = json.loads(msg.data.decode())
            self.status_queue.put_nowait(data)
        except queue.Full:
            pass
        except Exception:
            pass

    def send_input(self, inp):
        if self._nc and self.game_id is not None and self.slot is not None:
            subj = sub_game(self.game_id, "input", str(self.slot))
            asyncio.run_coroutine_threadsafe(
                self._nc.publish(subj, json.dumps(inp).encode()), self._loop
            )

    def send_leave(self):
        if self._nc and self.game_id is not None and self.slot is not None:
            subj = sub_game(self.game_id, "leave")
            asyncio.run_coroutine_threadsafe(
                self._nc.publish(subj, json.dumps({"slot": self.slot}).encode()), self._loop
            )

    def close(self):
        # Can't truly stop the loop from here, but drain the connection
        if self._nc and self._loop:
            future = asyncio.run_coroutine_threadsafe(self._nc.drain(), self._loop)
            try:
                future.result(timeout=3)
            except Exception:
                pass
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=3)


WHITE = (255, 255, 255)


class App:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Rebound")
        self.clock = pygame.time.Clock()
        self.menu = Menu()
        self.game = None
        self.nats = None
        self.state = "menu"
        self.error_msg = None
        self.error_timer = 0
        self.prev_mouse_down = False
        self.muted = False
        self.latest_state = None

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
                        self.game = Game(self.screen, result)
                        self.state = "game"
        return None

    def _start_online(self):
        self.error_msg = None
        self.nats = NATSClient()
        self.nats.start()
        try:
            result = self.nats.connect_and_match("medium")
            if result.get("ok"):
                self.state = "waiting"
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
            # Check if game started (state arriving)
            status = self._drain_queue(self.nats.status_queue)
            if status:
                pass  # could show countdown from status
            state = self._drain_queue(self.nats.state_queue)
            if state is not None:
                self.latest_state = state
                self.state = "remote_game"

        elif self.state == "remote_game":
            state = self._drain_queue(self.nats.state_queue)
            if state is not None:
                self.latest_state = state
            self._send_local_input()

        elif self.state == "game":
            self.game.update(dt)

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
                font = pygame.font.SysFont(None, 28)
                text = font.render(self.error_msg, True, (220, 80, 80))
                rect = text.get_rect(center=(WINDOW_WIDTH // 2, 520))
                self.screen.blit(text, rect)

        elif self.state == "waiting":
            self.screen.fill(BG_COLOR)
            font = pygame.font.SysFont(None, 40)
            text = font.render("Waiting for players...", True, (200, 200, 220))
            rect = text.get_rect(center=(WINDOW_WIDTH // 2, 300))
            self.screen.blit(text, rect)

            counts = self._drain_queue(self.nats.status_queue)
            remaining = 120
            if counts:
                remaining = counts.get("countdown", 120)
            timer_font = pygame.font.SysFont(None, 60)
            timer = timer_font.render(f"{remaining}s", True, (160, 160, 200))
            trect = timer.get_rect(center=(WINDOW_WIDTH // 2, 360))
            self.screen.blit(timer, trect)

            hint = pygame.font.SysFont(None, 24).render(
                f"Game will start in {remaining}s. Press Q to cancel.", True, (100, 100, 120)
            )
            hrect = hint.get_rect(center=(WINDOW_WIDTH // 2, 420))
            self.screen.blit(hint, hrect)

            if self.muted:
                muted_text = pygame.font.SysFont(None, 24).render("MUTED", True, (200, 200, 200))
                self.screen.blit(muted_text, (10, 10))

        elif self.state == "remote_game":
            if self.latest_state:
                if not self.muted:
                    play_sound_events(self.latest_state)
                draw_game(self.screen, self.latest_state, my_slot=self.nats.slot)
                if self.latest_state.get("game_over"):
                    font = pygame.font.SysFont(None, 24)
                    hint = font.render("Press Q to return to menu", True, (120, 120, 140))
                    self.screen.blit(hint, (WINDOW_WIDTH // 2 - 100, WINDOW_HEIGHT - 30))
            else:
                self.screen.fill(BG_COLOR)
            if self.muted:
                muted_text = pygame.font.SysFont(None, 24).render("MUTED", True, (200, 200, 200))
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
        App().run()
    except KeyboardInterrupt:
        pygame.quit()
        sys.exit(0)
