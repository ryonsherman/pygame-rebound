"""Analyze obstacle jitter and wall-escape with the wall re-clamp fix."""
import sys, os, io, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from contextlib import redirect_stdout
from collections import Counter

from src import engine as eng_mod
eng_mod.DEBUG = True
from src.engine import GameEngine

def extract_ids(line):
    ids = []
    for m in re.finditer(r'ids?:\[?(\d+(?:,\s*\d+)*)\]?', line):
        for part in m.group(1).split(','):
            ids.append(int(part.strip()))
    return ids

output = GameEngine(difficulty="hard", human_players=[]).__init__
output = None
buf = io.StringIO()
with redirect_stdout(buf):
    eng = GameEngine(difficulty="hard", human_players=[])
    for _ in range(5000):
        eng.update()
output = buf.getvalue()

lines = output.splitlines()
obs_lines = [l for l in lines if "[OBS]" in l]
wall_lines = [l for l in lines if "[WALL]" in l]
death_lines = [l for l in lines if "[DEATH]" in l]

ax, ay, aw, ah = 60, 60, 904, 648
arena_bounds = (ax, ay, ax+aw, ay+ah)

outside = 0
total_edge = 0
for l in obs_lines:
    if "z:edge" not in l:
        continue
    total_edge += 1
    parts = l.split()
    # parse pos from "id:NN x.x,y.y"
    pos_str = parts[2]
    x, y = float(pos_str.split(",")[0]), float(pos_str.split(",")[1])
    radius = int(re.search(r'r:(\d+)', l).group(1))
    b = int(re.search(r'b:(\d+)', l).group(1))
    if x - radius < ax or x + radius > ax + aw or y - radius < ay or y + radius > ay + ah:
        outside += 1
        if outside <= 5:
            print(f"OUTSIDE: {l}")

print(f"\n=== SUMMARY ===")
print(f"Total edge hits: {total_edge}")
print(f"Edge hits where ball extends past arena wall: {outside}")

# Multi-hit bricks
multi_hits = Counter()
for l in obs_lines:
    m = re.search(r'hits:(\d+)', l)
    if m:
        n = int(m.group(1))
        if n >= 5:
            multi_hits[n] += 1
print(f"Edge hits with 5+ brick overlaps: {sum(multi_hits.values())}")
if multi_hits:
    print(f"  Distribution: {dict(sorted(multi_hits.items()))}")

# Jitter: edge hits that are followed by a wall bounce on the same ball
edge_ids = set()
edge_hit_counts = Counter()
for l in obs_lines:
    if "z:edge" in l:
        bids = extract_ids(l)
        for bid in bids:
            edge_ids.add(bid)
            edge_hit_counts[bid] += 1
jitter = {k:v for k,v in edge_hit_counts.items() if v >= 2}
print(f"Balls with 2+ edge hits (jitter): {len(jitter)} (max: {max(jitter.values()) if jitter else 0})")
