import pygame
import sys
from config import WINDOW_WIDTH, WINDOW_HEIGHT, FPS, BG_COLOR
from game import Game
from menu import Menu

class App:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Rebound")
        self.clock = pygame.time.Clock()
        self.menu = Menu()
        self.game = None
        self.state = "menu"

    def run(self):
        while True:
            dt = self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_q:
                    if self.state == "game":
                        self.state = "menu"
                        self.game = None
                        continue
                    pygame.quit()
                    sys.exit()
                if self.state == "menu":
                    result = self.menu.handle_event(event)
                    if result:
                        self.game = Game(self.screen, result)
                        self.state = "game"
                else:
                    self.game.handle_event(event)
            if self.state == "menu":
                self.menu.draw(self.screen)
            else:
                self.game.update(dt)
                self.screen.fill(BG_COLOR)
                self.game.draw(self.screen)
            pygame.display.flip()

if __name__ == "__main__":
    App().run()
