#!/usr/bin/env python3
"""Make ring-escape race Shorts ("Which color wins?").

Usage:
  python3 generator/make_short.py --date 2026-10-25 --count 2 --out videos --check-dir /tmp/checks

For every slot it picks colours, theme, title and music from the date, searches
thousands of simulated races for the most exciting one (tie before the last ring,
lead changes, fast start), renders the video, synthesises the soundtrack and writes
  <out>/<date>_<slot>.mp4   the finished Short (1080x1920, 60 fps, -14 LUFS)
  <out>/<date>_<slot>.json  YouTube title, description, tags and race facts
plus a contact sheet <check-dir>/<date>_<slot>_check.png for a visual check.
"""
import argparse
import datetime
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from sim import simulate, N_RINGS  # noqa: E402
from timeline import Timeline, DEFAULT_PARAMS  # noqa: E402

TITLES = ["WHICH  COLOR  WINS?", "WHO  WILL  WIN?", "WHICH  BALL  WINS?", "WHO  ESCAPES?"]
THEMES = ["night", "space", "ocean", "candy", "sunset"]


def ensure_font():
    dst = os.path.expanduser("~/.local/share/fonts/LilitaOne-Regular.ttf")
    if not os.path.exists(dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy(os.path.join(HERE, "fonts", "LilitaOne-Regular.ttf"), dst)
        subprocess.run(["fc-cache", "-f"], check=False, capture_output=True)


def evaluate(seed):
    r = simulate(seed, *DEFAULT_PARAMS, record=False)
    td, br = r["t_done"], r["breaks"]
    if td is None or len(br) < N_RINGS:
        return None
    sc = [0] * 4
    leader, lc, hist = None, 0, []
    for (t, ri, b) in br:
        sc[b] += 1
        mx = max(sc)
        tops = [i for i in range(4) if sc[i] == mx]
        if len(tops) == 1:
            if leader is not None and tops[0] != leader:
                lc += 1
            leader = tops[0]
        hist.append(tuple(sc))
    final = sc
    mx = max(final)
    win = [i for i in range(4) if final[i] == mx]
    if len(win) != 1:
        return None
    w = win[0]
    before = hist[-2]
    srt = sorted(before, reverse=True)
    decided = srt[0] == srt[1] and before[w] == srt[0] and br[-1][2] == w
    ties = srt.count(srt[0]) if decided else 1
    gaps = [br[0][0]] + [br[i][0] - br[i - 1][0] for i in range(1, len(br))]
    early = sum(1 for (t, _, _) in br if t <= 3.5)
    if decided and lc >= 2 and early >= 3 and max(gaps) <= 3.6 and 19 <= td <= 26 and min(final) >= 1:
        tier = 3
    elif decided and lc >= 1 and max(gaps) <= 4.0 and 17 <= td <= 28 and min(final) >= 1:
        tier = 2
    elif 16 <= td <= 30 and max(gaps) <= 4.5:
        tier = 1
    else:
        return None
    score = 2 * min(lc, 4) + 1.5 * (ties - 1) + 0.5 * early - 0.3 * abs(td - 22) - 0.5 * max(gaps)
    return dict(seed=seed, tier=tier, score=round(score, 2), t=round(td, 2), final=final,
                before=list(before), lead_changes=lc, decided=decided, ties=ties, winner=w)


def search(start, n=3000):
    seeds = range(start, start + n)
    with Pool(max(1, os.cpu_count() or 1)) as pool:
        res = [r for r in pool.map(evaluate, seeds, chunksize=50) if r]
    if not res:
        raise RuntimeError("no usable race found")
    res.sort(key=lambda r: (-r["tier"], -r["score"]))
    return res[0]


def make_config(date, slot):
    rnd = random.Random(f"{date}-{slot}")
    d = datetime.date.fromisoformat(date)
    halloween = (d.month == 10 and d.day >= 24)
    cfg = {
        "balls": rnd.sample(range(8), 4),
        "theme": "halloween" if halloween else rnd.choice(THEMES),
        "title": "HALLOWEEN  RACE!" if halloween else rnd.choice(TITLES),
        "music": {"key": rnd.choice([0, 2, 5, 7]), "melody": rnd.randrange(4),
                  "prog": rnd.randrange(3), "bpm": round(rnd.uniform(118, 130), 1)},
        "search_start": rnd.randrange(10_000_000),
        "halloween": halloween,
    }
    return cfg, rnd


def metadata(cfg, race, rnd):
    from render import EMOJI, NAMES
    emojis = "".join(EMOJI[i] for i in cfg["balls"])
    if cfg["halloween"]:
        title = f"Halloween Ball Race 🎃 Which Color Wins? {emojis} #shorts"
    elif race["decided"] and race["ties"] >= 3:
        title = f"{race['ties']}-Way Tie Before the LAST Ring! 😱 {emojis} #shorts"
    elif race["decided"]:
        title = f"It All Came Down to the LAST Ring! 😱 {emojis} #shorts"
    else:
        title = rnd.choice([f"Which Color Wins? {emojis} #shorts",
                            f"Who Escapes First? {emojis} Ball Race #shorts",
                            f"Pick Your Color! {emojis} Ring Escape Race #shorts"])
    desc = (f"4 balls. {N_RINGS} spinning rings. Every broken ring = 1 point! "
            f"Which color did you pick? {emojis}\n\n#shorts #satisfying #colorrace #ballrace")
    if cfg["halloween"]:
        desc += " #halloween"
    names = [NAMES[i] for i in cfg["balls"]]
    tags = ["which color wins", "color race", "ball race", "satisfying", "ring escape", "kids"] + \
           [n.lower() for n in names]
    if cfg["halloween"]:
        tags.append("halloween")
    return dict(title=title[:100], description=desc, tags=tags, colors=names,
                winner=names[race["winner"]], final_scores=dict(zip(names, race["final"])),
                race=race, theme=cfg["theme"], made_for_kids=True)


def make_one(date, slot, out_dir, check_dir):
    import render
    import audio
    from PIL import Image

    cfg, rnd = make_config(date, slot)
    race = search(cfg["search_start"])
    tl = Timeline(race["seed"])
    base = os.path.join(out_dir, f"{date}_{slot}")
    with tempfile.TemporaryDirectory() as tmp:
        silent = os.path.join(tmp, "v.mp4")
        wav = os.path.join(tmp, "a.wav")
        render.render_video(tl, cfg, silent)
        audio.build(tl, cfg, wav)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", wav, "-map", "0:v",
                        "-map", "1:a", "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                        "-ar", "48000", "-c:a", "aac", "-b:a", "192k", "-shortest",
                        "-movflags", "+faststart", base + ".mp4"], check=True)
        times = [0.2, 3.0, tl.T_s1 - 1.0, tl.video_time(tl.t_f) + 0.1, tl.T_win + 1.2, tl.T_end - 0.02]
        pngs = render.preview(tl, cfg, times, tmp)
        ims = [Image.open(p).convert("RGB").resize((360, 640)) for p in pngs]
        sheet = Image.new("RGB", (360 * len(ims), 640))
        for i, im in enumerate(ims):
            sheet.paste(im, (360 * i, 0))
        os.makedirs(check_dir, exist_ok=True)
        check = os.path.join(check_dir, f"{date}_{slot}_check.png")
        sheet.save(check)
    meta = metadata(cfg, race, rnd)
    meta["duration_s"] = round(tl.T_end, 2)
    meta["file"] = os.path.basename(base + ".mp4")
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return base + ".mp4", check, meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--count", type=int, default=2)
    ap.add_argument("--first-slot", type=int, default=1)
    ap.add_argument("--out", default="videos")
    ap.add_argument("--check-dir", default=tempfile.gettempdir())
    a = ap.parse_args()
    ensure_font()
    os.makedirs(a.out, exist_ok=True)
    for slot in range(a.first_slot, a.first_slot + a.count):
        mp4, check, meta = make_one(a.date, slot, a.out, a.check_dir)
        print(json.dumps({"video": mp4, "check": check, "title": meta["title"],
                          "winner": meta["winner"], "duration_s": meta["duration_s"]}, ensure_ascii=False),
              flush=True)


if __name__ == "__main__":
    main()
