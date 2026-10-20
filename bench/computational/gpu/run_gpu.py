#!/usr/bin/env python3
"""Batched ML-KEM on the GPU (ICICLE's own API) against single-thread CPU
ML-KEM (liboqs' native build), plus the fixed costs of any GPU call.

Builds ICICLE and liboqs (see bench/driver/kem_build.py) and
icicle_batch.cu, then for each ML-KEM set:

1. checks a batch of 256 GPU results against liboqs on the CPU, byte for
   byte (the run stops if any check fails);
2. times single CPU operations;
3. times GPU calls at batch sizes 1, 2, 4 ... --max-batch, with data in
   host memory (copies included) and already on the GPU.

    python3 bench/computational/gpu/run_gpu.py
    python3 bench/computational/gpu/run_gpu.py --sets ML-KEM-768 --max-batch 4096

Results go to bench/computational/gpu/results/<UTC stamp>-<host>-batch/.
"""

from __future__ import annotations

import argparse
import csv
import json
import socket
import statistics
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent            # bench/computational/gpu
RESULTS = HERE / "results"
sys.path.insert(0, str(HERE.parent.parent / "driver"))
import kem_build as build  # noqa: E402  (bench/driver/kem_build.py)
from kem_build import OPS, log, output_of  # noqa: E402

SETS = ("ML-KEM-512", "ML-KEM-768", "ML-KEM-1024")
SRC = HERE / "icicle_batch.cu"
EXE = build.BUILD / "icicle_batch"
CPU_VARIANT = "native"
NVCC_FLAGS = ["-O2", "-std=c++17", "-arch=native"]


# ---------- building ----------

def build_exe() -> Path:
    build.build_icicle()
    build.build_liboqs(CPU_VARIANT)
    liboqs = build.liboqs_dir(CPU_VARIANT)
    inputs = [SRC, liboqs / "lib" / "liboqs.a", *build.ICICLE_LIBS]
    if EXE.exists() and EXE.stat().st_mtime >= max(p.stat().st_mtime for p in inputs):
        return EXE
    log(f"[build] {EXE.name}")
    # nvcc's warnings come from ICICLE's headers; show them only on failure.
    proc = subprocess.run([str(build.NVCC), *NVCC_FLAGS, "-o", str(EXE), str(SRC),
         f"-I{build.ICICLE_PREFIX / 'include'}", f"-I{liboqs / 'include'}",
         "-Xlinker", "--whole-archive", *map(str, build.ICICLE_LIBS), "-Xlinker", "--no-whole-archive",
         str(liboqs / "lib" / "liboqs.a")],
        capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"ERROR: building {EXE.name} failed\n{proc.stderr}")
    return EXE


# ---------- running ----------

def run_exe(target: str, args: argparse.Namespace) -> list[list[str]]:
    """Run icicle_batch and return its CSV lines, split."""
    proc = subprocess.run([str(EXE), target, str(args.max_batch), str(args.reps), str(args.max_seconds)],
                          capture_output=True, text=True)
    lines = [line.split(",") for line in proc.stdout.splitlines()]
    for _, set_, check, verdict, detail in (l for l in lines if l[0] == "C"):
        log(f"[check] {set_} {check}: {verdict} ({detail})")
    if proc.returncode != 0:
        sys.exit(f"ERROR: icicle_batch {target} exited {proc.returncode}\n{proc.stderr}")
    return lines


# ---------- summarising ----------

def summarise(lines: list[list[str]]) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    checks, probes, cpu, gpu = [], defaultdict(list), defaultdict(list), defaultdict(list)
    for line in lines:
        kind = line[0]
        if kind == "C":
            checks.append(dict(zip(("set", "check", "verdict", "detail"), line[1:])))
        elif kind == "P":
            probes[line[1]].append(int(line[3]))
        elif kind == "U":
            cpu[(line[1], line[2])].append(int(line[4]))
        elif kind == "G":
            gpu[(line[1], line[2], line[3], int(line[4]))].append(int(line[6]))

    probe_rows = [{"probe": k, "samples": len(v), "median_us": statistics.median(v) / 1e3}
                  for k, v in probes.items()]
    cpu_rows = []
    for (set_, op), v in cpu.items():
        us = statistics.median(v) / 1e3
        cpu_rows.append({"set": set_, "op": op, "samples": len(v), "median_us": us, "ops_per_s": 1e6 / us})
    cpu_rate = {(r["set"], r["op"]): r["ops_per_s"] for r in cpu_rows}
    gpu_rows = []
    for (set_, op, mode, n), v in sorted(gpu.items(), key=lambda kv: (SETS.index(kv[0][0]), OPS.index(kv[0][1]),
                                                                       kv[0][2], kv[0][3])):
        call_us = statistics.median(v) / 1e3
        rate = n * 1e6 / call_us
        gpu_rows.append({"set": set_, "op": op, "mode": mode, "batch": n, "samples": len(v),
                         "median_call_us": call_us, "us_per_op": call_us / n, "ops_per_s": rate,
                         "vs_one_cpu_thread": rate / cpu_rate[(set_, op)]})
    return checks, probe_rows, cpu_rows, gpu_rows


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, env: dict, checks, probe_rows, cpu_rows, gpu_rows) -> None:
    lines = [
        f"# GPU batch results: {env['host']}",
        "",
        f"GPU: {env['gpu']}. {env['nvcc']}. CPU: {env['cpu']}.",
        f"ICICLE `{env['icicle_revision'][:12]}`; liboqs `{env['liboqs_revision']}` ({CPU_VARIANT} build) "
        "for the CPU reference and the checks.",
        f"Kernel: {env['kernel']}. Load average at start / end: `{env['loadavg_start']}` / `{env['loadavg_end']}`.",
        "",
        "## Checks",
        "",
        "A batch of 256 GPU results per set, compared with liboqs on the CPU from the same seeds.",
        "",
        "| set | check | result |",
        "| --- | --- | --- |",
        *(f"| {c['set']} | {c['check']} | {c['verdict']} ({c['detail']}) |" for c in checks),
        "",
        "## Fixed cost of a GPU call",
        "",
        "| probe | samples | median µs |",
        "| --- | ---: | ---: |",
        *(f"| {p['probe']} | {p['samples']} | {p['median_us']:.1f} |" for p in probe_rows),
        "",
        "## CPU reference: one thread, one operation per call",
        "",
        "| set | op | samples | median µs | ops/s |",
        "| --- | --- | ---: | ---: | ---: |",
        *(f"| {r['set']} | {r['op']} | {r['samples']} | {r['median_us']:.2f} | {r['ops_per_s']:,.0f} |"
          for r in cpu_rows),
        "",
        "## GPU: one batched call",
        "",
        "`host`: inputs and outputs in host memory, so the call includes ICICLE's device allocations "
        "and both copies. `device`: everything already on the GPU. µs/op is the call time divided "
        "by the batch size. The last column is GPU throughput over one CPU thread's.",
        "",
        "| set | op | mode | batch | samples | median call µs | µs/op | ops/s | × one CPU thread |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        *(f"| {r['set']} | {r['op']} | {r['mode']} | {r['batch']} | {r['samples']} | {r['median_call_us']:,.1f} "
          f"| {r['us_per_op']:.3f} | {r['ops_per_s']:,.0f} | {r['vs_one_cpu_thread']:.2f} |" for r in gpu_rows),
    ]
    path.write_text("\n".join(lines) + "\n")


def read_text(path: str) -> str | None:
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def environment(args: argparse.Namespace) -> dict:
    cpu = next((l.split(":", 1)[1].strip() for l in (read_text("/proc/cpuinfo") or "").splitlines()
                if l.startswith("model name")), None)
    return {
        "host": socket.gethostname(),
        "cpu": cpu,
        "kernel": output_of(["uname", "-r"]),
        "nvcc_flags": NVCC_FLAGS,
        **build.build_description([CPU_VARIANT, "icicle"]),
        "loadavg_start": read_text("/proc/loadavg"),
        "args": vars(args),
    }


# ---------- main ----------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sets", nargs="+", choices=SETS, default=list(SETS))
    ap.add_argument("--max-batch", type=int, default=65536, help="largest batch (powers of two up to it)")
    ap.add_argument("--reps", type=int, default=30, help="timed GPU calls per (set, op, mode, batch)")
    ap.add_argument("--max-seconds", type=float, default=2.0,
                    help="time cap per (set, op, mode, batch) (at least 3 calls)")
    ap.add_argument("--build-only", action="store_true")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    build_exe()
    if args.build_only:
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = RESULTS / f"{stamp}-{socket.gethostname()}-batch"
    out.mkdir(parents=True)
    env = environment(args)

    lines = run_exe("probes", argparse.Namespace(**{**vars(args), "reps": 300}))
    for set_ in args.sets:
        log(f"[run] {set_}")
        lines += run_exe(set_, args)

    env["loadavg_end"] = read_text("/proc/loadavg")
    (out / "env.json").write_text(json.dumps(env, indent=2) + "\n")
    with (out / "raw.csv").open("w") as f:
        f.writelines(",".join(l) + "\n" for l in lines)
    checks, probe_rows, cpu_rows, gpu_rows = summarise(lines)
    write_csv(out / "summary.csv", gpu_rows)
    write_markdown(out / "summary.md", env, checks, probe_rows, cpu_rows, gpu_rows)
    log(f"\n-> {out}")


if __name__ == "__main__":
    main()
