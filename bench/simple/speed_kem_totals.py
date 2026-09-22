#!/usr/bin/env python3
"""Total time per cryptographic operation, by parsing liboqs' own speed_kem.

The minimal approach: no custom harness, no cycle counter, no variance
analysis. This is what the job looks like when "total time per op" is the
whole requirement.

The cycle columns liboqs prints are recorded as `tsc_ticks_*`, not
"cycles", because on x86_64 that is what they are -- and they are
truncated to 32 bits. See ../full/README.md for why that matters and what
measuring it properly costs.

Usage:  python3 bench/simple/speed_kem_totals.py [seconds_per_op]
"""

import csv
import re
import subprocess
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent
SPEED_KEM = BENCH / "build" / "liboqs" / "tests" / "speed_kem"
OUT = BENCH / "results" / "simple-speed_kem.csv"
DURATION = sys.argv[1] if len(sys.argv) > 1 else "3"

ALGS = [
    "ML-KEM-512", "ML-KEM-768", "ML-KEM-1024",
    "Classic-McEliece-348864", "Classic-McEliece-6688128",
    "NTRU-HPS-2048-509", "NTRU-HRSS-701",
]

# op | iterations | total time (s) | mean us | pop stdev | cycles | pop stdev
ROW = re.compile(
    r"^(keygen|encaps|decaps)\s*\|\s*(\d+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)"
    r"\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*$"
)

if not SPEED_KEM.exists():
    sys.exit(f"ERROR: {SPEED_KEM} not found -- see bench/simple/README.md")

rows = []
for alg in ALGS:
    print(f"[simple] {alg} ({DURATION}s/op)", file=sys.stderr)
    proc = subprocess.run([str(SPEED_KEM), "-d", DURATION, alg],
                          capture_output=True, text=True, check=True)
    for line in proc.stdout.splitlines():
        m = ROW.match(line.strip())
        if m:
            op, iters, total_s, mean_us, sd_us, ticks, sd_ticks = m.groups()
            rows.append([alg, op, int(iters), float(total_s), float(mean_us),
                         float(sd_us), float(ticks), float(sd_ticks)])

if not rows:
    sys.exit("ERROR: parsed no rows -- speed_kem output format may have changed")

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["alg", "op", "iterations", "total_time_s", "time_us_mean",
                "time_us_popstdev", "tsc_ticks_mean", "tsc_ticks_popstdev"])
    w.writerows(rows)

print(f"\n{'Algorithm':<26} {'Op':<7} {'iters':>9} {'total s':>9} {'us/op':>11}")
print("-" * 65)
for alg, op, iters, total_s, mean_us, _, _, _ in rows:
    print(f"{alg:<26} {op:<7} {iters:>9,} {total_s:>9.3f} {mean_us:>11.3f}")
print(f"\n-> {OUT}", file=sys.stderr)
