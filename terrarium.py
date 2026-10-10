#!/usr/bin/env python3
"""
Terrarium: a little shelf of living pixel environments.

Each environment is a tiny world with its own physics, its own mood, and a loop where
growth and decay pull against each other, so it never fills up and never dies out.
Leave it running on a side screen like a desk plant.

    python terrarium.py              # the shelf: every environment side by side
    python terrarium.py --mini       # frameless always-on-top mini window, bottom-right
    python terrarium.py --headless 3000   # no window: run each env and print vital signs

Keys:  Tab grid/single · M mini · ←/→ switch env · Space pause · click poke (Millpond: click casts / strikes, hold reels)
       R reseed · A auto-cycle · L scanlines · N labels · T on-top · O opacity · S snapshot · Esc
In mini mode: drag to move, right-click to poke, wheel to switch.
"""
from __future__ import annotations

import argparse
import colorsys
import math
import os
import random
import sys
import time
from collections import Counter

W, H = 96, 64                                       # every environment is 96x64 pixels


# ── colour helpers ───────────────────────────────────────────────────────────
def mix(a, b, f):
    return tuple(round(a[k] + (b[k] - a[k]) * f) for k in range(3))


def ramp(stops, n):
    out = []
    for i in range(n):
        p = i / max(1, n - 1) * (len(stops) - 1)
        a = int(p)
        b = min(a + 1, len(stops) - 1)
        out.append(mix(stops[a], stops[b], p - a))
    return out


def shade(c, f):
    return tuple(max(0, min(255, round(v * f))) for v in c)


def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1, max(0., min(1., s)), max(0., min(1., v)))
    return round(r * 255), round(g * 255), round(b * 255)


class Env:
    """An environment owns a 96x64 buffer of palette indices plus the palette itself."""
    name, mood, tempo = "env", "", 20               # tempo = simulation steps per second
    glow: tuple = ()                                # palette indices that bloom

    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.pix = bytearray(W * H)
        self.palette = [(0, 0, 0)] * 256
        self.steps = 0

    def step(self):
        self.steps += 1

    def animate(self, t):
        """Per-frame palette tweaks (shimmer, flicker); cheap, no pixel loop."""

    def frame(self):
        return self.pix

    def poke(self, x, y):
        """React to a click at pixel (x, y)."""

    def release(self):
        """The mouse button that poked this world has been let go."""

    def status(self):
        """Lines of text to show on the tile (most worlds have nothing to say)."""
        return ()

    def vitals(self):
        return {}


# ── Tidepool ─────────────────────────────────────────────────────────────────
class Tidepool(Env):
    """Kelp grows toward the light, ages and rots. Rot sinks as detritus, composts the sand,
    and rich sand sprouts new kelp. Fish graze the detritus; bubbles rise from rich sand and leaves."""
    name, mood, tempo = "Tidepool", "calm", 18
    WATER, SAND, RICH, KELP, DETRITUS, BUBBLE, ROCK = range(7)
    glow = (52, 53, 54, 55)

    def __init__(self, seed=None):
        super().__init__(seed)
        r = self.rng
        n = W * H
        self.type = bytearray(n)
        self.life = bytearray(n)
        self.age = bytearray(n)
        self.clock = bytearray(n)
        self.shade = bytes(r.randrange(4) for _ in range(n))
        self.tick = 1
        self.band = bytes(min(15, y * 16 // H) for y in range(H))
        self.build_palette()
        for i in range(n):
            self.paint(i)
        ph = r.random() * 6
        for x in range(W):
            top = H - int(7 + 2.5 * math.sin(x / 9 + ph) + 1.5 * math.sin(x / 4.3 + 2 * ph))
            for y in range(top, H):
                self.set(y * W + x, self.SAND)
        for _ in range(2):
            cx, cy, rad = r.randrange(8, W - 8), H - r.randrange(6, 10), r.randrange(3, 6)
            for y in range(cy - rad, H):
                for x in range(cx - rad - 2, cx + rad + 3):
                    if 0 <= x < W and ((x - cx) / (rad + 2)) ** 2 + ((y - cy) / rad) ** 2 <= 1:
                        self.set(y * W + x, self.ROCK)
        for _ in range(8):
            self.sprout(r.randrange(W), grown=True)
        for _ in range(12):
            i = self.floor(r.randrange(W))
            if i >= 0 and self.type[i] == self.SAND:
                self.set(i, self.RICH)
        self.fish = [self.new_fish() for _ in range(5)]

    def build_palette(self):
        p = self.palette
        self.water = [mix((46, 152, 168), (5, 20, 46), b / 15) for b in range(16)]
        p[0:16] = self.water
        for s in range(4):
            p[16 + s] = shade((196, 172, 122), .9 + s * .06)
            p[24 + s] = shade((128, 110, 70), .9 + s * .06)
            p[48 + s] = shade((112, 92, 62), .85 + s * .08)
            p[52 + s] = shade((205, 242, 250), .8 + s * .07)
            p[56 + s] = shade((66, 70, 84), .85 + s * .08)
        p[32:48] = ramp([(140, 214, 96), (62, 156, 64), (38, 98, 46), (96, 86, 40)], 16)
        p[64:67] = [(255, 204, 96), (245, 132, 62), (170, 70, 50)]
        p[68:71] = [(232, 242, 255), (150, 192, 242), (88, 120, 190)]

    def paint(self, i):
        t = self.type[i]
        if t == self.WATER:
            v = self.band[i // W]
        elif t == self.KELP:
            v = 32 + (self.age[i] >> 4)
        else:
            v = (0, 16, 24, 0, 48, 52, 56)[t] + self.shade[i]
        self.pix[i] = v

    def set(self, i, t, life=0, age=0):
        self.type[i] = t
        self.life[i] = life
        self.age[i] = age
        self.clock[i] = self.tick
        self.paint(i)

    def swap(self, i, j):
        T, L, A = self.type, self.life, self.age
        T[i], T[j] = T[j], T[i]
        L[i], L[j] = L[j], L[i]
        A[i], A[j] = A[j], A[i]
        self.clock[i] = self.clock[j] = self.tick
        self.paint(i)
        self.paint(j)

    def floor(self, x):
        for y in range(H):
            if self.type[y * W + x] != self.WATER:
                return y * W + x
        return -1

    def sprout(self, x, grown=False):
        r = self.rng
        i = self.floor(x)
        if i < W or self.type[i] not in (self.SAND, self.RICH):
            return
        height = r.randint(10, int(H * .72))
        if not grown:
            self.set(i - W, self.KELP, life=height)
            return
        y = i // W
        for k in range(1, r.randint(4, height)):
            if y - k < 1:
                break
            if r.random() < .2:
                x = max(0, min(W - 1, x + r.choice((-1, 1))))
            j = (y - k) * W + x
            if self.type[j] != self.WATER:
                break
            self.set(j, self.KELP, life=0, age=r.randrange(220))
        self.life[j] = r.randint(0, 12)

    def new_fish(self):
        r = self.rng
        return [r.uniform(5, W - 5), r.uniform(8, H - 22), r.choice((-1, 1)) * r.uniform(.12, .3),
                r.uniform(6, H - 20), r.randrange(2)]

    def supported(self, i, x, y):
        if y == H - 1:
            return True
        T = self.type
        b = i + W
        if T[b] != self.WATER and T[b] != self.BUBBLE and T[b] != self.DETRITUS:
            return True
        return (x > 0 and T[b - 1] == self.KELP) or (x < W - 1 and T[b + 1] == self.KELP)

    def step(self):
        super().step()
        T, L, A, C = self.type, self.life, self.age, self.clock
        WATER, SAND, RICH, KELP, DETRITUS, BUBBLE = self.WATER, self.SAND, self.RICH, self.KELP, self.DETRITUS, self.BUBBLE
        r = self.rng.random
        self.tick = tick = 3 - self.tick
        for y in range(H):
            row = y * W
            for x in range(W):
                i = row + x
                t = T[i]
                if t == WATER or t == SAND or t == self.ROCK or C[i] == tick:
                    continue
                C[i] = tick
                if t == KELP:
                    if A[i] < 255 and r() < .06:
                        A[i] += 1
                        self.paint(i)
                    if not self.supported(i, x, y):
                        if r() < .1:
                            self.set(i, DETRITUS)       # cut loose: drifts down as rot
                        continue
                    if L[i] and y > 1 and r() < .05:
                        nx = x + (int(r() * 3) - 1 if r() < .25 else 0)
                        j = i - W + (nx - x) if 0 <= nx < W else i - W
                        if T[j] == WATER:
                            self.set(j, KELP, life=L[i] - 1)
                            L[i] = 0
                    elif y > 0 and T[i - W] == WATER and r() < .0006:
                        self.set(i - W, BUBBLE)          # photosynthesis
                    if A[i] == 255 and r() < .004:
                        self.set(i, DETRITUS)
                elif t == BUBBLE:
                    if y == 0:
                        self.set(i, WATER)              # pop at the surface
                        continue
                    d = int(r() * 3) - 1 if r() < .35 else 0
                    j = i - W + d if 0 <= x + d < W else i - W
                    if T[j] == WATER:
                        self.swap(i, j)
                    elif T[i - W] == WATER:
                        self.swap(i, i - W)
                    elif r() < .1:
                        self.set(i, WATER)
                elif t == DETRITUS:
                    if r() > .4 or y == H - 1:
                        continue
                    b = i + W
                    bt = T[b]
                    if bt == WATER or bt == BUBBLE:
                        d = int(r() * 3) - 1
                        j = b + d if 0 <= x + d < W else b
                        self.swap(i, j if T[j] == WATER else b)
                    elif bt == SAND or bt == RICH:
                        if r() < .5:
                            self.set(b, RICH)           # compost
                        self.set(i, WATER)
                    else:
                        d = 1 if r() < .5 else -1
                        if 0 <= x + d < W and T[b + d] == WATER:
                            self.swap(i, b + d)
                        elif r() < .01:
                            self.set(i, WATER)
                elif t == RICH:
                    if y > 3 and T[i - W] == WATER:
                        if r() < .002 and self.uncrowded(x, y):
                            self.sprout(x)
                            self.set(i, SAND)
                        elif r() < .002:
                            self.set(i - W, BUBBLE)
        self.move_fish()

    def uncrowded(self, x, y):
        T = self.type
        for yy in range(max(0, y - 4), y):
            for xx in range(max(0, x - 3), min(W, x + 4)):
                if T[yy * W + xx] == self.KELP:
                    return False
        return True

    def move_fish(self):
        r = self.rng
        T = self.type
        for f in self.fish:
            x, y, vx, ty, kind = f
            x += vx
            y += (ty - y) * .02 + math.sin(self.steps * .2 + x) * .03
            if r.random() < .01:
                ty = r.uniform(4, H - 18)
            if r.random() < .004:
                vx = -vx
            ax = int(x + (2 if vx > 0 else -2))
            iy = max(0, min(H - 1, int(y)))
            if not 0 <= ax < W or T[iy * W + ax] in (self.SAND, self.RICH, self.ROCK):
                vx = -vx
                x = max(1, min(W - 2, x))
            if T[iy * W + max(0, min(W - 1, int(x)))] in (self.SAND, self.RICH, self.ROCK):
                y -= .6
                ty = min(ty, y - 4)
            i = iy * W + max(0, min(W - 1, int(x)))
            if T[i] == self.DETRITUS:
                self.set(i, self.WATER)                 # grazing
            f[:] = [x, y, vx, ty, kind]

    def frame(self):
        out = bytearray(self.pix)
        for x, y, vx, _, kind in self.fish:
            d = 1 if vx > 0 else -1
            ix, iy = int(x), int(y)
            tail_y = iy + (1 if (self.steps // 4) % 2 and 0 < iy < H - 1 else 0)
            for k, (px, py) in enumerate(((ix, iy), (ix - d, iy), (ix - 2 * d, tail_y))):
                if 0 <= px < W and 0 <= py < H:
                    out[py * W + px] = 64 + kind * 4 + k
        return out

    def animate(self, t):
        for b in range(8):                              # caustic shimmer near the surface
            self.palette[b] = shade(self.water[b], 1 + .08 * math.sin(t * 1.1 + b * .9) * (1 - b / 8))

    def poke(self, x, y):
        for _ in range(14):                             # feed the pool
            px, py = x + self.rng.randint(-3, 3), y + self.rng.randint(-2, 2)
            if 0 <= px < W and 0 <= py < H and self.type[py * W + px] == self.WATER:
                self.set(py * W + px, self.DETRITUS if self.rng.random() < .6 else self.BUBBLE)

    def vitals(self):
        T = self.type
        return {"kelp": T.count(self.KELP), "rot": T.count(self.DETRITUS), "rich": T.count(self.RICH),
                "bubbles": T.count(self.BUBBLE)}


# ── Ember Forest ─────────────────────────────────────────────────────────────
class EmberForest(Env):
    """Top-down forest-fire model: trees spread and mature, lightning and drifting embers
    start fires that race downwind, ash crumbles back into soil."""
    name, mood, tempo = "Ember Forest", "restless", 24
    SOIL, TREE, FIRE, ASH = range(4)
    glow = tuple(range(60, 68)) + (80,)

    def __init__(self, seed=None):
        super().__init__(seed)
        r = self.rng
        n = W * H
        self.type = bytearray(n)
        self.age = bytearray(n)
        self.life = bytearray(n)
        self.clock = bytearray(n)
        self.noise = bytes(r.randrange(4) for _ in range(n))
        self.tick = 1
        self.wind = r.random() * math.tau
        self.embers = []
        self.n4 = [tuple(j for j, ok in ((i - W, i >= W), (i + W, i < n - W), (i - 1, i % W > 0), (i + 1, i % W < W - 1)) if ok)
                   for i in range(n)]
        p = self.palette
        for s in range(4):
            p[s] = shade((40, 32, 22), .85 + s * .1)
            p[70 + s] = shade((96, 92, 86), .8 + s * .12)
        for a, c in enumerate(ramp([(168, 220, 96), (74, 164, 62), (30, 104, 48), (18, 70, 42)], 12)):
            for s in range(4):
                p[8 + a * 4 + s] = shade(c, .88 + s * .08)
        self.fire = ramp([(120, 16, 0), (230, 60, 0), (255, 140, 20), (255, 230, 140)], 12)
        p[80] = (255, 210, 110)
        for i in range(n):
            if r.random() < .5:
                self.type[i] = self.TREE
                self.age[i] = r.randrange(12)
            self.paint(i)

    def paint(self, i):
        t = self.type[i]
        if t == self.TREE:
            v = 8 + self.age[i] * 4 + self.noise[i]
        elif t == self.FIRE:
            v = 60 + (i * 7 + self.life[i]) % 8
        elif t == self.ASH:
            v = 70 + self.noise[i]
        else:
            v = self.noise[i]
        self.pix[i] = v

    def ignite(self, i):
        self.type[i] = self.FIRE
        self.life[i] = self.rng.randint(2, 4)
        self.clock[i] = self.tick
        self.paint(i)

    def step(self):
        super().step()
        T, A, L, C, N4 = self.type, self.age, self.life, self.clock, self.n4
        SOIL, TREE, FIRE, ASH = self.SOIL, self.TREE, self.FIRE, self.ASH
        r = self.rng.random
        self.tick = tick = 3 - self.tick
        self.wind += (r() - .5) * .06
        wx, wy = math.cos(self.wind), math.sin(self.wind)
        for i in range(W * H):
            t = T[i]
            if C[i] == tick:
                continue
            if t == TREE:
                if A[i] < 11 and r() < .008:
                    A[i] += 1
                    self.paint(i)
                if r() < 2.5e-6:
                    self.ignite(i)                      # lightning
            elif t == SOIL:
                if r() < .006:
                    nb = N4[i]
                    if T[nb[int(r() * len(nb))]] == TREE or r() < .06:
                        T[i] = TREE
                        A[i] = 0
                        self.paint(i)
            elif t == FIRE:
                x, y = i % W, i // W
                for j in N4[i]:
                    if T[j] == TREE:
                        dx, dy = j % W - x, j // W - y
                        if r() < .45 + A[j] * .035 + (dx * wx + dy * wy) * .3:
                            self.ignite(j)
                if r() < .04:
                    self.embers.append([x + .5, y + .5, wx * .4 + (r() - .5) * .4, wy * .4 + (r() - .5) * .4, 8 + int(r() * 24)])
                L[i] -= 1
                if L[i] == 0:
                    T[i] = ASH
                self.paint(i)
            elif t == ASH:
                if r() < .012:
                    T[i] = SOIL
                    self.paint(i)
        alive = []
        for e in self.embers:
            e[0] += e[2]
            e[1] += e[3]
            e[4] -= 1
            if not (0 <= e[0] < W and 0 <= e[1] < H):
                continue
            if e[4] <= 0:
                j = int(e[1]) * W + int(e[0])
                if T[j] == TREE and r() < .12:
                    self.ignite(j)                      # spot fire
                continue
            alive.append(e)
        self.embers = alive[-200:]

    def frame(self):
        out = bytearray(self.pix)
        for x, y, *_ in self.embers:
            out[int(y) * W + int(x)] = 80
        return out

    def animate(self, t):
        rnd = self.rng.random
        for k in range(8):
            self.palette[60 + k] = self.fire[int(rnd() ** .7 * 11.99)]

    def poke(self, x, y):
        j = y * W + x
        if self.type[j] == self.TREE:
            self.ignite(j)
        else:
            for dy in range(-3, 4):
                for dx in range(-3, 4):
                    px, py = x + dx, y + dy
                    if 0 <= px < W and 0 <= py < H and dx * dx + dy * dy <= 9 and self.type[py * W + px] != self.FIRE:
                        k = py * W + px
                        self.type[k], self.age[k] = self.TREE, 0
                        self.paint(k)

    def vitals(self):
        T = self.type
        return {"trees": T.count(self.TREE), "fire": T.count(self.FIRE), "ash": T.count(self.ASH),
                "embers": len(self.embers)}


# ── Crystal Garden ───────────────────────────────────────────────────────────
class Crystal(Env):
    """Packard-style snowflakes on a hex lattice: an empty cell freezes when the number of frozen
    neighbours is in the bloom's rule. Each bloom grows, holds, melts away, and a new one begins
    with a new rule, palette and seed layout."""
    name, mood, tempo = "Crystal Garden", "focused", 14
    CW, CH = 48, 32                                 # hex cells, each drawn 2x2 with odd rows offset
    RULES = [(1,), (1,), (1, 3), (1, 4), (1, 3, 4), (1, 5)]
    FAMILIES = [.55, .78, .42, .09, .93, .62]       # ice, amethyst, jade, amber, rose, sky
    glow = tuple(range(16, 80))

    def __init__(self, seed=None):
        super().__init__(seed)
        n = self.CW * self.CH
        self.gen = [0] * n
        self.layers = {}
        self.nb = [self.hex_neighbours(c % self.CW, c // self.CW) for c in range(n)]
        self.state, self.timer, self.g = "rest", 6, 0
        self.frontier = set()
        self.blooms = 0
        self.rule = (1,)
        self.base = [(0, 0, 0)] * 64
        self.palette[0] = (9, 10, 18)
        self.palette[1] = (26, 28, 46)
        for c in range(n):
            self.draw(c)

    def hex_neighbours(self, x, y):
        offs = ((-1, 0), (1, 0), (-1, -1), (0, -1), (-1, 1), (0, 1)) if y % 2 == 0 else \
               ((-1, 0), (1, 0), (0, -1), (1, -1), (0, 1), (1, 1))
        return tuple((y + dy) * self.CW + x + dx for dx, dy in offs
                     if 0 <= x + dx < self.CW and 0 <= y + dy < self.CH)

    def draw(self, c):
        x, y = c % self.CW, c // self.CW
        px, py = x * 2 + (y & 1), y * 2
        g = self.gen[c]
        for dy in (0, 1):
            for dx in (0, 1):
                if px + dx < W:
                    self.pix[(py + dy) * W + px + dx] = 16 + (g * 3) % 64 if g else (1 if dx == dy == 0 else 0)

    def freeze(self, c, g):
        self.gen[c] = g
        self.layers.setdefault(g, []).append(c)
        self.draw(c)

    def new_bloom(self, seeds=None):
        r = self.rng
        self.blooms += 1
        self.rule = r.choice(self.RULES)
        hue = r.choice(self.FAMILIES) + r.uniform(-.03, .03)
        self.base = [hsv(hue + .07 * math.sin(k / 64 * math.tau), .25 + .35 * (.5 + .5 * math.sin(k / 64 * math.tau * 2)),
                         .62 + .38 * (.5 + .5 * math.cos(k / 64 * math.tau))) for k in range(64)]
        if seeds is None:
            count = r.choice((1, 1, 1, 2, 3))
            if count == 1:
                seeds = [(self.CH // 2) * self.CW + self.CW // 2]
            else:
                seeds = [r.randrange(6, self.CH - 6) * self.CW + r.randrange(8, self.CW - 8) for _ in range(count)]
        self.g = 1
        for c in seeds:
            self.freeze(c, 1)
            self.frontier.update(k for k in self.nb[c] if not self.gen[k])
        self.state = "grow"

    def step(self):
        super().step()
        gen, nb = self.gen, self.nb
        if self.state == "rest":
            self.timer -= 1
            if self.timer <= 0:
                self.new_bloom()
        elif self.state == "grow":
            self.g += 1
            rule = self.rule
            grow = [c for c in self.frontier if not gen[c] and sum(1 for k in nb[c] if gen[k]) in rule]
            for c in grow:
                self.freeze(c, self.g)
            self.frontier = {k for c in grow for k in nb[c] if not gen[k]}
            if not grow or self.g >= 90:
                self.state, self.timer = "hold", self.tempo * 4
        elif self.state == "hold":
            self.timer -= 1
            if self.timer <= 0:
                inward = self.rng.random() < .5         # unravel from the tips, or hollow out from the heart
                self.melt = sorted(self.layers, reverse=not inward)
                self.state = "melt"
        elif self.state == "melt":
            for _ in range(1 + len(self.melt) // 30):
                if not self.melt:
                    break
                for c in self.layers.pop(self.melt.pop(0), []):
                    gen[c] = 0
                    self.draw(c)
            if not self.melt:
                self.frontier.clear()
                self.state, self.timer = "rest", int(self.tempo * 1.5)

    def animate(self, t):
        off = int(t * 10)
        p = self.palette
        for k in range(64):
            p[16 + k] = self.base[(k - off) % 64]

    def poke(self, x, y):
        cy = max(0, min(self.CH - 1, y // 2))
        cx = max(0, min(self.CW - 1, (x - (cy & 1)) // 2))
        c = cy * self.CW + cx
        if self.state == "rest":
            self.new_bloom([c])
        elif self.state == "grow" and not self.gen[c]:
            self.freeze(c, self.g)
            self.frontier.update(k for k in self.nb[c] if not self.gen[k])

    def vitals(self):
        return {"frozen": sum(1 for g in self.gen if g), "state": self.state, "blooms": self.blooms}


# ── Pulse ────────────────────────────────────────────────────────────────────
class Pulse(Env):
    """A Greenberg-Hastings excitable medium: resting cells fire when a neighbour fires, then
    stay refractory for a while. Imperfect propagation breaks wavefronts, and broken fronts curl
    into self-sustaining spirals. Propagation drifts slowly between crisp geometric diamonds
    and organic turbulence."""
    name, mood, tempo = "Pulse", "hypnotic", 22
    R = 18
    glow = (1, 2, 3)

    def __init__(self, seed=None):
        super().__init__(seed)
        n = W * H
        self.n4 = [((i - W) % n, (i + W) % n, i - i % W + (i - 1) % W, i - i % W + (i + 1) % W) for i in range(n)]
        self.active = []
        self.hue = self.rng.random()
        for _ in range(6):
            self.excite(self.rng.randrange(n), 1)

    def excite(self, i, rad):
        st = self.pix
        x, y = i % W, i // W
        for dy in range(-rad, rad + 1):
            for dx in range(-rad, rad + 1):
                j = ((y + dy) % H) * W + (x + dx) % W
                if st[j] == 0:
                    st[j] = 1
                    self.active.append(j)

    def step(self):
        super().step()
        st, n4, R = self.pix, self.n4, self.R
        r = self.rng.random
        p = .86 + .12 * math.sin(self.steps / 900)
        fired = set()
        for i in self.active:
            if st[i] == 1:
                for j in n4[i]:
                    if st[j] == 0 and r() < p:
                        fired.add(j)
        nxt = []
        for i in self.active:
            s = st[i] + 1
            if s > R:
                st[i] = 0
            else:
                st[i] = s
                nxt.append(i)
        for j in fired:
            st[j] = 1
            nxt.append(j)
        self.active = nxt
        if r() < .02:
            self.excite(int(r() * W * H), 1)            # a pacemaker blinks somewhere
        if r() < .004:                                  # tear a hole: open wavefronts curl into spirals
            x0, y0, s = int(r() * W), int(r() * H), 8 + int(r() * 10)
            for y in range(y0, y0 + s):
                for x in range(x0, x0 + s):
                    st[(y % H) * W + x % W] = 0
            self.active = [i for i in self.active if st[i]]

    def animate(self, t):
        h = self.hue + t * .004
        p = self.palette
        p[0] = hsv(h + .5, .5, .07)
        p[1] = (255, 252, 240)
        for k in range(2, self.R + 1):
            f = (k - 2) / (self.R - 2)
            p[k] = hsv(h + f * .35, .5 + .35 * f, (1 - f) ** 1.6 * .92 + .07)

    def poke(self, x, y):
        self.excite(y * W + x, 2)

    def vitals(self):
        return {"active": len(self.active), "firing": self.pix.count(1)}


# ── Firefly Meadow ───────────────────────────────────────────────────────────
class Fireflies(Env):
    """Pulse-coupled oscillators: each firefly flashes on its own rhythm, and every flash nudges the
    fireflies nearby a little closer to flashing. Coupling waxes and wanes, so the meadow drifts from
    scattered twinkling to waves of light rolling across the grass. Fireflies that flash together court
    and lay glowing eggs in the grass; the eggs hatch, and old fireflies fade out."""
    name, mood, tempo = "Firefly Meadow", "dreamy", 20
    glow = (16, 17, 18, 19, 41, 42, 43, 44, 45, 46, 48, 50)
    TOP, MAX = 22, 64                               # fireflies keep below TOP; cap on fireflies + eggs
    X, Y, VX, VY, PHASE, PERIOD, AGE, LIFE, FLASH = range(9)

    def __init__(self, seed=None):
        super().__init__(seed)
        r = self.rng
        self.ph = ph = r.random() * 6
        p = self.palette
        p[0:16] = ramp([(8, 10, 30), (20, 30, 64), (38, 62, 88)], 16)
        p[20:24] = [shade((14, 22, 30), .8 + s * .12) for s in range(4)]
        p[24:32] = ramp([(10, 26, 22), (26, 62, 42), (84, 128, 96)], 8)
        p[32:36] = [shade((8, 16, 14), .8 + s * .12) for s in range(4)]
        p[40] = (44, 50, 32)                        # a firefly between flashes
        p[41:46] = ramp([(250, 255, 196), (200, 244, 96), (110, 160, 40)], 5)
        p[46] = (64, 92, 28)                        # flash halo
        p[50], p[51] = (238, 234, 210), (196, 194, 180)
        hz = [26 + int(3 * math.sin(x / 11 + ph) + 2 * math.sin(x / 5 + 2 * ph)) for x in range(W)]
        for _ in range(r.randint(6, 11)):           # conifers on the ridge
            cx, h = r.randrange(W), r.randint(4, 11)
            top = hz[cx] - h
            for dx in range(-h // 2, h // 2 + 1):
                if 0 <= cx + dx < W:
                    hz[cx + dx] = min(hz[cx + dx], top + abs(dx) * 2)
        self.meadow = [H - 12 + int(1.5 * math.sin(x / 7 + ph)) for x in range(W)]
        for y in range(H):
            for x in range(W):
                if y < hz[x]:
                    v = min(15, y * 16 // 30)
                elif y < self.meadow[x]:
                    v = 20 + r.randrange(4)
                else:
                    v = 32 + r.randrange(4)
                self.pix[y * W + x] = v
        for _ in range(45):
            x, y = r.randrange(W), r.randrange(H)
            if y < hz[x] - 1:
                self.pix[y * W + x] = 16 + r.randrange(4)
        mx, my = r.randrange(10, W - 10), r.randrange(5, 10)
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                if dx * dx + dy * dy <= 10 and my + dy < hz[mx + dx]:
                    self.pix[(my + dy) * W + mx + dx] = 51 if (dx, dy) in ((1, -1), (-1, 1), (0, 2)) else 50
        self.blades = [(x, self.meadow[x] + r.randrange(3), r.randint(3, 9), r.random() * 6)
                       for x in range(W) for _ in range(2) if r.random() < .8]
        self.grass, self.grass_at = None, -1
        self.flies = [self.new_fly(r.uniform(2, W - 2), r.uniform(self.TOP, H - 4)) for _ in range(22)]
        for f in self.flies:
            f[self.AGE] = r.randrange(f[self.LIFE])
        self.eggs = []
        self.eps = 0.

    def new_fly(self, x, y, phase=None):
        r = self.rng
        return [x, y, 0., 0., r.random() if phase is None else phase, r.uniform(34, 44), 0, r.randint(1600, 3200), 0]

    def step(self):
        super().step()
        r = self.rng.random
        X, Y, VX, VY, PHASE, PERIOD, AGE, LIFE, FLASH = range(9)
        self.eps = eps = .003 + .06 * (.5 + .5 * math.sin(self.steps / 1400 + self.ph)) ** 2
        flashed = []
        for f in self.flies:
            f[VX] = f[VX] * .94 + (r() - .5) * .07
            f[VY] = f[VY] * .94 + (r() - .5) * .05
            f[X] += f[VX]
            f[Y] += f[VY]
            if not 1 <= f[X] < W - 1:
                f[VX], f[X] = -f[VX], max(1., min(W - 1.01, f[X]))
            if not self.TOP <= f[Y] < H - 3:
                f[VY], f[Y] = -f[VY], max(self.TOP, min(H - 3.01, f[Y]))
            f[AGE] += 1
            if f[FLASH]:
                f[FLASH] -= 1
            f[PHASE] += 1 / f[PERIOD]
            if f[PHASE] >= 1:
                f[PHASE], f[FLASH] = 0., 5
                flashed.append(f)
        for f in flashed:                           # each flash pulls nearby, nearly-ready fireflies forward
            x, y = f[X], f[Y]
            for g in self.flies:
                if g[PHASE] > .2 and abs(g[X] - x) < 16 and abs(g[Y] - y) < 12:
                    g[PHASE] += eps * (1 + g[PHASE])
        crowd = len(self.flies) + len(self.eggs)
        for f in flashed:                           # flashing in unison is courtship; easier when the meadow is sparse
            for g in self.flies:
                if g is not f and g[FLASH] >= 3 and abs(f[X] - g[X]) < 8 and abs(f[Y] - g[Y]) < 6 \
                        and crowd < self.MAX and r() < .2 + .6 * (1 - crowd / self.MAX):
                    ex = int(f[X])
                    self.eggs.append([ex, self.meadow[ex] + 1 + int(r() * 6), 500 + int(r() * 500)])
                    crowd += 1
                    break
        self.flies = [f for f in self.flies if f[AGE] < f[LIFE]]
        waiting = []
        for e in self.eggs:
            e[2] -= 1
            if e[2] <= 0:
                self.flies.append(self.new_fly(e[0] + .5, e[1] - 2.))
            else:
                waiting.append(e)
        self.eggs = waiting
        if len(self.flies) < 10 and r() < .01:      # a wanderer drifts in from the edge
            self.flies.append(self.new_fly(1. if r() < .5 else W - 2., self.TOP + r() * (H - 4 - self.TOP)))

    def frame(self):
        if self.grass_at != self.steps:             # sway the grass once per step, not per frame
            g = bytearray(self.pix)
            t = self.steps * .045
            for x, base, h, ph in self.blades:
                sway = 1.6 * math.sin(t + x * .12 + ph) + .6 * math.sin(t * 2.3 + ph)
                for k in range(h):
                    px = x + round(sway * (k / h) ** 2)
                    if 0 <= px < W and base - k < H:
                        g[(base - k) * W + px] = 24 + k * 8 // h
            self.grass, self.grass_at = g, self.steps
        out = bytearray(self.grass)
        for x, y, _ in self.eggs:
            if y < H:
                out[y * W + x] = 48
        for f in self.flies:
            i = int(f[self.Y]) * W + int(f[self.X])
            fl = f[self.FLASH]
            if fl:
                out[i] = 46 - fl
                if fl >= 3:
                    for j in (i - 1, i + 1, i - W, i + W):
                        out[j] = 46
            else:
                out[i] = 40
        return out

    def animate(self, t):
        p = self.palette
        for k in range(4):
            p[16 + k] = shade((210, 216, 255), .55 + .45 * math.sin(t * (1.1 + k * .37) + k * 2.1))
        p[48] = mix((34, 60, 28), (150, 220, 96), .5 + .5 * math.sin(t * 1.7))

    def poke(self, x, y):
        room = self.MAX - len(self.flies) - len(self.eggs)
        for _ in range(min(5, max(0, room))):       # release a little choir that flashes together
            self.flies.append(self.new_fly(max(1., min(W - 2., x + self.rng.uniform(-3, 3))),
                                           max(self.TOP, min(H - 4., y + self.rng.uniform(-2, 2))), .98))

    def vitals(self):
        n = len(self.flies)
        c = sum(math.cos(f[self.PHASE] * math.tau) for f in self.flies)
        s = sum(math.sin(f[self.PHASE] * math.tau) for f in self.flies)
        return {"fireflies": n, "eggs": len(self.eggs), "sync": round(math.hypot(c, s) / max(1, n), 2),
                "coupling": round(self.eps, 3)}


# ── Slime Mold ───────────────────────────────────────────────────────────────
class SlimeMold(Env):
    """Physarum: hundreds of tiny agents each sniff the scent trail ahead (left, centre, right), turn
    toward the strongest, step forward and leave scent behind. Scent spreads and evaporates, and the
    agents knit themselves into a network of veins between oat flakes. Food makes the mould grow;
    when it runs out the mould starves and pulls back until new oats fall."""
    name, mood, tempo = "Slime Mold", "curious", 18
    glow = tuple(range(44, 64)) + (64, 65, 66, 67)
    DIRS, SA, RA, SO = 32, 4, 3, 4                  # headings, sensor angle, turn step, sensor distance
    FULL, MAX = 500, 700                            # agent energy when fed; population cap

    def __init__(self, seed=None):
        super().__init__(seed)
        r = self.rng
        n = W * H
        self.trail = bytearray(n)
        self.lane_mask = int.from_bytes(b"\xff\x00" * n, "little")
        self.dx = [math.cos(k / self.DIRS * math.tau) for k in range(self.DIRS)]
        self.dy = [math.sin(k / self.DIRS * math.tau) for k in range(self.DIRS)]
        self.decay = bytes(max(0, v * 93 // 100 - 1) for v in range(256))
        self.shades = bytes(min(63, v >> 2) for v in range(256))
        self.base = ramp([(16, 20, 22), (44, 40, 20), (150, 108, 26), (244, 196, 64), (255, 246, 196)], 64)
        self.palette[0:64] = self.base
        self.palette[64:68] = [shade((236, 222, 186), .8 + s * .07) for s in range(4)]
        self.food = {}                              # pixel -> [amount, oat id]
        self.oats = 0
        self.timer = 0
        cx, cy = r.uniform(20, W - 20), r.uniform(16, H - 16)
        self.agents = [[cx + r.uniform(-4, 4), cy + r.uniform(-4, 4), r.randrange(self.DIRS), r.randint(200, self.FULL)]
                       for _ in range(300)]
        for _ in range(4):
            self.drop(r.randrange(4, W - 4), r.randrange(4, H - 4))

    def drop(self, x, y):
        """Lay an oat flake: a little disc of food that smells irresistible."""
        self.oats += 1
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                if dx * dx + dy * dy <= 5 and 0 <= x + dx < W and 0 <= y + dy < H:
                    self.food[(y + dy) * W + x + dx] = [90, self.oats]

    def spread(self, T):
        """Blur the scent, (4·centre + 4 neighbours) / 8, for every pixel at once: pack the bytes into
        16-bit lanes of one big integer and add shifted copies of it, so no per-pixel Python runs.
        (Row ends bleed into the next row, but the agents bounce off the walls so the edges stay faint.)"""
        lanes = bytearray(2 * W * H)
        lanes[::2] = T
        A = int.from_bytes(lanes, "little")
        S = ((A << 2) + (A << 16) + (A >> 16) + (A << 16 * W) + (A >> 16 * W)) >> 3 & self.lane_mask
        return bytearray(S.to_bytes(2 * W * H, "little")[::2])

    def step(self):
        super().step()
        r = self.rng.random
        T, food, dx, dy = self.trail, self.food, self.dx, self.dy
        D, SA, RA, SO, FULL = self.DIRS, self.SA, self.RA, self.SO, self.FULL
        for i in food:
            T[i] = 255                              # oats give off scent
        born, alive = [], []
        for a in self.agents:
            x, y, h, e = a
            s = []
            for k in (h - SA, h, h + SA):
                sx, sy = int(x + dx[k % D] * SO), int(y + dy[k % D] * SO)
                s.append(T[sy * W + sx] if 0 <= sx < W and 0 <= sy < H else 0)
            left, mid, right = s
            if mid >= left and mid >= right:
                pass
            elif left > right:
                h -= RA
            elif right > left:
                h += RA
            else:
                h += RA if r() < .5 else -RA
            h = (h + (1 if r() < .1 else -1 if r() < .11 else 0)) % D
            nx, ny = x + dx[h], y + dy[h]
            if not (0 <= nx < W and 0 <= ny < H):
                h, nx, ny = int(r() * D), x, y      # bumped the dish wall
            i = int(ny) * W + int(nx)
            if i in food:
                f = food[i]
                f[0] -= 1
                if f[0] <= 0:
                    del food[i]
                e = FULL
                if r() < .04 and len(self.agents) + len(born) < self.MAX:
                    born.append([nx, ny, int(r() * D), FULL])
            elif T[i] < 120 or r() < .5:            # veins carry nutrients; lone wanderers starve faster
                e -= 1
            if e > 0:
                T[i] = min(255, T[i] + 60)
                a[:] = nx, ny, h, e
                alive.append(a)
        self.agents = alive + born
        self.trail = T = self.spread(T).translate(self.decay)
        self.pix[:] = T.translate(self.shades)
        for i, (amt, _) in food.items():
            self.pix[i] = 64 + min(3, amt // 25)
        self.timer -= 1
        if self.timer <= 0:                         # new oats fall: sooner when the dish is bare
            bare = not food
            for _ in range(1 + int(r() * 2)):
                self.drop(2 + int(r() * (W - 4)), 2 + int(r() * (H - 4)))
            self.timer = (150 if bare else 500) + int(r() * 400)
        if len(self.agents) < 20:                   # a dormant sclerotium wakes up
            x, y = 6 + r() * (W - 12), 6 + r() * (H - 12)
            self.agents += [[x, y, int(r() * D), FULL] for _ in range(60)]

    def animate(self, t):
        p = self.palette
        for k in range(1, 64):                      # shuttle streaming: the network slowly breathes
            p[k] = shade(self.base[k], 1 + .14 * math.sin(t * 1.4 - k * .09) * k / 63)

    def poke(self, x, y):
        self.drop(x, y)

    def vitals(self):
        return {"agents": len(self.agents), "oats": len({o for _, o in self.food.values()}),
                "veins": sum(1 for v in self.trail if v > 64)}


# ── Millpond ─────────────────────────────────────────────────────────────────
class Fish:
    """One Millpond fish. `mode`: swim, rise, flee, court, nibble, take, hooked or landing."""
    __slots__ = ("x", "y", "vx", "ty", "kind", "age", "life", "hunger", "wary", "mode", "timer", "nibbles",
                 "stamina", "seed")

    def __init__(self, rng, x, y, kind, age, life):
        self.x, self.y, self.ty, self.kind, self.age, self.life = x, y, y, kind, age, life
        self.vx = rng.choice((-1, 1)) * rng.uniform(.1, .25)
        self.hunger = rng.random()
        self.wary = self.timer = self.nibbles = 0
        self.mode = "swim"
        self.stamina = 1.
        self.seed = rng.randrange(8)


class Millpond(Env):
    """A freshwater pond seen from the bank: a jetty, an angler, and a day that turns to night.
    Fish hatch from eggs laid on the weed, grow from fry to adults to old lunkers and die of age.
    Adults spawn while the pond has room, so the stock rises toward what the pond can hold and
    hovers there. Click the water to cast to that depth, sit out the nibbles, click when the float
    goes under, then hold to reel and let go when the fish runs. Every fish you keep is one fewer to
    spawn: fish the pond out and it takes a long, quiet while to come back."""
    name, mood, tempo = "Millpond", "patient", 24
    SURF, DOCK, DAY, K, ADULT = 20, 19, 7200, 16, 3000      # surface row, jetty end, steps per day, room, fry->adult
    SPAWN, LURE = .00012, .0022                             # spawning odds per adult per step; how keen they are to bite
    HAND, TIP, LAND = (18, 13), (35, 2), (22., 21.5)        # rod butt, rod tip at rest, where fish are landed
    BITE = 19                                               # steps the float stays under: the strike window
    KINDS = (  # name, odds, preferred depth (0 surface .. 1 bottom), strength
        ("roach", .45, (0., .45), .55),
        ("perch", .42, (.3, .75), .75),
        ("carp", .13, (.65, 1.), 1.1),
    )
    SKY, STAR, TREE, BANK, WOOD, WATER, MUD, STONE, WEED = 0, 16, 20, 24, 28, 32, 48, 52, 56
    PAD, FLOWER, REED, ORB, GLINT, LANTERN = 60, 62, 64, 68, 69, 70
    LINE, FLOAT, FLOATW, WET, RIPPLE, SPLASH, EGG, MIDGE = 72, 73, 74, 75, 76, 77, 78, 79
    FISH, ANGLER, METER, ROD, SPECK, MOTE, BAIT = 80, 96, 100, 104, 105, 106, 107
    glow = (16, 17, 18, 19, 68, 69, 70, 73, 78)
    SPRITE = ("..hh....",
              ".hhhh...",
              "..ff....",
              ".cccc...",
              ".ccccf..",
              ".cccc...",
              ".cccc...",
              ".cbbbb..",
              ".....b..",
              ".....b..")

    def __init__(self, seed=None):
        super().__init__(seed)
        r = self.rng
        S = self.SURF
        ph = r.random() * 6
        self.clock0 = r.uniform(.1, .17)                    # start in late afternoon; dusk falls at .25
        self.ground = [int(50 + 9 * math.sin(math.pi * x / 88) + 1.2 * math.sin(x / 6 + ph)) if x < 84
                       else max(15 - (x - 90) // 2, 52 - (x - 84) * 6) for x in range(W)]
        tree = [int(13 + 1.6 * math.sin(x / 8 + ph) + math.sin(x / 3.1 + 2 * ph)) for x in range(W)]
        for _ in range(r.randint(7, 11)):                   # round crowns on the far shore
            cx, rad = r.randrange(W), r.randint(3, 6)
            top = S - 5 - rad - r.randrange(4)
            for dx in range(-rad, rad + 1):
                if 0 <= cx + dx < W:
                    tree[cx + dx] = min(tree[cx + dx], top + dx * dx // rad)
        self.stone = set()
        for _ in range(r.randint(4, 6)):                    # stones on the bottom
            cx, rad = r.randrange(24, 80), r.randint(1, 3)
            for dx in range(-rad - 1, rad + 2):
                x = cx + dx
                if 0 <= x < W and self.ground[x] > S + 6:
                    self.ground[x] = min(self.ground[x], self.ground[cx] - rad + abs(dx) // 2 + 1)
                    self.stone.add(x)
        for y in range(H):
            for x in range(W):
                gy = self.ground[x]
                if y >= gy:
                    if gy < S:
                        v = self.BANK if y == gy else self.BANK + 1 + r.randrange(3)
                    elif x in self.stone and y < gy + 3:
                        v = self.STONE + r.randrange(4)
                    else:
                        v = self.MUD if y == gy else self.MUD + 1 + r.randrange(3)
                elif y < S:
                    v = self.TREE + r.randrange(4) if y >= tree[x] else min(15, y * 16 // S)
                else:
                    v = self.WATER if y == S else self.WATER + 1 + min(14, (y - S - 1) * 15 // (H - S - 1))
                self.pix[y * W + x] = v
        for _ in range(40):
            x, y = r.randrange(W), r.randrange(S)
            if self.pix[y * W + x] < 16:
                self.pix[y * W + x] = self.STAR + r.randrange(4)
        for x in range(self.DOCK + 1):                      # the jetty, its posts and a lantern
            self.pix[17 * W + x] = self.WOOD + (2 if x % 5 == 0 else r.randrange(2))
            self.pix[18 * W + x] = self.WOOD + 3
        for x in (2, 9, 16):
            for y in range(19, self.ground[x]):
                self.pix[y * W + x] = self.WOOD + 2 + (y % 3 == 0)
        for y in range(12, 17):
            self.pix[y * W + 1] = self.WOOD + 3
        self.pix[10 * W + 1] = self.WOOD + 3
        self.pix[11 * W + 1] = self.LANTERN
        for x, v in ((9, 53), (10, 53), (11, 53)):          # a bucket for the catch
            self.pix[15 * W + x] = v
            self.pix[16 * W + x] = 52
        codes = {"h": 0, "f": 1, "c": 2, "b": 3}
        for dy, row in enumerate(self.SPRITE):
            for dx, ch in enumerate(row):
                if ch in codes:
                    self.pix[(8 + dy) * W + 13 + dx] = self.ANGLER + codes[ch]
        for _ in range(r.randint(3, 4)):                    # lily pads lie flat on the surface
            cx = r.randrange(42, 76)
            for x in range(cx, cx + r.randint(2, 4)):
                self.pix[S * W + x] = self.PAD + r.randrange(2)
            if r.random() < .7:
                self.pix[(S - 1) * W + cx + 1] = self.FLOWER
        self.weeds = [[x, self.ground[x], r.randint(3, 8), r.random() * 6, r.randint(8, 16)]
                      for x in r.sample(range(24, 82), 16) if self.ground[x] > S + 10]
        self.reeds = [(x, self.ground[x], min(self.ground[x] - 3, r.randint(S - 12, S - 4)), r.random() * 6)
                      for x in range(78, W) for _ in range(2) if self.ground[x] < S + 26 and r.random() < .65]
        self.specks = [[r.uniform(0, W), r.uniform(S + 2, H - 4)] for _ in range(26)]
        self.fish = []
        for _ in range(11):
            f = self.spawn(r.uniform(22, 80), None, age=r.randrange(40000))
            f.age = min(f.age, int(f.life * .8))
        self.known = {f.kind for f in self.fish}            # every kind the pond started with is worth restoring
        self.eggs, self.motes, self.ripples, self.drops, self.midges = [], [], [], [], []
        self.swarm = r.uniform(40, 80)
        self.stray = r.randint(2400, 4800)
        self.line = "idle"                                  # idle, cast, sink, wait, fight, land
        self.bait = False
        self.bx, self.by, self.depth = 0., 0., 0.
        self.fly = (0., 0., 0, 0)                           # cast flight: start x, start y, step, steps
        self.suitor = None
        self.twitch = self.bite = self.warn = self.surge = self.slack = 0
        self.tension = 0.
        self.holding = False
        self.kept = []
        self.lost = 0
        self.msg = ("click the water to cast", 10 ** 9)
        self.light, self.dusk = self.daylight()
        self.out_at = -1

    # ── helpers ──
    def daylight(self):
        """Light 0 (midnight) .. 1 (noon), and how much of dusk or dawn is in the air (0..1)."""
        phase = self.steps / self.DAY + self.clock0
        light = .5 + .5 * math.cos(phase * math.tau)
        return light, max(0., 1 - abs(light - .5) * 3)

    def say(self, text, secs=3.):
        self.msg = (text, self.steps + int(secs * self.tempo))

    def stage(self, f):
        return 0 if f.age < self.ADULT else 2 if f.age > f.life * .7 else 1

    def cruise(self, f):
        """A depth this fish likes, as a pixel row."""
        lo, hi = self.KINDS[f.kind][2]
        return self.SURF + 2 + self.rng.uniform(lo, hi) * 34

    def spawn(self, x, y, kind=None, age=0):
        r = self.rng
        if kind is None:
            kind = r.choices(range(3), [k[1] for k in self.KINDS])[0]
        life = r.randint(48000, 60000) if kind == 2 else r.randint(36000, 48000)
        f = Fish(r, x, 0., kind, age, life)
        f.y = f.ty = self.cruise(f) if y is None else y
        self.fish.append(f)
        return f

    def wet(self, x, y):
        """Keep a point inside the water: below the surface, above the bottom, off the bank."""
        x = max(1., min(W - 2., x))
        while self.ground[int(x)] < self.SURF + 4:
            x -= 1
        return x, max(self.SURF + 1.5, min(self.ground[int(x)] - 1.5, y))

    def strength(self, f):
        return self.KINDS[f.kind][3] * (.5, 1., 1.4)[self.stage(f)]

    def splash(self, x, n, rip=True):
        r = self.rng.random
        if rip:
            self.ripples.append([x, 0., 14 + int(n * 2)])
        for _ in range(n):
            self.drops.append([x + (r() - .5) * 2, self.SURF - 1., (r() - .5) * .6, -.4 - r() * .5])

    # ── the pond's own life ──
    def step(self):
        super().step()
        r = self.rng.random
        S = self.SURF
        self.light, self.dusk = L, tw = self.daylight()
        room = max(0., 1 - (len(self.fish) + len(self.eggs) * .4) / self.K)
        adults = [f.kind for f in self.fish if f.age >= self.ADULT]
        pairs = {k for k in adults if adults.count(k) > 1}  # a kind can only spawn with two adults left
        alive = []
        for f in self.fish:
            f.age += 1
            f.hunger = min(1., f.hunger + .0006)
            if f.wary:
                f.wary -= 1
            if f.mode in ("hooked", "landing"):
                alive.append(f)
                continue
            if f.age > f.life:                              # old age: it sinks quietly into the mud
                self.motes.append([f.x, f.y])
                if f is self.suitor:
                    self.suitor = None
                continue
            alive.append(f)
            self.behave(f, tw)
            if f.mode == "swim" and f.age >= self.ADULT and f.kind in pairs and f.hunger < .75 \
                    and r() < self.SPAWN * room and self.weeds:
                self.lay(f)
        self.fish = alive
        hatched = []
        for e in self.eggs:
            e[2] -= 1
            if e[2] > 0:
                hatched.append(e)
            elif r() < .65 and len(self.fish) < self.K + 4:
                self.spawn(e[0] + .5, e[1] - 1., e[3])
        self.eggs = hatched
        count = Counter(f.kind for f in self.fish)
        viable = pairs | {e[3] for e in self.eggs} | {k for k, n in count.items() if n > 1}
        missing = self.known - viable                       # a kind fished out: wait for a stray from the stream
        if missing:
            self.stray -= 1
            if self.stray <= 0:
                lone = [f.kind for f in self.fish if f.age >= self.ADULT and f.kind in missing]
                kind = lone[0] if lone and r() < .7 else self.rng.choice(sorted(missing))
                self.spawn(2., S + 6. + r() * 10, kind, self.ADULT + int(r() * 3000)).vx = .2
                self.stray = self.rng.randint(2400, 4800)
                if self.line in ("idle", "wait"):
                    self.say("a newcomer swims in under the jetty", 4)
        else:
            self.stray = self.rng.randint(2400, 4800)
        self.line_step()
        self.weather(tw)

    def behave(self, f, tw):
        r = self.rng.random
        S = self.SURF
        if f.mode == "swim":
            f.x += f.vx
            f.y += (f.ty - f.y) * .03 + math.sin(self.steps * .2 + f.x) * .02
            if r() < .008:
                f.ty = self.cruise(f)
            if r() < .004:
                f.vx = -f.vx
            ax = int(f.x + (2 if f.vx > 0 else -2))
            if not 1 <= ax < W - 1 or f.y > self.ground[ax] - 2:
                f.vx = -f.vx
            if r() < .002:
                f.hunger = max(0., f.hunger - .2)           # a snail, a nymph
            if f.hunger > .3 and r() < .0016 * tw + .00012:
                f.mode = "rise"
        elif f.mode == "rise":                              # up to take a midge off the surface
            f.x += f.vx
            f.y -= .35
            if f.y < S + 1.6:
                self.splash(f.x, 1)
                f.hunger = max(0., f.hunger - .3)
                f.mode, f.ty = "swim", self.cruise(f)
        elif f.mode == "flee":
            f.x += f.vx
            f.y += (f.ty - f.y) * .08
            f.timer -= 1
            if f.timer <= 0:
                f.mode = "swim"
                f.vx = math.copysign(.15, f.vx)
        elif f.mode == "court":                             # nosing up to the bait
            dx, dy = self.bx - f.x, self.by - f.y
            f.vx = math.copysign(.15, dx)
            f.x += max(-.2, min(.2, dx))
            f.y += max(-.15, min(.15, dy))
            if abs(dx) < .6 and abs(dy) < .6:
                f.mode, f.timer = "nibble", self.rng.randint(15, 45)
                f.nibbles = self.rng.randint(0, 3) + 2 * (self.stage(f) == 2)
            elif r() < .003:
                self.leave(f, 90)
        elif f.mode == "nibble":
            f.x = self.bx - (.4 if f.vx > 0 else -.4) + (r() - .5) * .3
            f.timer -= 1
            if f.timer <= 0:
                if f.nibbles:
                    f.nibbles -= 1
                    f.timer = self.rng.randint(12, 44)
                    self.twitch = 3
                    self.ripples.append([self.bx, 0., 6])
                else:
                    f.mode, self.bite = "take", self.BITE
                    self.splash(self.bx, 2)
            elif r() < .004:
                self.leave(f, 120)
        elif f.mode == "take":
            f.x = self.bx - (.4 if f.vx > 0 else -.4)
            self.bite -= 1
            if self.bite <= 0:                              # too slow: it got the worm and not the hook
                self.bait = False
                f.hunger = max(0., f.hunger - .3)
                self.leave(f, 300)
                self.say("missed it... the bait's gone. click to cast again", 5)
        f.x, f.y = self.wet(f.x, f.y)

    def leave(self, f, wary):
        f.mode, f.wary = "swim", wary
        f.vx = math.copysign(self.rng.uniform(.15, .3), f.x - self.bx)
        if f is self.suitor:
            self.suitor = None

    def lay(self, f):
        w = min(self.weeds, key=lambda s: abs(s[0] - f.x))
        for _ in range(self.rng.randint(2, 5)):
            self.eggs.append([w[0] + self.rng.choice((-1, 1)), w[1] - self.rng.randint(1, max(1, w[2] - 1)),
                              self.rng.randint(700, 1300), f.kind])
        f.hunger = min(1., f.hunger + .25)
        if self.line in ("idle", "wait") and self.rng.random() < .5:
            self.say(f"the {self.KINDS[f.kind][0]} are spawning in the weed", 4)

    def weather(self, tw):
        r = self.rng.random
        S = self.SURF
        for rp in self.ripples:
            rp[1] += .3
            rp[2] -= 1
        self.ripples = [rp for rp in self.ripples if rp[2] > 0][-30:]
        for d in self.drops:
            d[0] += d[2]
            d[1] += d[3]
            d[3] += .12
        self.drops = [d for d in self.drops if d[1] < S][-40:]
        for s in self.specks:
            s[0] = (s[0] + .03 + (r() - .5) * .04) % W
            s[1] += (r() - .5) * .05
            if not S + 1 < s[1] < self.ground[int(s[0])] - 1:
                s[1] = S + 2 + r() * 30
        for m in self.motes:
            m[1] += .12
        settled = [m for m in self.motes if m[1] >= self.ground[int(m[0])] - 1]
        for m in settled:                                   # what dies feeds the weed
            if self.weeds:
                w = min(self.weeds, key=lambda s: abs(s[0] - m[0]))
                w[4] = min(20, w[4] + 2)
        self.motes = [m for m in self.motes if m[1] < self.ground[int(m[0])] - 1]
        for w in self.weeds:
            if w[2] < w[4] and r() < .002:
                w[2] += 1
            elif r() < .0004:
                w[4] = max(6, w[4] - 1)
                w[2] = min(w[2], w[4])
        self.swarm = max(30., min(84., self.swarm + (r() - .5) * .3))
        n = int(12 * tw)
        while len(self.midges) < n:
            self.midges.append([self.swarm + (r() - .5) * 8, S - 2 - r() * 5])
        del self.midges[n:]
        for m in self.midges:
            m[0] += (self.swarm - m[0]) * .02 + (r() - .5) * .8
            m[1] = max(S - 9., min(S - 1.5, m[1] + (r() - .5) * .7))

    # ── the angler ──
    def poke(self, x, y):
        self.holding = True
        f = self.suitor
        if self.line in ("fight", "land", "cast"):
            return
        if f is not None and f.mode == "take":
            self.hook(f)
            return
        if f is not None and f.mode == "nibble":
            self.leave(f, 400)                              # struck at a nibble: spooked it
            if self.rng.random() < .4:
                self.bait = False
            self.say("too soon! wait for the float to go right under", 4)
            return
        if x <= self.DOCK + 1 and y < self.SURF + 2:        # click the jetty to reel in and rest
            if self.line != "idle":
                self.line, self.suitor = "idle", None
                self.say("reeled in", 2)
            return
        self.cast(x, y)

    def release(self):
        self.holding = False

    def cast(self, x, y):
        tx = max(24, min(84, x))
        while self.ground[tx] < self.SURF + 6:
            tx -= 1
        self.depth = max(self.SURF + 2, min(self.ground[tx] - 2, y if y > self.SURF else self.SURF + 4))
        if self.suitor is not None:
            self.leave(self.suitor, 60)
        tip = self.rod_tip()
        self.fly = (tip[0], tip[1], 0, 8 + int(abs(tx - tip[0]) / 5))
        self.bx, self.by = float(tx), float(self.SURF)
        self.line, self.bait = "cast", True
        self.msg = ("", 0)

    def hook(self, f):
        if self.stage(f) == 0:
            self.leave(f, 600)
            self.line, self.suitor, self.bait = "idle", None, False
            self.say("a tiddler... slipped it back to grow", 4)
            return
        f.mode, f.stamina = "hooked", 1.
        self.line, self.tension, self.slack, self.surge, self.warn = "fight", .3, 0, 0, 0
        self.splash(f.x, 4)
        self.say("fish on! hold to reel, let go when it runs", 3)

    def lose(self, text):
        f = self.suitor
        self.leave(f, 900)
        self.line, self.bait, self.tension = "idle", False, 0.
        self.lost += 1
        self.say(text, 4)

    def line_step(self):
        r = self.rng.random
        S = self.SURF
        if self.twitch:
            self.twitch -= 1
        if self.line == "cast":
            x0, y0, k, n = self.fly
            self.fly = (x0, y0, k + 1, n)
            if k + 1 >= n:
                self.line = "sink"
                self.splash(self.bx, 3)
                for f in self.fish:                         # the plop scares anything close
                    if f.mode in ("swim", "rise") and abs(f.x - self.bx) < 7 and abs(f.y - S) < 14:
                        f.mode, f.timer, f.wary = "flee", 30, 120
                        f.vx = math.copysign(.6, f.x - self.bx)
        elif self.line == "sink":
            self.by += .4
            if self.by >= self.depth:
                self.by, self.line = self.depth, "wait"
        elif self.line == "wait":
            if self.suitor is None and self.bait:
                L, tw = self.light, self.dusk
                act = .5 + 1.1 * tw + .2 * (1 - L)
                frac = (self.by - S - 2) / 34
                for f in self.fish:
                    if f.mode != "swim" or f.wary:
                        continue
                    d = math.hypot(f.x - self.bx, f.y - self.by)
                    if d > 26:
                        continue
                    lo, hi = self.KINDS[f.kind][2]
                    pref = 1.5 if lo - .1 <= frac <= hi + .1 else .4
                    st = self.stage(f)
                    p = self.LURE * f.hunger * act * pref * (1 - d / 26) * (.25, 1., .6)[st]
                    if r() < p:
                        self.suitor, f.mode = f, "court"
                        break
        elif self.line == "fight":
            self.fight()
        elif self.line == "land":
            f = self.suitor
            f.timer += 1
            k = f.timer / 16
            x0, y0 = self.LAND
            f.x = x0 + (self.HAND[0] - x0) * k
            f.y = y0 + (self.HAND[1] - 1 - y0) * k - math.sin(math.pi * k) * 5
            if k >= 1:
                self.fish.remove(f)
                self.kept.append((f.kind, self.stage(f)))
                self.suitor, self.line, self.bait = None, "idle", False
                size = ("fry", "", "old ")[self.stage(f)]
                self.say(f"landed a {size}{self.KINDS[f.kind][0]}! {len(self.fish)} left in the pond", 5)

    def fight(self):
        r = self.rng.random
        f = self.suitor
        pw = self.strength(f)
        if self.warn:                                       # it shakes its head, then bolts
            self.warn -= 1
            if not self.warn:
                self.surge = self.rng.randint(10, 30)
        elif self.surge:
            self.surge -= 1
            f.stamina = max(0., f.stamina - .002)
        elif r() < .03 * f.stamina:
            self.warn = int(10 - 3 * pw)                    # big fish give less warning
            if f.y < self.SURF + 4:
                self.splash(f.x, 3)
        pull = pw * (1.8 if self.surge else .45) * (.3 + .7 * f.stamina)
        target = .25 + pull * .8 if self.holding else pull * .15
        self.tension += (target - self.tension) * .16
        if self.tension > 1:
            self.lose("SNAP! too much pressure, the line broke")
            return
        if self.tension > .85 and r() < .012:
            self.lose("the hook tore free... too much strain")
            return
        lx, ly = self.LAND
        dx, dy = f.x - lx, f.y - ly
        d = math.hypot(dx, dy) or 1.
        if self.holding:
            v = .3 - pull * .26
            f.stamina = max(0., f.stamina - (.001 + .004 * self.tension) / pw)
            self.slack = 0
        else:
            v = -pull * .3
            f.stamina = min(1., f.stamina + .0012)
            self.slack = self.slack + 1 if self.tension < .12 else 0
            if self.slack > 48 and r() < .03:
                self.lose("slack line... it threw the hook")
                return
        f.x -= dx / d * v
        f.y -= dy / d * v + (r() - .5) * (.6 if self.surge or self.warn else .2)
        f.x, f.y = self.wet(f.x, f.y)
        f.vx = .1 if dx >= 0 else -.1                       # head pointing away, pulling
        if self.surge and f.y < self.SURF + 3 and r() < .2:
            self.splash(f.x, 1)
        if math.hypot(f.x - lx, f.y - ly) < 2:
            self.line, f.mode, f.timer = "land", "landing", 0
            self.splash(f.x, 5)
            for g in self.fish:                             # the commotion puts the others off for a while
                if g.mode == "swim" and abs(g.x - lx) < 30:
                    g.wary = max(g.wary, 400)

    def rod_tip(self):
        tx, ty = self.TIP
        if self.line == "fight" and self.suitor:
            f = self.suitor
            dx, dy = f.x - tx, f.y - ty
            d = math.hypot(dx, dy) or 1.
            bend = 2 + self.tension * 6
            return tx + dx / d * bend, ty + dy / d * bend
        if self.line == "wait" and self.bite:
            return tx + .5, ty + 2.
        return float(tx), float(ty)

    # ── drawing ──
    def frame(self):
        if self.out_at == self.steps:                       # sprites only move once per step
            return self.out
        out = bytearray(self.pix)
        S = self.SURF
        steps = self.steps

        def put(x, y, v):
            x, y = int(x), int(y)
            if 0 <= x < W and 0 <= y < H:
                out[y * W + x] = v

        def curve(x0, y0, x1, y1, sag, v, under=None, dotted=False):
            n = int(max(abs(x1 - x0), abs(y1 - y0)) * 1.4) + 1
            for k in range(n + 1):
                t = k / n
                x = x0 + (x1 - x0) * t
                y = y0 + (y1 - y0) * t + sag * 4 * t * (1 - t)
                if dotted and k % 2:
                    continue
                if 0 <= int(x) < W and 0 <= int(y) < H and out[int(y) * W + int(x)] < self.FISH:
                    put(x, y, under if under is not None and y >= S + 1 else v)

        L = self.light
        phase = (steps / self.DAY + self.clock0) % 1
        day = phase < .25 or phase > .75
        k = ((phase + .25) % 1) / .5 if day else (phase - .25) / .5
        ox, oy = 6 + k * (W - 12), 13 - math.sin(math.pi * k) * 11
        for dx in (0, 1):
            for dy in (0, 1):
                x, y = int(ox) + dx, int(oy) + dy
                if 0 <= x < W and 0 <= y < S and out[y * W + x] < 20:
                    out[y * W + x] = self.ORB
        if not day:
            for y in range(S, S + 5):
                if (steps // 3 + y) % 3:
                    put(ox + (steps // 5 + y) % 3 - 1, y, self.GLINT)
        t = steps * .04
        for x, base, h, ph, _ in self.weeds:
            for j in range(h):
                sway = 1.4 * math.sin(t + ph + j * .25) * (j / max(1, h)) ** 1.5
                put(x + round(sway), base - 1 - j, self.WEED + min(3, j * 4 // max(1, h)))
        for x, base, top, ph in self.reeds:
            for y in range(top, base):
                sway = math.sin(t * .8 + ph) * ((base - y) / (base - top)) ** 2 * 1.2
                put(x + round(sway), y, self.REED + (0 if y == top else 1 + (y < S) + (y < top + 3)))
        for x, y in self.specks:
            put(x, y, self.SPECK)
        for x, y, *_ in self.eggs:
            put(x, y, self.EGG)
        for x, y in self.motes:
            put(x, y, self.MOTE)
        for f in self.fish:
            st = self.stage(f)
            d = 1 if f.vx > 0 else -1
            ix, iy = int(f.x), int(f.y)
            fast = f.mode in ("hooked", "flee") or (f.mode == "nibble")
            wag = (steps // (1 if fast else 4) + f.seed) % 2
            b = self.FISH + f.kind * 5
            cells = ((b + 4, b + 3), (b, b + 1, b + 3), (b, b + 1, b + 2, b + 3))[st]
            for j, v in enumerate(cells):
                ty = iy + (wag if j == len(cells) - 1 and iy < H - 1 else 0)
                put(ix - j * d, ty, v)
        for x, y in self.midges:
            put(x, y, self.MIDGE)
        for x, rad, life in self.ripples:
            for sx in (-1, 1):
                if rad > .5 or sx == 1:
                    put(x + sx * rad, S, self.RIPPLE)
            if rad < 1.5 and life > 8:
                put(x, S - 1, self.SPLASH)
        for x, y, *_ in self.drops:
            put(x, y, self.SPLASH)
        tx, ty = self.rod_tip()
        hx, hy = self.HAND
        n = 24                                              # the rod: a curve that bends with the strain
        bend = self.tension * 3 if self.line == "fight" else 0
        for j in range(n + 1):
            u = j / n
            put(hx + (tx - hx) * u, hy + (ty - hy) * u + bend * u * u, self.ROD)
        tx, ty = hx + (tx - hx), hy + (ty - hy) + bend
        if self.line == "idle":
            curve(tx, ty, tx, ty + 4, 0, self.LINE)
            put(tx, ty + 5, self.FLOATW)
        elif self.line == "cast":
            x0, y0, k, n = self.fly
            u = k / n
            fx = x0 + (self.bx - x0) * u
            fy = y0 + (S - 1 - y0) * u - math.sin(math.pi * u) * 8
            curve(tx, ty, fx, fy, 2, self.LINE)
            put(fx, fy, self.FLOAT)
        elif self.line in ("sink", "wait"):
            dip = 2 if self.bite else 1 if self.twitch else 0
            curve(tx, ty, self.bx, S - 2 + dip, 2.5, self.LINE)
            curve(self.bx, S + 1, self.bx, self.by, 0, self.WET, self.WET, dotted=True)
            put(self.bx, self.by, self.BAIT if self.bait else self.WET)
            if dip < 2:
                put(self.bx, S - 1 + dip, self.FLOAT)
            if dip == 0:
                put(self.bx, S, self.FLOATW)
        elif self.line in ("fight", "land") and self.suitor:
            f = self.suitor
            curve(tx, ty, f.x, f.y, .3 if self.tension > .5 else 1.5, self.LINE, self.WET)
            if self.line == "fight" and f.y > S:
                u = (S - ty) / max(.1, f.y - ty)
                put(tx + (f.x - tx) * u, S - 1, self.FLOAT)
            if self.line == "fight":                        # the tension gauge
                for j in range(20):
                    put(W - 22 + j, 1, self.METER + 3 if j >= self.tension * 20 else
                        self.METER + (0 if j < 11 else 1 if j < 16 else 2))
        for j in range(min(3, len(self.kept))):             # tails poking out of the bucket
            put(9 + j, 14, self.FISH + self.kept[-1 - j][0] * 5 + 3)
        self.out, self.out_at = out, self.steps
        return out

    def animate(self, t):
        p = self.palette
        L, tw = self.light, self.dusk
        dim = .28 + .72 * L
        for k in range(16):
            f = k / 15
            c = mix(mix((5, 7, 20), (20, 28, 56), f), mix((88, 150, 214), (196, 224, 238), f), L)
            p[k] = mix(c, mix((70, 62, 128), (252, 150, 92), f), tw * .75)
        for k in range(4):
            p[16 + k] = mix(p[3], (232, 234, 255), (1 - L) ** 2 * (.55 + .45 * math.sin(t * (1.3 + k * .4) + k * 2)))
        for k in range(4):
            p[20 + k] = mix(shade(mix((8, 12, 18), (44, 78, 58), L), .85 + k * .08), (36, 26, 44), tw * .5)
        p[24] = shade((96, 140, 64), dim)
        for k in range(3):
            p[25 + k] = shade((92, 72, 48), dim * (.8 + k * .1))
        for k in range(4):
            p[28 + k] = shade((150, 112, 72), dim * (1.05 - k * .17))
        top = mix(mix((14, 26, 40), (60, 120, 108), L), (130, 84, 70), tw * .35)
        deep = mix((2, 6, 10), (12, 36, 32), L)
        p[32] = mix(p[14], (255, 255, 255), .12 + .06 * math.sin(t * 1.3))
        for k in range(15):
            p[33 + k] = shade(mix(top, deep, k / 14), 1 + (.07 * math.sin(t * 1.1 + k * .9) if k < 4 else 0))
        for k in range(4):
            p[48 + k] = shade((70, 58, 40), dim * (1.05 - k * .1))
            p[52 + k] = shade((104, 108, 112), dim * (.8 + k * .08))
            p[56 + k] = shade(mix((40, 96, 50), (110, 168, 72), k / 3), dim)
            p[64 + k] = shade(mix((120, 140, 70), (54, 84, 40), k / 3), dim)
        p[60], p[61], p[62] = shade((70, 132, 62), dim), shade((52, 108, 52), dim), shade((246, 170, 200), dim)
        p[68] = (255, 236, 170) if L >= .5 else (222, 226, 242)
        p[69] = shade((200, 208, 236), (1 - L) * .9)
        night = max(0., min(1., (.62 - L) / .4))
        p[70] = mix((60, 52, 40), (255, 196, 100), night * (.88 + .12 * math.sin(t * 9) * math.sin(t * 4.3)))
        strain = max(0., self.tension - .55) / .45 if self.line == "fight" else 0
        p[72] = mix(shade((214, 214, 200), .45 + .55 * L), (255, 110, 80), strain)
        p[73], p[74] = (236, 54, 40), shade((240, 240, 236), dim)
        p[75] = mix(p[36], (200, 210, 200), .3)
        p[76] = mix(p[32], (255, 255, 255), .45)
        p[77] = shade((220, 236, 242), .5 + .5 * L)
        p[78] = shade((250, 206, 120), .6 + .4 * L)
        p[79] = mix((30, 28, 34), (120, 110, 130), 1 - L)
        fishes = (((226, 230, 238), (176, 186, 204), (140, 150, 172), (214, 76, 58), (196, 206, 214)),
                  ((206, 196, 86), (124, 154, 62), (72, 104, 44), (226, 112, 52), (184, 196, 120)),
                  ((222, 170, 78), (176, 124, 52), (138, 94, 40), (112, 74, 38), (220, 186, 120)))
        fd = .42 + .58 * L
        for k, cols in enumerate(fishes):
            for j, c in enumerate(cols):
                p[80 + k * 5 + j] = shade(c, fd)
        for k, c in enumerate(((70, 84, 58), (226, 180, 146), (64, 92, 120), (58, 44, 36))):
            p[96 + k] = shade(c, dim)
        p[100:104] = [(110, 210, 90), (240, 190, 60), (240, 70, 50), (30, 32, 40)]
        p[104] = shade((132, 92, 56), dim)
        p[105] = mix(p[38], (200, 210, 190), .18)
        p[106] = shade((176, 172, 150), dim)
        p[107] = shade((232, 120, 140), dim)

    def status(self):
        text, until = self.msg
        if self.steps >= until or not text:
            f = self.suitor
            if self.line == "wait" and not self.bait:
                text = "the bait's gone. click to cast again"
            elif self.line == "wait" and f is not None and f.mode == "take":
                text = "BITE! click!"
            elif self.line == "wait" and f is not None and f.mode == "nibble":
                text = "a nibble... wait for it"
            elif self.line == "wait":
                text = "waiting..."
            elif self.line == "fight":
                text = ("it's about to run!" if self.warn else "it's running, ease off!" if self.surge
                        else "hold to reel in")
            elif self.line == "idle":
                text = "click the water to cast: deeper click, deeper bait"
            else:
                text = "letting the bait sink..." if self.line == "sink" else "casting..."
        n = len(self.fish)
        return text, f"{n} fish · {len(self.eggs)} eggs · {len(self.kept)} kept"

    def vitals(self):
        st = [self.stage(f) for f in self.fish]
        return {"fish": len(self.fish), "fry": st.count(0), "adults": st.count(1), "old": st.count(2),
                "eggs": len(self.eggs), "light": round(self.light, 2)}


ENVIRONMENTS = [Tidepool, EmberForest, Crystal, Pulse, Fireflies, SlimeMold, Millpond]


def app_dir():
    """Where Terrarium lives: next to the script, or next to Terrarium.exe when packaged (so screenshots
    land on the USB stick, never in the host PC's temp folder)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


# ── the window ───────────────────────────────────────────────────────────────
class App:
    GAP = 6

    def __init__(self, args):
        import pygame
        self.pg = pygame
        pygame.init()
        seed = args.seed
        self.envs = [cls(None if seed is None else seed + k) for k, cls in enumerate(ENVIRONMENTS)]
        self.acc = [0.0] * len(self.envs)
        self.cur = 0
        self.mode = "grid"
        self.paused = False
        self.scanlines = True
        self.labels = True
        self.on_top = True
        self.opacity = 1.0
        self.autocycle = False
        self.cycle_at = time.time() + 90
        self.win = pygame.Window("Terrarium", self.default_size("grid"), resizable=True)
        self.font = pygame.font.SysFont("consolas,couriernew", 14, bold=True)
        self.small = pygame.font.SysFont("consolas,couriernew", 12)
        self.clock = pygame.time.Clock()
        self.overlay_cache = {}
        self.drag = None
        self.pressed = None                             # the world under a held mouse button
        self.last_click = (0, -1)
        self.shots = os.path.join(app_dir(), "shots")
        self.toast = ("", 0)
        self.restore = None
        if args.mini:
            self.set_mode("mini")

    def shape(self):
        """Shelf layout (cols, rows): 2x2 for four environments, up to 4x2 for eight, then 3 rows."""
        rows = 2 if len(self.envs) <= 8 else 3
        return -(-len(self.envs) // rows), rows

    def default_size(self, mode):
        if mode == "grid":
            cols, rows = self.shape()
            s = 16 // cols                          # keep the shelf about as wide as the old 2x2
            return (W * s * cols + self.GAP * (cols + 1), H * s * rows + self.GAP * (rows + 1))
        if mode == "single":
            return (W * 8, H * 8)
        return (W * 3, H * 3)

    def win_set(self, **props):
        """Set window properties, skipping any the platform/driver doesn't support."""
        for k, v in props.items():
            try:
                setattr(self.win, k, v)
            except (self.pg.error, AttributeError):
                pass

    def set_mode(self, mode):
        win, prev = self.win, self.mode
        if mode == prev:
            return
        if mode == "mini":
            self.restore = (prev, win.position, win.size)
            self.win_set(borderless=True, resizable=False, size=self.default_size("mini"))
            dw, dh = self.pg.display.get_desktop_sizes()[0]
            self.win_set(position=(dw - win.size[0] - 24, dh - win.size[1] - 72),
                         always_on_top=self.on_top, opacity=self.opacity)
        else:
            if prev == "mini":
                self.win_set(always_on_top=False, opacity=1.0, borderless=False, resizable=True)
                if self.restore:
                    _, pos, size = self.restore
                    self.win_set(size=size, position=pos)
            else:
                self.win_set(size=self.default_size(mode))
        self.mode = mode

    def tiles(self, size):
        w, h = size
        R = self.pg.Rect
        if self.mode != "grid":
            s = min(w / W, h / H)
            tw, th = int(W * s), int(H * s)
            return [(self.cur, R((w - tw) // 2, (h - th) // 2, tw, th))]
        g = self.GAP
        cols, rows = self.shape()
        s = min((w - (cols + 1) * g) / (cols * W), (h - (rows + 1) * g) / (rows * H))
        tw, th = int(W * s), int(H * s)
        ox, oy = (w - cols * tw - (cols - 1) * g) // 2, (h - rows * th - (rows - 1) * g) // 2
        return [(k, R(ox + (k % cols) * (tw + g), oy + (k // cols) * (th + g), tw, th)) for k in range(len(self.envs))]

    def overlay(self, size):
        """Scanlines + soft vignette, cached per tile size."""
        if size in self.overlay_cache:
            return self.overlay_cache[size]
        pg = self.pg
        w, h = size
        surf = pg.Surface(size, pg.SRCALPHA)
        step = max(2, round(h / H))
        for y in range(step - 1, h, step):
            pg.draw.line(surf, (0, 0, 0, 46), (0, y), (w, y))
        for k in range(14):
            pg.draw.rect(surf, (0, 0, 0, 7 * (14 - k)), (k * 2, k * 2, w - k * 4, h - k * 4), 2, border_radius=10 + k)
        self.overlay_cache = {size: surf}
        return surf

    def draw_env(self, screen, env, rect, t):
        pg = self.pg
        env.animate(t)
        buf = env.frame()
        img = pg.image.frombuffer(buf, (W, H), "P")
        img.set_palette(env.palette)
        screen.blit(pg.transform.scale(img, rect.size), rect)
        if env.glow:
            gp = [(0, 0, 0)] * 256
            for k in env.glow:
                gp[k] = env.palette[k]
            img.set_palette(gp)
            rgb = pg.Surface((W, H), 0, 32)
            rgb.blit(img, (0, 0))
            blur = pg.transform.smoothscale(rgb, (W // 4, H // 4))
            screen.blit(pg.transform.smoothscale(blur, rect.size), rect, special_flags=pg.BLEND_RGB_ADD)
        if self.scanlines:
            screen.blit(self.overlay(rect.size), rect)

    def label(self, screen, env, rect):
        title = self.font.render(env.name.upper(), True, (236, 238, 245))
        mood = self.small.render(env.mood, True, (170, 176, 196))
        box = self.pg.Rect(rect.x + 8, rect.bottom - 8 - title.get_height() - mood.get_height() - 6,
                           max(title.get_width(), mood.get_width()) + 12, title.get_height() + mood.get_height() + 6)
        shade_ = self.pg.Surface(box.size, self.pg.SRCALPHA)
        shade_.fill((6, 8, 14, 150))
        screen.blit(shade_, box)
        screen.blit(title, (box.x + 6, box.y + 3))
        screen.blit(mood, (box.x + 6, box.y + 3 + title.get_height()))

    def status(self, screen, env, rect):
        lines = [ln for ln in env.status() if ln]
        if not lines:
            return
        imgs = [self.small.render(ln, True, (255, 214, 140) if k == 0 else (190, 198, 214)) for k, ln in enumerate(lines)]
        box = self.pg.Rect(rect.x + 8, rect.y + 8, max(i.get_width() for i in imgs) + 12,
                           sum(i.get_height() for i in imgs) + 6)
        shade_ = self.pg.Surface(box.size, self.pg.SRCALPHA)
        shade_.fill((6, 8, 14, 150))
        screen.blit(shade_, box)
        y = box.y + 3
        for img in imgs:
            screen.blit(img, (box.x + 6, y))
            y += img.get_height()

    def env_at(self, pos):
        for k, rect in self.tiles(self.win.size):
            if rect.collidepoint(pos):
                return k, (pos[0] - rect.x) * W // rect.w, (pos[1] - rect.y) * H // rect.h
        return None

    def snapshot(self):
        os.makedirs(self.shots, exist_ok=True)
        path = os.path.join(self.shots, f"terrarium_{time.strftime('%Y%m%d_%H%M%S')}.png")
        self.pg.image.save(self.win.get_surface(), path)
        self.toast = (os.path.basename(path), time.time())

    def handle(self, e):
        pg = self.pg
        if e.type == pg.QUIT or (e.type == pg.WINDOWCLOSE):
            return False
        if e.type == pg.KEYDOWN:
            k = e.key
            if k == pg.K_ESCAPE:
                if self.mode == "mini":
                    self.set_mode(self.restore[0] if self.restore else "grid")
                else:
                    return False
            elif k == pg.K_TAB:
                self.set_mode("single" if self.mode == "grid" else "grid")
            elif k == pg.K_m:
                self.set_mode("grid" if self.mode == "mini" else "mini")
            elif k in (pg.K_RIGHT, pg.K_LEFT):
                self.cur = (self.cur + (1 if k == pg.K_RIGHT else -1)) % len(self.envs)
            elif k == pg.K_SPACE:
                self.paused = not self.paused
            elif k == pg.K_r:
                targets = range(len(self.envs)) if self.mode == "grid" else [self.cur]
                for j in targets:
                    self.envs[j] = ENVIRONMENTS[j]()
            elif k == pg.K_a:
                self.autocycle = not self.autocycle
                self.cycle_at = time.time() + 90
            elif k == pg.K_l:
                self.scanlines = not self.scanlines
            elif k == pg.K_n:
                self.labels = not self.labels
            elif k == pg.K_t:
                self.on_top = not self.on_top
                if self.mode == "mini":
                    self.win_set(always_on_top=self.on_top)
            elif k == pg.K_o:
                self.opacity = {1.0: .8, .8: .55}.get(self.opacity, 1.0)
                if self.mode == "mini":
                    self.win_set(opacity=self.opacity)
            elif k == pg.K_s:
                self.snapshot()
        elif e.type == pg.MOUSEBUTTONDOWN and e.button in (1, 3):
            if self.mode == "mini" and e.button == 1:
                self.drag = e.pos                       # frameless window: drag to move
                return True
            hit = self.env_at(e.pos)
            if hit:
                k, x, y = hit
                now = time.time()
                if e.button == 1 and self.mode == "grid" and self.last_click[1] == k and now - self.last_click[0] < .35:
                    self.cur = k                        # double-click a tile to open it
                    self.set_mode("single")
                else:
                    self.envs[k].poke(x, y)
                    self.pressed = k
                self.last_click = (now, k)
        elif e.type == pg.MOUSEBUTTONUP and e.button in (1, 3) or e.type == pg.WINDOWFOCUSLOST:
            if e.type == pg.WINDOWFOCUSLOST or e.button == 1:
                self.drag = None
            if self.pressed is not None and self.pressed < len(self.envs):
                self.envs[self.pressed].release()
            self.pressed = None
        elif e.type == pg.MOUSEMOTION and self.drag:
            px, py = self.win.position
            self.win_set(position=(px + e.pos[0] - self.drag[0], py + e.pos[1] - self.drag[1]))
        elif e.type == pg.MOUSEWHEEL and self.mode != "grid":
            self.cur = (self.cur - e.y) % len(self.envs)
        return True

    def run(self, frames=None, keep_open=False):
        """Main loop. `frames`/`keep_open` let a test drive a fixed number of frames."""
        pg = self.pg
        running = True
        start = time.time()
        while running:
            dt = min(self.clock.tick(60) / 1000, .1)
            for e in pg.event.get():
                running = self.handle(e) and running
            now = time.time()
            if self.autocycle and self.mode != "grid" and now > self.cycle_at:
                self.cur = (self.cur + 1) % len(self.envs)
                self.cycle_at = now + 90
            layout = self.tiles(self.win.size)
            if not self.paused:
                for k, _ in layout:
                    env = self.envs[k]
                    self.acc[k] += dt * env.tempo
                    n = 0
                    while self.acc[k] >= 1 and n < 4:
                        env.step()
                        self.acc[k] -= 1
                        n += 1
                    self.acc[k] = min(self.acc[k], 1)
            screen = self.win.get_surface()
            screen.fill((4, 5, 9))
            t = now - start
            hover = self.win.focused and pg.mouse.get_focused()
            for k, rect in layout:
                self.draw_env(screen, self.envs[k], rect, t)
                if self.labels and (self.mode != "mini" or hover):
                    self.label(screen, self.envs[k], rect)
                    if self.mode != "grid" or rect.h >= 220:
                        self.status(screen, self.envs[k], rect)
            msg, at = self.toast
            if now - at < 2.5:
                img = self.small.render("saved " + msg, True, (255, 200, 120))
                screen.blit(img, (10, 8))
            if self.paused:
                img = self.font.render("PAUSED", True, (255, 200, 120))
                screen.blit(img, (screen.get_width() - img.get_width() - 10, 8))
            self.win.flip()
            if frames is not None:
                frames -= 1
                if frames <= 0:
                    break
        if not keep_open:
            pg.quit()


def run_headless(steps, seed):
    envs = [cls(None if seed is None else seed + k) for k, cls in enumerate(ENVIRONMENTS)]
    every = max(1, steps // 6)
    for env in envs:
        t0 = time.perf_counter()
        print(f"\n{env.name} ({env.mood}, {env.tempo} steps/s)")
        for s in range(1, steps + 1):
            env.step()
            if s % every == 0:
                print(f"  step {s:5d}  " + "  ".join(f"{k} {v}" for k, v in env.vitals().items()))
        ms = (time.perf_counter() - t0) / steps * 1000
        print(f"  {ms:.2f} ms/step  ->  {ms * env.tempo / 10:.1f}% of one core at its tempo")


def main(argv=None):
    ap = argparse.ArgumentParser(description="a little shelf of living pixel environments")
    ap.add_argument("--mini", action="store_true", help="start as a frameless always-on-top mini window")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--headless", type=int, default=0, metavar="STEPS", help="no window: print each env's vital signs")
    args = ap.parse_args(argv)
    if args.headless:
        run_headless(args.headless, args.seed)
        return
    try:
        import pygame  # noqa: F401
    except ImportError:
        sys.exit("Needs pygame-ce:  pip install pygame-ce")
    App(args).run()


if __name__ == "__main__":
    main()
