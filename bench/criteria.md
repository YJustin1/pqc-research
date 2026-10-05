# Measurement criteria

Target criteria to be measured for each algorithm and, 
when applicable, per operation: keygen, encaps and decaps. 

## Computational (`computational/`)

| Metric | Unit | How | Status |
| --- | --- | --- | --- |
| Time per operation | µs/op | wall clock around each call, in `simple/` and `full/` | preliminary numbers from `simple/` on grape-nuts; no clean `full/` run yet |
| Cycles per operation | cycles/op | retired core cycles from `perf_event_open`, in `full/` | implemented; no clean run yet |
| Instructions per operation | instructions/op | retired instructions from `perf_event_open` | not implemented |

## Memory (`memory/`)

| Metric | Unit | How | Status |
| --- | --- | --- | --- |
| Peak stack | bytes/op | valgrind massif on liboqs' `test_kem_mem` | measured on grape-nuts, 2026-09-29 |
| Peak heap | bytes/op | same run | measured on grape-nuts, 2026-09-29 |
| Code size | bytes of text, data and bss | `size` over each parameter set's object files | measured on grape-nuts, 2026-09-29 |

All three come in a native (AVX2) and a generic (portable C) build.
Stack and heap are measured using the whole program, so anything under about 16 KB
carries about ±4 KB of noise. 

## Network (`network/`)

| Metric | Unit | How | Status |
| --- | --- | --- | --- |
| Public-key size | bytes | liboqs' `dump_alg_info` | recorded in `memory/results/*/sizes.csv` |
| Ciphertext size | bytes | same | recorded in `memory/results/*/sizes.csv` |
| Secret-key and shared-secret size | bytes | same | recorded in `memory/results/*/sizes.csv` |
| Handshake bytes | bytes per key exchange | public key plus ciphertext on the wire, including protocol framing | not measured |
| Packets per handshake | packets at a given MTU | from handshake bytes | not measured |

The sizes were checked once against each specification's formulas and,
for ML-KEM-512, with valgrind memcheck. Handshake bytes add framing 
on top of the raw sizes, so they depend on the protocol we pick. 
Nothing in `network/` exists yet.
