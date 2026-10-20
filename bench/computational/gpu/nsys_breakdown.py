#!/usr/bin/env python3
"""Splits single GPU ML-KEM calls into their parts, from an Nsight Systems
profile of kem_bench-icicle exported to SQLite.

    nsys profile -t cuda -o keygen bench/driver/build/kem_bench-icicle \\
        time liboqs ML-KEM-768 keygen 200 5 0.1
    nsys export --type sqlite -o keygen.sqlite keygen.nsys-rep
    python3 bench/computational/gpu/nsys_breakdown.py keygen.sqlite

One sample per call of the most frequent kernel, skipping the first 20
and last 5. "Kernel on GPU" and "copy on GPU" use the GPU clock; the API
durations use the CPU clock. "launch start -> kernel start" spans both
clocks, and under WSL2 we saw them disagree by several µs, so read it
as ±10 µs.
"""

from __future__ import annotations

import sqlite3
import statistics
import sys
from collections import defaultdict

MEMCPY_H2D, MEMCPY_D2H = 1, 2


def main() -> None:
    db = sqlite3.connect(sys.argv[1])
    names = dict(db.execute("select id, value from StringIds"))
    api = [(s, e, names[n].split("_v")[0], cid) for s, e, n, cid in db.execute(
        "select start, end, nameId, correlationId from CUPTI_ACTIVITY_KIND_RUNTIME order by start")]
    kernels = {cid: (s, e, names[n]) for s, e, cid, n in db.execute(
        "select start, end, correlationId, shortName from CUPTI_ACTIVITY_KIND_KERNEL")}
    copies = {cid: (s, e, kind) for s, e, cid, kind in db.execute(
        "select start, end, correlationId, copyKind from CUPTI_ACTIVITY_KIND_MEMCPY")}

    launches = [i for i, a in enumerate(api) if a[2] == "cudaLaunchKernel"]
    kernel = statistics.mode(kernels[api[i][3]][2] for i in launches)
    launches = [i for i in launches if kernels[api[i][3]][2] == kernel][20:-5]

    # A call's CUDA work: the allocations and copies just before its launch,
    # through to the ones just before the next launch's.
    def first_of_call(i: int) -> int:
        while i > 0 and api[i - 1][2] in ("cudaMallocAsync", "cudaMemcpyAsync"):
            i -= 1
        return i

    parts = defaultdict(list)
    for here, nxt in zip(launches, launches[1:]):
        calls = api[first_of_call(here):first_of_call(nxt)]
        span = calls[-1][1] - calls[0][0]
        k_start, k_end, _ = kernels[api[here][3]]
        d2h = [c for c in calls if c[2] == "cudaMemcpyAsync" and copies[c[3]][2] == MEMCPY_D2H]
        h2d = [c for c in calls if c[2] == "cudaMemcpyAsync" and copies[c[3]][2] == MEMCPY_H2D]
        parts["CUDA part of the call"].append(span)
        parts["host time between CUDA calls"].append(span - sum(e - s for s, e, _, _ in calls))
        parts["cudaMallocAsync + cudaFreeAsync"].append(
            sum(e - s for s, e, n, _ in calls if n in ("cudaMallocAsync", "cudaFreeAsync")))
        parts["host-to-device cudaMemcpyAsync"].append(sum(e - s for s, e, _, _ in h2d))
        parts["cudaLaunchKernel"].append(api[here][1] - api[here][0])
        parts["launch start -> kernel start (±10)"].append(k_start - api[here][0])
        parts["kernel on GPU"].append(k_end - k_start)
        parts["first device-to-host copy on GPU"].append(copies[d2h[0][3]][1] - copies[d2h[0][3]][0])
        for n, c in enumerate(d2h[1:], 2):
            parts[f"device-to-host cudaMemcpyAsync #{n} (GPU idle)"].append(c[1] - c[0])

    print(f"{kernel}: {len(launches) - 1} calls; medians in µs")
    for name, values in parts.items():
        print(f"  {name:48} {statistics.median(values) / 1e3:7.1f}")


if __name__ == "__main__":
    main()
