# Simple: per-operation timing via liboqs' `speed_kem`

A ~40 line Python wrapper around liboqs' `tests/speed_kem`. It measures
nothing itself. It runs liboqs' benchmark once per algorithm, parses the
table it prints, and collects the rows into one CSV.

```sh
python3 bench/simple/speed_kem_totals.py [seconds_per_op]   # default 3
```

Writes `bench/results/simple-speed_kem.csv` and prints the same table.

Algorithms benchmarked, set by `ALGS` in the script: ML-KEM-512/768/1024,
Classic-McEliece-348864/6688128, NTRU-HPS-2048-509, NTRU-HRSS-701.

## Build

`speed_kem` is a test binary, so liboqs must be configured without
`OQS_BUILD_ONLY_LIB=ON`:

```sh
cmake -S implementations/liboqs -B bench/build/liboqs \
      -DCMAKE_BUILD_TYPE=Release -DOQS_USE_OPENSSL=OFF \
      -DOQS_DIST_BUILD=OFF -DOQS_BUILD_ONLY_LIB=OFF -G Ninja
cmake --build bench/build/liboqs --target speed_kem
```

`OQS_USE_OPENSSL=OFF` drops the OpenSSL dependency and fixes the RNG and
hash providers across machines. `OQS_DIST_BUILD=OFF` compiles for the
host (`-march=native`); `ON` builds every ISA variant behind runtime
dispatch, which is what distro packages and liboqs CI use, and measures
something different.

`bench/build/` is shared with `bench/full/`, so object files are reused.

## What comes out

`speed_kem` prints one row per operation with 7 fields:

```
Operation | Iterations | Total time (s) | Time (us): mean | pop. stdev | CPU cycles: mean | pop. stdev
keygen    |     541850 |          3.000 |           5.537 |      1.362 |            18816 |       4331
```

The script adds the algorithm name and renames the cycle columns, giving
8 CSV columns:

| Column | Meaning |
| --- | --- |
| `alg`, `op` | algorithm, and one of keygen / encaps / decaps |
| `iterations` | how many operations fitted in the budget |
| `total_time_s` | the budget requested, not a result |
| `time_us_mean` | mean time for one operation |
| `time_us_popstdev` | population standard deviation over all iterations |
| `tsc_ticks_mean` | liboqs' "CPU cycles" column, renamed |
| `tsc_ticks_popstdev` | its population standard deviation |

### `total_time_s` is an input

`speed_kem` repeats an operation until a time budget expires, so this
column reads 3.000 on every row when 3 seconds was requested. The
measured quantity is `iterations`. A real total is
`iterations * time_us_mean`.

### The cycle columns are TSC ticks

They are renamed `tsc_ticks_*` rather than passed through as cycles,
because on x86_64 they are not cycles:

1. The TSC advances at a fixed nominal rate regardless of what the core
   is doing, so it does not see frequency boost. Measured against a real
   cycle counter on the Ryzen 5600X dev host, retired core cycles ran
   about 1.2x these figures, so the column understates by roughly 20%.
2. The value is truncated to 32 bits. `tests/ds_benchmark.h:130-134`
   reads the TSC through an `"=A"` inline-asm constraint, which on
   x86_64 selects a single register for a 64-bit value, discarding the
   upper half. The counter wraps every ~1.16 s at 3.70 GHz, and
   `STOP_TIMER` corrects only one wrap. Classic McEliece keygen is the
   case where this matters, and it produces a plausible small number
   rather than an error.

The header still reads `CPU cycles: mean` in both cases.

## `perf_event_open`

liboqs never calls `perf_event_open`. There is no reference to it, to
`linux/perf_event.h`, or to `PERF_COUNT_HW_*` anywhere in the tree.
`_bench_rdtsc()` is a compile-time `#if` chain with no runtime probing:

| Platform | Source | Real cycles? |
| --- | --- | --- |
| Windows | `QueryPerformanceCounter` | no |
| x86 / x86_64 | raw `rdtsc` | no, TSC ticks |
| AArch64 + `OQS_SPEED_USE_ARM_PMU` | `PMCCNTR_EL0` | yes, needs a kernel module |
| s390x | `stckf` | no |
| fallback | `clock_gettime` | no, header changes to `High-prec time (ns)` |

On any x86_64 host `speed_kem` reports TSC ticks, including a host with
every performance counter available. Configuration cannot change this;
only patching liboqs or running on AArch64 with a PMU module can.

Real cycles require asking the kernel for a hardware counter through
`perf_event_open` with `PERF_COUNT_HW_CPU_CYCLES`, which means code
liboqs does not have. Access is governed by
`/proc/sys/kernel/perf_event_paranoid`:

| Value | Unprivileged processes may |
| ---: | --- |
| 3 and above | nothing |
| 2 | measure their own process, user-space cycles only |
| 1 | also measure kernel-mode cycles |
| 0 / -1 | fewer restrictions still |

Measured on our hosts:

| Host | `paranoid` | `perf_event_open` |
| --- | ---: | --- |
| WSL2 desktop (Ryzen 5600X) | 2 | works, user-space cycles only |
| `coral` (UTCS) | 4 | refused |
| `grape-nuts` (UTCS) | 4 | refused |

The UTCS value is pushed by Puppet, so it is site policy rather than a
per-machine setting, and 4 should be expected on any departmental
workstation. Lowering it to 1 requires the administrators.

So on UTCS hardware there is no route to real cycle counts, through this
wrapper or through a larger harness. On the WSL2 box there is a route,
but only by writing the `perf_event_open` code.

## Limits of this approach

This script answers how long one operation takes, and on a quiet machine
that answer holds up. The ML-KEM figures in `bench/results/` come from
hundreds of thousands of iterations.

Five questions it cannot answer:

- **How many cycles?** Not available from `speed_kem` on x86_64, for the
  reasons above. Cycles are also the more portable comparison, being
  frequency-invariant, so they survive a machine that throttles, boosts,
  or has heterogeneous cores, where wall-clock microseconds do not.
- **Is this difference real?** `speed_kem` runs one process per
  algorithm, leaving nothing to compare across. It reports
  iteration-to-iteration spread inside that single process, which
  ignores what varies between processes: a different keypair, a
  different address-space layout, a different core, a different point in
  the machine's thermal and boost state. Averaging 500,000 iterations
  inside one process drives the within-process error towards zero while
  leaving per-process bias intact and invisible.
- **How many runs do I need?** Requires the between-process variance
  above. The sample count is `n >= (1.96 * CV / e)^2`, and the relevant
  `CV` is the one `speed_kem` cannot see.
- **What does the distribution look like?** No median, no percentiles.
  This matters most for Classic McEliece key generation, whose
  rejection-sampling retry loop makes it heavy-tailed: a coefficient of
  variation around 20-27%, against 4-8% for every other operation
  measured. A mean with a standard deviation misleads there.
- **Did I get enough samples?** The two McEliece keygen rows in our
  results come from 95 and 19 iterations, because at ~32 ms and ~158 ms
  per keygen few fit in a 3 second budget. Their large standard
  deviations mix the algorithm's real spread with sampling error, and
  the output does not distinguish them.

[`../full/`](../full/README.md) addresses these. It calls the liboqs API
directly, reads the full 64-bit counter, adds a `perf_event_open` cycle
counter where the kernel permits one, runs each algorithm as R
independent processes to separate within-run from between-run variance,
reports medians and percentiles alongside trimmed means, and computes
required sample sizes from the measured spread.

It is also much larger, and most of it is measurement machinery rather
than benchmarking. Use this script until one of the five questions above
is blocking.

## Related

- [`../full/README.md`](../full/README.md) — the harness for cycles and variance
- [`../../docs/benchmark-environments.md`](../../docs/benchmark-environments.md) — which host can measure what
- [`../../docs/implementations/liboqs.md`](../../docs/implementations/liboqs.md) — source references for the defects above
