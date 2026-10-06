#!/usr/bin/env python3
"""Per-operation timing of every parameter set in bench/algorithms.md,
through the liboqs and OpenSSL APIs, with one driver (kem_bench.c).

Builds liboqs (the submodule), a pinned OpenSSL release and the driver,
then runs each (implementation, algorithm, operation) as --runs
independent processes. Runs are interleaved, so slow drift in machine
load spreads over all algorithms instead of landing on one.

    python3 bench/computational/api/run_bench.py                 # everything
    python3 bench/computational/api/run_bench.py --algs X25519 ML-KEM-512
    python3 bench/computational/api/run_bench.py --build-only

Results go to bench/computational/results/<UTC stamp>-<host>/.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import socket
import statistics
import subprocess
import sys
import tarfile
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple, Sequence

# ---------- paths and pinned versions ----------

HERE = Path(__file__).resolve().parent            # bench/computational/api
COMPUTATIONAL = HERE.parent
REPO = COMPUTATIONAL.parent.parent
BUILD = COMPUTATIONAL / "build"
RESULTS = COMPUTATIONAL / "results"
ALGORITHMS_MD = REPO / "bench" / "algorithms.md"

LIBOQS_SRC = REPO / "implementations" / "liboqs"
LIBOQS_BUILD = BUILD / "liboqs-lib"   # same options as ../simple/, library only
LIBOQS_OPTIONS = {
    "CMAKE_BUILD_TYPE": "Release",
    "OQS_USE_OPENSSL": "OFF",   # liboqs uses its own RNG and hashes
    "OQS_DIST_BUILD": "OFF",    # -march=native, no runtime dispatch
    "OQS_BUILD_ONLY_LIB": "ON",
}

OPENSSL_VERSION = "3.5.9"
OPENSSL_SHA256 = "603f5602e2eef00d77fbd429d34dcd5822bb301757a1bc9cdb24c670f1eb859a"
OPENSSL_URL = (f"https://github.com/openssl/openssl/releases/download/"
               f"openssl-{OPENSSL_VERSION}/openssl-{OPENSSL_VERSION}.tar.gz")
OPENSSL_DIR = BUILD / f"openssl-{OPENSSL_VERSION}"
OPENSSL_PREFIX = OPENSSL_DIR / "install"
OPENSSL_CONFIGURE = ["no-shared", "no-tests"]

DRIVER_SRC = HERE / "kem_bench.c"
DRIVER = BUILD / "kem_bench"
DRIVER_CFLAGS = ["-O2", "-march=native", "-Wall", "-Wextra"]

# ---------- what to measure ----------

# The sets in bench/algorithms.md. check_list() fails if they drift apart.
LIBOQS_ALGS = [
    "ML-KEM-512", "ML-KEM-768", "ML-KEM-1024",
    "Classic-McEliece-348864", "Classic-McEliece-348864f",
    "Classic-McEliece-460896", "Classic-McEliece-460896f",
    "Classic-McEliece-6688128", "Classic-McEliece-6688128f",
    "Classic-McEliece-6960119", "Classic-McEliece-6960119f",
    "Classic-McEliece-8192128", "Classic-McEliece-8192128f",
    "NTRU-HPS-2048-509", "NTRU-HPS-2048-677", "NTRU-HPS-4096-821",
    "NTRU-HPS-4096-1229", "NTRU-HRSS-701", "NTRU-HRSS-1373",
]
# The classical baselines, plus ML-KEM a second time as the same-library
# comparison.
OPENSSL_ALGS = [
    "X25519", "P-256", "RSA-2048", "RSA-3072", "ffdhe2048", "ffdhe3072",
    "ML-KEM-512", "ML-KEM-768", "ML-KEM-1024",
]
OPS = ("keygen", "encaps", "decaps")


class Sample(NamedTuple):
    """One timed iteration, as printed by kem_bench."""
    tsc_ticks: int
    ns: int
    perf_cycles: int | None   # None where the kernel refuses perf


class RunOutput(NamedTuple):
    """Everything one kem_bench process printed."""
    meta: dict[str, str]
    samples: list[Sample]


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, **kw)


def output_of(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


# ---------- the algorithm list ----------

def listed_sets() -> set[str]:
    """First cell of every row in a `| Set | ...` table of algorithms.md."""
    names, in_table = set(), False
    for line in ALGORITHMS_MD.read_text().splitlines():
        if line.startswith("| Set "):
            in_table = True
        elif in_table and line.startswith("|"):
            cell = line.split("|")[1].strip()
            if not cell.startswith("---"):
                names.add(cell)
        else:
            in_table = False
    return names


def check_list() -> None:
    listed, ours = listed_sets(), set(LIBOQS_ALGS) | set(OPENSSL_ALGS)
    if listed != ours:
        sys.exit("ERROR: run_bench.py and bench/algorithms.md disagree.\n"
                 f"  only in algorithms.md: {sorted(listed - ours)}\n"
                 f"  only in run_bench.py:  {sorted(ours - listed)}")


# ---------- building ----------

def build_liboqs() -> None:
    if not (LIBOQS_BUILD / "CMakeCache.txt").exists():
        log("[build] configuring liboqs")
        run(["cmake", "-S", str(LIBOQS_SRC), "-B", str(LIBOQS_BUILD), "-G", "Ninja",
             *(f"-D{k}={v}" for k, v in LIBOQS_OPTIONS.items())])
    log("[build] liboqs")
    run(["cmake", "--build", str(LIBOQS_BUILD), "--target", "oqs"])


def fetch_openssl_source() -> Path:
    """Download (once) and verify the pinned tarball; return the source dir."""
    OPENSSL_DIR.mkdir(parents=True, exist_ok=True)
    tarball = OPENSSL_DIR / f"openssl-{OPENSSL_VERSION}.tar.gz"
    if not tarball.exists():
        log(f"[build] downloading {OPENSSL_URL}")
        urllib.request.urlretrieve(OPENSSL_URL, tarball)

    digest = hashlib.sha256(tarball.read_bytes()).hexdigest()
    if digest != OPENSSL_SHA256:
        tarball.unlink()
        sys.exit(f"ERROR: OpenSSL tarball SHA-256 {digest} != pinned {OPENSSL_SHA256}")

    src = OPENSSL_DIR / f"openssl-{OPENSSL_VERSION}"
    if not src.exists():
        with tarfile.open(tarball) as t:
            t.extractall(OPENSSL_DIR, filter="data")
    return src


def build_openssl() -> None:
    if (OPENSSL_PREFIX / "lib" / "libcrypto.a").exists():
        return
    src = fetch_openssl_source()
    log(f"[build] OpenSSL {OPENSSL_VERSION} (several minutes)")
    run(["./Configure", f"--prefix={OPENSSL_PREFIX}", "--libdir=lib", *OPENSSL_CONFIGURE], cwd=src)
    run(["make", f"-j{os.cpu_count() or 4}"], cwd=src, stdout=subprocess.DEVNULL)
    run(["make", "install_sw"], cwd=src, stdout=subprocess.DEVNULL)


def build_driver() -> None:
    libs = [LIBOQS_BUILD / "lib" / "liboqs.a", OPENSSL_PREFIX / "lib" / "libcrypto.a"]
    newest_input = max(p.stat().st_mtime for p in [DRIVER_SRC, *libs])
    if DRIVER.exists() and DRIVER.stat().st_mtime >= newest_input:
        return
    log("[build] kem_bench")
    run(["cc", *DRIVER_CFLAGS, "-o", str(DRIVER), str(DRIVER_SRC),
         f"-I{LIBOQS_BUILD / 'include'}", f"-I{OPENSSL_PREFIX / 'include'}",
         *map(str, libs), "-ldl", "-pthread"])


# ---------- running ----------

def run_driver(impl: str, alg: str, op: str, args: argparse.Namespace) -> RunOutput:
    """Run one kem_bench process and parse what it prints."""
    cmd = [str(DRIVER), impl, alg, op,
           str(args.max_iters), str(args.max_seconds), str(args.warmup)]
    stdout = run(cmd, capture_output=True, text=True, timeout=1800).stdout

    meta, samples = {}, []
    for line in stdout.splitlines():
        kind, *fields = line.split(",")
        if kind == "M":
            key, value = fields
            meta[key] = value
        elif kind == "S":
            tsc_ticks, ns, cycles = map(int, fields)
            samples.append(Sample(tsc_ticks, ns, cycles if cycles >= 0 else None))
    if not samples:
        raise RuntimeError(f"no samples from {impl} {alg} {op}")
    return RunOutput(meta, samples)


def select_combos(args: argparse.Namespace) -> list[tuple[str, str]]:
    """(implementation, set) pairs to run, after --algs and --impl."""
    combos = [("liboqs", alg) for alg in LIBOQS_ALGS] + [("openssl", alg) for alg in OPENSSL_ALGS]
    if args.algs:
        unknown = set(args.algs) - {alg for _, alg in combos}
        if unknown:
            sys.exit(f"ERROR: unknown sets {sorted(unknown)}")
        combos = [(impl, alg) for impl, alg in combos if alg in args.algs]
    if args.impl:
        combos = [(impl, alg) for impl, alg in combos if impl == args.impl]
    return combos


def run_all(combos, args, raw_csv: Path):
    """Run everything, writing every sample to raw_csv as it arrives.

    Returns (samples, meta): samples[(impl, alg, op)] is a list with one
    list of Samples per run; meta[(impl, alg)] is the driver's metadata.
    """
    samples: dict[tuple[str, str, str], list[list[Sample]]] = defaultdict(list)
    meta: dict[tuple[str, str], dict[str, str]] = {}
    total = args.runs * len(combos) * len(OPS)
    done, started = 0, time.monotonic()

    with raw_csv.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["impl", "alg", "op", "run", "iter", "tsc_ticks", "ns", "perf_user_cycles"])

        # Run 1 of everything, then run 2 of everything, and so on.
        for run_index in range(args.runs):
            for impl, alg in combos:
                for op in OPS:
                    result = run_driver(impl, alg, op, args)
                    meta[(impl, alg)] = result.meta
                    samples[(impl, alg, op)].append(result.samples)

                    for i, s in enumerate(result.samples):
                        cycles = "" if s.perf_cycles is None else s.perf_cycles
                        writer.writerow([impl, alg, op, run_index, i, s.tsc_ticks, s.ns, cycles])

                    done += 1
                    minutes_left = (time.monotonic() - started) / done * (total - done) / 60
                    log(f"[run {run_index + 1}/{args.runs}] {impl:<7} {alg:<26} {op:<6} "
                        f"{len(result.samples):>5} iters  ({done}/{total}, ~{minutes_left:.0f} min left)")
    return samples, meta


# ---------- statistics ----------

def quantile(xs: Sequence[float], p: float) -> float:
    """Linear-interpolation quantile, 0 <= p <= 1."""
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def cv(xs: Sequence[float]) -> float | None:
    """Coefficient of variation (stdev / mean), or None if undefined."""
    if len(xs) < 2 or statistics.fmean(xs) == 0:
        return None
    return statistics.stdev(xs) / statistics.fmean(xs)


def summarise(runs: list[list[Sample]]) -> dict:
    """Statistics for one (impl, alg, op) over all of its runs."""
    all_samples = [s for run_samples in runs for s in run_samples]
    ns = [s.ns for s in all_samples]
    tsc = [s.tsc_ticks for s in all_samples]
    cycles = [s.perf_cycles for s in all_samples if s.perf_cycles is not None]

    run_medians = [statistics.median(s.ns for s in run_samples) for run_samples in runs]
    within_cvs = [c for run_samples in runs if (c := cv([s.ns for s in run_samples])) is not None]
    between_cv = cv(run_medians)

    return {
        "runs": len(runs),
        "samples": len(ns),
        "min_samples_per_run": min(len(run_samples) for run_samples in runs),
        "median_us": statistics.median(ns) / 1e3,
        "p10_us": quantile(ns, 0.10) / 1e3,
        "p90_us": quantile(ns, 0.90) / 1e3,
        "mean_us": statistics.fmean(ns) / 1e3,
        "median_tsc_ticks": statistics.median(tsc),
        "median_perf_user_cycles": statistics.median(cycles) if cycles else None,
        "within_run_cv": statistics.median(within_cvs) if within_cvs else None,
        "between_run_cv": between_cv,
        # independent runs needed for a 95% interval of +-1% on the median
        "runs_for_1pct": math.ceil((1.96 * between_cv / 0.01) ** 2) if between_cv is not None else None,
    }


# ---------- output ----------

def read_text(path: str) -> str | None:
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def cpu_model() -> str | None:
    for line in (read_text("/proc/cpuinfo") or "").splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return None


def environment(args: argparse.Namespace) -> dict:
    return {
        "host": socket.gethostname(),
        "cpu": cpu_model(),
        "kernel": platform.release(),
        "compiler": output_of(["cc", "--version"]).splitlines()[0],
        "driver_cflags": DRIVER_CFLAGS,
        "libraries": output_of([str(DRIVER), "version"]).splitlines(),
        "liboqs_revision": output_of(["git", "-C", str(LIBOQS_SRC), "describe", "--tags", "--always"]),
        "liboqs_build": {k: v for k, v in LIBOQS_OPTIONS.items() if k != "OQS_BUILD_ONLY_LIB"},
        "openssl_source": {"version": OPENSSL_VERSION, "sha256": OPENSSL_SHA256,
                           "configure": OPENSSL_CONFIGURE},
        "perf_event_paranoid": read_text("/proc/sys/kernel/perf_event_paranoid"),
        "scaling_governor": read_text("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"),
        "loadavg_start": read_text("/proc/loadavg"),
        "args": vars(args),
    }


def summary_rows(samples, meta) -> list[dict]:
    rows = []
    for (impl, alg, op), runs in samples.items():
        sizes = meta[(impl, alg)]
        rows.append({
            "impl": impl, "alg": alg, "op": op,
            "public_key_bytes": sizes.get("public_key_bytes"),
            "ciphertext_bytes": sizes.get("ciphertext_bytes"),
            "shared_secret_bytes": sizes.get("shared_secret_bytes"),
            **summarise(runs),
        })
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def dash_if_none(x, spec: str, suffix: str = "") -> str:
    return "—" if x is None else format(x, spec) + suffix


def write_markdown(path: Path, rows: list[dict], env: dict) -> None:
    perf = "yes (user-space only)" if env["perf_available"] else "no"
    lines = [
        f"# API harness results — {env['host']}",
        "",
        f"CPU: {env['cpu']}. Libraries: {'; '.join(env['libraries'])}. "
        f"liboqs revision `{env['liboqs_revision']}`.",
        f"Load average at start / end: `{env['loadavg_start']}` / `{env['loadavg_end']}`.",
        f"perf cycle counter available: {perf}.",
        "",
        "Times are medians over all samples from all runs; p10–p90 shows the spread. "
        "Between-run CV is the coefficient of variation of the per-run medians.",
        "",
        "| impl | set | op | samples | median µs | p10–p90 µs | median TSC ticks | median perf cycles | between-run CV |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in rows:
        between_pct = None if r["between_run_cv"] is None else 100 * r["between_run_cv"]
        lines.append(
            f"| {r['impl']} | {r['alg']} | {r['op']} | {r['samples']} "
            f"| {r['median_us']:.2f} | {r['p10_us']:.2f}–{r['p90_us']:.2f} "
            f"| {r['median_tsc_ticks']:.0f} | {dash_if_none(r['median_perf_user_cycles'], '.0f')} "
            f"| {dash_if_none(between_pct, '.1f', '%')} |")
    path.write_text("\n".join(lines) + "\n")


# ---------- main ----------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", type=int, default=10, help="independent processes per (impl, alg, op)")
    ap.add_argument("--max-iters", type=int, default=1000, help="iteration cap per process")
    ap.add_argument("--max-seconds", type=float, default=1.0,
                    help="time cap per process (at least 3 iterations run)")
    ap.add_argument("--warmup", type=float, default=0.1, help="warmup seconds per process")
    ap.add_argument("--algs", nargs="+", help="only these sets (default: all)")
    ap.add_argument("--impl", choices=["liboqs", "openssl"], help="only this implementation")
    ap.add_argument("--build-only", action="store_true")
    return ap.parse_args()


def main() -> None:
    args = parse_args()

    check_list()
    build_liboqs()
    build_openssl()
    build_driver()
    if args.build_only:
        return

    combos = select_combos(args)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = RESULTS / f"{stamp}-{socket.gethostname()}"
    out.mkdir(parents=True)
    env = environment(args)

    samples, meta = run_all(combos, args, out / "raw.csv")

    env["loadavg_end"] = read_text("/proc/loadavg")
    env["perf_available"] = any(m.get("perf") == "1" for m in meta.values())
    (out / "env.json").write_text(json.dumps(env, indent=2) + "\n")

    rows = summary_rows(samples, meta)
    write_csv(out / "summary.csv", rows)
    write_markdown(out / "summary.md", rows, env)
    log(f"\n-> {out}")


if __name__ == "__main__":
    main()
