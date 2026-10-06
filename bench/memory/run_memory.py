#!/usr/bin/env python3
"""Memory footprint of every parameter set in bench/algorithms.md, through
the liboqs and OpenSSL APIs, measured in-process by kem_bench's memory
build (bench/driver/).

For every (implementation, set, operation) this records:

  * stack, heap   of single calls, measured inside the process: the first
                  call (including any one-time setup the library does on
                  first use) and the steady state (later calls)
  * object sizes  public key, ciphertext, shared secret, as the driver
                  reports them
  * code size     liboqs only: text / data / bss of the parameter set's
                  own object files. Not measured for OpenSSL, whose
                  algorithms are selected by name at run time, so no
                  per-algorithm code can be separated.

liboqs is measured in two builds, native (AVX2 here) and generic
(portable C); OpenSSL in its one default build.

    python3 bench/memory/run_memory.py                       # everything
    python3 bench/memory/run_memory.py --algs X25519 ML-KEM-768
    python3 bench/memory/run_memory.py --massif              # + cross-check

--massif also measures the liboqs native sets with valgrind massif
(whole-process, `once` minus `baseline`) and writes them next to the
in-process figures. Results go to bench/memory/results/<UTC stamp>-<host>/.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent          # bench/memory
RESULTS = HERE / "results"
sys.path.insert(0, str(HERE.parent / "driver"))
import kem_build as build  # noqa: E402  (bench/driver/kem_build.py)
from kem_build import OPS, log, output_of  # noqa: E402

OPENSSL_VARIANT = "default"   # label for OpenSSL rows; it has one build
MASSIF = ["valgrind", "--tool=massif", "--stacks=yes", "--peak-inaccuracy=0.0"]
# Stack comes from the plain build: the memory build's allocator wrappers
# would add their own frames. Heap comes from the memory build.
STACK_MEASURES = ("first_stack_bytes", "steady_stack_bytes", "stack_overhead_bytes")
HEAP_MEASURES = ("first_heap_bytes", "steady_heap_bytes")


def driver_output(cmd: list[str]) -> dict[str, str]:
    """Run the driver; return its M,<key>,<value> lines as a dict."""
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"ERROR: {' '.join(cmd[1:])} failed:\n{p.stderr}")
    meta = {}
    for line in p.stdout.splitlines():
        kind, *fields = line.split(",")
        if kind == "M":
            meta[fields[0]] = fields[1]
    return meta


# ---------- in-process measurement ----------

def measure(plain: Path, tracking: Path, impl: str, alg: str, workdir: Path, reps: int) -> tuple[dict, list[dict]]:
    """Prepare inputs once, then run `memory` reps times per operation in
    each build: stack from `plain`, heap from `tracking`.

    Returns (sizes, rows). Each row holds the maximum over reps of every
    measure, and the minimum in *_min columns."""
    sizes = driver_output([str(plain), "prepare", impl, alg, str(workdir)])
    rows = []
    for op in OPS:
        row = {"impl": impl, "alg": alg, "op": op}
        for driver, measures in ((plain, STACK_MEASURES), (tracking, HEAP_MEASURES)):
            runs = [driver_output([str(driver), "memory", impl, alg, op, str(workdir)]) for _ in range(reps)]
            for m in measures:
                values = [int(r[m]) for r in runs]
                row[m] = max(values)
                row[f"{m}_min"] = min(values)
        rows.append(row)
    return sizes, rows


# ---------- massif cross-check (liboqs) ----------

def massif_peak(path: Path) -> tuple[int, int]:
    """Largest mem_heap_B and mem_stacks_B over all snapshots."""
    heap = stack = 0
    for block in path.read_text().split("snapshot=")[1:]:
        fields = dict(re.findall(r"^(mem_\w+)=(\d+)", block, re.M))
        heap = max(heap, int(fields.get("mem_heap_B", 0)))
        stack = max(stack, int(fields.get("mem_stacks_B", 0)))
    return heap, stack


def massif_check(driver: Path, alg: str, workdir: Path) -> list[dict]:
    """Whole-process peaks of `once` and `baseline` for each operation."""
    rows = []
    for op in OPS:
        peaks = {}
        for mode in ("once", "baseline"):
            out = workdir / f"massif.{op}.{mode}"
            build.run([*MASSIF, f"--massif-out-file={out}", str(driver), mode, "liboqs", alg, op,
                       str(workdir)], capture_output=True)
            peaks[mode] = massif_peak(out)
        (heap_once, stack_once), (heap_base, _) = peaks["once"], peaks["baseline"]
        rows.append({"alg": alg, "op": op,
                     "massif_heap_delta_bytes": heap_once - heap_base,
                     "massif_stack_peak_bytes": stack_once})
    return rows


# ---------- code size (liboqs) ----------

def liboqs_ids() -> dict[str, str]:
    """"ML-KEM-512" -> "ml_kem_512", from `#define OQS_KEM_alg_<id> "<name>"`."""
    text = (build.LIBOQS_SRC / "src" / "kem" / "kem.h").read_text()
    return {name: ident for ident, name in re.findall(r'#define OQS_KEM_alg_(\w+)\s+"([^"]+)"', text)}


def code_size(variant: str, ident: str) -> dict[str, int]:
    """Sum `size` over the object files of this parameter set's
    implementation targets (CMakeFiles/<ident>_<impl>.dir/). Code shared
    between algorithms (SHA-3, RNG, common) is not included."""
    objs = [o for d in build.liboqs_dir(variant).glob(f"src/kem/*/CMakeFiles/{ident}_*.dir")
            for o in d.rglob("*.o")]
    if not objs:
        # A zero here would read as a measurement; the build layout changed.
        sys.exit(f"ERROR: no object files for {ident} in the {variant} build")
    totals = {"text_bytes": 0, "data_bytes": 0, "bss_bytes": 0}
    for line in output_of(["size", *map(str, objs)]).splitlines()[1:]:
        text, data, bss = map(int, line.split()[:3])
        totals["text_bytes"] += text
        totals["data_bytes"] += data
        totals["bss_bytes"] += bss
    return totals


# ---------- output ----------

def cpu_model() -> str | None:
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return None


def environment(args: argparse.Namespace, variants: list[str], driver: Path) -> dict:
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "host": socket.gethostname(),
        "cpu": cpu_model(),
        "kernel": platform.release(),
        "compiler": output_of(["cc", "--version"]).splitlines()[0],
        "libraries": output_of([str(driver), "version"]).splitlines(),
        **build.build_description(variants),
        "memory_wrap_flags": build.MEMORY_WRAP_FLAGS,
        "valgrind": output_of(["valgrind", "--version"]) if args.massif else None,
        "args": vars(args),
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summary_md(env: dict, sizes: list[dict], mem: list[dict], code: list[dict], massif: list[dict]) -> str:
    lines = [
        f"# Memory footprint (in-process) — {env['host']}", "",
        f"{env['timestamp_utc']} · {env['cpu']} · {env['compiler']} · "
        f"{'; '.join(env['libraries'])} · liboqs `{env['liboqs_revision']}`", "",
        "Stack and heap of **single calls**, measured inside the process (see",
        "`bench/memory/README.md`). *Steady* is a call after the first; *first*",
        "is the first call in a fresh process, including any one-time setup the",
        "library does on first use. Each figure is the maximum over repeated runs;",
        "`memory.csv` also has the minimum.", "",
        "## Object sizes (bytes)", "",
        "| impl | set | public key | ciphertext | shared secret |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for s in sizes:
        lines.append(f"| {s['impl']} | {s['alg']} | {s['public_key_bytes']} "
                     f"| {s['ciphertext_bytes']} | {s['shared_secret_bytes']} |")

    groups = dict.fromkeys((r["variant"], r["impl"]) for r in mem)
    for variant, impl in groups:
        rows = {(r["alg"], r["op"]): r for r in mem if (r["variant"], r["impl"]) == (variant, impl)}
        lines += ["", f"## {impl} ({variant}): stack and heap per call (bytes)", "",
                  "| set | keygen stack | encaps stack | decaps stack | keygen heap | encaps heap | decaps heap "
                  "| first-call heap (keygen / encaps / decaps) |",
                  "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for alg in dict.fromkeys(a for a, _ in rows):
            stack = [rows[(alg, op)]["steady_stack_bytes"] for op in OPS]
            heap = [rows[(alg, op)]["steady_heap_bytes"] for op in OPS]
            first = [rows[(alg, op)]["first_heap_bytes"] for op in OPS]
            lines.append(f"| {alg} | " + " | ".join(f"{x:,}" for x in stack + heap)
                         + " | " + " / ".join(f"{x:,}" for x in first) + " |")

    if code:
        variants = list(dict.fromkeys(c["variant"] for c in code))
        by = {(c["variant"], c["alg"]): c for c in code}
        lines += ["", "## liboqs code size of each set's own object files (bytes)", "",
                  "Excludes code shared between algorithms (SHA-3, RNG, common). Not measured",
                  "for OpenSSL.", "",
                  "| set | " + " | ".join(f"{v} text | {v} data+bss" for v in variants) + " |",
                  "| --- |" + " ---: | ---: |" * len(variants)]
        for alg in dict.fromkeys(c["alg"] for c in code):
            cells = []
            for v in variants:
                c = by.get((v, alg))
                cells += [f"{c['text_bytes']:,}", f"{c['data_bytes'] + c['bss_bytes']:,}"] if c else ["—", "—"]
            lines.append(f"| {alg} | " + " | ".join(cells) + " |")

    if massif:
        lines += ["", "## Cross-check: liboqs native, in-process vs valgrind massif (bytes)", "",
                  "massif heap is the whole-process peak of `once` minus that of `baseline`;",
                  "massif stack is the whole-process peak of `once`, so it includes `main()` and",
                  "setup frames.", "",
                  "| set | op | in-process heap | massif heap Δ | in-process stack | massif stack |",
                  "| --- | --- | ---: | ---: | ---: | ---: |"]
        inproc = {(r["alg"], r["op"]): r for r in mem if (r["variant"], r["impl"]) == ("native", "liboqs")}
        for m in massif:
            r = inproc[(m["alg"], m["op"])]
            lines.append(f"| {m['alg']} | {m['op']} | {r['steady_heap_bytes']:,} | {m['massif_heap_delta_bytes']:,} "
                         f"| {r['steady_stack_bytes']:,} | {m['massif_stack_peak_bytes']:,} |")
    return "\n".join(lines) + "\n"


# ---------- main ----------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variant", choices=[*build.VARIANTS, "both"], default="both",
                    help="liboqs build(s) to measure")
    ap.add_argument("--algs", nargs="+", help="only these sets (default: all)")
    ap.add_argument("--impl", choices=["liboqs", "openssl"], help="only this implementation")
    ap.add_argument("--reps", type=int, default=3, help="processes per (build, set, operation)")
    ap.add_argument("--massif", action="store_true", help="also cross-check liboqs native with massif")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    variants = list(build.VARIANTS) if args.variant == "both" else [args.variant]
    if args.massif and not shutil.which("valgrind"):
        sys.exit("ERROR: --massif needs valgrind")

    tracking = build.build_all(variants, memory=True)
    plain = build.build_all(variants)

    combos = build.all_combos()
    if args.algs:
        unknown = set(args.algs) - {alg for _, alg in combos}
        if unknown:
            sys.exit(f"ERROR: unknown sets {sorted(unknown)}")
        combos = [(impl, alg) for impl, alg in combos if alg in args.algs]
    if args.impl:
        combos = [(impl, alg) for impl, alg in combos if impl == args.impl]

    # (variant, impl, alg): every liboqs set in each build, OpenSSL once.
    jobs = [(v, impl, alg) for v in variants for impl, alg in combos if impl == "liboqs"]
    jobs += [(OPENSSL_VARIANT, impl, alg) for impl, alg in combos if impl == "openssl"]
    openssl_variant = "native" if "native" in variants else variants[0]

    env = environment(args, variants, plain[openssl_variant])
    ids = liboqs_ids()
    sizes, mem, code, massif = [], [], [], []
    seen_sizes = set()

    for variant, impl, alg in jobs:
        log(f"[{variant}] {impl} {alg}")
        build_variant = openssl_variant if impl == "openssl" else variant
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp) / "inputs"
            set_sizes, rows = measure(plain[build_variant], tracking[build_variant], impl, alg, workdir, args.reps)
            if (impl, alg) not in seen_sizes:
                seen_sizes.add((impl, alg))
                sizes.append({"impl": impl, "alg": alg, **set_sizes})
            mem += [{"variant": variant, **r} for r in rows]
            if impl == "liboqs":
                code.append({"variant": variant, "alg": alg, **code_size(variant, ids[alg])})
                if args.massif and variant == "native":
                    massif += massif_check(plain["native"], alg, workdir)

    # Created only now, so a failed build or run leaves no empty results dir.
    out = RESULTS / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{env['host']}"
    out.mkdir(parents=True)
    write_csv(out / "sizes.csv", sizes)
    write_csv(out / "memory.csv", mem)
    write_csv(out / "codesize.csv", code)
    write_csv(out / "massif.csv", massif)
    (out / "env.json").write_text(json.dumps(env, indent=2) + "\n")
    (out / "summary.md").write_text(summary_md(env, sizes, mem, code, massif))
    log(f"\n-> {out}")


if __name__ == "__main__":
    main()
