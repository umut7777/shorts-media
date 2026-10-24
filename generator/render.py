"""Render a ring-escape race Short frame by frame with pycairo.

A config dict decides the look of each video:
  cfg = {"balls": [palette indices x4], "theme": "night", "title": "WHICH  COLOR  WINS?"}
"""
import math
import os
import random
import subprocess
import sys

import cairo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sim import N_RINGS, CX, CY, BALL_R, RING_HALF, ring_angle  # noqa: E402
from timeline import FPS, T_INTRO  # noqa: E402

W, H = 1080, 1920
SCX, SCY = 540.0, 1060.0
Z0, Z1 = 1.12, 1.0
FONT = "Lilita One"
TAU = 2 * math.pi


def hexc(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def hsv(h, s, v):
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    p, q, t_ = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    return [(v, t_, p), (q, v, p), (p, v, t_), (p, q, v), (t_, p, v), (v, p, q)][i]


# ball colours: (name, base, dark, light, emoji)
PALETTE = [
    ("RED", "#FF4D5E", "#B0213A", "#FFB0B8", "🔴"),
    ("BLUE", "#3D8BFF", "#1E4DB5", "#B5D3FF", "🔵"),
    ("GREEN", "#35D45A", "#1A8536", "#B2F5BF", "🟢"),
    ("YELLOW", "#FFD23F", "#C08A10", "#FFF3B0", "🟡"),
    ("PURPLE", "#A45CFF", "#5E25B8", "#DCC2FF", "🟣"),
    ("ORANGE", "#FF9A2E", "#B85A0A", "#FFD3A3", "🟠"),
    ("PINK", "#FF6FC8", "#B52D84", "#FFC7EA", "🩷"),
    ("CYAN", "#2FD8E8", "#12838F", "#B8F6FB", "🩵"),
]
COLS = [(hexc(b), hexc(d), hexc(l)) for (_, b, d, l, _) in PALETTE]
NAMES = [p[0] for p in PALETTE]
EMOJI = [p[4] for p in PALETTE]

OUTLINE = hexc("#1A0B3D")
GOLD = hexc("#FFD23F")


def ring_colors(kind):
    n = N_RINGS
    if kind == "pastel":
        return [hsv((0.95 - i / n) % 1.0, 0.45, 1.0) for i in range(n)]
    if kind == "candy":
        return [hsv((0.92 - 0.34 * i / (n - 1)) % 1.0, 0.62, 1.0) for i in range(n)]
    if kind == "ocean":
        return [hsv(0.40 + 0.24 * i / (n - 1), 0.70, 1.0) for i in range(n)]
    if kind == "halloween":
        cyc = [hexc("#FF8A1F"), hexc("#9B4DFF"), hexc("#7CFF4F")]
        return [cyc[i % 3] for i in range(n)]
    return [hsv((0.95 - i / n) % 1.0, 0.72, 1.0) for i in range(n)]


THEMES = {
    "night": dict(bg=("#24104F", "#16195A", "#0B0F33"), glow=(0.55, 0.45, 1.0), rings="rainbow"),
    "space": dict(bg=("#070A1E", "#0B1030", "#02030A"), glow=(0.3, 0.5, 1.0), rings="rainbow"),
    "ocean": dict(bg=("#052B4A", "#06405E", "#021626"), glow=(0.2, 0.8, 1.0), rings="ocean"),
    "candy": dict(bg=("#3A0D45", "#4D1462", "#1E0830"), glow=(1.0, 0.45, 0.85), rings="candy"),
    "sunset": dict(bg=("#3A1240", "#5B1E4E", "#1B0A26"), glow=(1.0, 0.55, 0.4), rings="pastel"),
    "halloween": dict(bg=("#1C0B2E", "#2B0F3A", "#0A0510"), glow=(1.0, 0.55, 0.15), rings="halloween"),
}

BADGE_X = [135, 405, 675, 945]
BADGE_Y = 340
TITLE_Y = 178
NAME_Y = 420
STATUS_Y = 480


def smoothstep(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def ease_out_back(x):
    x = min(max(x, 0.0), 1.0)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def ease_out_elastic(x):
    x = min(max(x, 0.0), 1.0)
    if x in (0.0, 1.0):
        return x
    return 2 ** (-10 * x) * math.sin((x * 10 - 0.75) * (TAU / 3)) + 1


# ---------------------------------------------------------------- text
def text_extents(ctx, text, size):
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)
    return ctx.text_extents(text)


def draw_text(ctx, text, x, y, size, fill=(1, 1, 1), outline=OUTLINE, ow=None,
              alpha=1.0, colors=None, shadow=True, max_w=None, scale=1.0):
    if alpha <= 0.01 or scale <= 0.01:
        return
    ext = text_extents(ctx, text, size)
    if max_w and ext.x_advance > max_w:
        size = size * max_w / ext.x_advance
        ext = text_extents(ctx, text, size)
    if ow is None:
        ow = size * 0.16
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(scale, scale)
    x0 = -(ext.x_bearing + ext.width / 2)
    by = -(ext.y_bearing + ext.height / 2)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    if shadow:
        ctx.new_path()
        ctx.move_to(x0, by + size * 0.07)
        ctx.text_path(text)
        ctx.set_source_rgba(0, 0, 0, 0.35 * alpha)
        ctx.set_line_width(ow)
        ctx.stroke_preserve()
        ctx.fill()
    ctx.new_path()
    ctx.move_to(x0, by)
    ctx.text_path(text)
    ctx.set_source_rgba(*outline, alpha)
    ctx.set_line_width(ow)
    ctx.stroke()
    if colors:
        cx = x0
        k = 0
        for ch in text:
            adv = ctx.text_extents(ch).x_advance
            if ch != " ":
                ctx.new_path()
                ctx.move_to(cx, by)
                ctx.text_path(ch)
                ctx.set_source_rgba(*colors[k % len(colors)], alpha)
                ctx.fill()
                k += 1
            cx += adv
    else:
        ctx.new_path()
        ctx.move_to(x0, by)
        ctx.text_path(text)
        ctx.set_source_rgba(*fill, alpha)
        ctx.fill()
    ctx.restore()


# ---------------------------------------------------------------- shapes
def rounded_rect(ctx, x, y, w, h, r):
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    ctx.close_path()


def draw_crown(ctx, x, y, s, alpha=1.0):
    w, h = s, s * 0.72
    pts = [(-w / 2, h / 2), (-w / 2, -h * 0.18), (-w * 0.25, h * 0.10), (0, -h / 2),
           (w * 0.25, h * 0.10), (w / 2, -h * 0.18), (w / 2, h / 2)]
    ctx.save()
    ctx.translate(x, y)
    ctx.new_path()
    ctx.move_to(*pts[0])
    for p in pts[1:]:
        ctx.line_to(*p)
    ctx.close_path()
    g = cairo.LinearGradient(0, -h / 2, 0, h / 2)
    g.add_color_stop_rgba(0, *hexc("#FFF1A6"), alpha)
    g.add_color_stop_rgba(1, *hexc("#F5A800"), alpha)
    ctx.set_source(g)
    ctx.fill_preserve()
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.set_line_width(s * 0.07)
    ctx.set_source_rgba(*hexc("#7A4A00"), alpha)
    ctx.stroke()
    for (px, py), col in zip([(-w / 2, -h * 0.18), (0, -h / 2), (w / 2, -h * 0.18)],
                             [hexc("#FF4D5E"), hexc("#3D8BFF"), hexc("#35D45A")]):
        ctx.arc(px, py, s * 0.085, 0, TAU)
        ctx.set_source_rgba(*col, alpha)
        ctx.fill_preserve()
        ctx.set_line_width(s * 0.04)
        ctx.set_source_rgba(*hexc("#7A4A00"), alpha)
        ctx.stroke()
    ctx.restore()


def draw_star(ctx, x, y, r, rot, alpha, col=(1, 1, 1)):
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rot)
    ctx.new_path()
    for k in range(8):
        rr = r if k % 2 == 0 else r * 0.32
        a = k * math.pi / 4
        ctx.line_to(rr * math.cos(a), rr * math.sin(a))
    ctx.close_path()
    ctx.set_source_rgba(*col, alpha)
    ctx.fill()
    ctx.restore()


def draw_bat(ctx, x, y, s, alpha):
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(s, s)
    ctx.new_path()
    ctx.move_to(0, -6)
    ctx.curve_to(8, -14, 22, -16, 34, -8)
    ctx.curve_to(28, -6, 26, 0, 28, 6)
    ctx.curve_to(22, 2, 16, 2, 12, 8)
    ctx.curve_to(8, 4, 4, 4, 0, 10)
    ctx.curve_to(-4, 4, -8, 4, -12, 8)
    ctx.curve_to(-16, 2, -22, 2, -28, 6)
    ctx.curve_to(-26, 0, -28, -6, -34, -8)
    ctx.curve_to(-22, -16, -8, -14, 0, -6)
    ctx.close_path()
    ctx.set_source_rgba(0.03, 0.01, 0.06, alpha)
    ctx.fill()
    ctx.restore()


def draw_ball(ctx, x, y, r, col, lookx=0.0, looky=0.0, blink=False, mouth_open=False,
              alpha=1.0, glow=True):
    base, dark, light = col
    if glow:
        rg = cairo.RadialGradient(x, y, r * 0.7, x, y, r * 2.0)
        rg.add_color_stop_rgba(0, *base, 0.38 * alpha)
        rg.add_color_stop_rgba(1, *base, 0.0)
        ctx.set_source(rg)
        ctx.arc(x, y, r * 2.0, 0, TAU)
        ctx.fill()
    g = cairo.RadialGradient(x - r * 0.35, y - r * 0.4, r * 0.08, x, y, r * 1.05)
    g.add_color_stop_rgba(0, *light, alpha)
    g.add_color_stop_rgba(0.55, *base, alpha)
    g.add_color_stop_rgba(1, *dark, alpha)
    ctx.new_path()
    ctx.arc(x, y, r, 0, TAU)
    ctx.set_source(g)
    ctx.fill_preserve()
    ctx.set_line_width(max(1.2, r * 0.11))
    ctx.set_source_rgba(*(c * 0.6 for c in dark), alpha)
    ctx.stroke()
    for s in (-1, 1):
        ctx.arc(x + s * r * 0.6, y + r * 0.2, r * 0.13, 0, TAU)
        ctx.set_source_rgba(1.0, 0.45, 0.6, 0.45 * alpha)
        ctx.fill()
    ex, ey = r * 0.34, -r * 0.14
    erx, ery = r * 0.25, r * 0.30
    ink = (0.07, 0.06, 0.12)
    for s in (-1, 1):
        cx, cy = x + s * ex, y + ey
        if blink:
            ctx.new_path()
            ctx.move_to(cx - erx, cy)
            ctx.line_to(cx + erx, cy)
            ctx.set_line_width(max(1.0, r * 0.08))
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            ctx.set_source_rgba(*ink, alpha)
            ctx.stroke()
            continue
        ctx.save()
        ctx.translate(cx, cy)
        ctx.scale(erx, ery)
        ctx.new_path()
        ctx.arc(0, 0, 1, 0, TAU)
        ctx.restore()
        ctx.set_source_rgba(1, 1, 1, alpha)
        ctx.fill_preserve()
        ctx.set_line_width(max(0.8, r * 0.045))
        ctx.set_source_rgba(*ink, alpha)
        ctx.stroke()
        px, py = cx + lookx * erx * 0.42, cy + looky * ery * 0.42
        ctx.new_path()
        ctx.arc(px, py, r * 0.135, 0, TAU)
        ctx.set_source_rgba(*ink, alpha)
        ctx.fill()
        ctx.arc(px - r * 0.05, py - r * 0.06, r * 0.05, 0, TAU)
        ctx.set_source_rgba(1, 1, 1, alpha)
        ctx.fill()
    ctx.new_path()
    if mouth_open:
        ctx.arc(x, y + r * 0.22, r * 0.27, 0, math.pi)
        ctx.close_path()
        ctx.set_source_rgba(0.35, 0.05, 0.12, alpha)
        ctx.fill_preserve()
        ctx.set_line_width(max(0.8, r * 0.05))
        ctx.set_source_rgba(*ink, alpha)
        ctx.stroke()
        ctx.new_path()
        ctx.arc(x, y + r * 0.40, r * 0.11, math.pi, TAU)
        ctx.set_source_rgba(1.0, 0.45, 0.55, alpha)
        ctx.fill()
    else:
        ctx.arc(x, y + r * 0.14, r * 0.30, 0.18 * math.pi, 0.82 * math.pi)
        ctx.set_line_width(max(1.0, r * 0.085))
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_source_rgba(*ink, alpha)
        ctx.stroke()


# ---------------------------------------------------------------- scene
class Scene:
    def __init__(self, tl, cfg):
        self.tl = tl
        self.cfg = cfg
        self.cols = [COLS[i] for i in cfg["balls"]]
        self.names = [NAMES[i] for i in cfg["balls"]]
        self.theme = THEMES[cfg.get("theme", "night")]
        self.ring_col = ring_colors(self.theme["rings"])
        self.title = cfg.get("title", "WHICH  COLOR  WINS?")
        self.bg = self.make_background()
        rnd = random.Random(7)
        self.twinkles = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(1.2, 3.0),
                          rnd.uniform(0, TAU), rnd.uniform(1.5, 4.0)) for _ in range(40)]
        self.shards = []
        for k, (tb, ri, b) in enumerate(tl.breaks):
            ring = tl.rings[ri]
            th = ring_angle(ring, tb)
            a = ring["alpha"]
            R = ring["R"]
            rr = random.Random(1000 + ri)
            lst = []
            K = 46
            for j in range(K):
                ang = th + a + (TAU - 2 * a) * (j + rr.uniform(0.15, 0.85)) / K
                lst.append(dict(ang=ang, R=R, vr=rr.uniform(180, 620), vt=rr.uniform(-170, 170),
                                spin=rr.uniform(-10, 10), ln=(TAU * R / K) * rr.uniform(0.55, 0.95),
                                white=rr.random() < 0.18))
            self.shards.append(lst)
        self.break_pos = []
        for (tb, ri, b) in tl.breaks:
            p = tl.positions(tb)
            self.break_pos.append((p[2 * b], p[2 * b + 1]))
        self.combo = []
        for k in range(1, len(tl.breaks)):
            if tl.breaks[k][2] == tl.breaks[k - 1][2] and tl.breaks[k][0] - tl.breaks[k - 1][0] < 0.6:
                self.combo.append((tl.breaks[k][0], tl.breaks[k][2]))
        rc = random.Random(11)
        pal = [c[0] for c in self.cols] + [hexc("#FF7AD9"), (1, 1, 1), hexc("#7AF0FF")]
        self.confetti = [dict(x=rc.uniform(-20, W + 20), y=rc.uniform(-1100, -40), vy=rc.uniform(380, 760),
                              vx=rc.uniform(-50, 50), amp=rc.uniform(10, 40), fr=rc.uniform(2, 5),
                              ph=rc.uniform(0, TAU), rot=rc.uniform(0, TAU), rs=rc.uniform(-7, 7),
                              w=rc.uniform(12, 20), h=rc.uniform(7, 11), col=rc.choice(pal))
                         for _ in range(190)]

    def make_background(self):
        th = self.theme
        bg = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        c = cairo.Context(bg)
        lg = cairo.LinearGradient(0, 0, 0, H)
        for stop, col in zip((0.0, 0.5, 1.0), th["bg"]):
            lg.add_color_stop_rgb(stop, *hexc(col))
        c.set_source(lg)
        c.paint()
        rg = cairo.RadialGradient(SCX, SCY, 0, SCX, SCY, 700)
        rg.add_color_stop_rgba(0, *th["glow"], 0.25)
        rg.add_color_stop_rgba(1, *th["glow"], 0.0)
        c.set_source(rg)
        c.paint()
        rnd = random.Random(3)
        for _ in range(140):
            x, y = rnd.uniform(0, W), rnd.uniform(0, H)
            c.arc(x, y, rnd.uniform(0.8, 2.2), 0, TAU)
            c.set_source_rgba(1, 1, 1, rnd.uniform(0.12, 0.45))
            c.fill()
        for _ in range(26):
            x, y = rnd.uniform(0, W), rnd.uniform(0, H)
            col = self.cols[rnd.randrange(4)][0]
            c.arc(x, y, rnd.uniform(18, 46), 0, TAU)
            c.set_source_rgba(*col, 0.06)
            c.fill()
        if self.cfg.get("theme") == "halloween":
            mg = cairo.RadialGradient(860, 1720, 10, 860, 1720, 170)
            mg.add_color_stop_rgba(0, 1.0, 0.92, 0.6, 0.55)
            mg.add_color_stop_rgba(0.6, 1.0, 0.85, 0.45, 0.35)
            mg.add_color_stop_rgba(1, 1.0, 0.7, 0.3, 0.0)
            c.set_source(mg)
            c.arc(860, 1720, 170, 0, TAU)
            c.fill()
            for (x, y, s) in [(160, 1640, 1.6), (300, 1760, 1.1), (700, 1600, 1.3), (960, 1560, 0.9),
                              (90, 560, 0.8), (1000, 600, 0.9)]:
                draw_bat(c, x, y, s, 0.85)
        return bg

    def zoom(self, t):
        f = sum(smoothstep((t - tb) / 0.7) for tb in self.tl.break_times) / N_RINGS
        return Z0 + (Z1 - Z0) * f

    def shake(self, t):
        sx = sy = 0.0
        for k, tb in enumerate(self.tl.break_times):
            a = t - tb
            if 0 <= a < 0.25:
                amp = 8.0 * math.exp(-a / 0.06)
                sx += amp * math.sin(a * 95 + k)
                sy += amp * math.cos(a * 77 + 2 * k)
        return sx, sy

    def to_screen(self, wx, wy, z, sh):
        return SCX + sh[0] + z * (wx - CX), SCY + sh[1] + z * (wy - CY)

    def vage(self, T, tb):
        return T - self.tl.video_time(tb)

    def draw(self, ctx, T):
        tl = self.tl
        rew = tl.in_rewind(T)
        t = tl.sim_time(T)
        intro = T < T_INTRO
        z = self.zoom(t)
        sh = self.shake(t)
        nb = tl.broken(t)

        ctx.set_source_surface(self.bg, 0, 0)
        ctx.paint()
        for (x, y, r, ph, fr) in self.twinkles:
            ctx.arc(x, y, r, 0, TAU)
            ctx.set_source_rgba(1, 1, 1, 0.25 + 0.25 * math.sin(T * fr + ph))
            ctx.fill()

        ctx.save()
        ctx.translate(SCX + sh[0], SCY + sh[1])
        ctx.scale(z, z)
        ctx.translate(-CX, -CY)

        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        for i in range(nb, N_RINGS):
            ring = tl.rings[i]
            R = ring["R"]
            th = ring_angle(ring, t)
            a = ring["alpha"]
            col = self.ring_col[i]
            a1, a2 = th + a, th + TAU - a
            active = (i == nb)
            glow_a = 0.20 + (0.18 + 0.14 * math.sin(T * 7.0) if active else 0.0)
            ctx.new_path()
            ctx.arc(CX, CY, R, a1, a2)
            ctx.set_source_rgba(*col, glow_a)
            ctx.set_line_width(RING_HALF * 2 + (14 if active else 9))
            ctx.stroke()
            ctx.new_path()
            ctx.arc(CX, CY, R, a1, a2)
            ctx.set_source_rgb(*col)
            ctx.set_line_width(RING_HALF * 2)
            ctx.stroke()
            ctx.new_path()
            ctx.arc(CX, CY, R - 1.3, a1, a2)
            ctx.set_source_rgba(1, 1, 1, 0.5)
            ctx.set_line_width(2.0)
            ctx.stroke()

        for k, (tb, ri, b) in enumerate(tl.breaks):
            age = t - tb
            if age < 0 or age > 1.3:
                continue
            col = self.ring_col[ri]
            R = tl.rings[ri]["R"]
            if age < 0.32:
                u = age / 0.32
                ctx.new_path()
                ctx.arc(CX, CY, R + 95 * (1 - (1 - u) ** 2), 0, TAU)
                ctx.set_source_rgba(1, 1, 1, 0.65 * (1 - u))
                ctx.set_line_width(7 * (1 - u) + 0.5)
                ctx.stroke()
            fade = (1 - age / 1.3) ** 1.2
            ctx.set_line_width(RING_HALF * 1.6)
            for s in self.shards[k]:
                ca, sa = math.cos(s["ang"]), math.sin(s["ang"])
                px = CX + s["R"] * ca + (s["vr"] * ca - s["vt"] * sa) * age
                py = CY + s["R"] * sa + (s["vr"] * sa + s["vt"] * ca) * age + 0.5 * 1400 * age * age
                rot = s["ang"] + math.pi / 2 + s["spin"] * age
                hl = s["ln"] * 0.5
                ctx.new_path()
                ctx.move_to(px - hl * math.cos(rot), py - hl * math.sin(rot))
                ctx.line_to(px + hl * math.cos(rot), py + hl * math.sin(rot))
                if s["white"]:
                    ctx.set_source_rgba(1, 1, 1, fade)
                else:
                    ctx.set_source_rgba(*col, fade)
                ctx.stroke()

        p = tl.positions(t)
        pv = tl.positions(max(0.0, t - 0.02))
        show_trail = (not intro) and (not rew) and t > 0.03
        for b in range(4):
            if show_trail:
                for k in range(9, 0, -1):
                    tk = t - k * 0.011
                    if tk < 0:
                        continue
                    q = tl.positions(tk)
                    ctx.new_path()
                    ctx.arc(q[2 * b], q[2 * b + 1], BALL_R * (1 - k / 11.0), 0, TAU)
                    ctx.set_source_rgba(*self.cols[b][0], 0.30 * (1 - k / 10.0))
                    ctx.fill()
        for b in range(4):
            x, y = p[2 * b], p[2 * b + 1]
            if intro:
                y += math.sin(T * 9 + b * 1.7) * 3.0
                lx, ly = math.cos(T * 2.2 + b), 0.5 * math.sin(T * 2.2 + b)
            else:
                vx, vy = x - pv[2 * b], y - pv[2 * b + 1]
                n = math.hypot(vx, vy)
                lx, ly = (vx / n, vy / n) if n > 1e-6 else (0.0, 0.0)
            blink = ((T + b * 0.83 + 1.0) % 3.1) < 0.11
            mouth = (not rew) and any(bb == b and 0 <= self.vage(T, tb) < 0.7 for (tb, ri, bb) in tl.breaks)
            draw_ball(ctx, x, y, BALL_R, self.cols[b], lx, ly, blink, mouth)
        ctx.restore()

        if not rew:
            for k, (tb, ri, b) in enumerate(tl.breaks):
                age = self.vage(T, tb)
                if 0 <= age < 0.85:
                    wx, wy = self.break_pos[k]
                    sx, sy = self.to_screen(wx, wy, z, sh)
                    u = age / 0.85
                    draw_text(ctx, "+1", sx, sy - 45 - 110 * (1 - (1 - u) ** 2), 72,
                              fill=self.cols[b][0], outline=(1, 1, 1), ow=12,
                              alpha=1 - u ** 2, scale=ease_out_back(min(1, age / 0.18)))
            for (tc, b) in self.combo:
                age = self.vage(T, tc)
                if 0 <= age < 1.1:
                    u = age / 1.1
                    draw_text(ctx, "DOUBLE!", SCX, SCY - 230, 120, fill=self.cols[b][0], outline=(1, 1, 1),
                              ow=16, alpha=1 - u ** 3, scale=ease_out_back(min(1, age / 0.22)) * (1 + 0.1 * u))

        if intro:
            n = 3 - int(T / 0.45)
            a = (T % 0.45) / 0.45
            draw_text(ctx, str(max(n, 1)), SCX, SCY - 245, 230, fill=(1, 1, 1), ow=26,
                      scale=1.35 - 0.35 * smoothstep(a * 1.6), alpha=1 - 0.5 * a ** 3)
        elif not rew and T < T_INTRO + 0.6:
            u = (T - T_INTRO) / 0.6
            draw_text(ctx, "GO!", SCX, SCY - 245, 220, colors=[c[0] for c in self.cols], ow=26,
                      scale=0.7 + 0.6 * ease_out_back(min(1, u * 2.5)), alpha=1 - u ** 2)

        self.draw_hud(ctx, T, t, nb, rew, intro)
        if T >= tl.T_win:
            self.draw_winner(ctx, T, rew)
        if rew:
            self.draw_rewind(ctx, T)

    def draw_hud(self, ctx, T, t, nb, rew, intro):
        tl = self.tl
        draw_text(ctx, self.title, SCX, TITLE_Y, 104, colors=[c[0] for c in self.cols],
                  outline=(1, 1, 1), ow=18, max_w=1010)
        sc = tl.scores(t)
        mx = max(sc)
        leaders = [i for i in range(4) if sc[i] == mx]
        final_stage = (nb == N_RINGS - 1) and not rew and T < tl.T_win
        for ci in range(4):
            pulse = 0.0
            if not rew:
                for (tb, ri, b) in tl.breaks:
                    a = self.vage(T, tb)
                    if b == ci and 0 <= a < 0.35:
                        pulse = max(pulse, math.sin(math.pi * a / 0.35))
            s = 1 + 0.22 * pulse
            ctx.save()
            ctx.translate(BADGE_X[ci], BADGE_Y)
            ctx.scale(s, s)
            lead = (len(leaders) == 1 and leaders[0] == ci and mx > 0)
            tied = final_stage and len(leaders) > 1 and ci in leaders
            if lead or tied:
                rounded_rect(ctx, -120, -58, 240, 116, 32)
                ctx.set_source_rgba(*GOLD, (0.25 + 0.1 * math.sin(T * 8)) if lead
                                    else (0.30 + 0.25 * math.sin(T * 12)))
                ctx.fill()
            rounded_rect(ctx, -110, -50, 220, 100, 28)
            ctx.set_source_rgba(0.06, 0.04, 0.17, 0.78)
            ctx.fill_preserve()
            ctx.set_line_width(6)
            ctx.set_source_rgb(*(GOLD if lead else self.cols[ci][0]))
            ctx.stroke()
            blink = ((T + ci * 1.3) % 3.7) < 0.1
            draw_ball(ctx, -56, 0, 31, self.cols[ci], 0.35, 0.0, blink, pulse > 0.05, glow=False)
            fillc = tuple(1 - (1 - c) * pulse * 0.8 for c in self.cols[ci][2]) if pulse > 0 else (1, 1, 1)
            draw_text(ctx, str(sc[ci]), 42, 2, 80, fill=fillc, ow=13, shadow=False)
            ctx.restore()
            draw_text(ctx, self.names[ci], BADGE_X[ci], NAME_Y, 34, fill=self.cols[ci][0], ow=8, max_w=200)
        if len(leaders) == 1 and mx > 0:
            draw_crown(ctx, BADGE_X[leaders[0]], BADGE_Y - 70 + math.sin(T * 6) * 4, 58)

        if intro:
            draw_text(ctx, "PICK YOUR COLOR!", SCX, STATUS_Y, 62, fill=GOLD, ow=12,
                      scale=1 + 0.05 * math.sin(T * 10))
        elif rew:
            left = tl.T_end - T
            if left < 0.35:
                draw_text(ctx, "PICK YOUR COLOR!", SCX, STATUS_Y, 62, fill=GOLD, ow=12, alpha=1 - left / 0.35)
        elif T >= tl.T_win:
            pass
        elif nb < N_RINGS - 1:
            draw_text(ctx, f"RINGS LEFT: {N_RINGS - nb}", SCX, STATUS_Y, 54, fill=(1, 1, 1), ow=11)
        elif nb == N_RINGS - 1:
            n_tied = len(leaders)
            flash = (int(T * 6) % 2) == 0
            pop = 1 + 0.07 * math.sin(T * 14)
            if n_tied >= 2:
                head = "TIE!" if n_tied == 2 else f"{n_tied}-WAY TIE!"
                draw_text(ctx, head, SCX, STATUS_Y, 78, fill=GOLD if flash else (1, 1, 1), ow=14, scale=pop)
                draw_text(ctx, "LAST RING WINS!", SCX, STATUS_Y + 72, 54, fill=(1, 1, 1), ow=11)
            else:
                draw_text(ctx, "LAST RING!", SCX, STATUS_Y, 72, fill=GOLD if flash else (1, 1, 1), ow=13,
                          scale=pop)

    def draw_winner(self, ctx, T, rew):
        tl = self.tl
        w = tl.winner
        age = T - tl.T_win
        fade = 1.0
        if rew:
            fade = max(0.0, 1 - (T - tl.T_outro_end) / 0.22)
            if fade <= 0:
                return
        ctx.set_source_rgba(0.03, 0.02, 0.10, 0.55 * smoothstep(age / 0.25) * fade)
        ctx.paint()
        for k in range(10):
            a = k * TAU / 10 + age * 0.8
            rr = 235 + 18 * math.sin(age * 3 + k)
            tw = 0.5 + 0.5 * math.sin(age * 9 + k * 1.7)
            draw_star(ctx, SCX + rr * math.cos(a), 1110 + rr * math.sin(a), 16 + 8 * tw, age * 2 + k,
                      0.9 * fade * smoothstep(age / 0.4), col=(1, 1, 0.85))
        r = 150 * ease_out_elastic(age / 0.95)
        if r > 1:
            draw_ball(ctx, SCX, 1110, r, self.cols[w], 0.0, 0.15, False, True, alpha=fade)
            draw_crown(ctx, SCX, 1110 - r - 52 * (r / 150), 130 * (r / 150), alpha=fade)
        draw_text(ctx, f"{self.names[w]} WINS!", SCX, 735, 150, fill=self.cols[w][0], outline=(1, 1, 1), ow=22,
                  alpha=fade, scale=ease_out_back(min(1, age / 0.35)), max_w=1010)
        if age > 0.9:
            u = min(1.0, (age - 0.9) / 0.3)
            draw_text(ctx, f"DID YOU PICK {self.names[w]}?", SCX, 1440, 70, fill=(1, 1, 1), ow=13,
                      alpha=fade * u, scale=0.8 + 0.2 * ease_out_back(u), max_w=1000)
        for c in self.confetti:
            x = c["x"] + c["vx"] * age + c["amp"] * math.sin(c["fr"] * age + c["ph"])
            y = c["y"] + c["vy"] * age
            if y < -30 or y > H + 30:
                continue
            ctx.save()
            ctx.translate(x, y)
            rot = c["rot"] + c["rs"] * age
            ctx.rotate(rot)
            ctx.scale(1.0, max(0.15, abs(math.cos(rot * 1.3))))
            ctx.rectangle(-c["w"] / 2, -c["h"] / 2, c["w"], c["h"])
            ctx.set_source_rgba(*c["col"], 0.95 * fade)
            ctx.fill()
            ctx.restore()

    def draw_rewind(self, ctx, T):
        tl = self.tl
        u = (T - tl.T_outro_end) / (tl.T_end - tl.T_outro_end)
        a = min(1.0, u * 5) * min(1.0, max(0.0, (0.88 - u) * 7))
        if a <= 0.005:
            return
        ctx.set_source_rgba(0.25, 0.5, 1.0, 0.10 * a)
        ctx.paint()
        ctx.set_source_rgba(1, 1, 1, 0.06 * a)
        y = -12 + (T * 600) % 12
        while y < H:
            ctx.rectangle(0, y, W, 3)
            y += 12
        ctx.fill()
        rounded_rect(ctx, SCX - 300, SCY - 70, 600, 140, 70)
        ctx.set_source_rgba(0.05, 0.03, 0.15, 0.55 * a)
        ctx.fill()
        cx, cy, s = SCX - 205, SCY, 40
        ctx.new_path()
        for dx in (0, 58):
            ctx.move_to(cx + dx - s, cy)
            ctx.line_to(cx + dx + s * 0.4, cy - s * 0.9)
            ctx.line_to(cx + dx + s * 0.4, cy + s * 0.9)
            ctx.close_path()
        ctx.set_source_rgba(1, 1, 1, 0.9 * a)
        ctx.fill_preserve()
        ctx.set_line_width(6)
        ctx.set_source_rgba(*OUTLINE, 0.9 * a)
        ctx.stroke()
        draw_text(ctx, "REWIND", SCX + 70, SCY + 4, 96, fill=(1, 1, 1), ow=14, alpha=a)


def make_ctx():
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    ctx.set_antialias(cairo.ANTIALIAS_BEST)
    return surf, ctx


def preview(tl, cfg, times, out_dir):
    sc = Scene(tl, cfg)
    paths = []
    for T in times:
        surf, ctx = make_ctx()
        sc.draw(ctx, T)
        p = os.path.join(out_dir, f"preview_{T:06.2f}.png")
        surf.write_to_png(p)
        paths.append(p)
    return paths


def render_video(tl, cfg, out, crf=21):
    sc = Scene(tl, cfg)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    surf, ctx = make_ctx()
    for f in range(tl.n_frames):
        ctx.save()
        sc.draw(ctx, f / FPS)
        ctx.restore()
        surf.flush()
        proc.stdin.write(bytes(surf.get_data()))
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed")
