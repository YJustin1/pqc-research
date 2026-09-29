#!/usr/bin/env python3
"""Memory footprint of ML-KEM, Classic McEliece and NTRU in liboqs, using
valgrind massif on liboqs' own test_kem_mem program.

For every parameter set this records:

  * object sizes   public key, secret key, ciphertext, shared secret,
                   from liboqs' dump_alg_info
  * stack, heap    peak of each, per operation, from valgrind massif
                   (--stacks=yes) on test_kem_mem, whole process
  * code size      text / data / bss of the parameter set's own liboqs
                   object files (not including shared SHA-3 and RNG code)

each for two builds of liboqs:

  * native   OQS_OPT_TARGET=auto    (-march=native; AVX2 code on x86_64)
  * generic  OQS_OPT_TARGET=generic (-march=x86-64; portable C code)

test_kem_mem runs one operation per process: 0 = keygen, 1 = encaps,
2 = decaps. It passes keys and ciphertexts between steps through files in
./tmp, so each massif run contains exactly one operation.

    python3 bench/memory/run_massif.py                     # everything
    python3 bench/memory/run_massif.py --algs ML-KEM-512   # one set
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent          # bench/memory
REPO = HERE.parent.parent
LIBOQS_SRC = REPO / "implementations" / "liboqs"
BUILD = HERE / "build"
RESULTS = HERE / "results"

OPS = {0: "keygen", 1: "encaps", 2: "decaps"}
VARIANTS = {"native": "auto", "generic": "generic"}

ALGS = [
    "ML-KEM-512", "ML-KEM-768", "ML-KEM-1024",
    "Classic-McEliece-348864", "Classic-McEliece-348864f",
    "Classic-McEliece-460896", "Classic-McEliece-460896f",
    "Classic-McEliece-6688128", "Classic-McEliece-6688128f",
    "Classic-McEliece-6960119", "Classic-McEliece-6960119f",
    "Classic-McEliece-8192128", "Classic-McEliece-8192128f",
    "NTRU-HPS-2048-509", "NTRU-HPS-2048-677", "NTRU-HPS-4096-821",
    "NTRU-HPS-4096-1229", "NTRU-HRSS-701", "NTRU-HRSS-1373",
]

# --peak-inaccuracy=0 makes massif record the exact peak rather than one
# within 1% of it (the default).
MASSIF = ["valgrind", "--tool=massif", "--stacks=yes", "--peak-inaccuracy=0.0"]


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, **kw)


def alg_ids() -> dict[str, str]:
    """"ML-KEM-512" -> "ml_kem_512", from `#define OQS_KEM_alg_<id> "<name>"`."""
    text = (LIBOQS_SRC / "src" / "kem" / "kem.h").read_text()
    return {name: ident for ident, name in
            re.findall(r'#define OQS_KEM_alg_(\w+)\s+"([^"]+)"', text)}


def build(variant: str, algs: list[str], ids: dict[str, str],
          jobs: int, force: bool) -> Path:
    out = BUILD / f"liboqs-{variant}"
    minimal = ";".join(f"KEM_{ids[a]}" for a in sorted(algs))
    stamp = out / "minimal-build.txt"
    if ((out / "tests" / "test_kem_mem").exists() and not force
            and stamp.exists() and stamp.read_text() == minimal):
        log(f"[build] reusing {out}")
        return out
    cmake = shutil.which("cmake") or sys.exit("ERROR: cmake not found")
    args = [
        cmake, "-S", str(LIBOQS_SRC), "-B", str(out),
        "-DCMAKE_BUILD_TYPE=Release",
        "-DBUILD_SHARED_LIBS=OFF",
        "-DOQS_BUILD_ONLY_LIB=OFF",   # test_kem_mem and dump_alg_info are tests
        "-DOQS_USE_OPENSSL=OFF",
        "-DOQS_DIST_BUILD=OFF",
        f"-DOQS_OPT_TARGET={VARIANTS[variant]}",
        f"-DOQS_MINIMAL_BUILD={minimal}",
    ]
    if shutil.which("ninja"):
        args += ["-G", "Ninja"]
    log(f"[build] configuring liboqs ({variant}) ...")
    run(args, stdout=subprocess.DEVNULL)
    log(f"[build] compiling liboqs ({variant}, -j{jobs}) ...")
    run([cmake, "--build", str(out), "--parallel", str(jobs),
         "--target", "test_kem_mem", "dump_alg_info"], stdout=subprocess.DEVNULL)
    stamp.write_text(minimal)
    return out


def object_sizes(out: Path) -> dict[str, dict[str, int]]:
    """Parse dump_alg_info's YAML-like output into per-algorithm lengths."""
    text = run([str(out / "tests" / "dump_alg_info")], capture_output=True,
               text=True).stdout
    sizes: dict[str, dict[str, int]] = {}
    current = None
    for line in text.split("SIGs:")[0].splitlines():
        m = re.match(r"^  (\S.*):$", line)
        if m:
            current = m.group(1)
            continue
        m = re.match(r"^    length-([\w-]+): (\d+)$", line)
        if m and current:
            sizes.setdefault(current, {})[m.group(1)] = int(m.group(2))
    return sizes


def code_size(out: Path, ident: str) -> dict[str, int]:
    """Sum `size` over the object files of this parameter set's
    implementation targets (CMakeFiles/<ident>_<impl>.dir/)."""
    objs = [o for d in out.glob(f"src/kem/*/CMakeFiles/{ident}_*.dir")
            for o in d.rglob("*.o")]
    totals = {"text": 0, "data": 0, "bss": 0}
    if not objs:
        return totals
    lines = run(["size", *map(str, objs)], capture_output=True,
                text=True).stdout.splitlines()[1:]
    for line in lines:
        t, d, b = line.split()[:3]
        totals["text"] += int(t)
        totals["data"] += int(d)
        totals["bss"] += int(b)
    return totals


def massif_peak(path: Path) -> tuple[int, int]:
    """Largest mem_heap_B and mem_stacks_B over all snapshots."""
    heap = stack = 0
    for block in path.read_text().split("snapshot=")[1:]:
        f = dict(re.findall(r"^(mem_\w+)=(\d+)", block, re.M))
        heap = max(heap, int(f.get("mem_heap_B", 0)))
        stack = max(stack, int(f.get("mem_stacks_B", 0)))
    return heap, stack


def measure(out: Path, alg: str, workdir: Path, reps: int) -> list[dict]:
    """Run keygen, encaps, decaps in order, each under massif in its own
    process, sharing workdir so the files test_kem_mem writes carry over.

    The whole sequence is repeated `reps` times. Massif's figures vary by
    a few KB between runs of the same binary when test_kem_mem's own stdio
    and printf dominate (not liboqs), so the maximum is reported and the
    minimum recorded alongside it."""
    exe = out / "tests" / "test_kem_mem"
    seen: dict[str, list[tuple[int, int]]] = {op: [] for op in OPS.values()}
    for r in range(reps):
        for n, op in OPS.items():
            mfile = workdir / f"massif.{op}.{r}"
            p = subprocess.run([*MASSIF, f"--massif-out-file={mfile}", str(exe), alg, str(n)],
                               cwd=workdir, capture_output=True, text=True)
            if p.returncode != 0:
                sys.exit(f"ERROR: {alg} {op} failed:\n{p.stdout}\n{p.stderr}")
            if op == "decaps" and "shared secrets are equal" not in p.stdout:
                sys.exit(f"ERROR: {alg} decaps did not confirm equal shared secrets")
            seen[op].append(massif_peak(mfile))
    return [{"alg": alg, "op": op,
             "stack_peak_bytes": max(s for _, s in v),
             "stack_peak_bytes_min": min(s for _, s in v),
             "heap_peak_bytes": max(h for h, _ in v),
             "heap_peak_bytes_min": min(h for h, _ in v)}
            for op, v in seen.items()]


def sh(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def environment(liboqs_rev: str | None) -> dict:
    cpu = next((l.split(":", 1)[1].strip()
                for l in Path("/proc/cpuinfo").read_text().splitlines()
                if l.startswith("model name")), platform.processor())
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "host": platform.node(),
        "cpu": cpu,
        "kernel": platform.release(),
        "compiler": (sh([os.environ.get("CC", "cc"), "--version"]).splitlines() or [""])[0],
        "valgrind": sh(["valgrind", "--version"]),
        "massif_options": MASSIF[1:],
        "liboqs_revision": liboqs_rev or sh(["git", "-C", str(LIBOQS_SRC), "describe", "--tags", "--always"]),
        "build": {"OQS_DIST_BUILD": "OFF", "OQS_USE_OPENSSL": "OFF",
                  "CMAKE_BUILD_TYPE": "Release", "OQS_OPT_TARGET": VARIANTS},
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def summary_md(env: dict, sizes: list[dict], mem: list[dict], code: list[dict]) -> str:
    L = [f"# Memory footprint (valgrind massif) — {env['host']}", "",
         f"{env['timestamp_utc']} · {env['cpu']} · {env['compiler']} · "
         f"{env['valgrind']} · liboqs `{env['liboqs_revision']}`", "",
         "Stack and heap are **whole-process** peaks of liboqs' `test_kem_mem`",
         "under massif, so they include the test program's own buffers and",
         "start-up code, not only the liboqs operation. Each figure is the",
         "maximum over repeated runs; `memory.csv` also has the minimum. See",
         "`bench/memory/README.md`.", "",
         "## Object sizes (bytes)", "",
         "| Parameter set | public key | secret key | ciphertext | shared secret |",
         "| --- | ---: | ---: | ---: | ---: |"]
    for s in sizes:
        L.append(f"| {s['alg']} | {s['pk_bytes']:,} | {s['sk_bytes']:,} "
                 f"| {s['ct_bytes']:,} | {s['ss_bytes']:,} |")
    for v in VARIANTS:
        rows = {(r["alg"], r["op"]): r for r in mem if r["variant"] == v}
        if not rows:
            continue
        L += ["", f"## Peak stack and heap per operation — {v} (bytes)", "",
              "| Parameter set | keygen stack | encaps stack | decaps stack "
              "| keygen heap | encaps heap | decaps heap |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for alg in dict.fromkeys(a for a, _ in rows):
            s = [rows[(alg, o)]["stack_peak_bytes"] for o in OPS.values()]
            h = [rows[(alg, o)]["heap_peak_bytes"] for o in OPS.values()]
            L.append(f"| {alg} | " + " | ".join(f"{x:,}" for x in s + h) + " |")
    L += ["", "## Code size of each parameter set's own object files (bytes)", "",
          "Excludes code shared between algorithms (SHA-3, RNG, common).", "",
          "| Parameter set | " + " | ".join(f"{v} text | {v} data+bss" for v in VARIANTS) + " |",
          "| --- |" + " ---: | ---: |" * len(VARIANTS)]
    by = {(c["variant"], c["alg"]): c for c in code}
    for alg in dict.fromkeys(c["alg"] for c in code):
        cells = []
        for v in VARIANTS:
            c = by.get((v, alg))
            cells += [f"{c['text_bytes']:,}", f"{c['data_bytes'] + c['bss_bytes']:,}"] if c else ["—", "—"]
        L.append(f"| {alg} | " + " | ".join(cells) + " |")
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variant", choices=[*VARIANTS, "both"], default="both")
    ap.add_argument("--algs", nargs="+", default=ALGS)
    ap.add_argument("--reps", type=int, default=3,
                    help="massif runs per (build, parameter set, operation); max is reported")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--force-build", action="store_true")
    ap.add_argument("--liboqs-rev", help="record this revision (when the "
                    "source tree is not a git checkout)")
    args = ap.parse_args()

    if not shutil.which("valgrind"):
        sys.exit("ERROR: valgrind not found")
    ids = alg_ids()
    unknown = [a for a in args.algs if a not in ids]
    if unknown:
        sys.exit(f"ERROR: unknown parameter sets: {unknown}")
    variants = list(VARIANTS) if args.variant == "both" else [args.variant]

    BUILD.mkdir(parents=True, exist_ok=True)
    env = environment(args.liboqs_rev)
    outdir = RESULTS / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{env['host']}"
    outdir.mkdir(parents=True, exist_ok=True)

    sizes, mem, code = [], [], []
    for v in variants:
        out = build(v, args.algs, ids, args.jobs, args.force_build)
        lengths = object_sizes(out)
        for alg in args.algs:
            if not sizes or alg not in {s["alg"] for s in sizes}:
                l = lengths[alg]
                sizes.append({"alg": alg, "pk_bytes": l["public-key"],
                              "sk_bytes": l["secret-key"], "ct_bytes": l["ciphertext"],
                              "ss_bytes": l["shared-secret"]})
            log(f"[{v}] {alg}")
            with tempfile.TemporaryDirectory() as wd:
                mem += [{"variant": v, **r} for r in measure(out, alg, Path(wd), args.reps)]
            c = code_size(out, ids[alg])
            code.append({"variant": v, "alg": alg, "text_bytes": c["text"],
                         "data_bytes": c["data"], "bss_bytes": c["bss"]})

    write_csv(outdir / "sizes.csv", sizes)
    write_csv(outdir / "memory.csv", mem)
    write_csv(outdir / "codesize.csv", code)
    (outdir / "env.json").write_text(json.dumps(env, indent=2) + "\n")
    (outdir / "summary.md").write_text(summary_md(env, sizes, mem, code))
    log(f"[done] {outdir}")


if __name__ == "__main__":
    main()
