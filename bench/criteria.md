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
| Peak stack | bytes/op | in-process: separate pattern-filled stack, scanned after the call (`run_memory.py`) | implemented for liboqs and OpenSSL; no full run yet. Previous method (massif on `test_kem_mem`, liboqs only): grape-nuts, 2026-09-29 |
| Peak heap | bytes/op | in-process: wrapped allocator, peak live bytes during the call; first call and steady state | same |
| Code size | bytes of text, data and bss | `size` over each liboqs parameter set's object files | liboqs only; not measured for OpenSSL, whose algorithms cannot be separated |

liboqs comes in a native (AVX2) and a generic (portable C) build;
OpenSSL has its one default build. For OpenSSL, the first call in a
process includes one-time setup (tens to ~200 KB of heap). Steady state
is the figure to compare across libraries. See
[`memory/README.md`](memory/README.md).

## Network (`network/`)

| Metric | Unit | How | Status |
| --- | --- | --- | --- |
| Public-key size | bytes | reported by the shared driver: `OQS_KEM` lengths for liboqs, actual output lengths for OpenSSL | PQC in `memory/results/20260929T081700Z-grape-nuts/sizes.csv`; all sets once `run_memory.py` runs |
| Ciphertext size | bytes | same | same |
| Secret-key and shared-secret size | bytes | same; secret key for liboqs only | same |
| Handshake bytes | bytes per key exchange | public key plus ciphertext on the wire, including protocol framing | not measured |
| Packets per handshake | packets at a given MTU | from handshake bytes | not measured |

The sizes were checked once against each specification's formulas and,
for ML-KEM-512, with valgrind memcheck. Handshake bytes add framing 
on top of the raw sizes, so they depend on the protocol we pick. 
Nothing in `network/` exists yet.
