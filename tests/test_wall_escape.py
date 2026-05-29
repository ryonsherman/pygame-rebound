import sys, os, io, re, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from contextlib import redirect_stdout
from collections import defaultdict, Counter

from src import engine as eng_mod
eng_mod.DEBUG = True
from src.engine import GameEngine

import config
ax, ay, aw, ah = config.ARENA_RECT

TRIALS = 10
FRAMES = 2000

def rect_contains_circle(rx, ry, rw, rh, cx, cy, cr):
    cx_clamped = max(rx, min(cx, rx + rw))
    cy_clamped = max(ry, min(cy, ry + rh))
    dx = cx - cx_clamped
    dy = cy - cy_clamped
    return dx * dx + dy * dy < cr * cr

def circle_crosses_rect(x0, y0, x1, y1, cr, rx, ry, rw, rh, steps=8):
    for i in range(1, steps):
        t = i / steps
        cx = x0 + (x1 - x0) * t
        cy = y0 + (y1 - y0) * t
        if rect_contains_circle(rx, ry, rw, rh, cx, cy, cr):
            return True
    return False

all_overlaps = []
all_tunnels = []

for trial in range(TRIALS):
    buf = io.StringIO()
    with redirect_stdout(buf):
        eng = GameEngine(difficulty="hard", human_players=[])
        prev_positions = {}
        for frame in range(FRAMES):
            for p in eng.projectiles:
                prev_positions[p["id"]] = (p["x"], p["y"])
            eng.update()
            obses = eng.obstacles
            for p in eng.projectiles:
                x, y, r = p["x"], p["y"], p["radius"]
                px, py = prev_positions.get(p["id"], (x, y))
                for obs in obses:
                    rx, ry, rw, rh = obs["rect"]
                    if rect_contains_circle(rx, ry, rw, rh, x, y, r):
                        all_overlaps.append((trial, frame, p["id"], x, y, r, rx, ry, rw, rh, obs["zone"]))
                    elif not rect_contains_circle(rx, ry, rw, rh, px, py, r):
                        if circle_crosses_rect(px, py, x, y, r, rx, ry, rw, rh):
                            dist = math.hypot(x - px, y - py)
                            all_tunnels.append((trial, frame, p["id"], px, py, x, y, r, dist, obs["zone"]))

print(f"=== Overlap / Tunnel Analysis ({TRIALS} trials, {FRAMES} frames each) ===")

print(f"\n--- Post-resolution overlaps (ball still inside obstacle) ---")
print(f"Total: {len(all_overlaps)}")
if all_overlaps:
    by_zone = Counter(o[10] for o in all_overlaps)
    print(f"By zone: {dict(by_zone)}")
    edge_overlaps = [o for o in all_overlaps if o[10] == "edge"]
    if edge_overlaps:
        print(f"\nEdge zone overlaps ({len(edge_overlaps)}):")
        for o in edge_overlaps[:15]:
            trial, frame, pid, x, y, r, rx, ry, rw, rh, zone = o
            print(f"  T{trial}F{frame} id:{pid} ball:({x:.1f},{y:.1f})r={r} "
                  f"obs:({rx},{ry},{rw},{rh})")
else:
    print("  (none)")

print(f"\n--- Tunnel events (ball crossed through obstacle between frames) ---")
print(f"Total: {len(all_tunnels)}")
if all_tunnels:
    by_zone = Counter(t[9] for t in all_tunnels)
    print(f"By zone: {dict(by_zone)}")
    by_frame = Counter(t[1] for t in all_tunnels)
    multi_tunnel_frames = {f: c for f, c in by_frame.items() if c >= 5}
    if multi_tunnel_frames:
        print(f"Frames with >=5 tunnels: {dict(sorted(multi_tunnel_frames.items()))}")
    edge_tunnels = [t for t in all_tunnels if t[9] == "edge"]
    if edge_tunnels:
        print(f"\nEdge tunnel speeds (n={len(edge_tunnels)}):")
        speeds = [t[8] for t in edge_tunnels]
        print(f"  min: {min(speeds):.1f}  max: {max(speeds):.1f}  avg: {sum(speeds)/len(speeds):.1f}")
        print(f"  First 15 edge tunnels:")
        for t in edge_tunnels[:15]:
            trial, frame, pid, px, py, x, y, r, dist, zone = t
            print(f"  T{trial}F{frame} id:{pid} {px:.1f},{py:.1f}->{x:.1f},{y:.1f} "
                  f"r={r} dist={dist:.1f}")
else:
    print("  (none)")

print(f"\n--- Summary ---")
edge_overlap_count = len([o for o in all_overlaps if o[10] == "edge"])
center_overlap_count = len([o for o in all_overlaps if o[10] == "center"])
edge_tunnel_count = len([t for t in all_tunnels if t[9] == "edge"])
center_tunnel_count = len([t for t in all_tunnels if t[9] == "center"])
print(f"Edge overlaps (ball stuck in barrier): {edge_overlap_count}")
print(f"Center overlaps (ball stuck in center block): {center_overlap_count}")
print(f"Edge tunnels (ball crossed through barrier): {edge_tunnel_count}")
print(f"Center tunnels (ball crossed through center block): {center_tunnel_count}")
print(f"\nTotal potential visual defects: {edge_overlap_count + edge_tunnel_count}")
