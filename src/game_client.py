import pygame
from src.engine import GameEngine
from src.renderer import draw_game
from src.sounds import play_sound_events

class Game:
    def __init__(self, screen, difficulty="hard"):
        self.screen = screen
        self.engine = GameEngine(difficulty=difficulty, human_players=[])
        self.prev_mouse_down = False
        self.muted = True

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_m:
            self.muted = not self.muted

    def update(self, dt):
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
        draw_game(screen, state, my_slot=0)
        if self.muted:
            font = pygame.font.SysFont(None, 24)
            text = font.render("MUTED", True, (200, 200, 200))
            screen.blit(text, (10, 10))
