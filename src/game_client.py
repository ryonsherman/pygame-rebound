import pygame
from src.engine import GameEngine
from src.renderer import draw_game, draw_game_direct, _get_font
from src.sounds import play_sound_events

# Pre-rendered muted indicator (cached on first use)
_muted_surface = None

def _get_muted_surface():
    global _muted_surface
    if _muted_surface is None:
        _muted_surface = _get_font(24).render("MUTED", True, (200, 200, 200))
    return _muted_surface

class Game:
    def __init__(self, screen, difficulty="hard", spectate=False):
        self.screen = screen
        self.spectate = spectate
        human_players = [] if spectate else [0]
        self.engine = GameEngine(difficulty=difficulty, human_players=human_players)
        self.prev_mouse_down = False
        self.muted = True

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_m:
            self.muted = not self.muted

    def update(self, dt):
        if not self.spectate:
            mx, my = pygame.mouse.get_pos()
            keys = pygame.key.get_pressed()
            mouse_buttons = pygame.mouse.get_pressed()
            clicked = mouse_buttons[0] and not self.prev_mouse_down
            self.prev_mouse_down = mouse_buttons[0]

            self.engine.handle_input({
                0: {
                    "mouse_x": mx,
                    "mouse_y": my,
                    "space": keys[pygame.K_SPACE],
                    "click": clicked,
                }
            })
        self.engine.update()

    def draw(self, screen):
        # Play sounds from engine's sound_events directly (no state copy needed)
        if not self.muted and self.engine.sound_events:
            play_sound_events({"sound_events": self.engine.sound_events})
        # Render directly from engine — avoids get_state() copy every frame
        my_slot = None if self.spectate else 0
        aim_mode = "spectate" if self.spectate else "single_player"
        draw_game_direct(screen, self.engine, my_slot=my_slot, aim_mode=aim_mode)
        if self.muted:
            screen.blit(_get_muted_surface(), (10, 10))
        if self.spectate and self.engine.game_over:
            font = _get_font(48)
            colors = ["Red", "Blue", "Green", "Yellow"]
            txt = font.render(f"{colors[self.engine.winner]} Wins!", True, (255, 255, 255))
            screen.blit(txt, txt.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2)))
