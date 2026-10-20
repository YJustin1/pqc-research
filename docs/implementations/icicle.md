# ICICLE (CUDA-PQC backend)

## Overview

Per upstream documentation, ICICLE is Ingonyama's GPU cryptography
library. Its CUDA-PQC backend implements ML-KEM on NVIDIA GPUs and is
open source, separate from ICICLE's closed-source CUDA backend
(`icicle/backend/cuda_pqc/README.md`). We use it for ML-KEM only, in two
ways:

- through liboqs, built with `OQS_USE_ICICLE=ON`, which replaces liboqs'
  ML-KEM entry points with one-operation ICICLE calls (see
  [liboqs notes](liboqs.md#gpu-backends-for-ml-kem));
- directly through ICICLE's batched API, which liboqs cannot express.

It is not a submodule. `bench/driver/kem_build.py` clones it into
`bench/driver/build/icicle-src/` at a pinned commit.

## Upstream Repository

https://github.com/ingonyama-zk/icicle, pinned at
`625532a624e5aaa6e9d31a1c92587f1fcc30dc76` (`main`, 2025-08-06). The
liboqs glue (`icicle-liboqs@4ea3e61`) may have been written against a
different commit.

## Build System

CMake, with the recipe from liboqs' `CONFIGURE.md`: `CPU_BACKEND=OFF`,
`DISABLE_ALL_FEATURES=ON`, `PQC=ON`, `CUDA_PQC_BACKEND=ON`,
`ICICLE_STATIC_LINK=ON`, `PQC_PACKAGE=ON`.

Observed on our workstation (CUDA 13.3, GCC 15.2, CMake 4.2):

- It builds with warnings only. nvcc is given `-arch=native`
  (`icicle/backend/cuda_pqc/cmake/Common.cmake`, `set_gpu_env`), so it
  compiles for the local GPU. The `75` in `CMakeCache.txt` is CMake's
  default and is not what nvcc receives.
- The installed `icicle_pqc_packageConfig.cmake` calls
  `find_dependency(Taskflow QUIET)`. That is fatal when Taskflow is
  absent, even though no ICICLE target uses it. We satisfy it with an
  empty `TaskflowConfig.cmake` (`TASKFLOW_STUB` in `kem_build.py`).
- Consumers must link the three static libraries
  (`libicicle_device.a`, `libicicle_pqc.a`, `libicicle_backend_cuda_pqc.a`)
  with `--whole-archive`, because the backend registers itself from
  static initialisers. Without it there is no device. They also need the
  CUDA runtime and `libstdc++`.

## Tests

We have not run ICICLE's own tests. What we ran instead (2026-10-20):

- liboqs' tests on the `OQS_USE_ICICLE` build: `test_kem` for all three
  sets, and `tests/test_kat.py` and `tests/test_acvp_vectors.py`
  filtered to ML-KEM, all pass. `test_kat.py` routes keygen and
  encapsulation through ICICLE, so ICICLE reproduces the stored known
  answers from the same randomness. Several ACVP checks run on the CPU
  instead (see [liboqs notes](liboqs.md#observed-in-source)).
- Our batch benchmark, `bench/computational/gpu/icicle_batch.cu`,
  checks a batch of 256 per set before timing. GPU keys, ciphertexts and
  shared secrets equal liboqs' CPU output from the same seeds, byte for
  byte, and liboqs on the CPU decapsulates GPU ciphertexts correctly.

## Important Source Files

- `icicle/include/icicle/pqc/ml_kem.h`: the public API. `keygen`,
  `encapsulate` and `decapsulate` take a `MlKemConfig` with
  `batch_size`, a `*_on_device` flag for each buffer, `stream` and
  `is_async`.
- `icicle/backend/cuda_pqc/src/ml_kem/cuda_pqc_ml_kem.cu`: host code for
  each operation.
- `icicle/src/device_api.cpp`: device registry. The first backend to
  register becomes the default device.

## Interesting Observations

Observed in `cuda_pqc_ml_kem.cu`:

- One thread block of 128 threads per operation: a batch of `N`
  launches `N` blocks.
- Every call takes its buffers from the stream-ordered allocator
  (`cudaMallocAsync`/`cudaFreeAsync`): a scratch matrix `d_A` always, and
  staging buffers for any input or output not marked `*_on_device`.
- The call synchronises the stream only when `config.is_async` is
  true, which looks inverted. With the default (`false`), a call whose
  outputs are all on the device can return before the kernel has
  finished. With outputs on the host it cannot, because the copy back to
  pageable memory blocks.

Observed when running it (2026-10-20, under WSL2):

- With no GPU visible (`CUDA_VISIBLE_DEVICES=`), the first ML-KEM call
  throws an uncaught `IcicleError` and the process aborts. A liboqs build
  with `OQS_USE_ICICLE=ON` does the same; it never returns `OQS_ERROR`.
- CUDA's default memory pool has a release threshold of 0, so every
  synchronise returns ICICLE's per-call allocations to the system.
  A caller that synchronises after each call pays for fresh allocations
  every time. One ML-KEM-768 keygen with host buffers took a median
  2,049 µs that way, and 160 µs after raising the threshold
  (`keep_pool` in `icicle_batch.cu`). liboqs' glue never synchronises
  explicitly and measured about 140–160 µs.

### Where a single call's time goes (2026-10-20)

Nsight Systems profiles of 200 single ML-KEM-768 calls through the
liboqs `icicle` build, split by
[`bench/computational/gpu/nsys_breakdown.py`](../../bench/computational/gpu/nsys_breakdown.py).
Medians in µs; profiling makes the whole call 10–20% slower than the
unprofiled 161 µs (keygen) and 98 µs (decaps).

| part | keygen | decaps |
| --- | ---: | ---: |
| kernel running on the GPU | 54.3 | 45.4 |
| launch call start → kernel start (crosses CPU and GPU clocks; ±10) | 48.9 | 41.2 |
| second device-to-host copy, GPU idle (API time) | 50.1 | — |
| `cudaLaunchKernel` call | 10.1 | 11.0 |
| host-to-device copies (API time) | 8.5 | 17.6 |
| `cudaMallocAsync` + `cudaFreeAsync` | 6.8 | 8.2 |
| host time between CUDA calls | 25.7 | 30.1 |
| a device-to-host copy, on the GPU itself | 2.4 | 2.1 |

Observed:

- The kernel alone takes 54 µs for keygen and 45 µs for decaps. The
  whole operation on the CPU (AVX2) takes 10 µs and 15 µs. One
  operation is one block of 128 threads, so it runs on one of the RTX
  3060 Ti's 38 multiprocessors at 1.7 GHz, and the rest of the GPU is
  idle.
- Moving the data costs almost nothing on the GPU (about 2 µs per
  copy). Waiting for the GPU costs a lot: a 2.4 KB copy back with the
  GPU idle takes 50 µs from the CPU's side. This is about the same as
  the probes' empty kernel launch plus synchronise (48 µs).
- Decaps is cheaper than keygen mainly because it copies one output back
  instead of two, which saves one of those 50 µs round trips.

Our interpretation:

- A single GPU operation is slow for two separate reasons. The kernel
  itself is 4–5× slower than the CPU's whole operation, because one
  operation can use only one multiprocessor. On top of that, keygen
  waits about 50 µs twice: between the launch call and the kernel
  starting, and for the second copy back.
- WSL2 can only affect the round trips, not the kernel. Even with zero
  overhead, a single operation would still be 4–5× slower than the CPU,
  so WSL2 is not why the GPU loses at single operations. It may be why
  the loss is 15× rather than, say, 6×.

## Open Questions

- How much of the ~50 µs wait is WSL2's GPU passthrough rather than
  CUDA itself? One run of the probes and the profile on a native Linux
  host with an NVIDIA GPU would settle it.
- Is the `is_async` synchronisation inverted on purpose?
- Does ICICLE's code take constant time? Nothing we read addresses it.
