# Record of Work

## Week 1: Tue 2026-09-15 to Tue 2026-09-22

**Expected work**

- Not recorded.

**Actual work completed**

- Set up the repository (`ee2a97f`, 09-20): added liboqs, mlkem-native,
  PQClean, mldsa-native and slhdsa-c as submodules, with empty
  placeholder notes under `docs/` and `papers/`.
- Wrote a script that totals the output of liboqs' `speed_kem`, and took
  a first run on `grape-nuts` (`485c008`, 09-22).

## Week 2: Tue 2026-09-22 to Tue 2026-09-29

**Expected work**

- Not recorded.

**Actual work completed**

- Narrowed the scope to KEMs: removed the mldsa-native and slhdsa-c
  submodules (`187ced9`).
- Wrote the top-level `README.md`, note templates
  (`docs/algorithms/notesformat.md`, `docs/implementations/notesformat.md`),
  a terminology skeleton, `papers/README.md` and reading-note stubs for
  seven papers (`187ced9`).
- Moved the `speed_kem` script under `bench/computational/simple/`
  (`187ced9`).
- First memory measurements with valgrind massif (`run_massif.py`): object
  sizes, stack, heap and code size on `grape-nuts` (`910c14d`).
- Wrote the network benchmark proposal, `bench/network/proposal.md`,
  with its four layers and build order (`15aa7d7`).
- Implementation notes for PQClean and mlkem-native (last modified
  09-29; not yet committed).

## Week 3: Tue 2026-09-29 to Tue 2026-10-06

**Expected work**

- Build a replacement for the `speed_kem` timings that calls the liboqs
  and OpenSSL APIs directly, so PQC and classical algorithms are timed
  the same way (planned in `docs/README.md` as of `2f695ca`).
- Measure the classical baselines, which were not measured yet.

**Actual work completed**

- Wrote `bench/criteria.md` and made clarity edits across the bench READMEs
  (`5cc451a`).
- Added the classical baselines (X25519, ECDH P-256, RSA and `ffdhe`) to
  the project scope and rewrote the docs to match; added
  `docs/README.md` as the research index (`2f695ca`).
- Built the API timing harness (`bench/computational/api/`) and ran it
  on `froot-loops`, PQC and classical together (`c578f06`, 10-06).
- Added `bench/algorithms.md`, listing every measured parameter set
  (`c578f06`).
- Moved the C driver to `bench/driver/` so all benchmarks share it, and
  replaced massif with in-process memory measurement (`run_memory.py`);
  ran it on `DESKTOP-JustinY` (`d3fbf9b`, 10-06).
- Notes on liboqs (including the two defects in its x86_64 cycle
  counter), ML-KEM, Classic McEliece, NTRU, the classical baselines,
  testing and benchmarking methodology, and the benchmark hosts (last
  modified 10-06; not yet committed).

## Week 4: Tue 2026-10-06 to Tue 2026-10-13

**Expected work**

- Network proposal steps 1 to 3: a KEM client and server, a driver
  script for namespaces and `netem`, and layer 1 (clean link) runs with
  byte counts checked against `sizes.csv` (`bench/network/proposal.md`,
  "Minimum scope and build order").

**Actual work completed**

- Added the client/server KEM exchange to `bench/driver/kem_bench.c` and
  wrote `bench/network/run_network.py` (`cb30bd6`).
- Layer 1 run on `DESKTOP-JustinY`, 10-13 (`cb30bd6`).
- Checked the interface counters against a `tcpdump`/`tshark` capture;
  packets and bytes matched exactly (`bench/network/README.md`).
- Revised `proposal.md` and `criteria.md`, and wrote
  `bench/network/README.md` (`cb30bd6`).
- Updated `docs/README.md` and `.gitignore` for the new measurements
  (not yet committed).

## Week 5: Tue 2026-10-13 to Tue 2026-10-20 (in progress)

**Expected work**

- Network proposal step 4: measure real paths and turn them into
  `netem` profiles.
- Network proposal step 5: layer 2 runs, with and without `iperf3`
  competing traffic.
- Explore how using the graphics card affects computational speed, for
  both single operations and batches.
- Network proposal step 6: one layer 3 (real path) check, a phone on
  mobile data talking to a cloud VM, to see how a limited client
  affects speed.

**Actual work completed**

- Two `netem` runs on `DESKTOP-JustinY`, 10-18, with ML-KEM-768,
  Classic-McEliece-6688128 and X25519: `delay 10ms`, and
  `delay 10ms loss 5%` (not yet committed). The impairments were picked
  by hand, since step 4's measured profiles don't exist yet.
- Open issues from those runs: one failed McEliece handshake in each
  run, and in the loss run the liboqs ML-KEM-768 row fails the
  "wire bytes do not match packets x headers" check.
- GPU ML-KEM (10-19 to 10-20, not yet committed): read liboqs' cuPQC
  and ICICLE backends, built ICICLE and a liboqs `OQS_USE_ICICLE` build,
  and ran liboqs' ML-KEM tests on it (all pass). Added `--variant icicle`
  to the API harness and a batch harness, `bench/computational/gpu/`,
  which checks GPU output against the CPU byte for byte. Through liboqs, a
  single GPU operation is 5–22× slower than the CPU. In batches, the GPU
  beats one CPU thread from 8–32 operations per call and peaks at 12–47×
  it. Measured under WSL2. Notes in `docs/implementations/icicle.md` and
  `bench/computational/gpu/README.md`.
