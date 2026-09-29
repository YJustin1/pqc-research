# Memory footprint (valgrind massif) — grape-nuts

2026-09-29T08:17:00+00:00 · Intel(R) Xeon(R) W-1270 CPU @ 3.40GHz · cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0 · valgrind-3.22.0 · liboqs `0.16.0-38-gadbeba1ef`

Stack and heap are **whole-process** peaks of liboqs' `test_kem_mem`
under massif, so they include the test program's own buffers and
start-up code, not only the liboqs operation. Each figure is the
maximum over repeated runs; `memory.csv` also has the minimum. See
`bench/memory/README.md`.

## Object sizes (bytes)

| Parameter set | public key | secret key | ciphertext | shared secret |
| --- | ---: | ---: | ---: | ---: |
| ML-KEM-512 | 800 | 1,632 | 768 | 32 |
| ML-KEM-768 | 1,184 | 2,400 | 1,088 | 32 |
| ML-KEM-1024 | 1,568 | 3,168 | 1,568 | 32 |
| Classic-McEliece-348864 | 261,120 | 6,492 | 96 | 32 |
| Classic-McEliece-348864f | 261,120 | 6,492 | 96 | 32 |
| Classic-McEliece-460896 | 524,160 | 13,608 | 156 | 32 |
| Classic-McEliece-460896f | 524,160 | 13,608 | 156 | 32 |
| Classic-McEliece-6688128 | 1,044,992 | 13,932 | 208 | 32 |
| Classic-McEliece-6688128f | 1,044,992 | 13,932 | 208 | 32 |
| Classic-McEliece-6960119 | 1,047,319 | 13,948 | 194 | 32 |
| Classic-McEliece-6960119f | 1,047,319 | 13,948 | 194 | 32 |
| Classic-McEliece-8192128 | 1,357,824 | 14,120 | 208 | 32 |
| Classic-McEliece-8192128f | 1,357,824 | 14,120 | 208 | 32 |
| NTRU-HPS-2048-509 | 699 | 935 | 699 | 32 |
| NTRU-HPS-2048-677 | 930 | 1,234 | 930 | 32 |
| NTRU-HPS-4096-821 | 1,230 | 1,590 | 1,230 | 32 |
| NTRU-HPS-4096-1229 | 1,842 | 2,366 | 1,842 | 32 |
| NTRU-HRSS-701 | 1,138 | 1,450 | 1,138 | 32 |
| NTRU-HRSS-1373 | 2,401 | 2,983 | 2,401 | 32 |

## Peak stack and heap per operation — native (bytes)

| Parameter set | keygen stack | encaps stack | decaps stack | keygen heap | encaps heap | decaps heap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ML-KEM-512 | 10,280 | 12,904 | 13,640 | 11,208 | 12,008 | 12,040 |
| ML-KEM-768 | 14,664 | 17,768 | 18,824 | 12,360 | 13,480 | 13,512 |
| ML-KEM-1024 | 19,688 | 23,304 | 24,840 | 13,512 | 15,112 | 15,144 |
| Classic-McEliece-348864 | 455,568 | 7,680 | 43,088 | 271,820 | 276,516 | 272,452 |
| Classic-McEliece-348864f | 480,336 | 7,680 | 43,088 | 271,820 | 276,516 | 272,452 |
| Classic-McEliece-460896 | 693,936 | 7,680 | 81,456 | 541,976 | 546,732 | 542,420 |
| Classic-McEliece-460896f | 694,128 | 7,680 | 81,456 | 541,976 | 546,732 | 542,420 |
| Classic-McEliece-6688128 | 975,600 | 7,680 | 94,448 | 1,063,356 | 1,067,940 | 1,063,628 |
| Classic-McEliece-6688128f | 975,824 | 7,680 | 94,448 | 1,063,132 | 1,067,940 | 1,063,628 |
| Classic-McEliece-6960119 | 1,119,824 | 7,680 | 82,096 | 1,065,475 | 1,070,269 | 1,065,957 |
| Classic-McEliece-6960119f | 1,119,888 | 7,680 | 82,096 | 1,065,475 | 1,070,269 | 1,065,957 |
| Classic-McEliece-8192128 | 1,295,280 | 7,680 | 133,712 | 1,376,152 | 1,380,960 | 1,376,648 |
| Classic-McEliece-8192128f | 1,295,504 | 7,680 | 133,712 | 1,376,152 | 1,380,960 | 1,376,648 |
| NTRU-HPS-2048-509 | 35,888 | 30,928 | 29,264 | 6,314 | 11,141 | 11,173 |
| NTRU-HPS-2048-677 | 51,088 | 44,272 | 42,032 | 6,372 | 11,902 | 7,838 |
| NTRU-HPS-4096-821 | 64,432 | 56,400 | 53,808 | 11,596 | 12,858 | 12,890 |
| NTRU-HPS-4096-1229 | 62,168 | 50,264 | 46,360 | 8,416 | 14,858 | 10,794 |
| NTRU-HRSS-701 | 49,280 | 42,464 | 42,272 | 11,364 | 12,534 | 8,470 |
| NTRU-HRSS-1373 | 72,576 | 59,264 | 59,040 | 9,592 | 16,593 | 12,281 |

## Peak stack and heap per operation — generic (bytes)

| Parameter set | keygen stack | encaps stack | decaps stack | keygen heap | encaps heap | decaps heap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ML-KEM-512 | 9,328 | 11,984 | 12,688 | 11,208 | 12,008 | 8,304 |
| ML-KEM-768 | 13,712 | 16,848 | 17,872 | 12,360 | 13,480 | 9,776 |
| ML-KEM-1024 | 18,768 | 22,416 | 23,920 | 13,512 | 15,112 | 11,408 |
| Classic-McEliece-348864 | 424,560 | 7,680 | 24,320 | 271,820 | 276,516 | 271,980 |
| Classic-McEliece-348864f | 425,424 | 7,680 | 24,320 | 271,820 | 276,516 | 271,980 |
| Classic-McEliece-460896 | 887,152 | 7,680 | 38,880 | 541,976 | 546,732 | 542,196 |
| Classic-McEliece-460896f | 888,016 | 7,680 | 38,880 | 541,976 | 546,732 | 542,196 |
| Classic-McEliece-6688128 | 1,568,256 | 7,680 | 48,416 | 1,063,132 | 1,067,940 | 1,063,404 |
| Classic-McEliece-6688128f | 1,569,120 | 7,680 | 48,416 | 1,063,132 | 1,067,940 | 1,063,404 |
| Classic-McEliece-6960119 | 1,524,080 | 7,680 | 49,488 | 1,065,475 | 1,070,269 | 1,065,733 |
| Classic-McEliece-6960119f | 1,524,976 | 7,680 | 49,488 | 1,065,475 | 1,070,269 | 1,065,733 |
| Classic-McEliece-8192128 | 1,887,280 | 7,680 | 54,992 | 1,376,152 | 1,380,960 | 1,376,424 |
| Classic-McEliece-8192128f | 1,888,160 | 7,680 | 54,992 | 1,376,152 | 1,380,960 | 1,376,424 |
| NTRU-HPS-2048-509 | 29,488 | 24,512 | 22,944 | 5,842 | 11,141 | 6,829 |
| NTRU-HPS-2048-677 | 34,896 | 28,304 | 26,160 | 6,372 | 11,902 | 7,838 |
| NTRU-HPS-4096-821 | 41,552 | 33,584 | 31,056 | 7,028 | 12,858 | 8,794 |
| NTRU-HPS-4096-1229 | 61,920 | 50,032 | 46,160 | 8,416 | 14,858 | 14,890 |
| NTRU-HRSS-701 | 33,504 | 26,688 | 26,512 | 6,796 | 12,534 | 8,222 |
| NTRU-HRSS-1373 | 72,560 | 59,296 | 59,024 | 9,592 | 12,249 | 12,281 |

## Code size of each parameter set's own object files (bytes)

Excludes code shared between algorithms (SHA-3, RNG, common).

| Parameter set | native text | native data+bss | generic text | generic data+bss |
| --- | ---: | ---: | ---: | ---: |
| ML-KEM-512 | 82,605 | 0 | 29,481 | 0 |
| ML-KEM-768 | 79,275 | 0 | 29,735 | 0 |
| ML-KEM-1024 | 82,663 | 0 | 29,652 | 0 |
| Classic-McEliece-348864 | 105,408 | 384 | 32,709 | 0 |
| Classic-McEliece-348864f | 108,062 | 384 | 34,752 | 0 |
| Classic-McEliece-460896 | 128,973 | 384 | 33,367 | 0 |
| Classic-McEliece-460896f | 131,442 | 384 | 35,392 | 0 |
| Classic-McEliece-6688128 | 135,697 | 384 | 34,508 | 0 |
| Classic-McEliece-6688128f | 138,239 | 384 | 36,574 | 0 |
| Classic-McEliece-6960119 | 132,651 | 384 | 35,702 | 0 |
| Classic-McEliece-6960119f | 136,177 | 384 | 38,700 | 0 |
| Classic-McEliece-8192128 | 134,915 | 384 | 34,002 | 0 |
| Classic-McEliece-8192128f | 137,488 | 384 | 36,094 | 0 |
| NTRU-HPS-2048-509 | 136,809 | 25,952 | 59,359 | 0 |
| NTRU-HPS-2048-677 | 190,702 | 56,033 | 51,285 | 0 |
| NTRU-HPS-4096-821 | 243,473 | 81,088 | 55,466 | 0 |
| NTRU-HPS-4096-1229 | 62,126 | 0 | 36,534 | 0 |
| NTRU-HRSS-701 | 197,588 | 67,168 | 51,192 | 0 |
| NTRU-HRSS-1373 | 67,205 | 0 | 38,379 | 0 |
