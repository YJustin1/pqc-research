# mlkem-native

## Overview

## Upstream Repository

https://github.com/pq-code-package/mlkem-native

## Repository Structure

## Build System

## Tests

### Running the Tests

Everything goes through `make` or the `./scripts/tests` wrapper (a large
argparse front-end over the Makefile).

```sh
make test              # native backend
make OPT=0 test        # C-only backend
./scripts/tests all    # func, kat, acvp, wycheproof, unit, examples, alloc,
                       # rng_fail, abicheck (stack is off by default)
nmake /f .\Makefile.Microsoft_nmake quickcheck   # MSVC, C backend only
```

`Makefile:46-50` defines `build: func kat acvp wycheproof` and
`test: run_kat run_func run_acvp run_wycheproof run_unit run_alloc
run_rng_fail run_abicheck`.

Subcommands of `./scripts/tests` (`scripts/tests:1847-1876`): `all`,
`examples`, `acvp`, `wycheproof`, `bench`, `cbmc`, `hol_light`, `func`,
`kat`, `unit`, `stack`, `size`, `alloc`, `rng_fail`, `abicheck`.

`OPT`, `AUTO`, `CROSS_PREFIX` and `CYCLES` are cached in
`test/build/config.mk` (`test/mk/config.mk:82-124`); changing one forces a
rebuild.

### Test Files

| Binary | Source | Purpose |
| --- | --- | --- |
| `test_mlkem{512,768,1024}` | `test/src/test_mlkem.c` | round-trip, unaligned-buffer, invalid-pk, fixed-seed vectors |
| `gen_KAT{512,…}` | `test/src/gen_KAT.c` | emits hex KAT stream for hashing |
| `test_unit{…}` | `test/src/test_unit.c` | native backend vs `_c` reference, per kernel |
| `acvp_mlkem{…}` | `test/acvp/acvp_mlkem.c` | CLI harness driven by `acvp_client.py` |
| `wycheproof_mlkem{…}` | `test/wycheproof/wycheproof_mlkem.c` | Wycheproof harness |
| `test_stack{…}` | `test/src/test_stack.c` | stack measurement driver (`-fstack-usage`) |
| `test_alloc{…}` | `test/src/test_alloc.c` | bump-allocator: leaks, LIFO order, high-watermark, OOM propagation |
| `test_rng_fail{…}` | `test/src/test_rng_fail.c` | injects `randombytes` failure at every index |
| `abicheck` | `test/abicheck/` | callee-saved register preservation in asm kernels |

### What Is Actually Tested?

**KAT is hashed, not NIST `.rsp`.** No NIST KAT files are vendored.
`gen_KAT` derives all inputs deterministically from a fixed 64-byte seed
via SHAKE-256 and prints hex; the *entire stdout* is SHA-256'd and
compared against `kat-sha256` in `META.yml`:

```sh
test/build/mlkem512/bin/gen_KAT512 | python3 META.py --scheme 512
```

`NTESTS_KAT` is 100 (`test/src/gen_KAT.c:29-32`). Windows sets
`_O_BINARY` on stdout so CRLF cannot change the hash
(`gen_KAT.c:67-70`).

**ACVP vectors are downloaded, not vendored.** `test/acvp/acvp_client.py`
fetches from `usnistgov/ACVP-Server` at a pinned tag (default
`v1.1.0.43`), caching under `test/acvp/.acvp-data/`. CI sweeps three
versions (`.github/workflows/base.yml:72`). The client calls the harness
with `--info` first and filters prompt+expected cases uniformly so
reduced-API builds still compare byte-identically.

**Wycheproof** is pinned by commit (`wycheproof_client.py`).
`KNOWN_FIELDS` (`wycheproof_client.py:50-66`) enumerates every JSON field
each handler understands and **fails loudly on an unrecognised key**, so
upstream schema additions cannot be silently ignored.

**Unit tests are differential**: every native kernel is compared against
its `_c` reference (`mlk_poly_ntt_c`, `mlk_keccakf1600_permute_c`,
`mlk_rej_uniform_c`, …), built with `-DMLK_STATIC_TESTABLE=`
(`test/mk/components.mk:92-94`). `NUM_RANDOM_TESTS` = 8000.

**ABI checking** (`test/abicheck/README.md`) verifies each assembly
kernel preserves callee-saved registers for AAPCS64, SysV x86_64, ELFv2
ppc64le and Armv8.1-M/MVE. `abicheck.c:31-40` first runs a *meta-test*:
`selftest_<arch>.S` deliberately clobbers one callee-saved register each,
and the run aborts if the selftest does not fire — so a silently broken
checker cannot produce false passes. Requires `OPT=1`.

**Constant-time testing** is valgrind/ctgrind-style poisoning, not a
separate binary: `mlkem/src/sys.h:238-253` maps
`MLK_CT_TESTING_SECRET`/`_DECLASSIFY` onto
`VALGRIND_MAKE_MEM_UNDEFINED`/`_DEFINED` under
`MLK_CONFIG_CT_TESTING_ENABLED`. CI uses a **patched Valgrind from the
KyberSlash paper** with `--variable-latency-errors=yes`, which also flags
variable-latency instructions (divisions):

```sh
MK_COMPILER_SUPPORTS_SHA3=0 tests func \
  --exec-wrapper="valgrind --error-exitcode=1 --variable-latency-errors=yes" \
  --cflags="-DMLK_CONFIG_CT_TESTING_ENABLED -DNTESTS_FUNC=50 -Oz -DMLK_CONFIG_KEYGEN_PCT"
```

Run over 8 nix compiler shells × 8 optimisation levels; AArch64 SHA3 is
disabled because valgrind cannot emulate it.

**Formal verification — two systems.**

- *CBMC*: 202 proof directories under `proofs/cbmc/`, one per proved
  function. Specs live **in the production C sources** as
  `__contract__(requires/ensures/assigns)` and `__loop__(invariant(...))`;
  harnesses are boilerplate. Driven by `run-cbmc-proofs.py` (litani) over
  a data-model × solver matrix (`LP64`/`ILP32`; z3, bitwuzla,
  cvc5). An `unknown` solver answer is reported as `Inconclusive` and
  **fails** the run. CI tracks per-proof solver runtime against a
  `gh-pages` baseline with a 1.5× regression threshold.
- *HOL Light / s2n-bignum*: `proofs/hol_light/` proves the **assembly**
  — 15 AArch64 proofs (NTT, INTT, tomont, mulcache, reduce, basemul
  k2/k3/k4, tobytes, rej_uniform, 5 Keccak variants) and 21 x86_64/AVX2
  proofs.

`SOUNDNESS.md` is a 36 KB structured gap analysis: Gap A (specs vs
requirements, including "the bridge between CBMC and HOL Light"), Gap B
(model vs system — ISA fidelity, object-code reassembly, C-semantics
fidelity), Gap C (proof-infrastructure soundness — HOL Light kernel,
OCaml runtime, CBMC/SMT TCB). Worth reading before citing any of these
proofs as a guarantee.

**Sanitizers**: ASan + UBSan with `-fno-sanitize-recover=all` on nearly
every config variation; `scan-build` and `clang-tidy` at `-std=c90`.
No MSan, and **no fuzzing**.

**Portability.** `scripts/tests --platform` carries a profile table
(`scripts/tests:62-133`) mapping names to cross-prefix + cflags + QEMU
command: `linux/x86_64`, `linux/x86_64-no-avx2` (QEMU Snowridge),
`linux/aarch64`, `linux/aarch64_be`, `linux/ppc64le-power{7,8}`,
`linux/riscv64-rvv{128,256,512,1024}`, `linux/riscv32`,
`baremetal/aarch64-virt`, `baremetal/avr`, `zephyr`. Also: AVR
ATmega128RFR2 under simavr, Zephyr on five Cortex-M boards, native
POWER10 and RISC-V runners, MSVC and 11 MinGW versions, and a compiler
sweep of gcc 4.8–16 × clang 6–22 × zig 0.10–0.16 × C90/99/11/17/23.

**Other checks**: static stack usage from GCC `.su` files plus runtime
peak via `valgrind --tool=massif`; code size; namespace checking;
~30 config variations (PCT enabled and deliberately broken, custom
heap/zeroize/randombytes/memcpy, native-capability on/off, reduced APIs);
integration tests against liboqs, AWS-LC and Pavona.

## Benchmarking

Two harnesses per parameter set, both linking `test/hal/hal.c`:
`test/bench/bench_mlkem.c` (top-level) and
`test/bench/bench_components_mlkem.c` (~40 low-level components).

```sh
sudo make run_bench CYCLES=PERF
./scripts/tests bench -c PMU              # -c/--cycles is REQUIRED
./scripts/tests bench -c PERF -r
./scripts/tests bench --components -c NO
```

`CYCLES` is mandatory — `Makefile:183-185` errors with *"CYCLES
undefined. Benchmarking requires setting one of NO PMU PERF MAC"*.

**Cycle counting** (`test/hal/hal.c`):

| Mode | Backend |
| --- | --- |
| Zephyr | `k_cycle_get_64()` |
| `PMU` x86_64 | inline `rdtsc` |
| `PMU` AArch64 | `pmccntr_el0` MSR — **needs a kernel module** (mupq/pqax) |
| `PMU` Armv8-M | Cortex-M33 DWT `CYCCNT`; M55 `ARM_PMU_Get_CCNTR()` |
| `PMU` RISC-V | `rdcycle` |
| `PERF` | `perf_event_open(PERF_COUNT_HW_CPU_CYCLES)`, kernel/hv excluded |
| `MAC` | Apple private `kperf` via `dlopen`, event `CORE_ACTIVE_CYCLE` |
| `NO` | returns 0 — build/run smoke test only |

**Measured operations** are the *derandomized* entry points
(`mlk_kem_keypair_derand`, `mlk_kem_enc_derand`, `mlk_kem_dec`), so RNG
cost is excluded; each outer iteration re-randomizes coins and asserts
`memcmp(key_a, key_b) == 0`.

**Statistic — median.** `NWARMUP 50 / NITERATIONS 300 / NTESTS 500`
(`bench_mlkem.c:18-26`): per outer test, 50 unmeasured warmup calls, then
*one* counter read around 300 timed calls (amortizing counter-read
overhead), then `qsort` and report `cyc[NTESTS>>1] / NITERATIONS`. An
11-point percentile table (1,10,…,90,99) is also printed. Components use
NTESTS 20 and also report the median.

The component harness uses `BENCH_NATIVE_OK`
(`bench_components_mlkem.c:71-72`), which asserts the call did not
silently fall back: `CHECK((call) != MLK_NATIVE_FUNC_FALLBACK)`.

**Published results**: `./scripts/tests bench --output=output.json` emits
`[{"name": "ML-KEM-512 keypair", "unit": "cycles", "value": N}, …]` for
`benchmark-action/github-action-benchmark` (`customSmallerIsBetter`,
alert threshold 103%), pushed to
<https://pq-code-package.github.io/mlkem-native/dev/bench/>. Triggered by
`workflow_dispatch`, push to `main`, or a PR labelled `benchmark`.

**Hardware matrix** (`.github/workflows/bench.yml`): self-hosted rpi4
(A72, PMU), rpi5 (A76, PERF), Snapdragon 888 A55, Banana Pi F3 RISC-V,
M1 Mac mini (MAC), POWER10, Cortex-M55 Nucleo board; plus EC2 Graviton
2/3/4/5 (PERF) and AMD/Intel x86 (PMU via rdtsc).

Note `--mac-taskpolicy {utility,background,maintenance}` is shorthand for
`--exec-wrapper 'taskpolicy -c <clamp>'`; `background` pins to E-cores.
`--components` forces `output = False`, so component numbers are printed
but never tracked in JSON.

## Supported Algorithms / Parameter Sets

## Important Source Files

## Key Generation Call Path

## Encapsulation Call Path

## Decapsulation Call Path

## Randomness

## Hash / XOF Primitives

## Polynomial / Data Representation

## Optimized vs Reference Implementations

## Interesting Observations

## Open Questions

- What exactly does the CBMC↔HOL Light bridge leave unproven? `SOUNDNESS.md`
  names it as Gap A but we have not worked through the argument.
- The `MAC` cycle counter uses Apple's private `kperf` frameworks. Does it
  still work on current macOS, and does `--mac-taskpolicy background`
  (E-core pinning) give stable enough numbers to be worth using?
- `--components` refuses to write JSON. Is component-level tracking
  intentionally unpublished, or just unimplemented?
- For Phase 2: can we reuse `scripts/tests bench` directly for our own
  ML-KEM measurements, or do we need liboqs (or our own harness) for
  comparability with Classic McEliece and NTRU, which mlkem-native does
  not implement? Relevant: liboqs' ML-KEM is itself vendored mlkem-native
  (`src/kem/ml_kem/mlkem-native_*`), so the difference is liboqs' API,
  SHA-3 layer and RNG rather than the ML-KEM code (see
  [liboqs notes](liboqs.md#optimized-vs-reference-implementations)).
