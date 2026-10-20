# liboqs

## Overview

Per upstream documentation, liboqs is not itself a primitive implementation
of a PQC algorithm. It is a C library from the Open Quantum Safe project
that provides a common API over multiple KEM and signature schemes,
several of which are vendored in from other implementations (e.g.
PQClean). It is being tracked here as a benchmarking/comparison harness
rather than as an algorithm implementation. This project uses only its
KEM API, for ML-KEM, Classic McEliece and NTRU; the signature side is
out of scope and omitted from these notes.

## Upstream Repository

https://github.com/open-quantum-safe/liboqs

## Repository Structure

## Build System

## Tests

### Running the Tests

```sh
mkdir build && cd build && cmake -GNinja .. && ninja
ninja run_tests
```

There is **no CTest / `add_test()`** anywhere. `run_tests` is a custom
target that shells out to pytest from the repo root
(`tests/CMakeLists.txt:252-258`):

```sh
OQS_BUILD_DIR=<build> python3 -m pytest --verbose --numprocesses=auto \
    --ignore=scripts/copy_from_upstream/repos --ignore=tests/test_kat_all.py
```

Note `test_kat_all.py` is ignored by default (and in nearly every CI job)
because it is slow — the full-KAT sweep only runs in the weekly extended
workflow. Pytest must run from the repo root: helpers read `src/kem/kem.h`
and `docs/algorithms/` by relative path, and find binaries via
`OQS_BUILD_DIR`.

Filtering is by environment variable: `SKIP_ALGS` (comma-separated
regexes) and `SKIP_TESTS` (test-function suffixes), via the
`@helpers.filtered_test` decorator (`tests/helpers.py:155-172`).

### Test Files

Two layers: C programs in `tests/*.c`, and a pytest layer in `tests/*.py`
that runs them via `subprocess` and asserts on exit codes or stdout
hashes.

| Binary | Purpose |
| --- | --- |
| `test_kem` | correctness |
| `kat_kem` | KAT generation/checking |
| `vectors_kem` | ACVP / Wycheproof / intermediate-value driver |
| `test_kem_mem` | one operation per process, for external memory profiling |
| `test_aes`, `test_hash`, `test_sha3` | primitive tests (Unix only) |
| `speed_kem`, `speed_common` | benchmarks |
| `dump_alg_info` | YAML dump of all parameters, consumed by `test_alg_info.py` |
| `fuzz_test_*` | libFuzzer targets |

Python modules of note: `test_kat.py`, `test_kat_all.py`, `test_cmdline.py`,
`test_leaks.py`, `test_constant_time.py`, `test_mem.py`, `test_binary.py`,
`test_alg_info.py`, `test_code_conventions.py`, `test_hash.py`,
`test_speed.py`, `test_distbuild.py`, `test_acvp_vectors.py`,
`test_wycheproof_vectors.py`.

Every module is `@pytest.mark.parametrize`d over algorithms discovered by
parsing `src/kem/kem.h` for `#define OQS_KEM_alg_*`,
cross-checked against `oqsconfig.h` for what was actually compiled in.

### What Is Actually Tested?

**KAT verification is by SHA-256 of stdout**, like PQClean and the native
repos — not by shipping `.rsp` files. `kat_kem` writes NIST-format KAT
text to stdout; `tests/test_kat.py` normalises CRLF→LF, hashes it, and
compares against `tests/KATs/kem/kats.json`, which stores two digests per
algorithm (all ten Classic McEliece, three ML-KEM and six NTRU parameter
sets are present):

```json
"ML-KEM-512": {
  "all": "74b470e7…",
  "single": "c70041a7…"
}
```

`single` is `count = 0` only (the default); `all` requires `--all`.
`kat_kem.c:3-5` documents the derivation from an original submission
file: `cat PQCkemKAT_whatever.rsp | head -n 8 | tail -n 6`.

**ACVP and Wycheproof vectors are downloaded**: ACVP from
`usnistgov/ACVP-Server` at tag `v1.1.0.42`; Wycheproof from C2SP at a
pinned commit. Of our three algorithms, both cover **ML-KEM only**
(`test_wycheproof_vectors.py` maps just `ML-KEM-{512,768,1024}`). Both
are ignored in most CI jobs and run in the extended workflow.

**Constant-time testing** uses the ctgrind approach (credited in
`test_constant_time.py:159-172` to Langley / SUPERCOP / TIMECOP): under
`OQS_ENABLE_TEST_CONSTANT_TIME`, a custom `randombytes` marks every random
byte undefined via `VALGRIND_MAKE_MEM_UNDEFINED`, and public outputs are
declassified at ~20 sites per test program.

```sh
valgrind --tool=memcheck --gen-suppressions=all --error-exitcode=1 \
  --max-stackframe=20480000 --num-callers=20 \
  --suppressions=<passes files> --suppressions=<issues files> \
  build/tests/test_kem <alg>
```

**The passes/issues split is the interesting part for us.** Suppression
files live in `tests/constant_time/kem/{passes,issues}/` and are treated
identically at runtime — the distinction is an *auditor label*: "passes"
means analysed and judged not a threat, "issues" means un-analysed or
suspicious. Currently `kem/issues/` holds `classic-mceliece-*` (**all ten
parameter sets**) and `hqc-{1,3,5}`. The Classic McEliece entries are
commented *"This implementation of Classic McEliece may not be constant
time."* and point into key generation (e.g. `to_bitslicing_2x` under
`PQCLEAN_MCELIECE348864_AVX2_pk_gen`). `kem/passes/` holds `bike`,
`kyber` (e.g. rejection sampling of the public matrix in `gen_matrix`)
and `sntrup`; no file is named for ML-KEM or NTRU. So a green CT run here
does **not** mean every algorithm is constant time — it means known
deviations are suppressed.

**Memory**: `test_leaks.py` runs valgrind `--leak-check=full` (Linux
x86_64 only); ASan/MSan/UBSan
via `USE_SANITIZER` with clang; `scan-build` static analysis; coverage via
lcov to Coveralls.

**API/ABI hygiene**: `test_binary.py` runs `nm -D` on the shared library
and asserts every exported symbol matches an allowed namespace prefix,
and that `GNU_STACK` is `RW` (non-executable). CI additionally asserts the
dlopen build has no undefined OpenSSL symbols.

**Metadata cross-check**: `test_alg_info.py` runs `dump_alg_info`, loads
the matching `docs/algorithms/**.yml` datasheet, and asserts
`claimed-nist-level`, `claimed-security` and every `length-*` field match
the compiled C metadata.

**Code conventions**: astyle formatting, SPDX headers on every source
file, and a check that `src/` contains no raw
`malloc/free/calloc/realloc/strdup` unless the line carries
`// IGNORE memory-check`.

**Fuzzing**: four libFuzzer targets (`OQS_BUILD_FUZZ_TESTS=ON`,
clang-only). `docs/FUZZING.md`'s own coverage checklist marks **no KEM**
as fuzzed, including `ml_kem` and `classic_mceliece` (NTRU has no entry;
`ntruprime` is a different scheme); the only checked entries are
signature schemes. CI runs a 30-second smoke fuzz.
No OSS-Fuzz config is in-tree, though `LIB_FUZZING_ENGINE` is honoured.

**CI is GitHub Actions only** (no CircleCI; Travis is disabled per
`CI.md:113-116`), organised as caller workflows dispatching to callable
ones: `push.yml`/`pr.yml`/`commit-to-main.yml`/`weekly.yml`/`release.yml`
→ `basic.yml`, `platforms.yml` (→ android, apple, linux, macos, windows,
zephyr), `extended.yml`, `code-coverage.yml`. Commit-message tags
(`[full tests]`, `[extended tests]`, `[code coverage]`) opt into heavier
suites. `linux.yml` alone covers 15 configurations; one job runs under
**Intel SDE** to exercise AVX-512 paths, and `test_distbuild.py` runs
under QEMU with a minimum microarchitecture (`-cpu Westmere` /
`cortex-a53`) to verify runtime CPU feature dispatch.

## Benchmarking

This is the part most relevant to Phase 2 — liboqs is the only submodule
here built to benchmark *across* algorithms behind one API.

### Harness

All `speed_*` programs use `tests/ds_benchmark.h`. Cycle counting
(`ds_benchmark.h:123-152`):

| Platform | Source |
| --- | --- |
| Windows | `QueryPerformanceCounter` |
| x86 | raw `rdtsc` |
| AArch64 with `OQS_SPEED_USE_ARM_PMU` | `PMCCNTR_EL0` (needs a kernel module) |
| s390x | `stckf` |
| **fallback** | `clock_gettime(CLOCK_REALTIME)` in **nanoseconds** |

The fallback matters: it defines `USING_TIME_RATHER_THAN_CYCLES` and the
column header silently changes from `CPU cycles: mean` to
`High-prec time (ns): mean`. On a platform without rdtsc or a PMU module,
the "cycles" column is nanoseconds — check the header before comparing
numbers.

Wall time is measured separately with `gettimeofday()`. Mean and
**population** standard deviation are accumulated online (Welford) for
both cycles and time.

### Invocation

```sh
build/tests/speed_kem --algs                 # list, marks disabled ones
build/tests/speed_kem -d 5 ML-KEM-768        # 5 s per operation
build/tests/speed_common -m 1024 -o 32       # symmetric primitives
```

Default duration is **3 seconds per operation** (1 s for `speed_common`).
With no algorithm argument it loops over all of them. If built with OpenSSL, the RNG is switched
to `OQS_RAND_alg_openssl` before timing.

### Output

Fixed-width columns, deliberately Markdown-table-compatible (the header's
colons right-align cells), preceded by a "Configuration info" block from
`tests/system_info.c` recording compiler, compile options, git commit,
OpenSSL version and active CPU extensions:

```
Operation | Iterations | Total time (s) | Time (us): mean | pop. stdev | CPU cycles: mean | pop. stdev
```

It is **not CSV**. `scripts/parse_liboqs_speed.py` converts a log to JSON
for `github-action-benchmark`:

```sh
python3 parse_liboqs_speed.py <logfile> --algorithm <ALG>
```

emitting `{"name": "<alg> keygen", "value": <cycles>, "unit": "cycles",
"extra": "<config>"}`. Caveat: the output filename is overwritten by the
last parsed algorithm, so it only behaves as intended for a single
algorithm per log — which is how CI calls it.

### Published benchmarks

`.github/workflows/kem-bench.yml`, run weekly (cron Sunday 00:05) and on
demand. It builds only `speed_kem` static, then runs a matrix of 32 KEMs
with
**`max-parallel: 1`**, one algorithm per job:

```sh
./speed_kem "<alg>" > <alg>_output.txt
python3 parse_liboqs_speed.py <alg>_output.txt --algorithm <alg>
```

Results are pushed to the GitHub Pages dashboard via
`benchmark-action/github-action-benchmark` (`customSmallerIsBetter`,
`alert-threshold: 105%`, comment on regression).

Per `CI.md:108-111`, new algorithms must be **added manually** to these
matrices — so absence from the dashboard does not mean an algorithm is
unsupported.

### Caveats for our own use

- Runners are ordinary GitHub-hosted `ubuntu-latest` VMs: shared,
  frequency-scaled, noisy. Fine for trend tracking, weak for absolute
  numbers.
- Binaries are built with `OQS_DIST_BUILD=ON`, i.e. runtime CPU dispatch,
  not `-march=native`.
- Default 3 s per operation, mean (not median) with population stdev —
  contrast mlkem-native's median-of-500 design.
- Several vendored implementations come from PQClean, whose own README
  warns its shared primitives are not performance-tuned.

### Two defects in the x86_64 cycle counter

Both observed directly in source and confirmed by measurement on our
host (AMD Ryzen 5 5600X, WSL2, 2026-09-20).

**1. The TSC read is truncated to 32 bits.** `ds_benchmark.h:130-134`:

```c
#elif defined(__i586__) || defined(__amd64__)
    uint64_t x;
    __asm__ volatile(".byte 0x0f, 0x31"
                     : "=A"(x));
    return x;
```

`rdtsc` returns its 64-bit result split across `EDX:EAX`. The `"A"`
constraint means the `ax:dx` pair *only* for a double-word operand; for a
64-bit (DImode) value on x86_64 a single register is already a full word,
so GCC allocates `x` to `RAX` alone and the `EDX` half is discarded. The
counter therefore wraps every 2^32 ticks — about **1.16 s** at the
measured 3.70 GHz TSC rate.

`STOP_TIMER` (`ds_benchmark.h:196-198`) compensates for exactly one wrap:

```c
if (_bench_cycles_end < _bench_cycles_start) {
    _bench_cycles_end += (uint64_t) 1 << 32;
}
```

Our interpretation: this is safe for ML-KEM and NTRU, whose operations
are microseconds. It is thin cover for Classic McEliece keygen at the
larger parameter sets, and it fails silently rather than loudly — a
single operation exceeding ~1.16 s yields a plausible-looking small
number, and one exceeding ~2.3 s is not corrected at all.

**2. TSC ticks are reported as "CPU cycles".** The TSC on this CPU is
invariant (`constant_tsc`, `nonstop_tsc`, `tsc_reliable` all present in
`/proc/cpuinfo`), meaning it advances at a fixed nominal rate regardless
of the core's actual clock. Retired core cycles are a different quantity.
Measured with `perf` `PERF_COUNT_HW_CPU_CYCLES` over an identical
workload, the ratio was **about 1.2 core cycles per TSC tick** (1.19–1.23
once measured reliably; see the caveat below). The column header says
`CPU cycles: mean`.

This is separate from, and the opposite of, the documented
`USING_TIME_RATHER_THAN_CYCLES` fallback: on x86_64 the header does *not*
change, so there is no signal that the number is a TSC tick rather than a
cycle.

### Our own harness

An earlier replacement harness, written against the liboqs public API,
was deleted without being committed, so its source is not in this
repository. Its replacement,
[`bench/computational/api/`](../../bench/computational/api/README.md),
calls the liboqs and OpenSSL APIs directly, so the PQC algorithms and
the [classical baselines](../algorithms/classical-baselines.md) are
timed the same way. It avoids both defects above: it reads the full
64-bit counter with `RDTSCP`, and adds a per-iteration `perf` user-space
cycle counter where the kernel allows one. It also separates within-run
from between-run variance, which `ds_benchmark.h` does not, because the
latter aggregates a single process's iterations and has no notion of an
independent run.

`perf_event_open` was verified to work under WSL2 on this host, but only
with `exclude_kernel=1`: `/proc/sys/kernel/perf_event_paranoid` is 2, and
opening the counter with `exclude_kernel=0` fails.

### Counting only userspace cycles distorts RNG-heavy operations

Our own measurement mistake, worth recording because it is not obvious
and it produced plausible-looking wrong numbers.

This section records findings from the deleted harness described above.
The ratios were observed at the time, but the code that produced them is
gone, so treat them as findings to re-check rather than reproducible
results.

The first version of that harness derived core cycles per operation by
scaling the operation's TSC ticks by that operation's *own* measured
ratio of perf cycles to TSC ticks. With `exclude_kernel=1`, perf counts
only userspace cycles while the TSC counts everything, so the ratio is
not a pure frequency ratio — it is deflated in proportion to the time the
operation spends inside syscalls.

The result was internally inconsistent: NTRU-HPS-2048-509 `encaps`
appeared to take 11.9 µs / 18.9k cycles while `decaps` took 7.49 µs /
33.5k cycles — faster in wall time yet more cycles. The measured ratio
was stable to three decimal places across 20 independent runs, which
ruled out counter flakiness and pointed at a systematic per-operation
effect.

Ratios measured (2026-09-20). The `cycles/tick` column is a direct
measurement and was stable to three decimal places across 20 independent
runs. The derived fractions assume a reference ratio of ≈1.20 and are
**provisional** — see the caveat below.

| Operation | cycles/tick | userspace fraction |
| --- | ---: | ---: |
| NTRU-HPS-2048-509 encaps | 0.417 | ~35% |
| NTRU-HRSS-701 encaps | 0.655 | ~55% |
| NTRU-HPS-2048-509 keygen | 0.923 | ~77% |
| Classic-McEliece encaps | ~1.05 | ~88% |
| any decaps | ~1.22 | ~100% |

Our interpretation: the shortfall is time in `getrandom()`. Operations
that draw a lot of randomness — NTRU encapsulation samples a large
fixed-weight polynomial — spend a large fraction of their wall time in
the kernel. Decapsulation draws none and sits at the reference ratio.

The fix is to scale by a ratio measured over a pure-userspace spin loop
containing no syscalls, and to report the per-operation ratio separately
as a `userspace_cycle_fraction` diagnostic. Setting `perf_event_paranoid`
to 1 would remove the need for the correction entirely.

**Caveat on the reference ratio (2026-09-21).** A first attempt measured
that spin loop once, over a single window. It was badly unstable —
0.57–1.19 across repeated identical runs — because under WSL2 the TSC is
host-based and keeps advancing while the vCPU is descheduled, whereas
perf only counts cycles actually retired. All such interference is
one-sided (it can only depress the ratio), so the estimator was changed
to the **maximum over 8 short windows**, which gives 1.19–1.23 and an
implied 4.40–4.55 GHz, correct for this CPU under boost.

Consequently the `cycles/tick` column above is trustworthy but the
derived percentages are provisional, and no benchmark run to date is
clean enough to quote: the runs of 2026-09-20 used either the wrong
scaling or the unstable reference, and were additionally taken while the
machine was in interactive use. Numbers pending a run on a quiet host.

Open consequence: this means **NTRU encapsulation's cost in liboqs is
dominated by RNG syscall overhead on this platform**, not by the lattice
arithmetic. That is a property of how liboqs/PQClean call `randombytes`,
not of NTRU as an algorithm, and it would change completely with a
buffered userspace DRBG. Worth checking against `OQS_USE_OPENSSL=ON`,
which switches the RNG to `OQS_RAND_alg_openssl`.

## Supported Algorithms / Parameter Sets

## Important Source Files

## Key Generation Call Path

## Encapsulation Call Path

## Decapsulation Call Path

## Randomness

## Hash / XOF Primitives

## Polynomial / Data Representation

## Optimized vs Reference Implementations

Observed in `src/kem/`: ML-KEM is vendored mlkem-native
(`src/kem/ml_kem/mlkem-native_ml-kem-*_{ref,x86_64,aarch64}`), and NTRU
comes from PQClean (`src/kem/ntru/pqclean_ntru*_{clean,avx2}`). NTRU has
AVX2 code for HPS-2048-509, HPS-2048-677, HPS-4096-821 and HRSS-701 only;
HPS-4096-1229 and HRSS-1373 have `clean` (portable C) only.

## GPU Backends for ML-KEM

Read 2026-10-19, liboqs `adbeba1ef`.

Per upstream documentation (`CONFIGURE.md`, `OQS_USE_CUPQC` and
`OQS_USE_ICICLE`), two build options move ML-KEM onto an NVIDIA GPU.
Both are off by default, cover ML-KEM only, and are enabled only on
Linux and Darwin (`.CMake/alg_support.cmake`).

- cuPQC is NVIDIA's library. It is a separate download under NVIDIA's
  own licence, and `find_package(cuPQC 0.2.0 REQUIRED)` locates it
  (`CMakeLists.txt:156`). The glue comes from
  `open-quantum-safe/liboqs-cupqc-meta@b026f4e`.
- ICICLE is Ingonyama's library. It has to be built and installed
  separately as `icicle_pqc_package`; `CONFIGURE.md` gives the CMake
  recipe. The glue comes from `ingonyama-zk/icicle-liboqs@4ea3e61`.

The pinned sources are listed in `docs/algorithms/kem/ml_kem.md`.

### Observed in source

- The switch is made at compile time, for the whole library. In
  `src/kem/ml_kem/kem_ml_kem_768.c`, `OQS_KEM_ml_kem_768_keypair`,
  `_encaps` and `_decaps` call the GPU code unconditionally when the
  option is on. There is no runtime selection and no CPU fallback, and
  cuPQC wins if both options are on. The 512 and 1024 files follow the
  same pattern.
- The derandomised functions stay on the CPU.
  `OQS_KEM_ml_kem_768_keypair_derand` never reaches GPU code.
  `_encaps_derand` reaches ICICLE only in an `#elif` that comes after the
  x86_64 and aarch64 branches, so on an AVX2 host it runs mlkem-native.
  The cuPQC glue has no derandomised entry points.
- Each call does one operation and sets the GPU up from scratch. The
  cuPQC glue (`src/kem/ml_kem/cupqc_ml-kem-768_cuda/cupqc_ml-kem.cu`)
  creates a workspace (`make_workspace<...>(1)`) and entropy buffer
  (`get_entropy<...>(1)`), `cudaMalloc`s the key and ciphertext
  buffers, copies inputs to the device, launches a single block
  (`<<<1, BlockDim>>>`), copies results back and frees everything. The
  ICICLE glue (`src/kem/ml_kem/icicle_ml-kem-768_icicle_cuda/icicle_ml-kem.cpp`)
  passes a default `MlKemConfig`, which is one operation with every
  buffer on the host (see below).
- Randomness differs between the two. The ICICLE glue draws its coins
  from `OQS_randombytes`. The cuPQC glue uses cuPQC's own `get_entropy`,
  so liboqs' RNG selection does not reach it.
- The cuPQC objects are compiled with `-arch=compute_70`
  (`src/kem/ml_kem/CMakeLists.txt`), which is PTX for the driver to JIT on
  newer GPUs. `CMAKE_CUDA_ARCHITECTURES` defaults to `80 90` when unset
  (`CMakeLists.txt:153`).
- Test coverage: no workflow under `.github/` mentions CUDA, cuPQC or
  ICICLE, so upstream CI does not build these backends. With a GPU build,
  `tests/test_kem.c` round-trips through the GPU functions, and
  `tests/kat_kem.c` calls the non-derandomised functions too.
  `kat_kem` only prints its outputs; `tests/test_kat.py` does the
  comparison, hashing that output with SHA-256 and checking it against
  `kats[kem_name]['single']`.
  `tests/vectors_kem.c` checks keygen and encapsulation through the
  derandomised functions, so on x86_64 only its decapsulation checks
  reach the GPU.

### ICICLE upstream

Read from `ingonyama-zk/icicle` `main` on 2026-10-19 (last push
2025-11-10). This is newer than, and may differ from, the commit the
`icicle-liboqs` glue was written against.

- The ML-KEM API is batched (`icicle/include/icicle/pqc/ml_kem.h`).
  `MlKemConfig` has `batch_size` (default 1), a `*_on_device` flag for
  each buffer (default host), a `stream` and `is_async`.
- `icicle/backend/cuda_pqc/README.md` describes the CUDA-PQC backend as
  open source and licence-free, statically linked, and separate from
  ICICLE's closed-source CUDA backend.
- The first device backend to register becomes the default device
  (`icicle/src/device_api.cpp`), and the liboqs glue never selects one.
  The `CONFIGURE.md` recipe builds with `-DCPU_BACKEND=OFF`, which leaves
  CUDA-PQC as the only device.

### Our interpretation

- Timing a GPU build through the `OQS_KEM` API measures the latency of a
  drop-in GPU liboqs: each operation pays for allocation, transfers and
  a kernel launch. It says little about GPU throughput, which needs many
  operations per launch.
- The `OQS_KEM` API is one operation per call, so batches can't be
  measured through liboqs. ICICLE's own API with `batch_size = N` is an
  upstream route that needs no ML-KEM code of our own. Batching through
  cuPQC would need our own kernel-launch wrapper, like the liboqs glue
  with `N` blocks.
- Comparing CPU and GPU ML-KEM through liboqs needs two liboqs builds,
  because the backend is fixed at compile time.
- `tests/kat_kem.c` seeds `OQS_randombytes` and compares against stored
  outputs. Since the cuPQC glue bypasses `OQS_randombytes`, we expect
  its keygen and encapsulation to fail that test. We have not run it.
- If ICICLE is built with its CPU backend as well, which device liboqs
  ends up on depends on registration order. We have not checked this.

### Built and tested with ICICLE (2026-10-20)

Built as `bench/driver/build/liboqs-icicle-tests/` (tests included) and
`liboqs-icicle/` (library only, for the timing driver); see
[ICICLE notes](icicle.md) for the ICICLE build.

- `test_kem` passes for ML-KEM-512, -768 and -1024.
- `tests/test_kat.py` and `tests/test_acvp_vectors.py`, filtered with
  `-k ML-KEM`, pass: 15 tests. In the KAT test, ICICLE's keygen and
  encapsulation reproduce the stored answers from the same
  `OQS_randombytes` stream.
- To run the pytest files against a build outside the source tree, set
  `OQS_BUILD_DIR` to its absolute path and run from the liboqs root.
  `helpers.py` also needs `requests`.
- With `CUDA_VISIBLE_DEVICES=` the ML-KEM calls abort the process (an
  uncaught `IcicleError`). This confirms the GPU is in use.

## Interesting Observations

From our memory measurements
([`bench/memory/README.md`](../../bench/memory/README.md), which has the
figures and method):

- All heap use by the three KEMs comes from liboqs' SHA-3 layer, which
  allocates hashing state with `OQS_MEM_aligned_alloc`
  (`src/common/sha3/xkcp_sha3.c`, `xkcp_sha3x4.c`). mlkem-native built on
  its own keeps that state on the stack instead; liboqs connects it to
  its SHA-3 through a glue header.
- The NTRU AVX2 assembly (`square_*_shufbytes.s`) puts constant shuffle
  tables in `.data` rather than `.rodata`: 26–82 KB of writable static
  data per parameter set.

## Open Questions

- The `passes`/`issues` CT suppression split is an auditor judgement with
  no enforcement. Which "passes" entries have actually been analysed, and
  by whom? This matters before citing liboqs CT results.
- ~~On our hardware, does `speed_*` fall back to `clock_gettime` (ns) or
  get real cycles?~~ **Answered 2026-09-20**: neither. On x86_64 it takes
  the `rdtsc` path, so the column is TSC ticks — not nanoseconds, and not
  core cycles — and is truncated to 32 bits. See "Two defects in the
  x86_64 cycle counter" above.
- `OQS_SPEED_USE_ARM_PMU` needs a kernel module. Do we want to set that up
  for Phase 2, or standardise on `PERF` across machines? Leaning `perf`:
  it works unprivileged on x86_64 here and needs no module.
- Is the `"=A"` truncation worth reporting upstream? It is a real bug, but
  it only bites operations longer than ~1.16 s, which is why it has
  survived — the CI matrix is dominated by fast algorithms.
- Does `OQS_DIST_BUILD=ON` (runtime dispatch, what CI and distros use)
  measurably differ from `OFF` (`-march=native`) for these three families?
  The API harness builds only `OFF` today; a second build directory with
  `ON` would answer this.
- liboqs vendors implementations from PQClean and elsewhere. For any
  algorithm we benchmark, which implementation is actually being measured,
  and is it the optimised or reference one?
- Is `ninja run_tests` feasible to run locally here, and how long does the
  full (non-`kat_all`) suite take?
