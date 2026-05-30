import pygame
from config import WINDOW_WIDTH, WINDOW_HEIGHT, BG_COLOR
from src.renderer import _get_font

class Menu:
    def __init__(self):
        self.mode = "medium"
        self.mode_names = ["Easy", "Medium", "Hard", "Online"]
        self.mode_values = ["easy", "medium", "hard", "online"]
        self.mode_rects = []
        self.start_rect = None
        self.hover_idx = None
        # Navigation: row 0 = easy/medium/hard, row 1 = online
        self._row = 0  # 0 = difficulty, 1 = online
        self._col = 1  # index within difficulty row (0=easy,1=medium,2=hard)

    def _sync_mode(self):
        if self._row == 0:
            self.mode = self.mode_values[self._col]
        else:
            self.mode = "online"

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            mx, my = event.pos
            self.hover_idx = None
            for i, rect in enumerate(self.mode_rects):
                if rect.collidepoint(mx, my):
                    self.hover_idx = i
            if self.start_rect and self.start_rect.collidepoint(mx, my):
                self.hover_idx = len(self.mode_rects)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            for i, rect in enumerate(self.mode_rects):
                if rect.collidepoint(mx, my):
                    self.mode = self.mode_values[i]
                    if i < 3:
                        self._row = 0
                        self._col = i
                    else:
                        self._row = 1
            if self.start_rect and self.start_rect.collidepoint(mx, my):
                if self.mode == "online":
                    return {"online": True}
                return self.mode
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                if self.mode == "online":
                    return {"online": True}
                return self.mode
            elif event.key == pygame.K_LEFT:
                if self._row == 0:
                    self._col = max(0, self._col - 1)
                    self._sync_mode()
            elif event.key == pygame.K_RIGHT:
                if self._row == 0:
                    self._col = min(2, self._col + 1)
                    self._sync_mode()
            elif event.key == pygame.K_DOWN:
                if self._row == 0:
                    self._row = 1
                    self._sync_mode()
            elif event.key == pygame.K_UP:
                if self._row == 1:
                    self._row = 0
                    self._sync_mode()
        return None

    def draw(self, screen):
        screen.fill(BG_COLOR)
        title_font = _get_font(80)
        font = _get_font(44)
        small = _get_font(28)

        title = title_font.render("REBOUND", True, (200, 200, 220))
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, 100))
        screen.blit(title, title_rect)

        y = 240
        label = small.render("Select Mode", True, (120, 120, 140))
        screen.blit(label, (WINDOW_WIDTH // 2 - label.get_width() // 2, y - 36))
        self.mode_rects = []
        for i, name in enumerate(self.mode_names):
            if name == "Online":
                break
            selected = self.mode == self.mode_values[i]
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
            w = 150 if self.mode_names[i] == "Medium" else 130
            offset = -10 if self.mode_names[i] == "Medium" else 0
            r = pygame.Rect(WINDOW_WIDTH // 2 - 210 + i * 145 + offset, y, w, 44)
            pygame.draw.rect(screen, bg, r, border_radius=6)
            bw = 3 if selected else 2
            pygame.draw.rect(screen, c, r, bw, border_radius=6)
            t = font.render(name, True, c)
            tr = t.get_rect(center=r.center)
            screen.blit(t, tr)
            self.mode_rects.append(r)

        y = 310
        i = 3
        selected = self.mode == self.mode_values[i]
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
        r = pygame.Rect(WINDOW_WIDTH // 2 - 75, y, 150, 44)
        pygame.draw.rect(screen, bg, r, border_radius=6)
        bw = 3 if selected else 2
        pygame.draw.rect(screen, c, r, bw, border_radius=6)
        t = font.render("Online", True, c)
        tr = t.get_rect(center=r.center)
        screen.blit(t, tr)
        self.mode_rects.append(r)

        y = 380
        hovered = self.hover_idx == len(self.mode_rects)
        c = (200, 240, 200) if hovered else (160, 200, 160)
        bg = (65, 85, 65) if hovered else (50, 65, 50)
        self.start_rect = pygame.Rect(WINDOW_WIDTH // 2 - 70, y, 140, 48)
        pygame.draw.rect(screen, bg, self.start_rect, border_radius=8)
        pygame.draw.rect(screen, c, self.start_rect, 2, border_radius=8)
        t = font.render("START", True, c)
        tr = t.get_rect(center=self.start_rect.center)
        screen.blit(t, tr)

        hint = small.render("Click START to Play!", True, (80, 80, 100))
        hr = hint.get_rect(center=(WINDOW_WIDTH // 2, y + 70))
        screen.blit(hint, hr)
