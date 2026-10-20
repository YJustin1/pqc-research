# Benchmark Environments

This document records the machines considered for the Phase 2
performance measurements, what each one can and cannot measure, and why
one was chosen. The measurement environment turned out to matter more
than any detail of the benchmark harness: on the same hardware, whether
the machine was idle or in use changed one result by 32%. Any
performance figure in this repository should be read together with the
environment it was taken on.

Related material:

- [`bench/computational/simple/`](../bench/computational/simple/README.md)
  and [`bench/memory/`](../bench/memory/README.md) — the benchmark
  harnesses themselves.
- [liboqs notes](implementations/liboqs.md#two-defects-in-the-x86_64-cycle-counter)
  — two defects in liboqs' own cycle counter that motivated our harness.

Throughout, *observed* marks something measured directly on the host;
*interpretation* marks our own reading of it.

## Background: what a host must provide

Two quantities are measured for each operation:

- **Wall-clock time** (µs). Easy to obtain anywhere, but sensitive to
  CPU frequency and to other work on the machine.
- **Retired core cycles**, from the CPU's hardware performance counters
  via Linux `perf_event_open`. Much less sensitive to frequency changes,
  and therefore the preferred basis for comparison.

Access to hardware counters is controlled by the kernel setting
`/proc/sys/kernel/perf_event_paranoid`. At **2** (the upstream default)
an unprivileged process can count its own user-space cycles; at **1** it
can also count kernel-mode cycles; at values above 2, which are a
Debian/Ubuntu extension, unprivileged access is refused entirely.
Changing the value requires administrator rights.

## Summary

| | Workstation (WSL2) | `coral` (UTCS) | `grape-nuts` (UTCS) | `froot-loops` (UTCS) |
| --- | --- | --- | --- | --- |
| Role | **primary** (timing) | evaluated, not used | memory measurements; preliminary timing | first API harness run (see below) |
| CPU | AMD Ryzen 5 5600X, 6C/12T, uniform cores | Intel Core i5-14600, **hybrid** 6 P + 8 E cores | Intel Xeon W-1270, 8C/16T, uniform cores | Intel Xeon W-1270, 8C/16T, uniform cores |
| Access | single user | shared, 33 users logged in | shared, 11 users logged in | shared, but idle when observed |
| `perf_event_paranoid` | 2 | **4** | **4** | **4** |
| Retired core cycles | yes (user-space only) | **no** | **no** | **no** |
| Administrator access | yes | no | no | no |

**Decision:** Phase 2 timing measurements are taken on the workstation,
with the machine otherwise idle. The two departmental machines cannot
provide cycle counts (see below), and both were under sustained heavy
load. Memory measurements (stack, heap, code and object sizes) do not
depend on CPU frequency or load, and are taken on `grape-nuts`, which
provides valgrind.

## Primary host: workstation under WSL2

### Specification

Observed 2026-09-28.

| | |
| --- | --- |
| CPU | AMD Ryzen 5 5600X (Zen 3), 6 cores / 12 threads |
| CPU features relevant here | AVX2; invariant TSC (`constant_tsc`, `nonstop_tsc`, `tsc_reliable`); `rdtscp` |
| Memory visible to the VM | 15 GiB |
| GPU | NVIDIA GeForce RTX 3060 Ti, 8 GiB, reached through WSL2's GPU passthrough. `nvidia-smi` reports CUDA 13.4 and driver 617.42; compute capability 8.6. CUDA toolkit 13.3 installed 2026-10-20 from NVIDIA's WSL-Ubuntu apt repository (`/usr/local/cuda`) |
| Host OS | Windows, build 10.0.26200 |
| Virtualisation | WSL 2.7.13.0 (Hyper-V) |
| Guest OS / kernel | Ubuntu 26.04.1 LTS, Linux 6.18.33.2-microsoft-standard-WSL2 |
| Compiler / build | GCC 15.2.0, CMake 4.2.3, Python 3.14.4 |
| liboqs revision | `0.16.0-38-gadbeba1ef` |
| `perf_event_paranoid` | 2 |

### Measurement constraints

Any timing harness on this host has to handle each of these. The
mitigations below are the ones an earlier, since-deleted harness used.
The current API harness
([`bench/computational/api/`](../bench/computational/api/README.md))
does **not** implement them yet. It reports user-space perf cycles and
TSC ticks side by side, with no calibration between them.

- **User-space cycles only.** At `perf_event_paranoid=2`, time an
  operation spends inside system calls (for example `getrandom()`) is
  not counted as cycles, while the timestamp counter (TSC) keeps
  advancing. The mitigation is to calibrate against a loop that makes no
  system calls, and to report the fraction of time spent in user space
  as a diagnostic.
- **The virtual machine can be descheduled.** Under Hyper-V the TSC
  keeps advancing while the virtual CPU is not running, whereas the
  cycle counter only counts cycles actually executed. Interference can
  therefore only *lower* a measured cycles-per-tick ratio, never raise
  it, so the calibration should take the **maximum** over several short
  windows rather than the mean.
- **No control over CPU frequency.** Turbo boost and the frequency
  governor are managed by the Windows host and cannot be fixed from
  inside the VM. Cycle counts are the mitigation.
- **Other activity on the machine dominates all other noise.**
  *Observed:* the same ML-KEM-512 key generation measured 6.13 µs with
  the machine idle and 8.10 µs while it was in interactive use. Pinning
  the benchmark to one core did not help under load: between-run
  coefficient of variation rose from 5.9–7.0% to 6.8–11.3%.
  *Interpretation:* a pinned process must wait for its one core, whereas
  an unpinned one can migrate away from busy cores. Runs are therefore
  taken with the machine otherwise idle.

## Departmental machines (UTCS)

Both machines below are shared servers operated by the university's
computer science department. They were evaluated as candidates for a
more controlled, bare-metal environment than the WSL2 workstation.

### Common limitation: no hardware counters

*Observed:* `perf_event_paranoid` is **4** on both hosts, and
`perf_event_open` fails with `EACCES` whether or not kernel cycles are
excluded:

```
exclude_kernel=0 -> FAIL  errno=Permission denied
exclude_kernel=1 -> FAIL  errno=Permission denied
```

The setting is distributed by the department's configuration management
(Puppet), so it is site-wide policy rather than a per-machine choice,
and is a reasonable one for multi-user systems. Without counters, any
harness can report only TSC ticks and wall-clock time.

### `coral`

Observed 2026-09-21. Ubuntu 24.04.5 LTS, kernel 6.8.0-139-generic.

**Sustained multi-user load.**

```
up 5 days, 14:24, 33 users, load average: 45.00, 45.01, 45.00
```

A load average of 45 on 20 logical CPUs means roughly 2.3 runnable
processes per CPU. The 1-, 5- and 15-minute averages agree to two decimal
places, so this was a steady state rather than a short spike; the load
came from long-running CPU-bound jobs belonging to other users.

**Hybrid CPU topology.** The i5-14600 (Raptor Lake) combines two
different core designs:

| Logical CPUs | Cores | Type | Max clock |
| --- | --- | --- | ---: |
| 0–11 | 6 physical, SMT | P-core (Raptor Cove) | 5.2 GHz |
| 12–19 | 8 physical, no SMT | E-core (Gracemont) | 3.9 GHz |

P- and E-cores differ in issue width, cache and vector throughput, not
only in clock speed. A benchmark that the scheduler moves between them
produces two genuinely different timing populations, which averaging or
trimming cannot reconcile. Pinning to a P-core (CPUs 0–11) avoids this,
although each P-core still shares its execution resources with an SMT
sibling.

**Frequency scaling under load.** The governor is `powersave` on the
`intel_pstate` driver (800 MHz – 5.2 GHz). Observed under the load above:

| CPU | Type | Current | Max | % of max |
| --- | --- | ---: | ---: | ---: |
| 0 | P | 3.00 GHz | 5.2 GHz | 58% |
| 6 | P | 3.00 GHz | 5.2 GHz | 58% |
| 12 | E | 2.50 GHz | 3.9 GHz | 64% |
| 18 | E | 2.49 GHz | 3.9 GHz | 64% |

*Interpretation:* wall-clock times taken here would be inflated by
roughly 1.7× relative to the same hardware unloaded, and would drift as
other jobs start and stop.

**What would make it usable.** Lowering `perf_event_paranoid` to 1
(administrator action) is the decisive change: cycle counts are largely
unaffected by the frequency governor, and with a P-core pin they would
remain meaningful even under load. Wall-clock times would still not be
reportable unless the machine were idle.

### `grape-nuts`

Observed 2026-09-28. Intel Xeon W-1270 (Comet Lake), 8 cores / 16
threads, uniform cores, AVX2 (no AVX-512); 31 GiB RAM; Ubuntu 24.04.5
LTS, kernel 6.8.0-139-generic; GCC 13.3.0, CMake 3.28.3, valgrind 3.22.0;
governor `powersave` on `intel_pstate`.

```
up 7 days, 15:37, 11 users, load average: 47.28, 47.65, 47.37
```

As on `coral`, a load average of about 47 on 16 logical CPUs (roughly 3
runnable processes per CPU) held steady across all three averages.

**Memory measurements.** The memory footprint results in
[`bench/memory/`](../bench/memory/README.md) were taken here on
2026-09-29, with valgrind massif on liboqs' `test_kem_mem`. Stack depth,
heap use, code size and object sizes are counts of bytes, not of time,
so the load above does not affect them. Small figures can still shift by
a few KB between runs, from libc's stdio buffers in the test program;
see that README.

**Preliminary timing.** The preliminary per-algorithm figures currently quoted in
[ML-KEM](algorithms/ml-kem.md#measured-performance),
[Classic McEliece](algorithms/classic-mceliece.md#measured-performance)
and [NTRU](algorithms/ntru.md#measured-performance) come from this host:
`bench/computational/results/simple-speed_kem-grape-nuts.csv`, recorded
2026-09-21 with the `bench/computational/simple/` harness (liboqs `speed_kem`, 3 s per
operation).

What is known about the run:

- `perf_event_paranoid` is 4, so the file contains wall-clock times and
  TSC ticks only — no retired core cycles.
- The ratio of TSC ticks to microseconds is 3.398–3.408 across all 21
  rows, implying a TSC rate of about **3.40 GHz** (derived from the
  results file, not measured directly).
- The CPU model has since been identified as the Xeon W-1270 above,
  whose nominal 3.40 GHz clock matches that TSC rate.
- The system load and CPU frequency at the time of the run were **not
  recorded**. *Interpretation:* given the steady load observed on
  2026-09-28, the machine was probably heavily loaded then too.

These figures are therefore suitable for comparing algorithms against
one another within that single run, but not as absolute costs, and they
will be superseded by Phase 2 measurements on the primary host.

### `froot-loops`

Observed 2026-10-06. Same CPU as `grape-nuts`: Intel Xeon W-1270 (Comet
Lake), 8 cores / 16 threads, uniform cores, AVX2 (no AVX-512), invariant
TSC (`constant_tsc`, `nonstop_tsc`) and `rdtscp`. 31 GiB RAM; Ubuntu
24.04.5 LTS, kernel 6.8.0-139-generic; GCC 13.3.0, CMake 3.28.3,
Python 3.12.3, valgrind 3.22.0. Governor `powersave` on `intel_pstate`
(800 MHz – 5.0 GHz). `perf_event_paranoid` is 4, as on every UTCS host.
System OpenSSL is 3.0.13, which has neither ML-KEM nor DHKEM, so the API
harness builds its own pinned OpenSSL 3.5.9.

**Load.** Before our job:

```
up 11 days, 16:32, 9 users, load average: 0.00, 0.04, 0.00
```

Unlike `coral` and `grape-nuts`, sessions were open but nothing was
running.

**First API harness run** (2026-10-06, 06:53–06:58 UTC, results in
`bench/computational/results/20261006T065309Z-froot-loops/`). The load
average was 6.34 at the start. That is the decaying average left by our
own OpenSSL build, which had just finished with `make -j16`. It had
fallen to 1.04 by the end, which is the benchmark itself. *Observed:*

- Between-run CV, the spread of per-run medians across 10 independent
  processes, was 0.2–4.1% for every operation except the keygens with
  rejection loops. For comparison, the earlier harness measured 5.9–7.0%
  on the idle WSL2 workstation.
- The high-CV exceptions are Classic McEliece non-`f` keygen for
  `460896` and larger (11–18%; `348864` was 3.5%), and RSA keygen (18%
  for 2048, 38% for 3072). The McEliece `f` keygens sit at 0.3–0.7%. *Interpretation:* this
  is the algorithms' own retry loops, not machine noise.
- TSC ticks per nanosecond were 3.396–3.408 across all 84 operations:
  the 3.40 GHz nominal rate. Without perf, the TSC column is wall time in
  other units and carries no frequency information.

*Interpretation:* `froot-loops` is the only host seen so far that is
both bare metal and idle. That makes it the strongest candidate for
wall-clock timing. It cannot provide cycle counts, and nothing stops
another user from loading it mid-run. A run should therefore be checked
by its between-run CV, and by its load average at start and end.

## Open Questions

- Should `froot-loops` replace the workstation as the primary host for
  wall-clock timing (and `grape-nuts` for memory), keeping the
  workstation only for perf cycle counts? The **Decision** above still
  names the workstation.

- Would the department lower `perf_event_paranoid` to 1 on a lab machine
  for the duration of the project? It is the single change that would
  make the departmental hardware usable for cycle counts.
- Is a uniform-core, single-user, bare-metal machine available? It would
  remove both the virtualisation effects of WSL2 and the load problems
  of shared servers.
- Should the Phase 2 reference numbers be taken in one dedicated quiet
  window (e.g. overnight) on the workstation and treated as fixed, with
  later runs compared only against that baseline?
- Could `coral`'s hybrid topology be studied in its own right? P-core
  versus E-core cost ratios per algorithm would show how these schemes
  behave on heterogeneous hardware.
