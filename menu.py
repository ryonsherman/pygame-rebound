import pygame
from config import WINDOW_WIDTH, WINDOW_HEIGHT, BG_COLOR

class Menu:
    def __init__(self):
        self.difficulty = "medium"
        self.diff_names = ["Easy", "Medium", "Hard"]
        self.diff_values = ["easy", "medium", "hard"]
        self.diff_rects = []
        self.start_rect = None
        self.hover_idx = None

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            mx, my = event.pos
            self.hover_idx = None
            for i, rect in enumerate(self.diff_rects):
                if rect.collidepoint(mx, my):
                    self.hover_idx = i
            if self.start_rect and self.start_rect.collidepoint(mx, my):
                self.hover_idx = 3
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            for i, rect in enumerate(self.diff_rects):
                if rect.collidepoint(mx, my):
                    self.difficulty = self.diff_values[i]
            if self.start_rect and self.start_rect.collidepoint(mx, my):
                return self.difficulty
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            return self.difficulty
        return None

    def draw(self, screen):
        screen.fill(BG_COLOR)
        title_font = pygame.font.SysFont(None, 80)
        font = pygame.font.SysFont(None, 44)
        small = pygame.font.SysFont(None, 28)

        title = title_font.render("REBOUND", True, (200, 200, 220))
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, 100))
        screen.blit(title, title_rect)

        y = 240
        label = small.render("Difficulty", True, (120, 120, 140))
        screen.blit(label, (WINDOW_WIDTH // 2 - label.get_width() // 2, y - 36))
        self.diff_rects = []
        for i, name in enumerate(self.diff_names):
            selected = self.difficulty == self.diff_values[i]
            hovered = self.hover_idx == i
            if selected:
                c = (255, 255, 255)
                bg = (70, 70, 95)
            elif hovered:
                c = (200, 200, 220)
                bg = (55, 55, 75)
            else:
                c = (150, 150, 180)
                bg = (40, 40, 60)
            r = pygame.Rect(WINDOW_WIDTH // 2 - 195 + i * 130, y, 120, 44)
            pygame.draw.rect(screen, bg, r, border_radius=6)
            bw = 3 if selected else 2
            pygame.draw.rect(screen, c, r, bw, border_radius=6)
            t = font.render(name, True, c)
            tr = t.get_rect(center=r.center)
            screen.blit(t, tr)
            self.diff_rects.append(r)

        y = 340
        hovered = self.hover_idx == 3
        c = (200, 240, 200) if hovered else (160, 200, 160)
        bg = (65, 85, 65) if hovered else (50, 65, 50)
        self.start_rect = pygame.Rect(WINDOW_WIDTH // 2 - 70, y, 140, 48)
        pygame.draw.rect(screen, bg, self.start_rect, border_radius=8)
        pygame.draw.rect(screen, c, self.start_rect, 2, border_radius=8)
        t = font.render("START", True, c)
        tr = t.get_rect(center=self.start_rect.center)
        screen.blit(t, tr)

        hint = small.render("Click to select difficulty, then START", True, (80, 80, 100))
        hr = hint.get_rect(center=(WINDOW_WIDTH // 2, y + 70))
        screen.blit(hint, hr)
