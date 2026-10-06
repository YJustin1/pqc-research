# Memory benchmarks

`run_memory.py` measures the stack and heap of single KEM calls, the
object sizes, and liboqs' code size, for every parameter set in
[`../algorithms.md`](../algorithms.md). The PQC KEMs go through the
liboqs API, and the classical baselines (plus ML-KEM a second time) go
through the OpenSSL API. Both are called from the driver shared with the
timing harness, [`../driver/kem_bench.c`](../driver/kem_bench.c). The
code being measured is upstream's; the figures still contain a small,
measured contribution from the harness, described under Stack.

```sh
python3 bench/memory/run_memory.py                          # everything
python3 bench/memory/run_memory.py --algs X25519 ML-KEM-768
python3 bench/memory/run_memory.py --massif                 # + valgrind cross-check
```

Requirements: `cmake`, `ninja`, `make`, `perl`, a C compiler and Python
3.12+; `valgrind` only for `--massif`. Results are byte counts, not
times, so machine load does not matter and a shared host is fine.
Results go to `bench/memory/results/<UTC stamp>-<host>/`:

| File | Contents |
| --- | --- |
| `summary.md` | all tables |
| `sizes.csv` | public key, ciphertext and shared-secret sizes, per (impl, set) |
| `memory.csv` | stack and heap, first call and steady state, and the subtracted stack overhead, per (build, impl, set, operation) |
| `codesize.csv` | liboqs text / data / bss per (build, set) |
| `massif.csv` | `--massif` only: the valgrind cross-check |
| `env.json` | host, CPU, compiler, library versions, liboqs revision, build options |

## Builds

liboqs is measured twice, both with `OQS_DIST_BUILD=OFF` and
`OQS_USE_OPENSSL=OFF`, so each entry point calls exactly one
implementation:

| Build | `OQS_OPT_TARGET` | Code that runs |
| --- | --- | --- |
| `native` | `auto` (`-march=native`) | optimised AVX2 implementations on x86_64 |
| `generic` | `generic` (`-march=x86-64`) | portable C implementations |

OpenSSL has one build (labelled `default`), the pinned 3.5.9 release
described in [`../computational/api/README.md`](../computational/api/README.md).
It contains both portable and assembly code paths and picks one at run
time from the CPU's features.

## Method

For each (build, set), `kem_bench prepare` generates a keypair and a
ciphertext, checks the round trip, and writes them to a temporary
directory. Then, for each operation, `kem_bench memory` runs in fresh
processes, in two builds of the driver: the plain build (also used for
timing) gives the stack figures, and the memory build, which tracks
allocations, gives the heap figures. The memory build's allocator
wrappers would otherwise add their own frames to the stack of any call
that allocates. It loads only the inputs that operation needs (a sender holds
the public key; a recipient holds the keypair and a ciphertext) and
measures three calls:

- **first**: the first call in the process. This includes any one-time
  setup the library does on first use.
- **steady**: the larger of the next two calls.

Decapsulation's secret is checked against the saved one. Each
(build, set, operation) runs in `--reps` separate processes (default 3);
`memory.csv` reports the maximum and keeps the minimum in `*_min`
columns.

**Heap.** The memory build links with `-Wl,--wrap=` for `malloc`,
`calloc`, `realloc`, `free`, `aligned_alloc`, `posix_memalign` and
`memalign`. liboqs and libcrypto are linked statically, so every
allocation they make reaches the wrappers, which track each live block's
requested size. The figure is the peak of live bytes during the call,
above the level when it started. Counted:

- requested sizes, not allocator overhead;
- anything the call returns that is still allocated when it ends. That
  matters for OpenSSL keygen, which returns a newly allocated key object.
  liboqs writes its outputs into buffers the caller provides, which are
  not counted.

Allocations glibc makes internally (its stdio buffers, for example) do
not pass through the wrappers and are not counted.

**Stack.** The call runs on a separate 64 MiB stack, filled with a byte
pattern and with an inaccessible guard page below it, so an overflow
crashes instead of giving a wrong answer. Afterwards, the deepest byte
that no longer holds the pattern marks how far the call reached. The two
steady calls use different patterns (`0xA5`, `0x5A`), so a call that
happens to write the pattern byte at its deepest point cannot hide it.
Stack that a function reserves but never writes is not counted.

The scan also sees the harness's own frames: the context-switch
trampoline and the call through the backend's function pointer. Each
process measures them by running an operation that does nothing, the
same way, and subtracts the result. It is reported as
`stack_overhead_bytes` and was 40 bytes for every measurement on the
workstation. Measured with the allocator-tracking build instead, the same
calls came out at most 8 bytes deeper in the cases checked.

## First call versus steady state

*Observed:* for liboqs the two are identical; it does no setup on first
use. For OpenSSL the first call is much larger: tens to about 200 KB of
heap, against hundreds of bytes to tens of KB in steady state.

*Interpretation:* OpenSSL creates some state on first use and keeps it
for the life of the process. Initialising its random-number generator
before the call removed most of the difference in an experiment. The rest
is consistent with the first lookup of the helper algorithms an
operation uses (HKDF and SHA-256 for DHKEM, SHA-3 for ML-KEM), but those
allocations have not been traced.

The two figures answer different questions:
- **steady** is the per-operation cost in a long-running process, such as
  a server doing many handshakes. It is the figure to compare across
  libraries.
- **first** is what a short-lived process doing one handshake pays.

Loading a key can itself trigger the setup. OpenSSL ML-KEM decapsulation,
whose keypair import already does it, shows no difference between first
and steady.

## Sizes and code size

Object sizes are what the driver reports for each (impl, set):
`OQS_KEM`'s lengths for liboqs, and the actual output lengths for
OpenSSL. RSA has no "encoded public key", so its public-key size is the
modulus size.

liboqs code size is `size` summed over the object files of the parameter
set's own implementation targets, `src/kem/<family>/CMakeFiles/<id>_*.dir/`
in each build. `text` includes `.rodata`. Code shared between algorithms
(SHA-3, the RNG and `src/common/`) is not counted. Every function in the
parameter set's own objects is, whether or not the three KEM operations
ever reach it.

OpenSSL code size is **not measured**. Programs select its algorithms by
name at run time, from a table of everything the library contains, so
the linker keeps them all and no per-algorithm code can be separated.

## Cross-check with valgrind massif

`--massif` also runs every liboqs native set under
`valgrind --tool=massif --stacks=yes --peak-inaccuracy=0.0`, twice per
operation:
- `kem_bench once`: load the inputs, run the operation once, and exit;
- `kem_bench baseline`: the same, minus the operation.

The massif heap figure is the difference of the two whole-process peaks,
and the stack figure is `once`'s whole-process peak.

*Observed (workstation, 2026-10-06, all 19 liboqs native sets):*
- **Heap.** It agreed with the in-process figure for every operation
  except Classic McEliece keygen (9 of the 10 sets in one run, all 10 in
  the next). There, massif reported 0 where in-process found 224 bytes:
  a larger transient during start-up set both processes' peaks.
- **Stack.** For 47 of the 57 operations, massif was 576–736 bytes
  higher. That is `main()`, start-up frames and the 40-byte harness
  overhead, which the in-process figure subtracts. For Classic McEliece
  encaps it was 2.4–5.0 KB higher. That operation's own stack is smaller
  than the loading code's, so massif reports the loading code's depth.

massif cannot measure OpenSSL this way. A process has a single peak, so
OpenSSL's first-use setup always dominates, and no warm-up call can
separate it out.

## Earlier results

`results/20260929T081700Z-grape-nuts/` was produced by the previous
method: valgrind massif on liboqs' own `tests/test_kem_mem`, whole
process, liboqs only. Its stack and heap include the test program's own
buffers, stdio and start-up. They are not directly comparable with
in-process figures.
