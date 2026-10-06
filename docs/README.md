# Research Knowledge Index

This is the main index for accumulated research notes.

## Algorithms

- [ML-KEM](algorithms/ml-kem.md)
- [Classic McEliece](algorithms/classic-mceliece.md)
- [NTRU](algorithms/ntru.md) — unstandardised; studied as the lattice
  alternative to ML-KEM
- [Classical baselines](algorithms/classical-baselines.md) — the
  pre-quantum key-establishment algorithms (X25519, ECDH P-256, RSA-3072
  as a KEM) measured alongside the three KEMs, to show the cost of
  migrating

## Implementations

- [mlkem-native](implementations/mlkem-native.md)
- [PQClean](implementations/pqclean.md)
- [liboqs](implementations/liboqs.md) — benchmarking/comparison harness, not a PQC implementation itself

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

So far these measure only liboqs' builds of ML-KEM, Classic McEliece
and NTRU. The classical baselines are not measured yet.

- [`bench/computational/simple/`](../bench/computational/simple/README.md)
  — per-operation time from liboqs' own `speed_kem`, with its cycle
  column recorded as TSC ticks. That tool truncates the x86_64 counter
  to 32 bits and reports TSC ticks as CPU cycles; see
  [liboqs notes](implementations/liboqs.md#two-defects-in-the-x86_64-cycle-counter).
  A replacement harness is planned. It will call the liboqs and OpenSSL
  APIs directly, so the PQC and classical algorithms are timed the same
  way.
- [`bench/memory/`](../bench/memory/README.md) — object sizes, stack
  depth, heap use and code size per parameter set and operation.

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
