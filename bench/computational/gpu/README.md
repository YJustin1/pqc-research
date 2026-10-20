# GPU harness: batched ML-KEM through ICICLE

Times ML-KEM keygen, encaps and decaps on an NVIDIA GPU through
ICICLE's own API, at batch sizes from 1 to 65,536 operations per call.
Compares them with single-thread CPU ML-KEM from liboqs' native build.
liboqs' API does one operation per call, so batches can't be measured
through it. For single GPU operations through liboqs, use the API
harness with `--variant icicle` (see below).

```sh
python3 bench/computational/gpu/run_gpu.py                          # all three sets
python3 bench/computational/gpu/run_gpu.py --sets ML-KEM-768 --max-batch 4096
python3 bench/computational/gpu/run_gpu.py --build-only
```

Needs an NVIDIA GPU, the CUDA toolkit (`/usr/local/cuda`, or set
`CUDA_HOME`), and everything the API harness needs. Network access is
needed once, to clone ICICLE.

## What it does

[`icicle_batch.cu`](icicle_batch.cu) links ICICLE and liboqs' native
build into one program. For each set it:

1. Checks a batch of 256 GPU results against liboqs on the CPU, from
   the same seeds: GPU keys, ciphertexts and shared secrets must equal
   the CPU's byte for byte, and the CPU must decapsulate GPU ciphertexts.
   Device mode must give the same ciphertexts as host mode. Any failure
   stops the run.
2. Times the CPU, one thread and one operation per call, through
   liboqs' derandomised functions.
3. Times the GPU at batch sizes 1, 2, 4 ... `--max-batch`, in two
   modes:
   - `host`: inputs and outputs in host memory. Each call includes
     ICICLE's device allocations and the copies both ways. This is what a
     server handing keys to the GPU would pay.
   - `device`: inputs and outputs already on the GPU, so close to the
     kernel alone.

Every GPU call is followed by `cudaDeviceSynchronize()`. ICICLE only
synchronises itself when `is_async` is set, so without it a device-mode
call could be timed before its kernel had finished
([ICICLE notes](../../../docs/implementations/icicle.md#interesting-observations)).

A separate `probes` run measures fixed per-call costs: an empty kernel
launch plus synchronise, a 1 KiB copy there and back, a 4 KiB
`cudaMalloc`/`cudaFree`, and one ML-KEM-768 keygen with CUDA's default
memory pool and with the pool kept.

### The memory pool

ICICLE allocates its buffers with `cudaMallocAsync` on every call.
CUDA's default pool has a release threshold of 0, so every synchronise
hands that memory back and the next call allocates from scratch. On our
workstation that made one call cost about 2 ms instead of about 160 µs.
The set runs therefore raise the threshold first (`keep_pool`), as a
long-running server would. The probes report both figures.

## Single operations through liboqs

```sh
python3 bench/computational/api/run_bench.py --variant icicle --impl liboqs \
    --algs ML-KEM-512 ML-KEM-768 ML-KEM-1024
```

This times liboqs built with `OQS_USE_ICICLE=ON`, through the same
driver and statistics as the CPU numbers. Run the same command with
`--variant native` for the CPU side.

## Build

[`run_gpu.py`](run_gpu.py) builds through
[`../../driver/kem_build.py`](../../driver/kem_build.py):

- ICICLE, cloned into `bench/driver/build/icicle-src/` at a pinned
  commit and built with the recipe from liboqs' `CONFIGURE.md`;
- liboqs' native build, for the CPU reference and the checks;
- `bench/driver/build/icicle_batch`, compiled with nvcc for the local GPU
  (`-arch=native`).

## Output

Both GPU harnesses write under [`results/`](results/): `run_gpu.py` to
`<UTC stamp>-<host>-batch/`, and `run_bench.py --variant icicle` to
`<UTC stamp>-<host>-liboqs/` (laid out as in the
[API harness](../api/README.md)). A batch run contains:

- `summary.md`: checks, probes, the CPU reference and one row per
  (set, op, mode, batch);
- `summary.csv`: the GPU rows;
- `env.json`: GPU, driver, nvcc, ICICLE and liboqs revisions, load;
- `raw.csv` (gitignored): every timed call.

## Results (2026-10-20, workstation)

RTX 3060 Ti under WSL2, CUDA 13.3, ICICLE `625532a`, liboqs
`0.16.0-38-gadbeba1ef`. Runs:

- CPU single operations:
  [`20261020T055009Z-DESKTOP-JustinY`](../results/20261020T055009Z-DESKTOP-JustinY/summary.md),
  with the other API harness results
- GPU single operations through liboqs:
  [`20261020T055302Z-DESKTOP-JustinY-liboqs`](results/20261020T055302Z-DESKTOP-JustinY-liboqs/summary.md).
  Load average 11.6 at the start, falling to 5.7. Between-run CV was
  3 to 7%, and the medians match an earlier run within 2%.
- GPU batches:
  [`20261020T054851Z-DESKTOP-JustinY-batch`](results/20261020T054851Z-DESKTOP-JustinY-batch/summary.md).
  Load average under 1. All 15 checks pass.

### Single operations: the GPU is slower

Median time per operation, through liboqs' API with the native (AVX2)
and `icicle` builds:

| set | op | CPU µs | GPU µs | GPU ÷ CPU |
| --- | --- | ---: | ---: | ---: |
| ML-KEM-512 | keygen | 6.6 | 140.5 | 21.3× |
| ML-KEM-512 | encaps | 6.6 | 146.2 | 22.1× |
| ML-KEM-512 | decaps | 8.2 | 79.3 | 9.7× |
| ML-KEM-768 | keygen | 9.9 | 161.1 | 16.3× |
| ML-KEM-768 | encaps | 10.4 | 160.5 | 15.4× |
| ML-KEM-768 | decaps | 15.0 | 97.7 | 6.5× |
| ML-KEM-1024 | keygen | 14.0 | 177.4 | 12.7× |
| ML-KEM-1024 | encaps | 14.6 | 169.6 | 11.6× |
| ML-KEM-1024 | decaps | 21.2 | 108.3 | 5.1× |

The probes put the fixed costs of one GPU call at about 48 µs for a
kernel launch plus synchronise, and 56 µs for a 1 KiB copy there and
back. That is already several CPU operations' worth before any ML-KEM
work. From ML-KEM-512 to -1024 the GPU time grows by about a quarter,
while the CPU time roughly doubles, so the gap narrows as the parameter
set grows.

An Nsight Systems profile splits one call into parts (details in the
[ICICLE notes](../../../docs/implementations/icicle.md#where-a-single-calls-time-goes-2026-10-20),
made with [`nsys_breakdown.py`](nsys_breakdown.py)). For ML-KEM-768
keygen, the kernel alone takes 54 µs, longer than the CPU's whole
10 µs operation, because one operation runs on one of the GPU's 38
multiprocessors. The copies themselves take about 2 µs. Waiting on the
GPU costs about 50 µs a time, and keygen waits twice: once between the
launch call and the kernel starting, and once for the second copy back.

WSL2 can only inflate the waits. Without any of them, a single
operation would still be 4 to 5× slower than the CPU. We haven't
measured how much of each ~50 µs wait is due to WSL2.

### Batches: the GPU wins from about 16 operations per call

Throughput of one batched call, against one CPU thread doing one
operation at a time. "Batch to beat it" is the smallest batch whose
throughput exceeds the CPU thread's. Peaks are the best batch size from
1 to 65,536.

| set | op | 1 CPU thread, ops/s | host: batch to beat it | host: peak ops/s | device: batch to beat it | device: peak ops/s |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| ML-KEM-512 | keygen | 181,488 | 32 | 2.25M (12×, batch 32768) | 32 | 5.02M (28×, batch 8192) |
| ML-KEM-512 | encaps | 165,563 | 32 | 2.61M (16×, batch 65536) | 16 | 4.39M (27×, batch 8192) |
| ML-KEM-512 | decaps | 125,471 | 16 | 2.16M (17×, batch 16384) | 16 | 4.22M (34×, batch 8192) |
| ML-KEM-768 | keygen | 85,397 | 16 | 1.65M (19×, batch 16384) | 16 | 3.81M (45×, batch 4096) |
| ML-KEM-768 | encaps | 81,639 | 16 | 1.94M (24×, batch 65536) | 16 | 3.30M (40×, batch 65536) |
| ML-KEM-768 | decaps | 63,857 | 8 | 1.55M (24×, batch 32768) | 8 | 3.03M (47×, batch 4096) |
| ML-KEM-1024 | keygen | 63,291 | 16 | 1.20M (19×, batch 65536) | 16 | 2.63M (42×, batch 4096) |
| ML-KEM-1024 | encaps | 59,952 | 16 | 1.37M (23×, batch 16384) | 8 | 2.29M (38×, batch 65536) |
| ML-KEM-1024 | decaps | 48,688 | 8 | 1.05M (22×, batch 65536) | 8 | 1.92M (39×, batch 4096) |

- Throughput levels off from about 4,096 operations per call. Beyond
  that, larger batches change the rate by a few percent either way.
- Keeping the data on the GPU roughly doubles peak throughput. In host
  mode the copies and staging allocations cost about as much as the
  ML-KEM work.
- The CPU reference here comes from `icicle_batch`'s own loop, not the
  API harness. The two disagree by up to about 20% per row, in both
  directions. Keygen and encaps for 768 and 1024 are 13 to 19% slower
  here (11.7 µs against 9.9 µs for ML-KEM-768 keygen), which flatters
  the GPU in those rows. All three ML-KEM-512 operations are 3 to 17%
  faster here.

## What the results mean
### Why batching pays off

ML-KEM-768 keygen in host mode, from the batch run. The CPU does one in
about 10 µs.

| ops per call | whole call | per operation |
| ---: | ---: | ---: |
| 1 | 159 µs | 159 µs |
| 4 | 159 µs | 40 µs |
| 16 | 164 µs | 10 µs |
| 64 | 189 µs | 3.0 µs |
| 256 | 325 µs | 1.3 µs |
| 4,096 | 2,723 µs | 0.67 µs |
| 65,536 | 39,785 µs | 0.61 µs |

For one operation, only 54 µs of the 159 µs call is the GPU computing.
The other ~100 µs goes on sending the request and waiting for the card
to start and for each result to come back. That alone is ten times the
CPU's whole operation.

Going from 1 to 64 operations per call adds only 30 µs. Two things are
shared across a batch. The fixed waiting is paid once per call, however
many operations it carries. And until the card is full, operations run
side by side on its 38 processor groups, so 16 keygens take about as
long as one. By 16 operations per call, the GPU's cost per operation
matches the CPU's.

From about 256 operations on, the call time grows roughly in step with
the batch: the card is full, so twice the work takes twice the time.
What's left per operation, about 0.6 µs, is the ML-KEM work plus copying
each operation's keys to and from the card. Device mode, where the data
is already on the card, levels off at 0.27 µs, so at full batch roughly
half the host-mode cost is moving data. Batching removes the fixed
overhead but not the copying.

### Conclusions

- On the GPU, ML-KEM is a throughput tool, not a latency tool. One key
  exchange at a time, as a client or a single handshake does, is 5 to
  22× faster on the CPU.
- A GPU only helps a server with many handshakes in progress at once,
  and only if it batches them. Waiting to fill a batch adds delay to
  every handshake in it.
- The gain over the whole CPU is smaller than the table suggests. Every
  CPU figure here is one thread. If the 6-core 5600X scaled perfectly,
  host-mode peaks would be roughly 2 to 4× the whole CPU. This is an
  estimate; we haven't measured a multi-threaded CPU.
- ML-KEM is rarely what a handshake waits on. In our network run with a
  10 ms delay each way
  ([`20261018T061145Z-DESKTOP-JustinY`](../../network/results/20261018T061145Z-DESKTOP-JustinY/summary.md)),
  liboqs ML-KEM-768 took 0.078 ms of client compute out of a 40.6 ms
  median handshake.
- Acceleration would matter more for expensive operations. In the same
  run, Classic-McEliece-6688128 spent 162 ms on client compute. Neither
  liboqs GPU backend covers it, and we haven't looked for one that does.

These conclusions rest on one library (ICICLE), one consumer card (an
RTX 3060 Ti) and one setup (WSL2). ICICLE runs each operation on one
block of threads, which is a design choice; another library could
spread one operation wider. They support "ML-KEM on this GPU is a
throughput tool", not a general claim about GPUs.

## Caveats

- The workstation runs Linux under WSL2, so every GPU call goes through
  Windows' GPU passthrough. The fixed per-call cost is likely higher than
  on native Linux. This hurts small batches most and large batches
  least. The probes measure it, but we have no native Linux run to
  compare against.
- The CPU reference is one thread. The 5600X has 6 cores and 12 threads,
  so a multi-threaded CPU would do several times better. We haven't
  measured that.
- Host mode copies from pageable memory. Pinned host memory would make
  the copies faster, but ICICLE's host mode allocates its own staging
  buffers either way.
