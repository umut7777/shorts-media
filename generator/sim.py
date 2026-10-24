"""Physics simulation for the 'Which color wins?' ring-escape race.

Four balls start inside the innermost of N concentric rotating rings.
Every ring has a gap. When a ball's centre passes through the gap of the
innermost intact ring, that ring breaks and the ball scores a point.
All visuals are rendered later from the recorded states, so a run can be
searched for drama first and rendered afterwards (deterministic per seed).
"""
import math
import random

FPS = 60
SUB = 4
DT = 1.0 / (FPS * SUB)

W, H = 1080, 1920
CX, CY = 540.0, 1010.0

BALL_R = 27.0
N_RINGS = 14
R0 = 140.0
SPACING = 24.0
RING_HALF = 4.5
G = 1500.0
VMIN = 950.0
VMAX = 2300.0
T_AFTER = 2.5   # seconds simulated after the last ring breaks
T_LIMIT = 70.0  # hard stop

COLORS = ["RED", "BLUE", "GREEN", "YELLOW"]


def ring_radius(i):
    return R0 + i * SPACING


def wrap(a):
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def make_rings(rng, alpha_in=0.40, alpha_out=0.27, w_base=1.15):
    rings = []
    for i in range(N_RINGS):
        f = i / (N_RINGS - 1)
        alpha = alpha_in + (alpha_out - alpha_in) * f
        sign = 1.0 if i % 2 == 0 else -1.0
        omega = sign * (w_base * (1.0 - 0.25 * f) * rng.uniform(0.85, 1.15))
        theta0 = rng.uniform(-math.pi, math.pi)
        rings.append({"R": ring_radius(i), "alpha": alpha, "omega": omega, "theta0": theta0})
    return rings


def ring_angle(ring, t):
    return ring["theta0"] + ring["omega"] * t


def simulate(seed, alpha_in=0.40, alpha_out=0.27, w_base=1.15, record=True):
    rng = random.Random(seed)
    rings = make_rings(rng, alpha_in, alpha_out, w_base)

    # start positions: small square around the centre, random velocities
    px, py, vx, vy = [], [], [], []
    offsets = [(-38, -30), (38, -30), (-38, 34), (38, 34)]
    for k in range(4):
        ox, oy = offsets[k]
        px.append(CX + ox + rng.uniform(-6, 6))
        py.append(CY + oy + rng.uniform(-6, 6))
        ang = rng.uniform(0, 2 * math.pi)
        sp = rng.uniform(650, 900)
        vx.append(sp * math.cos(ang))
        vy.append(sp * math.sin(ang))

    cur = 0  # index of innermost intact ring
    scores = [0, 0, 0, 0]
    breaks = []      # (t, ring_index, ball)
    hits = []        # (t, kind, ball, strength)
    states = []      # per substep: (t, [x0,y0,x1,y1,...], cur)
    t = 0.0
    t_done = None
    step = 0
    last_hit_t = [-1.0] * 4
    if record:
        st0 = []
        for b in range(4):
            st0.append(px[b])
            st0.append(py[b])
        states.append((0.0, st0, 0))

    while True:
        if t_done is not None and t - t_done >= T_AFTER:
            break
        if t > T_LIMIT:
            break

        # integrate
        for b in range(4):
            vy[b] += G * DT
            px[b] += vx[b] * DT
            py[b] += vy[b] * DT

        # ball-ball collisions
        for i in range(4):
            for j in range(i + 1, 4):
                dx = px[j] - px[i]
                dy = py[j] - py[i]
                d2 = dx * dx + dy * dy
                lim = 2 * BALL_R
                if d2 < lim * lim and d2 > 1e-9:
                    d = math.sqrt(d2)
                    nx, ny = dx / d, dy / d
                    ov = lim - d
                    px[i] -= nx * ov * 0.5
                    py[i] -= ny * ov * 0.5
                    px[j] += nx * ov * 0.5
                    py[j] += ny * ov * 0.5
                    u = (vx[i] - vx[j]) * nx + (vy[i] - vy[j]) * ny
                    if u > 0:
                        vx[i] -= u * nx
                        vy[i] -= u * ny
                        vx[j] += u * nx
                        vy[j] += u * ny
                        if u > 150:
                            hits.append((t, "bb", i, u))

        # ring collisions (innermost intact ring only)
        if cur < N_RINGS:
            ring = rings[cur]
            R = ring["R"]
            alpha = ring["alpha"]
            om = ring["omega"]
            th = ring_angle(ring, t)
            for b in range(4):
                dx = px[b] - CX
                dy = py[b] - CY
                d = math.hypot(dx, dy)
                if d < 1e-6:
                    continue
                if d + BALL_R < R - RING_HALF:
                    continue  # not touching
                phi = math.atan2(dy, dx)
                delta = wrap(phi - th)
                nx, ny = dx / d, dy / d
                if abs(delta) >= alpha:
                    # wall region: push inward and reflect
                    pen = d + BALL_R - (R - RING_HALF)
                    if pen > 0:
                        px[b] -= nx * pen
                        py[b] -= ny * pen
                        vn = vx[b] * nx + vy[b] * ny
                        if vn > 0:
                            vx[b] -= 2 * vn * nx
                            vy[b] -= 2 * vn * ny
                            sp = math.hypot(vx[b], vy[b])
                            if sp < VMIN:
                                s = VMIN / max(sp, 1e-6)
                                vx[b] *= s
                                vy[b] *= s
                            elif sp > VMAX:
                                s = VMAX / sp
                                vx[b] *= s
                                vy[b] *= s
                            if t - last_hit_t[b] > 0.06:
                                hits.append((t, "wall", b, vn))
                                last_hit_t[b] = t
                else:
                    # gap region: collide with the nearest end cap
                    edge = th + (alpha if delta > 0 else -alpha)
                    ex = CX + R * math.cos(edge)
                    ey = CY + R * math.sin(edge)
                    cdx = px[b] - ex
                    cdy = py[b] - ey
                    cd = math.hypot(cdx, cdy)
                    lim = BALL_R + RING_HALF
                    if cd < lim and cd > 1e-6:
                        cnx, cny = cdx / cd, cdy / cd
                        px[b] = ex + cnx * lim
                        py[b] = ey + cny * lim
                        cvx = -om * (ey - CY)
                        cvy = om * (ex - CX)
                        rvx = vx[b] - cvx
                        rvy = vy[b] - cvy
                        vn = rvx * cnx + rvy * cny
                        if vn < 0:
                            vx[b] -= 2 * vn * cnx
                            vy[b] -= 2 * vn * cny
                            sp = math.hypot(vx[b], vy[b])
                            if sp > VMAX:
                                s = VMAX / sp
                                vx[b] *= s
                                vy[b] *= s
                            hits.append((t, "cap", b, -vn))
                    # escape check: centre beyond the ring line inside the gap
                    dx = px[b] - CX
                    dy = py[b] - CY
                    d = math.hypot(dx, dy)
                    if d > R:
                        delta2 = wrap(math.atan2(dy, dx) - th)
                        if abs(delta2) < alpha:
                            scores[b] += 1
                            breaks.append((t, cur, b))
                            cur += 1
                            if cur >= N_RINGS:
                                t_done = t
                            break  # ring gone; next ring checked next substep

        t += DT
        step += 1
        if record:
            st = []
            for b in range(4):
                st.append(px[b])
                st.append(py[b])
            states.append((t, st, cur))

    return {
        "seed": seed,
        "rings": rings,
        "breaks": breaks,
        "hits": hits,
        "states": states,
        "scores": scores,
        "t_done": t_done,
        "params": {"alpha_in": alpha_in, "alpha_out": alpha_out, "w_base": w_base},
    }


def drama(res):
    """Return (ok, score, info) describing how exciting a run is."""
    if res["t_done"] is None:
        return False, -1e9, {"reason": "unfinished"}
    br = res["breaks"]
    t_done = res["t_done"]
    scores = [0, 0, 0, 0]
    leader = None
    lead_changes = 0
    for (t, ri, b) in br[:-1]:
        scores[b] += 1
    before_last = list(scores)
    # recount for lead changes over the whole race
    scores = [0, 0, 0, 0]
    for (t, ri, b) in br:
        scores[b] += 1
        mx = max(scores)
        tops = [i for i in range(4) if scores[i] == mx]
        if len(tops) == 1:
            if leader is not None and tops[0] != leader:
                lead_changes += 1
            leader = tops[0]
    final = scores
    mx = max(final)
    winners = [i for i in range(4) if final[i] == mx]
    last_breaker = br[-1][2]
    srt = sorted(before_last, reverse=True)
    tie_before_last = srt[0] == srt[1]
    decided_by_last = (len(winners) == 1 and winners[0] == last_breaker and tie_before_last
                       and before_last[last_breaker] == srt[0])
    gaps = [br[0][0]] + [br[i][0] - br[i - 1][0] for i in range(1, len(br))]
    info = {
        "t_done": round(t_done, 2), "final": final, "before_last": before_last,
        "lead_changes": lead_changes, "decided_by_last": decided_by_last,
        "max_gap": round(max(gaps), 2), "first": round(br[0][0], 2),
        "winner": winners[0] if len(winners) == 1 else None,
    }
    ok = (len(winners) == 1 and min(final) >= 1 and 24.0 <= t_done <= 34.0
          and max(gaps) <= 5.0 and br[0][0] <= 2.5)
    score = 0.0
    score += 6.0 if decided_by_last else 0.0
    score += 1.5 * min(lead_changes, 4)
    score -= 0.6 * max(0.0, max(gaps) - 3.5)
    score -= 0.15 * abs(t_done - 29.0)
    score += 0.5 * (4 - (final[winners[0]] - sorted(final)[-2] if len(winners) == 1 else 4))
    return ok, score, info


if __name__ == "__main__":
    import sys
    import statistics
    a_in = float(sys.argv[1]) if len(sys.argv) > 1 else 0.40
    a_out = float(sys.argv[2]) if len(sys.argv) > 2 else 0.27
    wb = float(sys.argv[3]) if len(sys.argv) > 3 else 1.15
    n = int(sys.argv[4]) if len(sys.argv) > 4 else 40
    durs = []
    for s in range(n):
        r = simulate(s, a_in, a_out, wb, record=False)
        if r["t_done"] is not None:
            durs.append(r["t_done"])
    print(f"alpha_in={a_in} alpha_out={a_out} w={wb}: finished {len(durs)}/{n}",
          "median", round(statistics.median(durs), 1) if durs else None,
          "min", round(min(durs), 1) if durs else None, "max", round(max(durs), 1) if durs else None)
