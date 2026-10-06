# API harness: per-operation timing through liboqs and OpenSSL

Times keygen, encaps and decaps for every parameter set in
[`../../algorithms.md`](../../algorithms.md). The PQC KEMs go through
the liboqs API, and the classical baselines go through the OpenSSL API.
ML-KEM is also timed through OpenSSL, as the same-library comparison.
Both libraries are called from one C driver,
[`../../driver/kem_bench.c`](../../driver/kem_bench.c) (shared with the
memory harness), with the same loop and the same counters. Differences in the results therefore
come from the algorithms and libraries, not from two different benchmark
tools.

```sh
python3 bench/computational/api/run_bench.py                      # all 28 (impl, set) pairs
python3 bench/computational/api/run_bench.py --algs X25519 ML-KEM-512
python3 bench/computational/api/run_bench.py --impl openssl --runs 20
python3 bench/computational/api/run_bench.py --build-only
```

Needs `cmake`, `ninja`, `make`, `perl`, a C compiler and Python 3.12+.
Network access is needed once, to fetch OpenSSL. With the defaults
(10 runs, at most 1000 iterations or 1 s per run), a full run takes
roughly 20–30 minutes.

## Build

`run_bench.py` builds through
[`../../driver/kem_build.py`](../../driver/kem_build.py), which puts
everything under `bench/driver/build/` (gitignored) and rebuilds only
what is missing or out of date. Timing uses:

| What | Where | How |
| --- | --- | --- |
| liboqs | `liboqs-native/` | the submodule, `Release`, `OQS_DIST_BUILD=OFF`, `OQS_OPT_TARGET=auto` (`-march=native`), `OQS_USE_OPENSSL=OFF`, library only |
| OpenSSL | `openssl-3.5.9/` | the 3.5.9 release tarball, checked against a pinned SHA-256, `no-shared no-tests` |
| driver | `kem_bench-native` | `cc -O2 -march=native`, linked statically against both; no allocator tracking |

OpenSSL is built from a pinned source release rather than taken from
the system. The departmental hosts run Ubuntu 24.04, whose system
OpenSSL predates ML-KEM and DHKEM, and a pinned build is reproducible
across hosts, as the liboqs submodule is.

The two libraries are compiled differently. liboqs is built for the host
CPU (`-march=native`). OpenSSL keeps its default build, which selects
assembly code paths at run time from the CPU's feature flags. Each
library is built the way it is normally deployed.

## What is timed

Before timing, each process generates one keypair, encapsulates,
decapsulates, and checks that the two shared secrets match. It aborts
otherwise. The timed loop then repeats one operation against that
keypair. Setup stays outside the timed window: liboqs' `OQS_KEM_new`,
and OpenSSL's algorithm fetch and keygen and KEM contexts.

| Backend | keygen | encaps | decaps |
| --- | --- | --- | --- |
| liboqs | `OQS_KEM_keypair` into preallocated buffers | `OQS_KEM_encaps` | `OQS_KEM_decaps` |
| OpenSSL KEMs (X25519 and P-256 via DHKEM, RSA via RSASVE, ML-KEM) | `EVP_PKEY_generate`, which allocates a new key object | `EVP_PKEY_encapsulate` | `EVP_PKEY_decapsulate` |
| OpenSSL ffdhe (no KEM exists) | `EVP_PKEY_generate` | generate an ephemeral key, encode its public key, derive | decode the peer's public key, derive |

Freeing what an operation allocated happens after the timed window. The
ffdhe derive pads the secret to the group size, as TLS 1.3 does, and
keeps OpenSSL's default peer-key validation. The mapping is explained in
[`classical-baselines.md`](../../../docs/algorithms/classical-baselines.md).

Each process warms up for `--warmup` seconds, then times up to
`--max-iters` iterations. It stops early after `--max-seconds`, but
always runs at least 3. Slow operations, such as Classic McEliece and
RSA keygen, therefore get a few samples per run. They get their sample
count from the number of runs.

## Counters

Every iteration records three numbers:

- **`tsc_ticks`**: the full 64-bit time-stamp counter, read with
  `RDTSCP`. On x86_64 this ticks at a fixed nominal rate, not with the
  core clock. See
  [`../simple/README.md`](../simple/README.md#the-cycle-columns-are-tsc-ticks).
- **`ns`**: `CLOCK_MONOTONIC` wall time.
- **`perf_user_cycles`**: retired core cycles from `perf_event_open`,
  where the kernel allows it (`perf_event_paranoid` ≤ 2). The counter is
  reset, enabled before the timed window and disabled after it, every
  iteration. Two limits apply. It counts **user-space cycles only**, so
  time inside system calls is missing. It also includes a small,
  constant overhead from the counter control around the operation.
  Nothing corrects for either. Where perf is refused, as on the UTCS
  hosts, the column is empty.

## Runs and statistics

Each (implementation, set, operation) runs as `--runs` separate
processes, each with its own keypair. Runs are interleaved: run 1 of
everything, then run 2, and so on. Load that changes during a long
session therefore spreads across all algorithms instead of landing on
whichever was running at the time.

## Output

`../results/<UTC stamp>-<host>/`:

| File | Contents |
| --- | --- |
| `raw.csv` | every sample (gitignored; large) |
| `summary.csv` | per (impl, set, op): sizes, samples, median, p10, p90 and mean in µs; median TSC ticks and perf cycles; within-run and between-run CV; runs needed for ±1% |
| `summary.md` | the main columns as a table |
| `env.json` | host, CPU, kernel, compiler, library versions, liboqs revision, build options, `perf_event_paranoid`, governor, load average at start and end, arguments |

The **between-run CV** is the coefficient of variation of the per-run
medians. If it is much larger than the within-run CV, the spread comes
from differences between processes (keypair, memory layout, core, load).
More iterations per run will not reduce it; only more runs will.
`runs_for_1pct` is `(1.96 × between-run CV / 0.01)²`.

## Known differences between the two libraries

These are differences in the code being measured, not in the harness.
Keep them in mind before reading a gap between liboqs and OpenSSL as a
property of the algorithm.

- **Randomness.** With `OQS_USE_OPENSSL=OFF`, every liboqs
  `OQS_randombytes` call on Linux goes to `getentropy`, at most 256
  bytes per call (`implementations/liboqs/src/common/rand/rand.c:94-105`).
  That is a system call each time. OpenSSL draws from a DRBG in user
  space. *Our interpretation:* this penalises the liboqs operations that
  draw a lot of randomness in wall time, and it hides that cost from the
  perf column. See the NTRU encaps note in
  [`../../../docs/implementations/liboqs.md`](../../../docs/implementations/liboqs.md).
- **ML-KEM.** liboqs' ML-KEM is vendored mlkem-native, and OpenSSL's is
  its own implementation. Their gap combines API overhead with
  implementation differences.
- **DHKEM adds HKDF** on top of raw X25519 or ECDH. TLS 1.3 runs raw
  ECDH and its own key schedule.

## Not implemented

- Correcting perf's user-space cycles for time spent in the kernel. An
  earlier, deleted harness calibrated this; see
  [`experimental-environments.md`](../../../docs/experimental-environments.md).
