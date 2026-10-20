# GPU batch results: DESKTOP-JustinY

GPU: NVIDIA GeForce RTX 3060 Ti, 617.42, 8.6. Build cuda_13.3.r13.3/compiler.38244171_0. CPU: AMD Ryzen 5 5600X 6-Core Processor.
ICICLE `625532a624e5`; liboqs `0.16.0-38-gadbeba1ef` (native build) for the CPU reference and the checks.
Kernel: 6.18.33.2-microsoft-standard-WSL2. Load average at start / end: `0.57 4.18 4.58 1/545 213632` / `0.93 3.76 4.42 1/509 214264`.

## Checks

A batch of 256 GPU results per set, compared with liboqs on the CPU from the same seeds.

| set | check | result |
| --- | --- | --- |
| ML-KEM-512 | keygen_equals_cpu | ok (256/256 match) |
| ML-KEM-512 | encaps_equals_cpu | ok (256/256 match) |
| ML-KEM-512 | decaps_recovers_secret | ok (256/256 match) |
| ML-KEM-512 | cpu_decaps_of_gpu_ciphertext | ok (256/256 match) |
| ML-KEM-512 | device_mode_equals_host_mode | ok (ciphertexts of the whole batch) |
| ML-KEM-768 | keygen_equals_cpu | ok (256/256 match) |
| ML-KEM-768 | encaps_equals_cpu | ok (256/256 match) |
| ML-KEM-768 | decaps_recovers_secret | ok (256/256 match) |
| ML-KEM-768 | cpu_decaps_of_gpu_ciphertext | ok (256/256 match) |
| ML-KEM-768 | device_mode_equals_host_mode | ok (ciphertexts of the whole batch) |
| ML-KEM-1024 | keygen_equals_cpu | ok (256/256 match) |
| ML-KEM-1024 | encaps_equals_cpu | ok (256/256 match) |
| ML-KEM-1024 | decaps_recovers_secret | ok (256/256 match) |
| ML-KEM-1024 | cpu_decaps_of_gpu_ciphertext | ok (256/256 match) |
| ML-KEM-1024 | device_mode_equals_host_mode | ok (ciphertexts of the whole batch) |

## Fixed cost of a GPU call

| probe | samples | median µs |
| --- | ---: | ---: |
| icicle_768_keygen_default_pool | 300 | 1849.4 |
| icicle_768_keygen_pool_kept | 300 | 149.2 |
| launch_and_sync | 300 | 47.5 |
| copy_1KiB_round_trip | 300 | 55.9 |
| malloc_free_4KiB | 300 | 1.9 |

## CPU reference: one thread, one operation per call

| set | op | samples | median µs | ops/s |
| --- | --- | ---: | ---: | ---: |
| ML-KEM-512 | keygen | 600 | 5.51 | 181,488 |
| ML-KEM-512 | encaps | 600 | 6.04 | 165,563 |
| ML-KEM-512 | decaps | 600 | 7.97 | 125,471 |
| ML-KEM-768 | keygen | 600 | 11.71 | 85,397 |
| ML-KEM-768 | encaps | 600 | 12.25 | 81,639 |
| ML-KEM-768 | decaps | 600 | 15.66 | 63,857 |
| ML-KEM-1024 | keygen | 600 | 15.80 | 63,291 |
| ML-KEM-1024 | encaps | 600 | 16.68 | 59,952 |
| ML-KEM-1024 | decaps | 600 | 20.54 | 48,688 |

## GPU: one batched call

`host`: inputs and outputs in host memory, so the call includes ICICLE's device allocations and both copies. `device`: everything already on the GPU. µs/op is the call time divided by the batch size. The last column is GPU throughput over one CPU thread's.

| set | op | mode | batch | samples | median call µs | µs/op | ops/s | × one CPU thread |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ML-KEM-512 | keygen | device | 1 | 30 | 86.2 | 86.159 | 11,606 | 0.06 |
| ML-KEM-512 | keygen | device | 2 | 30 | 86.7 | 43.327 | 23,080 | 0.13 |
| ML-KEM-512 | keygen | device | 4 | 30 | 87.0 | 21.749 | 45,980 | 0.25 |
| ML-KEM-512 | keygen | device | 8 | 30 | 87.4 | 10.921 | 91,571 | 0.50 |
| ML-KEM-512 | keygen | device | 16 | 30 | 88.3 | 5.522 | 181,109 | 1.00 |
| ML-KEM-512 | keygen | device | 32 | 30 | 84.8 | 2.650 | 377,363 | 2.08 |
| ML-KEM-512 | keygen | device | 64 | 30 | 90.1 | 1.409 | 709,932 | 3.91 |
| ML-KEM-512 | keygen | device | 128 | 30 | 97.7 | 0.763 | 1,310,683 | 7.22 |
| ML-KEM-512 | keygen | device | 256 | 30 | 118.6 | 0.463 | 2,158,989 | 11.90 |
| ML-KEM-512 | keygen | device | 512 | 30 | 172.4 | 0.337 | 2,969,950 | 16.36 |
| ML-KEM-512 | keygen | device | 1024 | 30 | 262.8 | 0.257 | 3,896,381 | 21.47 |
| ML-KEM-512 | keygen | device | 2048 | 30 | 449.5 | 0.219 | 4,556,569 | 25.11 |
| ML-KEM-512 | keygen | device | 4096 | 30 | 840.3 | 0.205 | 4,874,319 | 26.86 |
| ML-KEM-512 | keygen | device | 8192 | 30 | 1,633.5 | 0.199 | 5,015,129 | 27.63 |
| ML-KEM-512 | keygen | device | 16384 | 30 | 3,508.3 | 0.214 | 4,670,008 | 25.73 |
| ML-KEM-512 | keygen | device | 32768 | 30 | 6,667.8 | 0.203 | 4,914,396 | 27.08 |
| ML-KEM-512 | keygen | device | 65536 | 30 | 13,525.8 | 0.206 | 4,845,271 | 26.70 |
| ML-KEM-512 | keygen | host | 1 | 30 | 139.9 | 139.853 | 7,150 | 0.04 |
| ML-KEM-512 | keygen | host | 2 | 30 | 144.4 | 72.182 | 13,854 | 0.08 |
| ML-KEM-512 | keygen | host | 4 | 30 | 137.1 | 34.281 | 29,171 | 0.16 |
| ML-KEM-512 | keygen | host | 8 | 30 | 138.5 | 17.310 | 57,770 | 0.32 |
| ML-KEM-512 | keygen | host | 16 | 30 | 140.3 | 8.771 | 114,018 | 0.63 |
| ML-KEM-512 | keygen | host | 32 | 30 | 144.1 | 4.502 | 222,110 | 1.22 |
| ML-KEM-512 | keygen | host | 64 | 30 | 144.3 | 2.254 | 443,600 | 2.44 |
| ML-KEM-512 | keygen | host | 128 | 30 | 204.0 | 1.593 | 627,549 | 3.46 |
| ML-KEM-512 | keygen | host | 256 | 30 | 255.9 | 1.000 | 1,000,303 | 5.51 |
| ML-KEM-512 | keygen | host | 512 | 30 | 389.8 | 0.761 | 1,313,457 | 7.24 |
| ML-KEM-512 | keygen | host | 1024 | 30 | 631.9 | 0.617 | 1,620,410 | 8.93 |
| ML-KEM-512 | keygen | host | 2048 | 30 | 1,129.4 | 0.551 | 1,813,328 | 9.99 |
| ML-KEM-512 | keygen | host | 4096 | 30 | 1,943.3 | 0.474 | 2,107,714 | 11.61 |
| ML-KEM-512 | keygen | host | 8192 | 30 | 3,748.6 | 0.458 | 2,185,369 | 12.04 |
| ML-KEM-512 | keygen | host | 16384 | 30 | 7,378.4 | 0.450 | 2,220,539 | 12.24 |
| ML-KEM-512 | keygen | host | 32768 | 30 | 14,533.3 | 0.444 | 2,254,682 | 12.42 |
| ML-KEM-512 | keygen | host | 65536 | 30 | 29,193.0 | 0.445 | 2,244,925 | 12.37 |
| ML-KEM-512 | encaps | device | 1 | 30 | 90.3 | 90.294 | 11,075 | 0.07 |
| ML-KEM-512 | encaps | device | 2 | 30 | 89.2 | 44.605 | 22,419 | 0.14 |
| ML-KEM-512 | encaps | device | 4 | 30 | 90.2 | 22.540 | 44,366 | 0.27 |
| ML-KEM-512 | encaps | device | 8 | 30 | 90.6 | 11.331 | 88,257 | 0.53 |
| ML-KEM-512 | encaps | device | 16 | 30 | 90.3 | 5.646 | 177,119 | 1.07 |
| ML-KEM-512 | encaps | device | 32 | 30 | 85.6 | 2.676 | 373,640 | 2.26 |
| ML-KEM-512 | encaps | device | 64 | 30 | 89.6 | 1.399 | 714,653 | 4.32 |
| ML-KEM-512 | encaps | device | 128 | 30 | 95.8 | 0.749 | 1,335,504 | 8.07 |
| ML-KEM-512 | encaps | device | 256 | 30 | 124.5 | 0.486 | 2,056,572 | 12.42 |
| ML-KEM-512 | encaps | device | 512 | 30 | 181.7 | 0.355 | 2,817,940 | 17.02 |
| ML-KEM-512 | encaps | device | 1024 | 30 | 296.6 | 0.290 | 3,452,380 | 20.85 |
| ML-KEM-512 | encaps | device | 2048 | 30 | 515.4 | 0.252 | 3,973,879 | 24.00 |
| ML-KEM-512 | encaps | device | 4096 | 30 | 967.6 | 0.236 | 4,232,953 | 25.57 |
| ML-KEM-512 | encaps | device | 8192 | 30 | 1,864.9 | 0.228 | 4,392,672 | 26.53 |
| ML-KEM-512 | encaps | device | 16384 | 30 | 3,965.6 | 0.242 | 4,131,492 | 24.95 |
| ML-KEM-512 | encaps | device | 32768 | 30 | 7,832.8 | 0.239 | 4,183,442 | 25.27 |
| ML-KEM-512 | encaps | device | 65536 | 30 | 15,370.7 | 0.235 | 4,263,709 | 25.75 |
| ML-KEM-512 | encaps | host | 1 | 30 | 143.3 | 143.284 | 6,979 | 0.04 |
| ML-KEM-512 | encaps | host | 2 | 30 | 149.0 | 74.509 | 13,421 | 0.08 |
| ML-KEM-512 | encaps | host | 4 | 30 | 139.2 | 34.806 | 28,731 | 0.17 |
| ML-KEM-512 | encaps | host | 8 | 30 | 142.8 | 17.847 | 56,031 | 0.34 |
| ML-KEM-512 | encaps | host | 16 | 30 | 142.1 | 8.879 | 112,622 | 0.68 |
| ML-KEM-512 | encaps | host | 32 | 30 | 135.5 | 4.234 | 236,165 | 1.43 |
| ML-KEM-512 | encaps | host | 64 | 30 | 141.5 | 2.211 | 452,380 | 2.73 |
| ML-KEM-512 | encaps | host | 128 | 30 | 229.6 | 1.794 | 557,375 | 3.37 |
| ML-KEM-512 | encaps | host | 256 | 30 | 314.1 | 1.227 | 815,152 | 4.92 |
| ML-KEM-512 | encaps | host | 512 | 30 | 407.6 | 0.796 | 1,256,284 | 7.59 |
| ML-KEM-512 | encaps | host | 1024 | 30 | 617.7 | 0.603 | 1,657,776 | 10.01 |
| ML-KEM-512 | encaps | host | 2048 | 30 | 989.2 | 0.483 | 2,070,409 | 12.51 |
| ML-KEM-512 | encaps | host | 4096 | 30 | 1,717.9 | 0.419 | 2,384,370 | 14.40 |
| ML-KEM-512 | encaps | host | 8192 | 30 | 3,228.9 | 0.394 | 2,537,087 | 15.32 |
| ML-KEM-512 | encaps | host | 16384 | 30 | 6,581.4 | 0.402 | 2,489,445 | 15.04 |
| ML-KEM-512 | encaps | host | 32768 | 30 | 12,822.3 | 0.391 | 2,555,545 | 15.44 |
| ML-KEM-512 | encaps | host | 65536 | 30 | 25,068.4 | 0.383 | 2,614,285 | 15.79 |
| ML-KEM-512 | decaps | device | 1 | 30 | 78.9 | 78.949 | 12,666 | 0.10 |
| ML-KEM-512 | decaps | device | 2 | 30 | 79.1 | 39.575 | 25,269 | 0.20 |
| ML-KEM-512 | decaps | device | 4 | 30 | 80.0 | 19.992 | 50,019 | 0.40 |
| ML-KEM-512 | decaps | device | 8 | 30 | 79.4 | 9.927 | 100,732 | 0.80 |
| ML-KEM-512 | decaps | device | 16 | 30 | 82.3 | 5.143 | 194,437 | 1.55 |
| ML-KEM-512 | decaps | device | 32 | 30 | 80.1 | 2.502 | 399,630 | 3.19 |
| ML-KEM-512 | decaps | device | 64 | 30 | 80.5 | 1.258 | 794,942 | 6.34 |
| ML-KEM-512 | decaps | device | 128 | 30 | 95.9 | 0.749 | 1,334,863 | 10.64 |
| ML-KEM-512 | decaps | device | 256 | 30 | 124.2 | 0.485 | 2,060,470 | 16.42 |
| ML-KEM-512 | decaps | device | 512 | 30 | 183.2 | 0.358 | 2,795,088 | 22.28 |
| ML-KEM-512 | decaps | device | 1024 | 30 | 299.9 | 0.293 | 3,414,842 | 27.22 |
| ML-KEM-512 | decaps | device | 2048 | 30 | 529.1 | 0.258 | 3,870,760 | 30.85 |
| ML-KEM-512 | decaps | device | 4096 | 30 | 999.5 | 0.244 | 4,098,086 | 32.66 |
| ML-KEM-512 | decaps | device | 8192 | 30 | 1,939.8 | 0.237 | 4,223,022 | 33.66 |
| ML-KEM-512 | decaps | device | 16384 | 30 | 4,144.6 | 0.253 | 3,953,108 | 31.51 |
| ML-KEM-512 | decaps | device | 32768 | 30 | 8,209.3 | 0.251 | 3,991,569 | 31.81 |
| ML-KEM-512 | decaps | device | 65536 | 30 | 16,081.2 | 0.245 | 4,075,316 | 32.48 |
| ML-KEM-512 | decaps | host | 1 | 30 | 87.3 | 87.324 | 11,452 | 0.09 |
| ML-KEM-512 | decaps | host | 2 | 30 | 84.1 | 42.045 | 23,784 | 0.19 |
| ML-KEM-512 | decaps | host | 4 | 30 | 82.1 | 20.522 | 48,727 | 0.39 |
| ML-KEM-512 | decaps | host | 8 | 30 | 82.8 | 10.351 | 96,608 | 0.77 |
| ML-KEM-512 | decaps | host | 16 | 30 | 84.9 | 5.303 | 188,559 | 1.50 |
| ML-KEM-512 | decaps | host | 32 | 30 | 85.2 | 2.664 | 375,437 | 2.99 |
| ML-KEM-512 | decaps | host | 64 | 30 | 129.0 | 2.015 | 496,224 | 3.95 |
| ML-KEM-512 | decaps | host | 128 | 30 | 153.2 | 1.197 | 835,545 | 6.66 |
| ML-KEM-512 | decaps | host | 256 | 30 | 221.7 | 0.866 | 1,154,698 | 9.20 |
| ML-KEM-512 | decaps | host | 512 | 30 | 342.2 | 0.668 | 1,496,260 | 11.93 |
| ML-KEM-512 | decaps | host | 1024 | 30 | 567.1 | 0.554 | 1,805,551 | 14.39 |
| ML-KEM-512 | decaps | host | 2048 | 30 | 1,042.6 | 0.509 | 1,964,366 | 15.66 |
| ML-KEM-512 | decaps | host | 4096 | 30 | 2,148.5 | 0.525 | 1,906,410 | 15.19 |
| ML-KEM-512 | decaps | host | 8192 | 30 | 4,020.3 | 0.491 | 2,037,668 | 16.24 |
| ML-KEM-512 | decaps | host | 16384 | 30 | 7,597.3 | 0.464 | 2,156,570 | 17.19 |
| ML-KEM-512 | decaps | host | 32768 | 30 | 15,269.0 | 0.466 | 2,146,053 | 17.10 |
| ML-KEM-512 | decaps | host | 65536 | 30 | 31,436.9 | 0.480 | 2,084,684 | 16.61 |
| ML-KEM-768 | keygen | device | 1 | 30 | 109.0 | 108.974 | 9,177 | 0.11 |
| ML-KEM-768 | keygen | device | 2 | 30 | 104.8 | 52.407 | 19,081 | 0.22 |
| ML-KEM-768 | keygen | device | 4 | 30 | 103.9 | 25.979 | 38,493 | 0.45 |
| ML-KEM-768 | keygen | device | 8 | 30 | 104.2 | 13.024 | 76,780 | 0.90 |
| ML-KEM-768 | keygen | device | 16 | 30 | 107.3 | 6.705 | 149,137 | 1.75 |
| ML-KEM-768 | keygen | device | 32 | 30 | 102.2 | 3.195 | 313,007 | 3.67 |
| ML-KEM-768 | keygen | device | 64 | 30 | 115.9 | 1.811 | 552,157 | 6.47 |
| ML-KEM-768 | keygen | device | 128 | 30 | 122.9 | 0.960 | 1,041,760 | 12.20 |
| ML-KEM-768 | keygen | device | 256 | 30 | 145.2 | 0.567 | 1,762,800 | 20.64 |
| ML-KEM-768 | keygen | device | 512 | 30 | 217.9 | 0.426 | 2,349,502 | 27.51 |
| ML-KEM-768 | keygen | device | 1024 | 30 | 334.9 | 0.327 | 3,057,246 | 35.80 |
| ML-KEM-768 | keygen | device | 2048 | 30 | 577.3 | 0.282 | 3,547,703 | 41.54 |
| ML-KEM-768 | keygen | device | 4096 | 30 | 1,075.1 | 0.262 | 3,809,896 | 44.61 |
| ML-KEM-768 | keygen | device | 8192 | 30 | 2,185.1 | 0.267 | 3,749,044 | 43.90 |
| ML-KEM-768 | keygen | device | 16384 | 30 | 4,586.1 | 0.280 | 3,572,544 | 41.83 |
| ML-KEM-768 | keygen | device | 32768 | 30 | 9,021.4 | 0.275 | 3,632,257 | 42.53 |
| ML-KEM-768 | keygen | device | 65536 | 30 | 17,958.1 | 0.274 | 3,649,386 | 42.73 |
| ML-KEM-768 | keygen | host | 1 | 30 | 158.9 | 158.904 | 6,293 | 0.07 |
| ML-KEM-768 | keygen | host | 2 | 30 | 165.4 | 82.692 | 12,093 | 0.14 |
| ML-KEM-768 | keygen | host | 4 | 30 | 158.7 | 39.671 | 25,207 | 0.30 |
| ML-KEM-768 | keygen | host | 8 | 30 | 161.8 | 20.231 | 49,429 | 0.58 |
| ML-KEM-768 | keygen | host | 16 | 30 | 164.2 | 10.261 | 97,461 | 1.14 |
| ML-KEM-768 | keygen | host | 32 | 30 | 176.3 | 5.509 | 181,521 | 2.13 |
| ML-KEM-768 | keygen | host | 64 | 30 | 188.9 | 2.952 | 338,744 | 3.97 |
| ML-KEM-768 | keygen | host | 128 | 30 | 248.3 | 1.940 | 515,489 | 6.04 |
| ML-KEM-768 | keygen | host | 256 | 30 | 325.4 | 1.271 | 786,707 | 9.21 |
| ML-KEM-768 | keygen | host | 512 | 30 | 514.6 | 1.005 | 994,976 | 11.65 |
| ML-KEM-768 | keygen | host | 1024 | 30 | 846.2 | 0.826 | 1,210,091 | 14.17 |
| ML-KEM-768 | keygen | host | 2048 | 30 | 1,483.4 | 0.724 | 1,380,631 | 16.17 |
| ML-KEM-768 | keygen | host | 4096 | 30 | 2,722.6 | 0.665 | 1,504,429 | 17.62 |
| ML-KEM-768 | keygen | host | 8192 | 30 | 5,120.2 | 0.625 | 1,599,932 | 18.74 |
| ML-KEM-768 | keygen | host | 16384 | 30 | 9,942.9 | 0.607 | 1,647,817 | 19.30 |
| ML-KEM-768 | keygen | host | 32768 | 30 | 20,012.5 | 0.611 | 1,637,374 | 19.17 |
| ML-KEM-768 | keygen | host | 65536 | 30 | 39,784.8 | 0.607 | 1,647,262 | 19.29 |
| ML-KEM-768 | encaps | device | 1 | 30 | 102.9 | 102.934 | 9,715 | 0.12 |
| ML-KEM-768 | encaps | device | 2 | 30 | 101.4 | 50.707 | 19,721 | 0.24 |
| ML-KEM-768 | encaps | device | 4 | 30 | 101.1 | 25.285 | 39,549 | 0.48 |
| ML-KEM-768 | encaps | device | 8 | 30 | 102.3 | 12.788 | 78,198 | 0.96 |
| ML-KEM-768 | encaps | device | 16 | 30 | 103.0 | 6.441 | 155,266 | 1.90 |
| ML-KEM-768 | encaps | device | 32 | 30 | 105.9 | 3.309 | 302,160 | 3.70 |
| ML-KEM-768 | encaps | device | 64 | 30 | 109.7 | 1.715 | 583,229 | 7.14 |
| ML-KEM-768 | encaps | device | 128 | 30 | 120.0 | 0.938 | 1,066,320 | 13.06 |
| ML-KEM-768 | encaps | device | 256 | 30 | 144.5 | 0.564 | 1,771,522 | 21.70 |
| ML-KEM-768 | encaps | device | 512 | 30 | 229.4 | 0.448 | 2,231,929 | 27.34 |
| ML-KEM-768 | encaps | device | 1024 | 30 | 359.4 | 0.351 | 2,849,336 | 34.90 |
| ML-KEM-768 | encaps | device | 2048 | 30 | 657.9 | 0.321 | 3,112,916 | 38.13 |
| ML-KEM-768 | encaps | device | 4096 | 30 | 1,252.7 | 0.306 | 3,269,792 | 40.05 |
| ML-KEM-768 | encaps | device | 8192 | 30 | 2,708.8 | 0.331 | 3,024,267 | 37.04 |
| ML-KEM-768 | encaps | device | 16384 | 30 | 5,033.6 | 0.307 | 3,254,921 | 39.87 |
| ML-KEM-768 | encaps | device | 32768 | 30 | 9,980.3 | 0.305 | 3,283,273 | 40.22 |
| ML-KEM-768 | encaps | device | 65536 | 30 | 19,850.1 | 0.303 | 3,301,552 | 40.44 |
| ML-KEM-768 | encaps | host | 1 | 30 | 161.0 | 161.014 | 6,211 | 0.08 |
| ML-KEM-768 | encaps | host | 2 | 30 | 158.0 | 79.024 | 12,654 | 0.16 |
| ML-KEM-768 | encaps | host | 4 | 30 | 159.7 | 39.927 | 25,046 | 0.31 |
| ML-KEM-768 | encaps | host | 8 | 30 | 161.7 | 20.216 | 49,466 | 0.61 |
| ML-KEM-768 | encaps | host | 16 | 30 | 164.9 | 10.309 | 97,000 | 1.19 |
| ML-KEM-768 | encaps | host | 32 | 30 | 188.8 | 5.899 | 169,506 | 2.08 |
| ML-KEM-768 | encaps | host | 64 | 30 | 179.5 | 2.804 | 356,590 | 4.37 |
| ML-KEM-768 | encaps | host | 128 | 30 | 308.9 | 2.413 | 414,364 | 5.08 |
| ML-KEM-768 | encaps | host | 256 | 30 | 361.5 | 1.412 | 708,197 | 8.67 |
| ML-KEM-768 | encaps | host | 512 | 30 | 511.9 | 1.000 | 1,000,175 | 12.25 |
| ML-KEM-768 | encaps | host | 1024 | 30 | 802.1 | 0.783 | 1,276,652 | 15.64 |
| ML-KEM-768 | encaps | host | 2048 | 30 | 1,253.2 | 0.612 | 1,634,227 | 20.02 |
| ML-KEM-768 | encaps | host | 4096 | 30 | 2,317.8 | 0.566 | 1,767,179 | 21.65 |
| ML-KEM-768 | encaps | host | 8192 | 30 | 4,781.5 | 0.584 | 1,713,277 | 20.99 |
| ML-KEM-768 | encaps | host | 16384 | 30 | 8,484.8 | 0.518 | 1,930,987 | 23.65 |
| ML-KEM-768 | encaps | host | 32768 | 30 | 16,961.4 | 0.518 | 1,931,916 | 23.66 |
| ML-KEM-768 | encaps | host | 65536 | 30 | 33,734.2 | 0.515 | 1,942,720 | 23.80 |
| ML-KEM-768 | decaps | device | 1 | 30 | 95.9 | 95.939 | 10,423 | 0.16 |
| ML-KEM-768 | decaps | device | 2 | 30 | 97.3 | 48.660 | 20,551 | 0.32 |
| ML-KEM-768 | decaps | device | 4 | 30 | 96.0 | 23.998 | 41,669 | 0.65 |
| ML-KEM-768 | decaps | device | 8 | 30 | 97.1 | 12.132 | 82,428 | 1.29 |
| ML-KEM-768 | decaps | device | 16 | 30 | 98.0 | 6.125 | 163,267 | 2.56 |
| ML-KEM-768 | decaps | device | 32 | 30 | 102.1 | 3.190 | 313,497 | 4.91 |
| ML-KEM-768 | decaps | device | 64 | 30 | 102.8 | 1.607 | 622,423 | 9.75 |
| ML-KEM-768 | decaps | device | 128 | 30 | 118.5 | 0.926 | 1,079,863 | 16.91 |
| ML-KEM-768 | decaps | device | 256 | 30 | 162.3 | 0.634 | 1,576,957 | 24.70 |
| ML-KEM-768 | decaps | device | 512 | 30 | 246.7 | 0.482 | 2,075,290 | 32.50 |
| ML-KEM-768 | decaps | device | 1024 | 30 | 392.4 | 0.383 | 2,609,802 | 40.87 |
| ML-KEM-768 | decaps | device | 2048 | 30 | 710.0 | 0.347 | 2,884,511 | 45.17 |
| ML-KEM-768 | decaps | device | 4096 | 30 | 1,350.8 | 0.330 | 3,032,342 | 47.49 |
| ML-KEM-768 | decaps | device | 8192 | 30 | 2,861.0 | 0.349 | 2,863,346 | 44.84 |
| ML-KEM-768 | decaps | device | 16384 | 30 | 5,478.6 | 0.334 | 2,990,526 | 46.83 |
| ML-KEM-768 | decaps | device | 32768 | 30 | 10,881.6 | 0.332 | 3,011,320 | 47.16 |
| ML-KEM-768 | decaps | device | 65536 | 30 | 21,631.9 | 0.330 | 3,029,597 | 47.44 |
| ML-KEM-768 | decaps | host | 1 | 30 | 101.3 | 101.319 | 9,870 | 0.15 |
| ML-KEM-768 | decaps | host | 2 | 30 | 99.9 | 49.934 | 20,026 | 0.31 |
| ML-KEM-768 | decaps | host | 4 | 30 | 100.6 | 25.154 | 39,756 | 0.62 |
| ML-KEM-768 | decaps | host | 8 | 30 | 104.9 | 13.112 | 76,267 | 1.19 |
| ML-KEM-768 | decaps | host | 16 | 30 | 99.9 | 6.241 | 160,226 | 2.51 |
| ML-KEM-768 | decaps | host | 32 | 30 | 150.7 | 4.708 | 212,408 | 3.33 |
| ML-KEM-768 | decaps | host | 64 | 30 | 164.3 | 2.568 | 389,440 | 6.10 |
| ML-KEM-768 | decaps | host | 128 | 30 | 186.6 | 1.458 | 685,983 | 10.74 |
| ML-KEM-768 | decaps | host | 256 | 30 | 274.2 | 1.071 | 933,734 | 14.62 |
| ML-KEM-768 | decaps | host | 512 | 30 | 501.3 | 0.979 | 1,021,406 | 16.00 |
| ML-KEM-768 | decaps | host | 1024 | 30 | 799.3 | 0.781 | 1,281,148 | 20.06 |
| ML-KEM-768 | decaps | host | 2048 | 30 | 1,346.7 | 0.658 | 1,520,791 | 23.82 |
| ML-KEM-768 | decaps | host | 4096 | 30 | 2,743.8 | 0.670 | 1,492,801 | 23.38 |
| ML-KEM-768 | decaps | host | 8192 | 30 | 5,551.8 | 0.678 | 1,475,551 | 23.11 |
| ML-KEM-768 | decaps | host | 16384 | 30 | 10,642.7 | 0.650 | 1,539,456 | 24.11 |
| ML-KEM-768 | decaps | host | 32768 | 30 | 21,163.4 | 0.646 | 1,548,334 | 24.25 |
| ML-KEM-768 | decaps | host | 65536 | 30 | 42,605.2 | 0.650 | 1,538,216 | 24.09 |
| ML-KEM-1024 | keygen | device | 1 | 30 | 122.8 | 122.774 | 8,145 | 0.13 |
| ML-KEM-1024 | keygen | device | 2 | 30 | 122.8 | 61.397 | 16,287 | 0.26 |
| ML-KEM-1024 | keygen | device | 4 | 30 | 126.4 | 31.595 | 31,651 | 0.50 |
| ML-KEM-1024 | keygen | device | 8 | 30 | 131.7 | 16.463 | 60,742 | 0.96 |
| ML-KEM-1024 | keygen | device | 16 | 30 | 128.6 | 8.035 | 124,456 | 1.97 |
| ML-KEM-1024 | keygen | device | 32 | 30 | 116.9 | 3.655 | 273,635 | 4.32 |
| ML-KEM-1024 | keygen | device | 64 | 30 | 121.6 | 1.899 | 526,498 | 8.32 |
| ML-KEM-1024 | keygen | device | 128 | 30 | 139.0 | 1.086 | 920,936 | 14.55 |
| ML-KEM-1024 | keygen | device | 256 | 30 | 175.1 | 0.684 | 1,462,076 | 23.10 |
| ML-KEM-1024 | keygen | device | 512 | 30 | 281.4 | 0.550 | 1,819,749 | 28.75 |
| ML-KEM-1024 | keygen | device | 1024 | 30 | 437.6 | 0.427 | 2,340,004 | 36.97 |
| ML-KEM-1024 | keygen | device | 2048 | 30 | 808.7 | 0.395 | 2,532,599 | 40.02 |
| ML-KEM-1024 | keygen | device | 4096 | 30 | 1,554.9 | 0.380 | 2,634,268 | 41.62 |
| ML-KEM-1024 | keygen | device | 8192 | 30 | 3,301.4 | 0.403 | 2,481,334 | 39.21 |
| ML-KEM-1024 | keygen | device | 16384 | 30 | 6,456.6 | 0.394 | 2,537,542 | 40.09 |
| ML-KEM-1024 | keygen | device | 32768 | 30 | 12,992.7 | 0.397 | 2,522,027 | 39.85 |
| ML-KEM-1024 | keygen | device | 65536 | 30 | 25,673.3 | 0.392 | 2,552,690 | 40.33 |
| ML-KEM-1024 | keygen | host | 1 | 30 | 176.8 | 176.844 | 5,655 | 0.09 |
| ML-KEM-1024 | keygen | host | 2 | 30 | 176.3 | 88.142 | 11,345 | 0.18 |
| ML-KEM-1024 | keygen | host | 4 | 30 | 180.0 | 44.992 | 22,226 | 0.35 |
| ML-KEM-1024 | keygen | host | 8 | 30 | 201.1 | 25.141 | 39,776 | 0.63 |
| ML-KEM-1024 | keygen | host | 16 | 30 | 190.6 | 11.914 | 83,933 | 1.33 |
| ML-KEM-1024 | keygen | host | 32 | 30 | 184.5 | 5.765 | 173,471 | 2.74 |
| ML-KEM-1024 | keygen | host | 64 | 30 | 186.8 | 2.919 | 342,623 | 5.41 |
| ML-KEM-1024 | keygen | host | 128 | 30 | 275.9 | 2.156 | 463,882 | 7.33 |
| ML-KEM-1024 | keygen | host | 256 | 30 | 379.2 | 1.481 | 675,094 | 10.67 |
| ML-KEM-1024 | keygen | host | 512 | 30 | 599.7 | 1.171 | 853,775 | 13.49 |
| ML-KEM-1024 | keygen | host | 1024 | 30 | 1,116.2 | 1.090 | 917,394 | 14.49 |
| ML-KEM-1024 | keygen | host | 2048 | 30 | 1,886.5 | 0.921 | 1,085,618 | 17.15 |
| ML-KEM-1024 | keygen | host | 4096 | 30 | 3,581.6 | 0.874 | 1,143,616 | 18.07 |
| ML-KEM-1024 | keygen | host | 8192 | 30 | 7,333.9 | 0.895 | 1,117,000 | 17.65 |
| ML-KEM-1024 | keygen | host | 16384 | 30 | 14,252.8 | 0.870 | 1,149,529 | 18.16 |
| ML-KEM-1024 | keygen | host | 32768 | 30 | 27,348.2 | 0.835 | 1,198,176 | 18.93 |
| ML-KEM-1024 | keygen | host | 65536 | 30 | 54,509.4 | 0.832 | 1,202,288 | 19.00 |
| ML-KEM-1024 | encaps | device | 1 | 30 | 114.0 | 113.999 | 8,772 | 0.15 |
| ML-KEM-1024 | encaps | device | 2 | 30 | 114.0 | 57.010 | 17,541 | 0.29 |
| ML-KEM-1024 | encaps | device | 4 | 30 | 117.7 | 29.433 | 33,975 | 0.57 |
| ML-KEM-1024 | encaps | device | 8 | 30 | 121.9 | 15.241 | 65,612 | 1.09 |
| ML-KEM-1024 | encaps | device | 16 | 30 | 112.5 | 7.033 | 142,179 | 2.37 |
| ML-KEM-1024 | encaps | device | 32 | 30 | 113.1 | 3.534 | 282,963 | 4.72 |
| ML-KEM-1024 | encaps | device | 64 | 30 | 119.6 | 1.869 | 535,099 | 8.93 |
| ML-KEM-1024 | encaps | device | 128 | 30 | 138.4 | 1.082 | 924,532 | 15.42 |
| ML-KEM-1024 | encaps | device | 256 | 30 | 197.9 | 0.773 | 1,293,658 | 21.58 |
| ML-KEM-1024 | encaps | device | 512 | 30 | 311.2 | 0.608 | 1,645,347 | 27.44 |
| ML-KEM-1024 | encaps | device | 1024 | 30 | 499.2 | 0.487 | 2,051,364 | 34.22 |
| ML-KEM-1024 | encaps | device | 2048 | 30 | 945.0 | 0.461 | 2,167,296 | 36.15 |
| ML-KEM-1024 | encaps | device | 4096 | 30 | 1,816.6 | 0.444 | 2,254,744 | 37.61 |
| ML-KEM-1024 | encaps | device | 8192 | 30 | 3,771.3 | 0.460 | 2,172,189 | 36.23 |
| ML-KEM-1024 | encaps | device | 16384 | 30 | 7,204.5 | 0.440 | 2,274,137 | 37.93 |
| ML-KEM-1024 | encaps | device | 32768 | 30 | 14,356.3 | 0.438 | 2,282,489 | 38.07 |
| ML-KEM-1024 | encaps | device | 65536 | 30 | 28,572.8 | 0.436 | 2,293,649 | 38.26 |
| ML-KEM-1024 | encaps | host | 1 | 30 | 174.7 | 174.673 | 5,725 | 0.10 |
| ML-KEM-1024 | encaps | host | 2 | 30 | 170.2 | 85.084 | 11,753 | 0.20 |
| ML-KEM-1024 | encaps | host | 4 | 30 | 190.7 | 47.682 | 20,972 | 0.35 |
| ML-KEM-1024 | encaps | host | 8 | 30 | 184.9 | 23.115 | 43,261 | 0.72 |
| ML-KEM-1024 | encaps | host | 16 | 30 | 182.3 | 11.393 | 87,775 | 1.46 |
| ML-KEM-1024 | encaps | host | 32 | 30 | 168.2 | 5.256 | 190,268 | 3.17 |
| ML-KEM-1024 | encaps | host | 64 | 30 | 180.4 | 2.819 | 354,721 | 5.92 |
| ML-KEM-1024 | encaps | host | 128 | 30 | 338.9 | 2.647 | 377,724 | 6.30 |
| ML-KEM-1024 | encaps | host | 256 | 30 | 436.0 | 1.703 | 587,182 | 9.79 |
| ML-KEM-1024 | encaps | host | 512 | 30 | 655.5 | 1.280 | 781,055 | 13.03 |
| ML-KEM-1024 | encaps | host | 1024 | 30 | 977.5 | 0.955 | 1,047,521 | 17.47 |
| ML-KEM-1024 | encaps | host | 2048 | 30 | 1,722.6 | 0.841 | 1,188,911 | 19.83 |
| ML-KEM-1024 | encaps | host | 4096 | 30 | 3,316.0 | 0.810 | 1,235,229 | 20.60 |
| ML-KEM-1024 | encaps | host | 8192 | 30 | 6,238.4 | 0.762 | 1,313,160 | 21.90 |
| ML-KEM-1024 | encaps | host | 16384 | 30 | 11,943.5 | 0.729 | 1,371,797 | 22.88 |
| ML-KEM-1024 | encaps | host | 32768 | 30 | 24,328.8 | 0.742 | 1,346,879 | 22.47 |
| ML-KEM-1024 | encaps | host | 65536 | 30 | 48,076.2 | 0.734 | 1,363,169 | 22.74 |
| ML-KEM-1024 | decaps | device | 1 | 30 | 109.3 | 109.304 | 9,149 | 0.19 |
| ML-KEM-1024 | decaps | device | 2 | 30 | 109.6 | 54.809 | 18,245 | 0.37 |
| ML-KEM-1024 | decaps | device | 4 | 30 | 128.3 | 32.085 | 31,167 | 0.64 |
| ML-KEM-1024 | decaps | device | 8 | 30 | 110.7 | 13.841 | 72,248 | 1.48 |
| ML-KEM-1024 | decaps | device | 16 | 30 | 108.2 | 6.761 | 147,896 | 3.04 |
| ML-KEM-1024 | decaps | device | 32 | 30 | 108.7 | 3.398 | 294,283 | 6.04 |
| ML-KEM-1024 | decaps | device | 64 | 30 | 113.8 | 1.778 | 562,346 | 11.55 |
| ML-KEM-1024 | decaps | device | 128 | 30 | 142.5 | 1.113 | 898,283 | 18.45 |
| ML-KEM-1024 | decaps | device | 256 | 30 | 203.0 | 0.793 | 1,260,845 | 25.90 |
| ML-KEM-1024 | decaps | device | 512 | 30 | 344.8 | 0.673 | 1,484,781 | 30.50 |
| ML-KEM-1024 | decaps | device | 1024 | 30 | 594.5 | 0.581 | 1,722,354 | 35.38 |
| ML-KEM-1024 | decaps | device | 2048 | 30 | 1,106.5 | 0.540 | 1,850,965 | 38.02 |
| ML-KEM-1024 | decaps | device | 4096 | 30 | 2,137.9 | 0.522 | 1,915,898 | 39.35 |
| ML-KEM-1024 | decaps | device | 8192 | 30 | 4,462.7 | 0.545 | 1,835,662 | 37.70 |
| ML-KEM-1024 | decaps | device | 16384 | 30 | 8,795.6 | 0.537 | 1,862,745 | 38.26 |
| ML-KEM-1024 | decaps | device | 32768 | 30 | 17,322.0 | 0.529 | 1,891,703 | 38.85 |
| ML-KEM-1024 | decaps | device | 65536 | 30 | 34,814.5 | 0.531 | 1,882,434 | 38.66 |
| ML-KEM-1024 | decaps | host | 1 | 30 | 118.6 | 118.559 | 8,435 | 0.17 |
| ML-KEM-1024 | decaps | host | 2 | 30 | 113.1 | 56.539 | 17,687 | 0.36 |
| ML-KEM-1024 | decaps | host | 4 | 30 | 114.4 | 28.597 | 34,968 | 0.72 |
| ML-KEM-1024 | decaps | host | 8 | 30 | 123.3 | 15.411 | 64,888 | 1.33 |
| ML-KEM-1024 | decaps | host | 16 | 30 | 123.5 | 7.719 | 129,550 | 2.66 |
| ML-KEM-1024 | decaps | host | 32 | 30 | 158.0 | 4.937 | 202,559 | 4.16 |
| ML-KEM-1024 | decaps | host | 64 | 30 | 175.2 | 2.737 | 365,393 | 7.50 |
| ML-KEM-1024 | decaps | host | 128 | 30 | 238.4 | 1.863 | 536,883 | 11.03 |
| ML-KEM-1024 | decaps | host | 256 | 30 | 356.1 | 1.391 | 718,896 | 14.77 |
| ML-KEM-1024 | decaps | host | 512 | 30 | 613.3 | 1.198 | 834,768 | 17.15 |
| ML-KEM-1024 | decaps | host | 1024 | 30 | 1,085.8 | 1.060 | 943,114 | 19.37 |
| ML-KEM-1024 | decaps | host | 2048 | 30 | 2,065.5 | 1.009 | 991,536 | 20.37 |
| ML-KEM-1024 | decaps | host | 4096 | 30 | 4,111.4 | 1.004 | 996,261 | 20.46 |
| ML-KEM-1024 | decaps | host | 8192 | 30 | 8,232.9 | 1.005 | 995,030 | 20.44 |
| ML-KEM-1024 | decaps | host | 16384 | 30 | 15,876.8 | 0.969 | 1,031,945 | 21.20 |
| ML-KEM-1024 | decaps | host | 32768 | 30 | 32,584.7 | 0.994 | 1,005,625 | 20.65 |
| ML-KEM-1024 | decaps | host | 65536 | 30 | 62,567.8 | 0.955 | 1,047,439 | 21.51 |
