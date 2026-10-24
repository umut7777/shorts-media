"""Synthesise the soundtrack (all sounds generated here, no samples).

cfg["music"] = {"key": semitones above C, "melody": idx, "prog": idx, "bpm": float}
"""
import math
import os
import random
import sys
import wave

import numpy as np
from scipy.signal import butter, sosfilt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from timeline import T_INTRO  # noqa: E402

SR = 48000
PAN = [-0.55, -0.18, 0.18, 0.55]
rng = np.random.default_rng(5)

PENTA = [0, 2, 4, 7, 9]
MELODIES = [
    [0, 2, 4, 5, 4, 2, 1, 2, 4, 7, 5, 4, 5, 7, 8, 7, 5, 4, 2, 4, 5, 4, 2, 1],
    [4, 5, 7, 5, 4, 2, 4, 2, 0, 2, 4, 5, 7, 9, 7, 5, 4, 5, 4, 2, 1, 2, 4, 2],
    [2, 4, 2, 0, 1, 2, 4, 5, 7, 5, 4, 5, 2, 4, 5, 7, 8, 7, 5, 7, 4, 5, 2, 1],
    [7, 5, 4, 5, 7, 8, 7, 5, 4, 2, 4, 5, 2, 1, 0, 1, 2, 4, 5, 4, 7, 5, 4, 2],
]
PROGS = [
    [(0, "maj"), (9, "min"), (5, "maj"), (7, "maj")],
    [(0, "maj"), (7, "maj"), (9, "min"), (5, "maj")],
    [(9, "min"), (5, "maj"), (0, "maj"), (7, "maj")],
]


def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def penta_hz(idx, key, base=72):
    octave, deg = divmod(idx, 5)
    return midi_hz(base + key + 12 * octave + PENTA[deg])


def env_exp(n, decay, attack=0.003):
    t = np.arange(n) / SR
    e = np.exp(-t / decay)
    a = int(attack * SR)
    if a > 0:
        e[:a] *= np.linspace(0, 1, a)
    return e


def sine(f, dur, phase=0.0):
    t = np.arange(int(dur * SR)) / SR
    return np.sin(2 * np.pi * f * t + phase)


def hp(x, fc):
    return sosfilt(butter(2, fc, "highpass", fs=SR, output="sos"), x)


def lp(x, fc):
    return sosfilt(butter(2, fc, "lowpass", fs=SR, output="sos"), x)


def bp(x, lo, hi):
    return sosfilt(butter(2, [lo, hi], "bandpass", fs=SR, output="sos"), x)


class Mix:
    def __init__(self, dur):
        self.n = int(math.ceil(dur * SR))
        self.L = np.zeros(self.n)
        self.R = np.zeros(self.n)

    def add(self, sig, T, gain=1.0, pan=0.0):
        i = int(round(T * SR))
        if i >= self.n or i + len(sig) <= 0:
            return
        if i < 0:
            sig = sig[-i:]
            i = 0
        sig = sig[: self.n - i]
        gl = gain * math.sqrt(0.5 * (1 - pan))
        gr = gain * math.sqrt(0.5 * (1 + pan))
        self.L[i:i + len(sig)] += sig * gl
        self.R[i:i + len(sig)] += sig * gr


def kalimba(f, dur=0.45):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = (np.sin(2 * np.pi * f * t) * np.exp(-t / 0.22)
         + 0.35 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t / 0.08)
         + 0.20 * np.sin(2 * np.pi * 4.07 * f * t) * np.exp(-t / 0.025))
    s[: int(0.002 * SR)] *= np.linspace(0, 1, int(0.002 * SR))
    return s


def bell(f, dur=0.9):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = (np.sin(2 * np.pi * f * t) * np.exp(-t / 0.35)
         + 0.45 * np.sin(2 * np.pi * 2.76 * f * t) * np.exp(-t / 0.16)
         + 0.25 * np.sin(2 * np.pi * 5.4 * f * t) * np.exp(-t / 0.06))
    s[: int(0.002 * SR)] *= np.linspace(0, 1, int(0.002 * SR))
    return s


def boop(f0=420, dur=0.09):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f0 * (1 - 0.45 * t / dur)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(n, 0.03, 0.002)


def tink(f=2600, dur=0.08):
    return sine(f, dur) * env_exp(int(dur * SR), 0.02, 0.001)


def tick(dur=0.012):
    n = int(dur * SR)
    return hp(rng.standard_normal(n), 4000) * env_exp(n, 0.004, 0.0005)


def kick(dur=0.22):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 45 + 95 * np.exp(-t / 0.035)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(n, 0.10, 0.001)


def hat(dur=0.05):
    n = int(dur * SR)
    return hp(rng.standard_normal(n), 7000) * env_exp(n, 0.015, 0.0005)


def snare(dur=0.16):
    n = int(dur * SR)
    noise = bp(rng.standard_normal(n), 1500, 6000) * env_exp(n, 0.05, 0.001)
    body = sine(190, dur) * env_exp(n, 0.04, 0.001)
    return 0.8 * noise + 0.5 * body


def pluck_bass(f, dur=0.32):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for h in range(1, 7):
        s += np.sin(2 * np.pi * f * h * t) / h * np.exp(-t * (6 + 5 * h))
    s[: int(0.004 * SR)] *= np.linspace(0, 1, int(0.004 * SR))
    return s


def pad(freqs, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for f in freqs:
        for det in (-0.6, 0.6):
            s += (2 / np.pi) * np.arcsin(np.sin(2 * np.pi * (f + det) * t))
    s /= len(freqs) * 2
    a, r = int(0.15 * SR), int(0.25 * SR)
    e = np.ones(n)
    e[:a] = np.linspace(0, 1, a)
    e[-r:] *= np.linspace(1, 0, r)
    return lp(s * e, 2500)


def brass(f, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for h in range(1, 9):
        s += np.sin(2 * np.pi * f * h * t + h) / h
    a, r = int(0.03 * SR), int(0.12 * SR)
    e = np.ones(n)
    e[:a] = np.linspace(0, 1, a)
    e[-r:] *= np.linspace(1, 0, r)
    return lp(s * e * (1 + 0.004 * np.sin(2 * np.pi * 5.5 * t)), 3200)


def pop_burst():
    n = int(0.28 * SR)
    out = 0.7 * lp(rng.standard_normal(n), 2600) * env_exp(n, 0.05, 0.0005)
    thump = boop(170, 0.16)
    out[: len(thump)] += 0.9 * thump
    return out


def sparkle(seed, count=7):
    r = random.Random(seed)
    n = int(0.55 * SR)
    out = np.zeros(n)
    for _ in range(count):
        f = r.uniform(2200, 6500)
        d = r.uniform(0.12, 0.4)
        s = sine(f, d) * env_exp(int(d * SR), d / 3.5, 0.001)
        i = int(r.uniform(0, 0.09) * SR)
        out[i:i + len(s)] += s[: n - i]
    return out


def crash(dur=1.6):
    n = int(dur * SR)
    return hp(rng.standard_normal(n), 3500) * env_exp(n, 0.45, 0.001)


def whoosh(dur, up=True):
    n = int(dur * SR)
    noise = rng.standard_normal(n)
    u = np.arange(n) / n
    fc = 300 + 3800 * (u if up else 1 - u)
    a = 1 - np.exp(-2 * np.pi * fc / SR)
    y = np.empty(n)
    acc = 0.0
    for i in range(n):
        acc += a[i] * (noise[i] - acc)
        y[i] = acc
    y = hp(y, 150)
    return y * np.sin(np.pi * u) ** 1.5 / max(np.abs(y).max(), 1e-9)


def build(tl, cfg, out_path):
    music = cfg.get("music", {})
    key = music.get("key", 0)
    melody = MELODIES[music.get("melody", 0) % len(MELODIES)]
    prog = PROGS[music.get("prog", 0) % len(PROGS)]
    bpm = music.get("bpm", 124.0)

    mix = Mix(tl.T_end)
    T_last_stage = tl.video_time(tl.breaks[-2][0])
    T_final = tl.video_time(tl.t_f)

    for k in range(3):
        b = sine(880, 0.16) + 0.3 * sine(1760, 0.16)
        mix.add(b * env_exp(len(b), 0.06), k * 0.45, 0.30)
    g = sine(1318.5, 0.4) + 0.5 * sine(1975.5, 0.4)
    mix.add(g * env_exp(len(g), 0.16), T_INTRO, 0.32)
    mix.add(whoosh(0.5), T_INTRO - 0.12, 0.10)

    beat = 60.0 / bpm
    T = T_INTRO
    k = 0
    while T < T_last_stage - 0.05:
        root, qual = prog[(k // 4) % 4]
        triad = [0, 4, 7] if qual == "maj" else [0, 3, 7]
        mix.add(kick(), T, 0.42)
        mix.add(hat(), T + beat / 2, 0.07, pan=0.3)
        if k % 2 == 1:
            mix.add(snare(), T, 0.14)
        mix.add(pluck_bass(midi_hz(36 + key + root)), T, 0.30)
        if k % 4 == 0:
            mix.add(pad([midi_hz(60 + key + root + iv) for iv in triad], beat * 4), T, 0.10)
        T += beat
        k += 1

    T = T_last_stage + 0.05
    gap = 0.62
    while T < T_final - 0.15:
        mix.add(kick(0.25), T, 0.55)
        mix.add(kick(0.22), T + 0.17, 0.35)
        T += gap
        gap = max(0.38, gap * 0.93)
    dur = max(0.2, T_final - T_last_stage)
    n = int(dur * SR)
    tt = np.arange(n) / SR
    f = 180 + 520 * (tt / dur) ** 1.5
    rise = np.sin(2 * np.pi * np.cumsum(f) / SR) * (0.2 + 0.8 * tt / dur)
    mix.add(lp(rise, 1500), T_last_stage, 0.08)
    roll_t = T_final - 1.4
    while roll_t < T_final - 0.02:
        u = 1 - (T_final - roll_t) / 1.4
        mix.add(snare(0.08), roll_t, 0.05 + 0.18 * u)
        roll_t += 0.055

    mel_i = 0
    last_mel = -1.0
    for (t, kind, b, s) in tl.hits:
        T = tl.video_time(t)
        if T >= tl.T_outro_end:
            continue
        strength = min(1.0, max(0.15, s / 1500.0))
        if kind == "wall":
            if T - last_mel >= 0.10:
                mix.add(kalimba(penta_hz(melody[mel_i % len(melody)], key)), T,
                        0.24 * (0.55 + 0.45 * strength), PAN[b])
                mel_i += 1
                last_mel = T
            else:
                mix.add(tick(), T, 0.05, PAN[b])
        elif kind == "bb":
            mix.add(boop(380 + 40 * b), T, 0.12 * strength, PAN[b])
        elif kind == "cap":
            mix.add(tink(), T, 0.08, PAN[b])

    for k, (t, ri, b) in enumerate(tl.breaks):
        T = tl.video_time(t)
        final = (k == len(tl.breaks) - 1)
        mix.add(pop_burst(), T, 0.42 if not final else 0.6, PAN[b] * 0.5)
        mix.add(sparkle(100 + k), T, 0.07)
        mix.add(bell(penta_hz(10 + min(ri, 10), key, base=60)), T + 0.01, 0.20, PAN[b] * 0.4)
        if final:
            mix.add(crash(), T, 0.22)
            mix.add(kick(0.6), T, 0.7)

    Tw = tl.T_win
    for j, iv in enumerate([0, 4, 7]):
        mix.add(brass(midi_hz(72 + key + iv), 0.16), Tw + j * 0.11, 0.16)
    for iv in [0, 4, 7, 12]:
        mix.add(brass(midi_hz(72 + key + iv), 1.25), Tw + 0.33, 0.09)
    mix.add(crash(1.2), Tw + 0.33, 0.12)
    for j in range(6):
        mix.add(sparkle(300 + j, 5), Tw + 0.2 + j * 0.35, 0.06)
    T = Tw + 0.33
    k = 0
    while T < tl.T_outro_end - 0.1:
        mix.add(kick(), T, 0.30)
        mix.add(hat(), T + beat / 2, 0.06, pan=0.3)
        if k % 2 == 1:
            mix.add(snare(), T, 0.12)
        T += beat
        k += 1

    Tr = tl.T_outro_end
    dur = tl.T_end - Tr
    mix.add(whoosh(dur, up=False), Tr, 0.16)
    tt = 0.0
    while tt < dur - 0.05:
        mix.add(tink(1800 - 1300 * math.sin(math.pi * tt / dur), 0.03), Tr + tt, 0.05)
        tt += 0.035

    L = np.tanh(1.1 * mix.L) / np.tanh(1.1)
    R = np.tanh(1.1 * mix.R) / np.tanh(1.1)
    peak = max(np.abs(L).max(), np.abs(R).max(), 1e-9)
    L, R = L / peak * 0.89, R / peak * 0.89
    data = np.empty(len(L) * 2, dtype=np.int16)
    data[0::2] = (L * 32767).astype(np.int16)
    data[1::2] = (R * 32767).astype(np.int16)
    with wave.open(out_path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
