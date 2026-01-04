#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# & "C:\Users\Guan ying\AppData\Local\Programs\Python\Python310\python.exe" catch_treasure.py

"""
-Catch the Treasure (Pygame) - 720p + PNG assets, NO glow, 12s slow, no bars

- Uses PNG assets from ./assets if present; otherwise falls back to vector-drawn art.
- No additive glow or background bars; clean rendering with transparent PNGs.
- 1280x720, resizable, F to toggle fullscreen
- Random item size per spawn (0.7x ~ 1.4x), bigger falls faster
- Slow effect lasts 12 seconds when picking the hourglass (slow) item
- Near-shot bomb bonus: if a bomb is shot <= 20 px above the paddle, +10 pts; else +1
- Always shoot (SPACE), ammo cap = 3
"""

import os
import random
import sys
import math
import pygame
import pygame.gfxdraw as gfx

# ---------- Global Switches ----------
USE_GLOW = False  # <- disable ALL additive glow halos

# ---------- Game Params ----------
W, H = 1280, 720
FPS = 60
SPAWN_MS = 720
LEVEL_UP_EVERY = 10
MAX_LIVES = 5
AMMO_MAX = 3

GROUND_Y = H - 56  # logic anchor only; no visual bar

# Bonus rule
NEAR_SHOT_BONUS_THRESHOLD_PX = 20
NEAR_SHOT_BONUS_SCORE = 10
NORMAL_BOMB_SHOT_SCORE = 1

# Slow effect
SLOW_SECONDS = 12
SLOW_FACTOR = 0.5

# Item kinds
TREASURE = "treasure"
BOMB = "bomb"
HEART = "heart"
HOURGLASS = "hourglass"  # slow
AMMO = "ammo"

# Asset paths
ASSET_PATHS = {
    TREASURE: os.path.join("assets", "treasure.png"),
    BOMB: os.path.join("assets", "bomb.png"),
    HEART: os.path.join("assets", "heart.png"),
    HOURGLASS: os.path.join("assets", "hourglass.png"),
    AMMO: os.path.join("assets", "ammo.png"),
}

# kind -> {"surf": Surface, "glow_color": (r,g,b)|None, "base_w": int}
BASE_ART = {}

# ---------- Helpers ----------


def clamp(v, lo, hi):
    return max(lo, min(v, hi))


def draw_text(surface, text, size, x, y, color=(255, 255, 255), center=True, bold=True, shadow=True):
    font = pygame.font.SysFont(None, size, bold=bold)
    surf = font.render(text, True, color)
    rect = surf.get_rect()
    if center:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)
    if shadow:
        sh = font.render(text, True, (0, 0, 0))
        sh_rect = sh.get_rect(center=rect.center) if center else sh.get_rect(
            topleft=rect.topleft)
        sh_rect.x += 2
        sh_rect.y += 2
        surface.blit(sh, sh_rect)
    surface.blit(surf, rect)


def aa_circle(surface, x, y, r, color):
    gfx.filled_circle(surface, x, y, r, color)
    gfx.aacircle(surface, x, y, r, color)


def aa_polygon(surface, pts, color, outline=None):
    gfx.filled_polygon(surface, pts, color)
    gfx.aapolygon(surface, pts, color if outline is None else outline)


# Glow cache (kept for completeness; disabled via USE_GLOW)
GLOW_CACHE = {}


def make_glow(radius, color, falloff=2.5):
    key = (radius, color, falloff)
    if key in GLOW_CACHE:
        return GLOW_CACHE[key]
    size = radius * 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = cy = radius
    for r in range(radius, 0, -1):
        a = int(255 * (r / radius) ** falloff)
        col = (color[0], color[1], color[2], a)
        pygame.gfxdraw.filled_circle(surf, cx, cy, r, col)
    surf = surf.convert_alpha()
    GLOW_CACHE[key] = surf
    return surf


def draw_shadow(surface, centerx, bottom, base_w, max_alpha=110):
    h = max(0, GROUND_Y - bottom)
    w = int(clamp(base_w * (1.0 - h / 450.0), base_w * 0.35, base_w))
    w = max(14, w)
    shadow_h = max(5, int(w * 0.22))
    alpha = int(clamp(max_alpha * (1.0 - h / 450.0), 24, max_alpha))
    s = pygame.Surface((w, shadow_h), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, alpha), s.get_rect())
    rect = s.get_rect(center=(int(centerx), int(GROUND_Y)))
    surface.blit(s, rect)

# ---------- Fallback vector art ----------


def make_vector_art(kind):
    glow_color = None
    if kind == TREASURE:
        r = 18
        surf = pygame.Surface((r*2+6, r*2+6), pygame.SRCALPHA)
        cx, cy = r+3, r+3
        aa_circle(surf, cx, cy, r, (255, 200, 40))
        aa_circle(surf, cx, cy, r-5, (255, 235, 150))
        gfx.aacircle(surf, cx, cy, r, (255, 200, 40))
        glow_color = (255, 220, 90)
    elif kind == BOMB:
        r = 22
        surf = pygame.Surface((r*2+10, r*2+10), pygame.SRCALPHA)
        cx, cy = r+5, r+5
        aa_circle(surf, cx, cy, r, (45, 45, 55))
        gfx.aacircle(surf, cx, cy, r, (120, 120, 130))
        pygame.draw.line(surf, (160, 120, 60), (cx, cy -
                         r + 4), (cx + 10, cy - r - 6), 3)
        glow_color = (255, 200, 120)
    elif kind == HEART:
        s = 44
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        aa_circle(surf, s//3, s//3, s//5+6, (240, 80, 100))
        aa_circle(surf, 2*s//3, s//3, s//5+6, (240, 80, 100))
        pts = [(s//8, s//3), (7*s//8, s//3), (s//2, s-6)]
        aa_polygon(surf, pts, (240, 80, 100))
        aa_polygon(surf, pts, (255, 160, 170))
        glow_color = None
    elif kind == HOURGLASS:
        w, h = 36, 50
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(surf, (220, 200, 160),
                         (3, 3, w-6, h-6), width=3, border_radius=8)
        aa_polygon(surf, [(5, 5), (w-5, 5), (w//2, h//2)], (200, 180, 140))
        aa_polygon(surf, [(5, h-5), (w-5, h-5), (w//2, h//2)], (200, 180, 140))
        glow_color = (120, 200, 255)
    elif kind == AMMO:
        w, h = 26, 40
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(surf, (90, 200, 255),
                         (3, 3, w-6, h-6), border_radius=8)
        pygame.draw.rect(surf, (255, 255, 255),
                         (3, 3, w-6, h//2-3), border_radius=8)
        pygame.draw.rect(surf, (0, 0, 0), (3, 3, w-6, h-6),
                         width=2, border_radius=8)
        glow_color = (120, 220, 255)
    else:
        surf = pygame.Surface((24, 24), pygame.SRCALPHA)
        surf.fill((255, 0, 255, 160))
        glow_color = None

    # respect global glow switch
    if not USE_GLOW:
        glow_color = None
    return surf.convert_alpha(), glow_color


def prepare_base_art():
    for kind in [TREASURE, BOMB, HEART, HOURGLASS, AMMO]:
        path = ASSET_PATHS.get(kind)
        if path and os.path.exists(path):
            try:
                surf = pygame.image.load(path).convert_alpha()
                glow_color = None if not USE_GLOW else (
                    (255, 220, 90) if kind == TREASURE else
                    (120, 200, 255) if kind == HOURGLASS else
                    (120, 220, 255) if kind == AMMO else
                    (255, 200, 120) if kind == BOMB else None
                )
            except Exception:
                surf, glow_color = make_vector_art(kind)
        else:
            surf, glow_color = make_vector_art(kind)
        BASE_ART[kind] = {"surf": surf,
                          "glow_color": glow_color, "base_w": surf.get_width()}

# ---------- Sprites ----------


class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.w, self.h = 110, 32
        self.image = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        pygame.draw.rect(self.image, (70, 170, 255),
                         (0, 0, self.w, self.h), border_radius=10)
        pygame.draw.rect(self.image, (255, 255, 255),
                         (6, 6, self.w-12, self.h-12), width=2, border_radius=8)
        self.rect = self.image.get_rect()
        self.rect.midbottom = (W//2, GROUND_Y - 8)
        self.speed = 10

    def update(self, keys):
        dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - \
            (keys[pygame.K_LEFT] or keys[pygame.K_a])
        self.rect.x += dx * self.speed
        self.rect.x = clamp(self.rect.x, 0, W - self.w)


class Falling(pygame.sprite.Sprite):
    def __init__(self, kind, level=1):
        super().__init__()
        self.kind = kind
        self.level = level

        base = BASE_ART[kind]
        base_surf = base["surf"]
        glow_color = base["glow_color"]
        base_w = base["base_w"]

        self.scale = random.uniform(0.7, 1.4)
        new_w = max(12, int(base_surf.get_width() * self.scale))
        new_h = max(12, int(base_surf.get_height() * self.scale))
        self.image = pygame.transform.smoothscale(base_surf, (new_w, new_h))
        self.rect = self.image.get_rect()
        self.rect.midtop = (random.randint(24, W-24), -self.rect.height)

        self.glow = (make_glow(max(6, int(new_w * 0.7)), glow_color)
                     if (USE_GLOW and glow_color) else None)

        base_speed = 3.6 + level * 0.45
        jitter = random.uniform(-0.6, 0.6)
        size_speed_scale = 0.7 + self.scale * 0.8
        self.vy = (base_speed * size_speed_scale) + jitter

        self.phase = random.uniform(0, math.tau)
        self.vx_amp = (0.9 if kind == BOMB else 0.4) * (0.7 + self.scale*0.3)
        self.base_shadow_w = max(20, int(base_w * self.scale))

    def update(self, slow_factor=1.0):
        self.rect.y += self.vy * slow_factor
        self.phase += 0.03
        self.rect.x += math.sin(self.phase) * self.vx_amp
        if self.rect.top > H + 60 or self.rect.right < -60 or self.rect.left > W + 60:
            self.kill()


class Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        w, h = 10, 22
        self.image = pygame.Surface((w, h), pygame.SRCALPHA)
        pts = [(w//2, 0), (0, h), (w, h)]
        aa_polygon(self.image, pts, (255, 255, 255), outline=(0, 0, 0))
        self.rect = self.image.get_rect(center=(x, y))
        self.vy = -14
        self.glow = None  # no glow

    def update(self):
        self.rect.y += self.vy
        if self.rect.bottom < -10:
            self.kill()

# --- Particles (no glow) ---


class Particle(pygame.sprite.Sprite):
    def __init__(self, x, y, color, speed, angle, life, grav=0.35, size=3):
        super().__init__()
        self.size = size
        self.image = pygame.Surface((size*2, size*2), pygame.SRCALPHA)
        pygame.draw.circle(self.image, color, (size, size), size)
        self.rect = self.image.get_rect(center=(x, y))
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.life = self.max_life = life
        self.grav = grav

    def update(self):
        self.vy += self.grav
        self.rect.x += int(self.vx)
        self.rect.y += int(self.vy)
        self.life -= 1
        self.image.set_alpha(int(255 * (self.life / self.max_life)))
        if self.life <= 0:
            self.kill()


class Smoke(pygame.sprite.Sprite):
    def __init__(self, x, y, start=16, end=48, life=22):
        super().__init__()
        self.start, self.end = start, end
        self.life = self.max_life = life
        self.image = pygame.Surface((end*2, end*2), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(x, y))

    def update(self):
        t = 1.0 - self.life / self.max_life
        radius = int(self.start + (self.end - self.start) * t)
        self.image.fill((0, 0, 0, 0))
        col = (90, 90, 90, int(150 * (1 - t)))
        pygame.gfxdraw.filled_circle(
            self.image, self.end, self.end, radius, col)
        self.rect = self.image.get_rect(center=self.rect.center)
        self.life -= 1
        if self.life <= 0:
            self.kill()


class RadialGlow(pygame.sprite.Sprite):
    """Kept for compatibility, but disabled when USE_GLOW=False."""

    def __init__(self, x, y, color=(255, 180, 80), start=24, end=110, life=16):
        super().__init__()
        self.enabled = USE_GLOW
        self.color, self.start, self.end = color, start, end
        self.life = self.max_life = life
        self.image = make_glow(start, color) if self.enabled else pygame.Surface(
            (1, 1), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(x, y))

    def update(self):
        if not self.enabled:
            self.kill()
            return
        t = 1.0 - self.life / self.max_life
        r = int(self.start + (self.end - self.start) * t)
        self.image = make_glow(r, self.color)
        self.rect = self.image.get_rect(center=self.rect.center)
        self.life -= 1
        if self.life <= 0:
            self.kill()

# ---------- Game ----------


class Game:
    def __init__(self):
        pygame.init()
        flags = pygame.SCALED | pygame.RESIZABLE
        try:
            self.screen = pygame.display.set_mode((W, H), flags, vsync=1)
        except TypeError:
            self.screen = pygame.display.set_mode((W, H), flags)
        pygame.display.set_caption("幹林娘出來啊!遊戲")
        self.clock = pygame.time.Clock()

        # Initialize sounds
        self.sounds = {
            "heart": pygame.mixer.Sound(os.path.join("sounds", "heart.mp3")),
            "game_over": pygame.mixer.Sound(os.path.join("sounds", "game_over.mp3")),
            "slow": pygame.mixer.Sound(os.path.join("sounds", "slow.mp3")),
            "shoot": pygame.mixer.Sound(os.path.join("sounds", "shoot.mp3")),
            "bomb_hit": pygame.mixer.Sound(os.path.join("sounds", "bomb_hit.mp3")),
            "bomb_shot": pygame.mixer.Sound(os.path.join("sounds", "bomb_shot.mp3")),
            "treasure": pygame.mixer.Sound(os.path.join("sounds", "treasure.mp3")),
        }

        prepare_base_art()

        self.all_sprites = pygame.sprite.Group()
        self.falls = pygame.sprite.Group()
        self.bullets = pygame.sprite.Group()
        self.fx = pygame.sprite.Group()

        self.player = Player()
        self.all_sprites.add(self.player)

        self.score = 0
        self.lives = 3
        self.level = 1
        self.best_score = 0
        self.ammo = 0
        self.paused = False
        self.game_over = False
        self.fullscreen = False

        self.slow_timer = 0
        self.SLOW_FRAMES = int(FPS * SLOW_SECONDS)   # 12 seconds
        self.slow_factor = SLOW_FACTOR

        self.SPAWN_EVENT = pygame.USEREVENT + 1
        pygame.time.set_timer(self.SPAWN_EVENT, SPAWN_MS)

        self.bg_color = (16, 20, 30)
        self.starfield = self.make_starfield()

    def make_starfield(self):
        sf = pygame.Surface((W, H), pygame.SRCALPHA)
        random.seed(42)
        for _ in range(350):
            x = random.randint(0, W-1)
            y = random.randint(0, H-1)
            a = random.randint(110, 210)
            sf.fill((200, 220, 255, a), (x, y, 2, 2))
        return sf.convert_alpha()

    # ----- Shooting -----
    def try_shoot(self):
        if self.ammo <= 0:
            return
        self.ammo -= 1
        b = Bullet(self.player.rect.centerx, self.player.rect.top - 6)
        self.bullets.add(b)
        self.all_sprites.add(b)
        self.sounds["shoot"].play()

    # ----- Core -----
    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.SCALED)
        else:
            try:
                pygame.display.set_mode(
                    (W, H), pygame.SCALED | pygame.RESIZABLE, vsync=1)
            except TypeError:
                pygame.display.set_mode(
                    (W, H), pygame.SCALED | pygame.RESIZABLE)

    def reset(self):
        self.all_sprites.empty()
        self.falls.empty()
        self.bullets.empty()
        self.fx.empty()
        self.player = Player()
        self.all_sprites.add(self.player)
        self.score = 0
        self.lives = 3
        self.level = 1
        self.paused = False
        self.game_over = False
        self.slow_timer = 0
        self.ammo = 0
        pygame.time.set_timer(self.SPAWN_EVENT, SPAWN_MS)

    def spawn(self):
        p_bomb = clamp(0.20 + self.level * 0.02, 0.20, 0.45)
        p_heart = 0.06
        p_hourglass = 0.07
        p_ammo = 0.07
        p_treasure = 1.0 - (p_bomb + p_heart + p_hourglass + p_ammo)
        r = random.random()
        if r < p_bomb:
            kind = BOMB
        elif r < p_bomb + p_heart:
            kind = HEART
        elif r < p_bomb + p_heart + p_hourglass:
            kind = HOURGLASS
        elif r < p_bomb + p_heart + p_hourglass + p_ammo:
            kind = AMMO
        else:
            kind = TREASURE
        f = Falling(kind, self.level)
        self.falls.add(f)
        self.all_sprites.add(f)

    def level_check(self):
        new_level = 1 + self.score // LEVEL_UP_EVERY
        if new_level > self.level:
            self.level = new_level
            interval = max(420, int(SPAWN_MS * (0.94 ** (self.level - 1))))
            pygame.time.set_timer(self.SPAWN_EVENT, interval)

    def explosion_at(self, x, y):
        if USE_GLOW:
            self.fx.add(RadialGlow(x, y, color=(255, 180, 80),
                        start=24, end=110, life=16))
        for _ in range(20):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(3.5, 8)
            size = random.randint(2, 4)
            life = random.randint(14, 24)
            color = random.choice(
                [(255, 200, 80), (255, 160, 60), (255, 230, 120)])
            self.fx.add(Particle(x, y, color, speed,
                        angle, life, grav=0.35, size=size))
        self.fx.add(Smoke(x, y, start=14, end=60, life=22))

    def apply_collision(self):
        caught = []
        for f in self.falls:
            if f.rect.bottom >= self.player.rect.top and self.player.rect.left - 6 <= f.rect.centerx <= self.player.rect.right + 6:
                caught.append(f)

        for f in caught:
            if f.kind == TREASURE:
                self.sounds["treasure"].play()
                self.score += 1
            elif f.kind == HEART:
                self.sounds["heart"].play()
                self.lives = clamp(self.lives + 1, 0, MAX_LIVES)
            elif f.kind == HOURGLASS:
                self.sounds["slow"].play()
                self.slow_timer = int(FPS * SLOW_SECONDS)
            elif f.kind == AMMO:
                self.ammo = clamp(self.ammo + 1, 0, AMMO_MAX)
            elif f.kind == BOMB:
                self.sounds["bomb_hit"].play()
                self.lives -= 1
                self.explosion_at(f.rect.centerx, self.player.rect.top - 8)
            f.kill()

        for b in list(self.bullets):
            for f in list(self.falls):
                if getattr(f, "kind", None) == BOMB and b.rect.colliderect(f.rect):
                    dy_to_paddle = self.player.rect.top - f.rect.bottom
                    if 0 <= dy_to_paddle <= NEAR_SHOT_BONUS_THRESHOLD_PX:
                        self.score += NEAR_SHOT_BONUS_SCORE
                    else:
                        self.score += NORMAL_BOMB_SHOT_SCORE
                    bx, by = f.rect.center
                    self.sounds["bomb_shot"].play()
                    b.kill()
                    f.kill()
                    self.explosion_at(bx, by)
                    break

        if self.lives <= 0:
            self.game_over = True
            self.best_score = max(self.best_score, self.score)

    def draw_bg(self):
        self.screen.fill((16, 20, 30))
        self.screen.blit(self.starfield, (0, 0))

    def draw_shadows(self):
        draw_shadow(self.screen, self.player.rect.centerx,
                    self.player.rect.bottom, base_w=int(self.player.w*0.9))
        for f in self.falls:
            draw_shadow(self.screen, f.rect.centerx, f.rect.bottom,
                        base_w=max(20, f.base_shadow_w), max_alpha=100)
        for b in self.bullets:
            draw_shadow(self.screen, b.rect.centerx,
                        b.rect.bottom, base_w=18, max_alpha=70)

    def draw_glows(self):
        if not USE_GLOW:
            return
        for b in self.bullets:
            if getattr(b, "glow", None):
                self.screen.blit(b.glow, b.glow.get_rect(
                    center=b.rect.center), special_flags=pygame.BLEND_ADD)
        for f in self.falls:
            if getattr(f, "glow", None):
                self.screen.blit(f.glow, f.glow.get_rect(
                    center=f.rect.center), special_flags=pygame.BLEND_ADD)

    def draw_hud(self):
        draw_text(self.screen, f"Score: {self.score}", 26, 90, 28, color=(
            255, 230, 120), center=False)
        draw_text(self.screen, f"Ammo: {self.ammo}/{AMMO_MAX}", 20,
                  220, 28, color=(200, 240, 255), center=False, bold=True)
        draw_text(self.screen, f"Level: {self.level}", 22,
                  W//2, 28, color=(180, 220, 255), center=True)

        heart_r = 9
        x0 = W - 26 * MAX_LIVES - 12
        for i in range(MAX_LIVES):
            x, y = x0 + 26*i, 28
            c = (235, 80, 100) if i < self.lives else (90, 90, 100)
            aa_circle(self.screen, x-6, y-2, heart_r, c)
            aa_circle(self.screen, x+6, y-2, heart_r, c)
            aa_polygon(self.screen, [(x-16, y-2), (x+16, y-2), (x, y+12)], c)

        if self.slow_timer > 0:
            draw_text(self.screen, "SLOW", 18, W//2, 54, color=(150, 210, 255))

    def run(self):
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        pygame.quit()
                        sys.exit(0)
                    if e.key == pygame.K_p:
                        self.paused = not self.paused
                    if e.key == pygame.K_r:
                        self.reset()
                    if e.key == pygame.K_SPACE and not (self.paused or self.game_over):
                        self.try_shoot()
                    if e.key == pygame.K_f:
                        self.toggle_fullscreen()
                elif e.type == self.SPAWN_EVENT and not (self.paused or self.game_over):
                    self.spawn()

            keys = pygame.key.get_pressed()

            if not self.paused and not self.game_over:
                self.player.update(keys)

                slow = 1.0
                if self.slow_timer > 0:
                    slow = self.slow_factor
                    self.slow_timer -= 1

                for f in list(self.falls):
                    f.update(slow_factor=slow)
                for b in list(self.bullets):
                    b.update()
                for fx in list(self.fx):
                    fx.update()

                self.apply_collision()
                self.level_check()

            # draw
            self.draw_bg()
            self.draw_shadows()
            self.falls.draw(self.screen)
            self.bullets.draw(self.screen)
            self.screen.blit(self.player.image, self.player.rect)
            self.draw_glows()
            for fx in self.fx:
                if isinstance(fx, RadialGlow) and USE_GLOW:
                    self.screen.blit(fx.image, fx.rect,
                                     special_flags=pygame.BLEND_ADD)
                else:
                    self.screen.blit(fx.image, fx.rect)

            if self.paused:
                draw_text(self.screen, "Paused", 40, W //
                          2, H//2, color=(200, 220, 255))
                draw_text(self.screen, "Press P to resume", 20,
                          W//2, H//2 + 44, color=(200, 200, 210))
            if self.game_over:
                draw_text(self.screen, "Game Over", 48, W//2,
                          H//2 - 10, color=(255, 120, 130))
                draw_text(self.screen, f"Score: {self.score}  Best: {self.best_score}",
                          24, W//2, H//2 + 36, color=(255, 230, 160))
                draw_text(self.screen, "Press R to restart, ESC to quit",
                          18, W//2, H//2 + 70, color=(210, 220, 230))

            self.draw_hud()
            pygame.display.flip()
            self.clock.tick(FPS)


def main():
    Game().run()


if __name__ == "__main__":
    main()
