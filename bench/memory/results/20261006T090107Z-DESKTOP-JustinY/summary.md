# Memory footprint (in-process) — DESKTOP-JustinY

2026-10-06T08:56:38+00:00 · AMD Ryzen 5 5600X 6-Core Processor · cc (Ubuntu 15.2.0-16ubuntu1) 15.2.0 · liboqs 0.16.0; OpenSSL 3.5.9 29 Sep 2026 · liboqs `0.16.0-38-gadbeba1ef`

Stack and heap of **single calls**, measured inside the process (see
`bench/memory/README.md`). *Steady* is a call after the first; *first*
is the first call in a fresh process, including any one-time setup the
library does on first use. Each figure is the maximum over repeated runs;
`memory.csv` also has the minimum.

## Object sizes (bytes)

| impl | set | public key | ciphertext | shared secret |
| --- | --- | ---: | ---: | ---: |
| liboqs | ML-KEM-512 | 800 | 768 | 32 |
| liboqs | ML-KEM-768 | 1184 | 1088 | 32 |
| liboqs | ML-KEM-1024 | 1568 | 1568 | 32 |
| liboqs | Classic-McEliece-348864 | 261120 | 96 | 32 |
| liboqs | Classic-McEliece-348864f | 261120 | 96 | 32 |
| liboqs | Classic-McEliece-460896 | 524160 | 156 | 32 |
| liboqs | Classic-McEliece-460896f | 524160 | 156 | 32 |
| liboqs | Classic-McEliece-6688128 | 1044992 | 208 | 32 |
| liboqs | Classic-McEliece-6688128f | 1044992 | 208 | 32 |
| liboqs | Classic-McEliece-6960119 | 1047319 | 194 | 32 |
| liboqs | Classic-McEliece-6960119f | 1047319 | 194 | 32 |
| liboqs | Classic-McEliece-8192128 | 1357824 | 208 | 32 |
| liboqs | Classic-McEliece-8192128f | 1357824 | 208 | 32 |
| liboqs | NTRU-HPS-2048-509 | 699 | 699 | 32 |
| liboqs | NTRU-HPS-2048-677 | 930 | 930 | 32 |
| liboqs | NTRU-HPS-4096-821 | 1230 | 1230 | 32 |
| liboqs | NTRU-HPS-4096-1229 | 1842 | 1842 | 32 |
| liboqs | NTRU-HRSS-701 | 1138 | 1138 | 32 |
| liboqs | NTRU-HRSS-1373 | 2401 | 2401 | 32 |
| openssl | X25519 | 32 | 32 | 32 |
| openssl | P-256 | 65 | 65 | 32 |
| openssl | RSA-2048 | 256 | 256 | 256 |
| openssl | RSA-3072 | 384 | 384 | 384 |
| openssl | ffdhe2048 | 256 | 256 | 256 |
| openssl | ffdhe3072 | 384 | 384 | 384 |
| openssl | ML-KEM-512 | 800 | 768 | 32 |
| openssl | ML-KEM-768 | 1184 | 1088 | 32 |
| openssl | ML-KEM-1024 | 1568 | 1568 | 32 |

## liboqs (native): stack and heap per call (bytes)

| set | keygen stack | encaps stack | decaps stack | keygen heap | encaps heap | decaps heap | first-call heap (keygen / encaps / decaps) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ML-KEM-512 | 10,072 | 12,760 | 13,400 | 832 | 832 | 832 | 832 / 832 / 832 |
| ML-KEM-768 | 14,424 | 17,592 | 18,552 | 832 | 832 | 832 | 832 / 832 / 832 |
| ML-KEM-1024 | 19,448 | 23,128 | 24,568 | 832 | 832 | 832 | 832 / 832 / 832 |
| Classic-McEliece-348864 | 455,264 | 2,688 | 42,752 | 224 | 224 | 224 | 224 / 224 / 224 |
| Classic-McEliece-348864f | 480,000 | 2,688 | 42,752 | 224 | 224 | 224 | 224 / 224 / 224 |
| Classic-McEliece-460896 | 693,560 | 3,664 | 81,048 | 224 | 224 | 224 | 224 / 224 / 224 |
| Classic-McEliece-460896f | 693,784 | 3,664 | 81,048 | 224 | 224 | 224 | 224 / 224 / 224 |
| Classic-McEliece-6688128 | 975,224 | 5,024 | 94,040 | 224 | 224 | 224 | 224 / 224 / 224 |
| Classic-McEliece-6688128f | 975,416 | 5,024 | 94,040 | 224 | 224 | 224 | 224 / 224 / 224 |
| Classic-McEliece-6960119 | 1,119,448 | 5,008 | 81,688 | 224 | 224 | 224 | 224 / 224 / 224 |
| Classic-McEliece-6960119f | 1,119,480 | 5,008 | 81,688 | 224 | 224 | 224 | 224 / 224 / 224 |
| Classic-McEliece-8192128 | 1,294,904 | 5,312 | 133,304 | 224 | 224 | 224 | 224 / 224 / 224 |
| Classic-McEliece-8192128f | 1,295,096 | 5,312 | 133,304 | 224 | 224 | 224 | 224 / 224 / 224 |
| NTRU-HPS-2048-509 | 35,544 | 30,584 | 28,952 | 0 | 224 | 224 | 0 / 224 / 224 |
| NTRU-HPS-2048-677 | 50,744 | 43,928 | 41,720 | 0 | 224 | 224 | 0 / 224 / 224 |
| NTRU-HPS-4096-821 | 64,088 | 56,056 | 53,496 | 0 | 224 | 224 | 0 / 224 / 224 |
| NTRU-HPS-4096-1229 | 61,824 | 49,888 | 46,048 | 0 | 224 | 224 | 0 / 224 / 224 |
| NTRU-HRSS-701 | 48,920 | 42,104 | 41,944 | 0 | 224 | 224 | 0 / 224 / 224 |
| NTRU-HRSS-1373 | 72,352 | 59,040 | 58,848 | 0 | 224 | 224 | 0 / 224 / 224 |

## liboqs (generic): stack and heap per call (bytes)

| set | keygen stack | encaps stack | decaps stack | keygen heap | encaps heap | decaps heap | first-call heap (keygen / encaps / decaps) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ML-KEM-512 | 9,128 | 11,784 | 12,456 | 832 | 832 | 832 | 832 / 832 / 832 |
| ML-KEM-768 | 13,480 | 16,648 | 17,640 | 832 | 832 | 832 | 832 / 832 / 832 |
| ML-KEM-1024 | 18,536 | 22,216 | 23,688 | 832 | 832 | 832 | 832 / 832 / 832 |
| Classic-McEliece-348864 | 423,988 | 1,776 | 24,000 | 224 | 224 | 224 | 224 / 224 / 224 |
| Classic-McEliece-348864f | 424,868 | 1,776 | 24,000 | 224 | 224 | 224 | 224 / 224 / 224 |
| Classic-McEliece-460896 | 886,560 | 2,496 | 38,544 | 224 | 224 | 224 | 224 / 224 / 224 |
| Classic-McEliece-460896f | 887,456 | 2,496 | 38,544 | 224 | 224 | 224 | 224 / 224 / 224 |
| Classic-McEliece-6688128 | 1,567,664 | 3,456 | 48,080 | 224 | 224 | 224 | 224 / 224 / 224 |
| Classic-McEliece-6688128f | 1,568,528 | 3,456 | 48,080 | 224 | 224 | 224 | 224 / 224 / 224 |
| Classic-McEliece-6960119 | 1,523,520 | 3,424 | 49,152 | 224 | 224 | 224 | 224 / 224 / 224 |
| Classic-McEliece-6960119f | 1,524,416 | 3,424 | 49,152 | 224 | 224 | 224 | 224 / 224 / 224 |
| Classic-McEliece-8192128 | 1,886,688 | 3,568 | 54,656 | 224 | 224 | 224 | 224 / 224 / 224 |
| Classic-McEliece-8192128f | 1,887,568 | 3,568 | 54,656 | 224 | 224 | 224 | 224 / 224 / 224 |
| NTRU-HPS-2048-509 | 29,128 | 24,152 | 22,520 | 0 | 224 | 224 | 0 / 224 / 224 |
| NTRU-HPS-2048-677 | 34,504 | 27,912 | 25,704 | 0 | 224 | 224 | 0 / 224 / 224 |
| NTRU-HPS-4096-821 | 41,160 | 33,192 | 30,616 | 0 | 224 | 224 | 0 / 224 / 224 |
| NTRU-HPS-4096-1229 | 61,560 | 49,672 | 45,752 | 0 | 224 | 224 | 0 / 224 / 224 |
| NTRU-HRSS-701 | 33,112 | 26,296 | 26,120 | 0 | 224 | 224 | 0 / 224 / 224 |
| NTRU-HRSS-1373 | 72,168 | 58,904 | 58,632 | 0 | 224 | 224 | 0 / 224 / 224 |

## openssl (default): stack and heap per call (bytes)

| set | keygen stack | encaps stack | decaps stack | keygen heap | encaps heap | decaps heap | first-call heap (keygen / encaps / decaps) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| X25519 | 1,632 | 2,544 | 2,560 | 441 | 1,159 | 1,127 | 147,625 / 198,862 / 51,171 |
| P-256 | 1,696 | 3,200 | 3,024 | 1,972 | 4,285 | 4,229 | 150,224 / 201,988 / 52,586 |
| RSA-2048 | 4,000 | 1,520 | 2,272 | 19,728 | 2,392 | 6,168 | 166,856 / 150,808 / 159,408 |
| RSA-3072 | 2,720 | 2,656 | 1,888 | 28,672 | 3,288 | 8,920 | 175,800 / 152,216 / 164,656 |
| ffdhe2048 | 1,728 | 1,952 | 1,248 | 8,904 | 8,904 | 7,632 | 156,032 / 159,262 / 13,814 |
| ffdhe3072 | 2,656 | 1,952 | 1,696 | 19,152 | 19,152 | 17,232 | 166,280 / 169,126 / 24,438 |
| ML-KEM-512 | 2,304 | 6,912 | 9,840 | 5,056 | 504 | 504 | 180,063 / 147,075 / 504 |
| ML-KEM-768 | 2,304 | 6,848 | 9,776 | 8,640 | 504 | 504 | 183,647 / 147,075 / 504 |
| ML-KEM-1024 | 2,304 | 6,848 | 9,776 | 13,248 | 504 | 504 | 188,255 / 147,075 / 504 |

## liboqs code size of each set's own object files (bytes)

Excludes code shared between algorithms (SHA-3, RNG, common). Not measured
for OpenSSL.

| set | native text | native data+bss | generic text | generic data+bss |
| --- | ---: | ---: | ---: | ---: |
| ML-KEM-512 | 86,759 | 8 | 30,714 | 8 |
| ML-KEM-768 | 80,043 | 8 | 30,823 | 8 |
| ML-KEM-1024 | 83,551 | 8 | 30,869 | 8 |
| Classic-McEliece-348864 | 107,641 | 392 | 33,649 | 8 |
| Classic-McEliece-348864f | 110,281 | 392 | 36,143 | 8 |
| Classic-McEliece-460896 | 134,710 | 392 | 36,501 | 8 |
| Classic-McEliece-460896f | 137,485 | 392 | 39,004 | 8 |
| Classic-McEliece-6688128 | 141,902 | 392 | 37,603 | 8 |
| Classic-McEliece-6688128f | 144,750 | 392 | 40,060 | 8 |
| Classic-McEliece-6960119 | 139,091 | 392 | 38,875 | 8 |
| Classic-McEliece-6960119f | 142,338 | 392 | 41,855 | 8 |
| Classic-McEliece-8192128 | 141,115 | 392 | 37,090 | 8 |
| Classic-McEliece-8192128f | 143,902 | 392 | 39,574 | 8 |
| NTRU-HPS-2048-509 | 138,246 | 25,960 | 59,362 | 8 |
| NTRU-HPS-2048-677 | 194,641 | 56,041 | 52,722 | 8 |
| NTRU-HPS-4096-821 | 245,984 | 81,096 | 57,222 | 8 |
| NTRU-HPS-4096-1229 | 59,233 | 8 | 38,325 | 8 |
| NTRU-HRSS-701 | 200,883 | 67,176 | 51,997 | 8 |
| NTRU-HRSS-1373 | 61,703 | 8 | 40,836 | 8 |

## Cross-check: liboqs native, in-process vs valgrind massif (bytes)

massif heap is the whole-process peak of `once` minus that of `baseline`;
massif stack is the whole-process peak of `once`, so it includes `main()` and
setup frames.

| set | op | in-process heap | massif heap Δ | in-process stack | massif stack |
| --- | --- | ---: | ---: | ---: | ---: |
| ML-KEM-512 | keygen | 832 | 832 | 10,072 | 10,648 |
| ML-KEM-512 | encaps | 832 | 832 | 12,760 | 13,336 |
| ML-KEM-512 | decaps | 832 | 832 | 13,400 | 13,976 |
| ML-KEM-768 | keygen | 832 | 832 | 14,424 | 15,000 |
| ML-KEM-768 | encaps | 832 | 832 | 17,592 | 18,168 |
| ML-KEM-768 | decaps | 832 | 832 | 18,552 | 19,128 |
| ML-KEM-1024 | keygen | 832 | 832 | 19,448 | 20,024 |
| ML-KEM-1024 | encaps | 832 | 832 | 23,128 | 23,704 |
| ML-KEM-1024 | decaps | 832 | 832 | 24,568 | 25,144 |
| Classic-McEliece-348864 | keygen | 224 | 0 | 455,264 | 455,968 |
| Classic-McEliece-348864 | encaps | 224 | 224 | 2,688 | 7,712 |
| Classic-McEliece-348864 | decaps | 224 | 224 | 42,752 | 43,488 |
| Classic-McEliece-348864f | keygen | 224 | 0 | 480,000 | 480,704 |
| Classic-McEliece-348864f | encaps | 224 | 224 | 2,688 | 7,712 |
| Classic-McEliece-348864f | decaps | 224 | 224 | 42,752 | 43,488 |
| Classic-McEliece-460896 | keygen | 224 | 0 | 693,560 | 694,240 |
| Classic-McEliece-460896 | encaps | 224 | 224 | 3,664 | 7,712 |
| Classic-McEliece-460896 | decaps | 224 | 224 | 81,048 | 81,728 |
| Classic-McEliece-460896f | keygen | 224 | 0 | 693,784 | 694,464 |
| Classic-McEliece-460896f | encaps | 224 | 224 | 3,664 | 7,712 |
| Classic-McEliece-460896f | decaps | 224 | 224 | 81,048 | 81,728 |
| Classic-McEliece-6688128 | keygen | 224 | 0 | 975,224 | 975,904 |
| Classic-McEliece-6688128 | encaps | 224 | 224 | 5,024 | 7,712 |
| Classic-McEliece-6688128 | decaps | 224 | 224 | 94,040 | 94,720 |
| Classic-McEliece-6688128f | keygen | 224 | 0 | 975,416 | 976,096 |
| Classic-McEliece-6688128f | encaps | 224 | 224 | 5,024 | 7,712 |
| Classic-McEliece-6688128f | decaps | 224 | 224 | 94,040 | 94,720 |
| Classic-McEliece-6960119 | keygen | 224 | 0 | 1,119,448 | 1,120,128 |
| Classic-McEliece-6960119 | encaps | 224 | 224 | 5,008 | 7,712 |
| Classic-McEliece-6960119 | decaps | 224 | 224 | 81,688 | 82,400 |
| Classic-McEliece-6960119f | keygen | 224 | 0 | 1,119,480 | 1,120,160 |
| Classic-McEliece-6960119f | encaps | 224 | 224 | 5,008 | 7,712 |
| Classic-McEliece-6960119f | decaps | 224 | 224 | 81,688 | 82,400 |
| Classic-McEliece-8192128 | keygen | 224 | 0 | 1,294,904 | 1,295,584 |
| Classic-McEliece-8192128 | encaps | 224 | 224 | 5,312 | 7,712 |
| Classic-McEliece-8192128 | decaps | 224 | 224 | 133,304 | 134,016 |
| Classic-McEliece-8192128f | keygen | 224 | 0 | 1,295,096 | 1,295,776 |
| Classic-McEliece-8192128f | encaps | 224 | 224 | 5,312 | 7,712 |
| Classic-McEliece-8192128f | decaps | 224 | 224 | 133,304 | 134,016 |
| NTRU-HPS-2048-509 | keygen | 0 | 0 | 35,544 | 36,240 |
| NTRU-HPS-2048-509 | encaps | 224 | 224 | 30,584 | 31,280 |
| NTRU-HPS-2048-509 | decaps | 224 | 224 | 28,952 | 29,648 |
| NTRU-HPS-2048-677 | keygen | 0 | 0 | 50,744 | 51,440 |
| NTRU-HPS-2048-677 | encaps | 224 | 224 | 43,928 | 44,624 |
| NTRU-HPS-2048-677 | decaps | 224 | 224 | 41,720 | 42,416 |
| NTRU-HPS-4096-821 | keygen | 0 | 0 | 64,088 | 64,784 |
| NTRU-HPS-4096-821 | encaps | 224 | 224 | 56,056 | 56,752 |
| NTRU-HPS-4096-821 | decaps | 224 | 224 | 53,496 | 54,192 |
| NTRU-HPS-4096-1229 | keygen | 0 | 0 | 61,824 | 62,520 |
| NTRU-HPS-4096-1229 | encaps | 224 | 224 | 49,888 | 50,584 |
| NTRU-HPS-4096-1229 | decaps | 224 | 224 | 46,048 | 46,744 |
| NTRU-HRSS-701 | keygen | 0 | 0 | 48,920 | 49,616 |
| NTRU-HRSS-701 | encaps | 224 | 224 | 42,104 | 42,800 |
| NTRU-HRSS-701 | decaps | 224 | 224 | 41,944 | 42,640 |
| NTRU-HRSS-1373 | keygen | 0 | 0 | 72,352 | 73,048 |
| NTRU-HRSS-1373 | encaps | 224 | 224 | 59,040 | 59,736 |
| NTRU-HRSS-1373 | decaps | 224 | 224 | 58,848 | 59,544 |
