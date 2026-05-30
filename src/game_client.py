import pygame
from src.engine import GameEngine
from src.renderer import draw_game
from src.sounds import play_sound_events

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
        state = self.engine.get_state()
        if not self.muted:
            play_sound_events(state)
        my_slot = None if self.spectate else 0
        draw_game(screen, state, my_slot=my_slot)
        if self.muted:
            font = pygame.font.SysFont(None, 24)
            text = font.render("MUTED (M)", True, (200, 200, 200))
            screen.blit(text, (10, 10))
        if self.spectate and self.engine.game_over:
            font = pygame.font.SysFont(None, 48)
            colors = ["Red", "Blue", "Green", "Yellow"]
            txt = font.render(f"{colors[self.engine.winner]} Wins!", True, (255, 255, 255))
            screen.blit(txt, txt.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2)))
