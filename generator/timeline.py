"""Shared timeline: maps video time T (seconds) to simulation time t."""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sim import simulate, DT  # noqa: E402

FPS = 60
T_INTRO = 1.35        # 3-2-1 countdown, balls held at the start
SLOW_PRE = 0.45       # slow motion starts this long (sim time) before the final break
SLOW_POST = 0.20      # ... and ends this long after it
SLOW_RATE = 0.30
OUTRO_LEN = 3.3       # normal speed after slow motion (winner card)
REWIND_LEN = 1.2      # fast rewind back to the first frame (seamless loop)
WIN_DELAY = 0.25      # winner card appears this long after slow motion ends

DEFAULT_PARAMS = (0.32, 0.16, 1.15)


class Timeline:
    def __init__(self, seed, params=DEFAULT_PARAMS):
        r = simulate(seed, *params)
        self.r = r
        self.rings = r["rings"]
        self.breaks = r["breaks"]
        self.hits = r["hits"]
        self.times = np.array([s[0] for s in r["states"]])
        self.pos = np.array([s[1] for s in r["states"]])
        self.t_f = self.breaks[-1][0]
        self.ts1 = self.t_f - SLOW_PRE
        self.ts2 = self.t_f + SLOW_POST
        self.T_s1 = T_INTRO + self.ts1
        self.T_s2 = self.T_s1 + (self.ts2 - self.ts1) / SLOW_RATE
        self.T_outro_end = self.T_s2 + OUTRO_LEN
        self.T_end = self.T_outro_end + REWIND_LEN
        self.T_win = self.T_s2 + WIN_DELAY
        self.sim_end = float(self.times[-1])
        self.t_rew_from = min(self.sim_end, self.ts2 + OUTRO_LEN)
        self.n_frames = int(round(self.T_end * FPS))
        self.break_times = np.array([b[0] for b in self.breaks])
        fs = self.final_scores()
        self.winner = fs.index(max(fs))

    def sim_time(self, T):
        if T < T_INTRO:
            return 0.0
        if T < self.T_s1:
            return T - T_INTRO
        if T < self.T_s2:
            return self.ts1 + (T - self.T_s1) * SLOW_RATE
        if T < self.T_outro_end:
            return min(self.sim_end, self.ts2 + (T - self.T_s2))
        u = min(max((T - self.T_outro_end) / REWIND_LEN, 0.0), 1.0)
        e = u * u * (3 - 2 * u)
        return self.t_rew_from * (1.0 - e)

    def video_time(self, t):
        if t < self.ts1:
            return T_INTRO + t
        if t < self.ts2:
            return self.T_s1 + (t - self.ts1) / SLOW_RATE
        return self.T_s2 + (t - self.ts2)

    def in_rewind(self, T):
        return T >= self.T_outro_end

    def positions(self, t):
        t = min(max(t, 0.0), self.sim_end)
        f = t / DT
        i = int(math.floor(f))
        if i >= len(self.times) - 1:
            return self.pos[-1]
        a = f - i
        return self.pos[i] * (1 - a) + self.pos[i + 1] * a

    def broken(self, t):
        return int(np.searchsorted(self.break_times, t, side="right"))

    def scores(self, t):
        sc = [0, 0, 0, 0]
        for (tb, ri, b) in self.breaks:
            if tb <= t:
                sc[b] += 1
        return sc

    def final_scores(self):
        sc = [0, 0, 0, 0]
        for (tb, ri, b) in self.breaks:
            sc[b] += 1
        return sc
