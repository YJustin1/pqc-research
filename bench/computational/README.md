# Computational benchmarks

Two timing harnesses for ML-KEM, Classic McEliece and NTRU over the
`liboqs` submodule. They share `build/` and `results/`. Memory footprint
is measured separately, in [`../memory/`](../memory/README.md).

| | [`simple/`](simple/README.md) | [`full/`](full/README.md) |
| --- | --- | --- |
| Approach | parses liboqs' `speed_kem` | custom C harness on the liboqs API |
| Size | ~70 lines Python | ~1,700 lines C + Python |
| Total time per op | yes | yes |
| Cycles per op | TSC ticks, 32-bit truncated | retired core cycles via `perf` |
| Variance | population stdev only | sample stdev, percentiles, trimmed moments |
| Independent runs | no — one process | yes — R processes, variance split two ways |
| Sample-size guidance | no | `--pilot` computes required N and R |

Start with `simple/`. Move to `full/` when you need cycle counts you can
trust or error bars you can defend.

```sh
python3 bench/computational/simple/speed_kem_totals.py   # quick totals
python3 bench/computational/full/run_bench.py --pilot    # measure variability first
python3 bench/computational/full/run_bench.py            # full run
```

Both use liboqs built out-of-tree in `bench/computational/build/`; the
`implementations/liboqs` working directory is never written to.

Results land in `bench/computational/results/`. Per-iteration sample dumps
(`--raw`) are gitignored — they run tens of MB.

Why two exist at all: liboqs hands you the operation but not a
trustworthy measurement of it. The defects that forced a custom harness
are documented in [`full/README.md`](full/README.md) and in
[`docs/implementations/liboqs.md`](../../docs/implementations/liboqs.md#two-defects-in-the-x86_64-cycle-counter).
