# Testing and Benchmarking Methodology

A side-by-side comparison of how the three submodules in `implementations/`
verify and measure themselves, limited to what applies to the three KEMs
this project studies: ML-KEM, Classic McEliece and NTRU. Per-repository
detail lives in `docs/implementations/`.

Submodule commits this was written against (2026-09-15):

| Repo | Commit | Date |
| --- | --- | --- |
| liboqs | `adbeba1ef` | 2026-09-11 |
| mlkem-native | `438f0da1` | 2026-09-10 |
| pqclean | `0586a824` | 2026-08-04 |

## Testing at a glance

| | mlkem-native | PQClean | liboqs |
| --- | --- | --- | --- |
| Our algorithms covered | ML-KEM | ML-KEM, Classic McEliece | ML-KEM, Classic McEliece, NTRU |
| Driver | `make` + `./scripts/tests` | pytest over (scheme × impl) | pytest → C binaries |
| KAT style | hashed stdout vs `META.yml` | hashed stdout vs `META.yml` (first case only) | hashed stdout vs `kats.json` |
| ACVP | downloaded, pinned tag | — | downloaded, pinned tag |
| Wycheproof | yes, pinned commit | — | yes, pinned commit |
| Constant-time | patched valgrind (variable-latency) | **none** for KEMs | valgrind + suppression lists |
| Sanitizers | ASan, UBSan | ASan, UBSan | ASan/MSan/UBSan, scan-build |
| Formal verification | CBMC (202) + HOL Light | — | — |
| Fuzzing | — | — | libFuzzer, but no KEM target covered |
| Benchmarking | cycles, median | **out of scope** | cycles or ns, mean |

PQClean has no NTRU implementation (`crypto_kem/` holds only HQC,
Classic McEliece and ML-KEM), so **liboqs is the only submodule covering
all three algorithms**.

## "KAT" means a hash, not a vector comparison

All three repos use the word "KAT", and for KEMs none of them compares
vendored vectors.

**Hashed self-generated output** — mlkem-native, PQClean and liboqs all
generate KAT text deterministically, SHA-256 the whole stdout, and compare
that digest to a value in `META.yml` (or `kats.json`). No vectors are
stored. This catches *any* change in output, cheaply, but tells you
nothing about *which* byte moved when it fails, and a wrong-but-consistent
implementation would still need the original digest to have been
generated correctly once.

All three independently document the same derivation from a NIST
submission file:
```sh
cat PQCkemKAT_whatever.rsp | head -n 8 | tail -n 6 | sha256sum
```

PQClean's KEM check (`nistkat-sha256`) covers only the **first** NIST test
case; its other deterministic-vector mechanism, `testvectors-sha256`, is
used for signatures only.

Actual field-by-field comparison against external vectors comes from
**ACVP** (ML-KEM, FIPS 203) and **Wycheproof**, in mlkem-native and
liboqs only. Both are **downloaded at test time**, cached under a
gitignored directory and pinned by tag or commit. That means a test run
needs network access on first use, and that the pinned version is itself
a thing to track — liboqs and mlkem-native both sweep multiple ACVP
versions in CI. Both vector sets cover ML-KEM only (liboqs'
`test_wycheproof_vectors.py` maps just the three ML-KEM parameter sets),
so for Classic McEliece and NTRU the hashed KAT is the only known-answer
check.

## Constant-time testing: what it does and does not prove

Every repo that does CT testing uses the same underlying trick (ctgrind,
credited to Adam Langley, via SUPERCOP/TIMECOP): mark secret bytes as
*undefined* with `VALGRIND_MAKE_MEM_UNDEFINED`, and let memcheck report
any branch or memory access that depends on them. Public values are
explicitly declassified.

The differences matter:

- **mlkem-native** uses a *patched* Valgrind from the KyberSlash paper
  with `--variable-latency-errors=yes`, which also flags variable-latency
  instructions such as division. Run across 8 compiler shells × 8
  optimisation levels. This is the strongest CT setup of the three.
- **liboqs** runs stock valgrind but maintains **suppression lists split
  into `passes/` and `issues/`** — treated identically at runtime, the
  split being an auditor's label. `kem/issues/` holds **all ten Classic
  McEliece parameter sets**, alongside other KEMs outside our scope.
  `kem/passes/` holds `bike`, `kyber` and `sntrup`; no suppression file
  is named for ML-KEM or NTRU. A green liboqs CT run therefore means
  *known deviations are suppressed*, not *the code is constant time*.
- **PQClean** does no CT testing for KEMs. Its only valgrind poisoning is
  in the signature test driver (`test/crypto_sign/functest.c`);
  `test/crypto_kem/` contains none. Its README correspondingly leaves
  *"No branching on secret data"* and *"No access to secret memory
  locations"* as unchecked boxes; `test_boolean.py` (no comparisons in
  assignments or call arguments) is the static stand-in.

## Formal verification

Only mlkem-native does any, so none of the Classic McEliece or NTRU code
in scope is formally verified.

- **mlkem-native** carries CBMC contracts **inline in the production C
  sources** (`__contract__(requires/ensures/assigns)`,
  `__loop__(invariant(...))`), with one boilerplate harness directory per
  proved function — 202 in total. Proofs run over a data-model × solver
  matrix, and an `unknown` SMT answer is reported as `Inconclusive` and
  **fails** the run. On top of that, **HOL Light / s2n-bignum proves the
  hand-written assembly** (15 AArch64 and 21 x86_64/AVX2 kernels).
- **PQClean** has none, but describes its implementations as *"suitable
  targets for formal verification"*.
- **liboqs** has none.

mlkem-native's `SOUNDNESS.md` is worth reading in full before citing any
of this: it is a 36 KB structured gap analysis covering specification
faithfulness, the bridge between CBMC and HOL Light, ISA fidelity, and the
trusted computing base of the proof tools themselves.

## Portability testing

mlkem-native is by far the most aggressive:

- QEMU profiles for x86_64 (with and without AVX2), aarch64, **aarch64
  big-endian**, ppc64le POWER7/8, riscv64 at VLEN 128/256/512/1024, and
  riscv32.
- Bare metal: AVR ATmega128RFR2 under simavr, AArch64-virt without an MMU.
- Zephyr on five Cortex-M boards plus a physical Nucleo board.
- Compiler sweep of gcc 4.8–16 × clang 6–22 × zig 0.10–0.16 ×
  C90/99/11/17/23.

PQClean's notable contribution is **32-bit big-endian PowerPC** under
qemu-user, which is what makes its "consistent test vectors across
endianness and word size" claim meaningful. liboqs runs one job under
Intel SDE for AVX-512 and uses QEMU with a minimum microarchitecture
(`-cpu Westmere` / `cortex-a53`) to verify runtime CPU feature dispatch.

## Benchmarking

### Who benchmarks what

- **PQClean deliberately does not.** `README.md:36` lists *"including
  benchmarking of implementations"* under what PQClean is **not** aiming
  for; it instead aims to be easy to drop into SUPERCOP and pqm4. There
  is no timing code in the tree.
- **mlkem-native and liboqs count cycles**, with different
  statistics and different platform support. mlkem-native benchmarks
  ML-KEM only, so liboqs is the only upstream benchmark for Classic
  McEliece and NTRU.

### Cycle counting is not portable, and the fallbacks are quiet

Both harnesses degrade silently in ways that matter:

| Platform | mlkem-native (`test/hal/hal.c`) | liboqs (`ds_benchmark.h`) |
| --- | --- | --- |
| x86_64 | `rdtsc` | `rdtsc` |
| AArch64 | `pmccntr_el0` — **needs a kernel module** | PMU only with `OQS_SPEED_USE_ARM_PMU` |
| Linux generic | `perf_event_open` | — |
| macOS | private `kperf` frameworks | — |
| Fallback | `NO` mode returns **0** | `clock_gettime` in **nanoseconds** |

liboqs's fallback is *a* trap: the column header changes from
`CPU cycles: mean` to `High-prec time (ns): mean` and nothing else
signals it. Always check the header before recording a number.

**But on x86_64 the worse problem gives no signal at all.** There the
`rdtsc` path is taken and the header keeps saying `CPU cycles`, yet the
number is neither cycles nor nanoseconds:

1. It is **TSC ticks**, which advance at a fixed nominal rate. Retired
   core cycles were measured at ~1.2x TSC ticks on our Ryzen 5600X under
   boost, so the figure understates cycles by roughly 20%.
2. It is **truncated to 32 bits** by an `"=A"` inline-asm constraint,
   wrapping every ~1.16 s at 3.70 GHz, with only one wrap corrected.

Neither is visible from the output. Details and the source references are
in [liboqs notes](implementations/liboqs.md#two-defects-in-the-x86_64-cycle-counter);
our replacement harness, over the liboqs and OpenSSL APIs, is
[`bench/computational/api/`](../bench/computational/api/README.md).

Two further platform lessons from building an earlier, since-deleted
harness, both of which
apply to *any* cycle measurement, not just liboqs':

- `perf_event_open` at the common default `perf_event_paranoid=2` counts
  **user-space cycles only**. Any operation that spends time in syscalls
  — notably anything calling `getrandom()` — has its perf-to-TSC ratio
  deflated accordingly, so that ratio is not a frequency ratio.
- Under a hypervisor (WSL2 here) the TSC is host-based and continues
  advancing while the vCPU is descheduled, whereas perf only counts
  retired cycles. Interference is therefore **one-sided**: it can only
  depress a measured cycles-per-tick ratio, never inflate it, which
  makes the maximum over several windows a better estimator than the
  mean.

mlkem-native makes `CYCLES` a required variable rather than defaulting
— `make run_bench` errors with *"CYCLES undefined. Benchmarking requires
setting one of NO PMU PERF MAC"* — which is the safer design.

### Median vs mean, and why they differ

| | mlkem-native | liboqs |
| --- | --- | --- |
| Warmup | 50 | — |
| Inner iterations | 300 | duration-based |
| Outer samples | 500 | — |
| Reported | **median** | mean + population stdev |
| Duration | fixed iteration counts | 3 s per operation |

mlkem-native reads the cycle counter *once around 300 calls*, amortising
counter-read overhead, then takes the median of 500 such samples.

A median is appropriate when per-operation cost is tightly clustered, as
it was for ML-KEM and NTRU in our runs (CV 4–8%). It is not appropriate
for every algorithm: Classic
McEliece key generation restarts whenever Gaussian elimination fails, so
its cost is heavy-tailed, and a median alone would understate its real
cost. The right summary statistic depends on the algorithm's own
distribution — it is not a stylistic choice.

mlkem-native also prints an 11-point percentile table (1, 10, …, 90, 99),
which is more informative than either single number and worth reproducing
in our own Phase 2 work.

### Published results and regression tracking

Both cycle-counting repos push to GitHub Pages dashboards via
`benchmark-action/github-action-benchmark`:

- <https://pq-code-package.github.io/mlkem-native/dev/bench/>
- liboqs KEM dashboard, refreshed weekly

Regression alert thresholds are 103% (mlkem-native) and 105% (liboqs).
liboqs runs benchmark jobs with `max-parallel: 1` specifically to avoid
noise. mlkem-native additionally benchmarks on a self-hosted hardware
fleet — Raspberry Pi 4/5, Snapdragon 888, Banana Pi RISC-V, M1 Mac mini,
POWER10, a Cortex-M55 board — plus EC2 Graviton 2/3/4/5 and AMD/Intel
x86.

Component-level benchmarking (NTT, invNTT, Keccak, rejection sampling,
compression) exists in mlkem-native but is **printed only, never tracked
in JSON**.

## Implications for Phase 2

Recorded here so the performance-evaluation phase does not have to
rediscover them:

1. **Cross-algorithm comparison needs one harness.** mlkem-native
   benchmarks only ML-KEM, and PQClean benchmarks nothing and lacks NTRU.
   liboqs is the only submodule that can put all three algorithms on the
   same axis — at the cost of measuring *its* vendored implementations
   rather than the native ones.
2. **Verify the cycle source before trusting any figure**, especially on
   AArch64 where both harnesses need privileged access or a kernel module
   and both fall back silently.
3. **Pick the statistic per algorithm.** Median is fine for ML-KEM and
   NTRU, whose operations measured at a CV of 4–8%. Classic McEliece
   **key generation** is the exception: its rejection loop gave a
   within-run CV of ~27%, so a mean ± stdev actively misleads there and
   the median with p95 should be quoted instead.
4. **Record the build configuration alongside results.** liboqs bakes
   compile options and git commit into its output header for this reason;
   `OQS_DIST_BUILD=ON` (runtime dispatch) measures something different
   from `-march=native`.
5. **A green CT run is not a constant-time guarantee** — and for Classic
   McEliece in liboqs it is explicitly an `issues/` suppression. See the
   suppression-list discussion above.
6. **The measuring machine must be idle, and this dominates.** The same
   ML-KEM-512 keygen measured 6.13 µs idle and 8.10 µs while the host was
   in interactive use — a 32% inflation no amount of averaging removes,
   because the work genuinely took longer. Pinning to a core (`--cpu`)
   helps only on an already-quiet machine; under load it made between-run
   CV worse, not better. Cycle counts survive this far better than
   wall-clock times do.

## Open Questions

- Which harness do we adopt for Phase 2 — liboqs for breadth, mlkem-native
  for ML-KEM fidelity, or our own thin layer over both?
- ~~Can we get a real cycle counter on the target hardware here?~~
  **Answered 2026-09-20**: yes. `perf_event_open` works unprivileged on
  x86_64 under WSL2 and gives retired core cycles; no kernel module
  needed. Caveat: at `perf_event_paranoid=2` it counts user-space cycles
  only — see the cycle-counting section above.
- How much of the CI benchmark noise (shared cloud runners, frequency
  scaling) would our own measurements avoid, and does that change which
  published numbers are worth citing?
