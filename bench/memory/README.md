# Memory benchmarks

`run_massif.py` measures the memory footprint of ML-KEM, Classic McEliece
and NTRU in liboqs. It builds liboqs, runs liboqs' own test program under
valgrind's massif and collects the numbers. None of the code being
measured is ours.

```sh
python3 bench/memory/run_massif.py                     # all 19 parameter sets, both builds
python3 bench/memory/run_massif.py --algs ML-KEM-768   # one parameter set
```

Requirements: `valgrind`, `cmake` and a C compiler. Implementation measures
bytes and rather than time, so machine load doesn't matter and a shared host
is fine. Results go to `bench/memory/results/<UTC stamp>-<host>/`:

| File | Contents |
| --- | --- |
| `summary.md` | all tables |
| `sizes.csv` | key, ciphertext and shared-secret sizes |
| `memory.csv` | peak stack and heap per (build, parameter set, operation) |
| `codesize.csv` | text / data / bss per (build, parameter set) |
| `env.json` | host, CPU, compiler, valgrind version, liboqs revision, build options |

Every figure is reported for two builds, both configured with
`OQS_DIST_BUILD=OFF` and `OQS_USE_OPENSSL=OFF` so that each liboqs entry
point calls exactly one implementation:

| Build | `OQS_OPT_TARGET` | Code that runs |
| --- | --- | --- |
| `native` | `auto` (`-march=native`) | optimised AVX2 implementations on x86_64 |
| `generic` | `generic` (`-march=x86-64`) | portable C implementations |

## Stack and heap

liboqs ships `tests/test_kem_mem.c`, which does one KEM operation per
process. `test_kem_mem <alg> 0` generates a keypair, `1` encapsulates, and
`2` decapsulates and checks that the shared secrets match. Keys and
ciphertexts pass between steps through files in `./tmp`, so each process
holds exactly one operation. We run each step under
`valgrind --tool=massif --stacks=yes --peak-inaccuracy=0.0` and report the
largest `mem_stacks_B` and `mem_heap_B` across massif's snapshots. Setting
the peak inaccuracy to zero gets the exact peak instead of one within 1%.
Heap counts requested bytes, not allocator overhead. If decapsulation
doesn't print `shared secrets are equal`, the run aborts.

Massif sees the whole process, so the numbers cover `test_kem_mem` as well
as liboqs. The heap figure includes the key and ciphertext buffers the
test program allocates, the `OQS_KEM` descriptor, and libc's stdio and
`FILE` buffers. For Classic McEliece the public-key buffer alone is 261 KB
to 1.36 MB and dominates everything else. The stack figure includes
`main()`, C runtime start-up and the test program's own `printf` and file
I/O, which can be the deepest point when the operation itself needs
little stack, as McEliece encapsulation does. Read the heap as roughly
what an application holding one keypair and one ciphertext would need,
and the stack as an upper bound on what the operation uses.

Small figures are noisy. libc's 4 KB stdio buffers are sometimes live at
the heap peak and sometimes not, and we've seen the same binary shift by a
few KB between invocations. Where liboqs sets the peak, as in McEliece key
generation, the numbers don't move. Each operation runs `--reps` times
(default 3), and `memory.csv` reports the maximum with the minimum in the
`*_min` columns. Treat anything under about 16 KB as ±4 KB. That covers
every ML-KEM and NTRU heap figure and McEliece encapsulation's stack.

## Sizes and code size

Key, ciphertext and shared-secret lengths come from liboqs'
`tests/dump_alg_info`. They're fixed by each scheme's specification.

Code size is `size` summed over the object files of the parameter set's
own implementation targets, `src/kem/<family>/CMakeFiles/<id>_*.dir/`.
`text` includes `.rodata`. Code shared between algorithms, meaning SHA-3,
the RNG and `src/common/`, isn't counted. Every function in the
parameter set's own objects is, whether or not the three KEM operations
ever reach it.
