# Research Knowledge Index

This is the main index for accumulated research notes.

## Algorithms

- [ML-KEM](algorithms/ml-kem.md)
- [Classic McEliece](algorithms/classic-mceliece.md)
- [NTRU](algorithms/ntru.md) — unstandardised; studied as the lattice
  alternative to ML-KEM
- [Classical baselines](algorithms/classical-baselines.md) — the
  pre-quantum key-establishment algorithms (X25519, ECDH P-256, RSA and
  `ffdhe` at 3072 and 2048 bits) measured alongside the three KEMs, to show the
  cost of migrating
- [`bench/algorithms.md`](../bench/algorithms.md) — every parameter set
  the benchmarks measure, with what each name means, sizes and security
  levels

## Implementations

- [mlkem-native](implementations/mlkem-native.md)
- [PQClean](implementations/pqclean.md)
- [liboqs](implementations/liboqs.md) — benchmarking/comparison harness, not a PQC implementation itself
- [ICICLE](implementations/icicle.md) — GPU (CUDA) ML-KEM, used through
  liboqs' `OQS_USE_ICICLE` build and through its own batched API

## Cross-Cutting Notes

- [Terminology](terminology.md) — glossary (skeleton; most entries are
  still empty).
- [Testing and benchmarking methodology](testing-and-benchmarking.md) —
  how the three submodules verify and measure themselves, side by side.
- [Benchmark environments](experimental-environments.md) — the hosts
  available for Phase 2 measurement and what each one can and cannot
  measure. Read before trusting any timing number.

Note templates: [algorithms](algorithms/notesformat.md),
[implementations](implementations/notesformat.md).

## Our Own Measurements

The API harness, `memory/` and `network/` cover the classical baselines as well as
the PQC KEMs; `simple/` measures liboqs only. All three share one driver,
[`bench/driver/`](../bench/driver/kem_bench.c).

- [`bench/computational/simple/`](../bench/computational/simple/README.md)
  — per-operation time from liboqs' own `speed_kem`, with its cycle
  column recorded as TSC ticks. That tool truncates the x86_64 counter
  to 32 bits and reports TSC ticks as CPU cycles; see
  [liboqs notes](implementations/liboqs.md#two-defects-in-the-x86_64-cycle-counter).
- [`bench/computational/api/`](../bench/computational/api/README.md) —
  per-operation time, full 64-bit TSC ticks and (where the kernel
  allows) user-space perf cycles. It calls the liboqs and OpenSSL APIs
  from one driver, so the PQC KEMs and the classical baselines are timed
  the same way. `--variant icicle` times liboqs' GPU ML-KEM instead.
- [`bench/computational/gpu/`](../bench/computational/gpu/README.md) —
  batched ML-KEM on the GPU through ICICLE, from 1 to 65,536 operations
  per call, against one CPU thread. GPU output is checked against liboqs
  on the CPU first.
- [`bench/memory/`](../bench/memory/README.md) — stack depth and heap
  use of single calls (first call and steady state), measured
  in-process, plus object sizes and liboqs code size.
- [`bench/network/`](../bench/network/README.md) — bytes, packets and
  time to shared secret of one key exchange over TCP, between two network
  namespaces at MTU 1500, optionally impaired with `netem`.

## Current Focus

The current focus is understanding implementation structure and testing
methodology for each of the implementations listed above.

## Initial Research Questions

- How is each repository organized?
- How are tests invoked?
- What properties do individual tests actually verify?
- Are NIST known-answer tests or other test vectors used?
- How are parameter sets selected?
- Where does randomness enter each implementation?
- Which SHA-3/SHAKE/hash primitives are used?
- How are reference and optimized implementations separated?
- What are the keygen / encaps / decaps call paths?
