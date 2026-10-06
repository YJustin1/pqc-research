# Measurement criteria

Target criteria to be measured for each algorithm and, 
when applicable, per operation: keygen, encaps and decaps. 

Algorithms: every computational, memory and network measurement covers
the same 25 parameter sets, listed with their names, sizes and security
levels in [`algorithms.md`](algorithms.md). These are 19 PQC KEMs from
liboqs and 6 classical baselines from OpenSSL. The mapping of
Diffie-Hellman onto keygen/encaps/decaps is in
[`docs/algorithms/classical-baselines.md`](../docs/algorithms/classical-baselines.md). Every status below covers the PQC KEMs only unless
it says otherwise.

## Computational (`computational/`)

| Metric | Unit | How | Status |
| --- | --- | --- | --- |
| Time per operation | µs/op | wall clock around each call: `simple/` (liboqs `speed_kem`), and `api/` (liboqs and OpenSSL) | preliminary numbers from `simple/` on grape-nuts; `api/` implemented, no clean run yet |
| Cycles per operation | cycles/op | `api/`: full 64-bit TSC ticks; retired user-space core cycles from `perf_event_open` where permitted | implemented in `api/`; perf is refused on the UTCS hosts; `simple/` reports truncated TSC ticks only |
| Instructions per operation | instructions/op | retired instructions from `perf_event_open` | not implemented |

`simple/` wraps liboqs' `speed_kem`, so it can time only the PQC
algorithms. Note: its cycle column is TSC ticks rather than core cycles.
Its figures for the liboqs algorithms should roughly match the API harness's, 
since we are using the same implementation and only modifying the harness

The API harness (`api/`) calls the liboqs and OpenSSL APIs directly.
Every algorithm, PQC and classical, is timed with the same loop and
counters, so the differences in the results come
from the algorithms and libraries, not from two different benchmark
tools.

## Memory (`memory/`)

| Metric | Unit | How | Status |
| --- | --- | --- | --- |
| Peak stack | bytes/op | valgrind massif on liboqs' `test_kem_mem` | measured on grape-nuts, 2026-09-29 |
| Peak heap | bytes/op | same run | measured on grape-nuts, 2026-09-29 |
| Code size | bytes of text, data and bss | `size` over each parameter set's object files | measured on grape-nuts, 2026-09-29 |

All three come in a native (AVX2) and a generic (portable C) build.
Stack and heap are measured using the whole program, so anything under about 16 KB
carries about ±4 KB of noise. 

The classical baselines are not measured. `test_kem_mem` is a liboqs
program and cannot run OpenSSL algorithms. The current measuring method
depends on liboqs' libraries and will need to be rewritten for the new harness. 

## Network (`network/`)

| Metric | Unit | How | Status |
| --- | --- | --- | --- |
| Public-key size | bytes | liboqs' `dump_alg_info`; OpenSSL's API for the classical baselines | PQC recorded in `memory/results/*/sizes.csv`; classical taken from the specifications only |
| Ciphertext size | bytes | same | recorded in `memory/results/*/sizes.csv` |
| Secret-key and shared-secret size | bytes | same | recorded in `memory/results/*/sizes.csv` |
| Handshake bytes | bytes per key exchange | public key plus ciphertext on the wire, including protocol framing | not measured |
| Packets per handshake | packets at a given MTU | from handshake bytes | not measured |

The sizes were checked once against each specification's formulas and,
for ML-KEM-512, with valgrind memcheck. Handshake bytes add framing 
on top of the raw sizes, so they depend on the protocol we pick. 
Nothing in `network/` exists yet.
