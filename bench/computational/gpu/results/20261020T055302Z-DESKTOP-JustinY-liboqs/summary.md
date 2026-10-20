# API harness results — DESKTOP-JustinY

CPU: AMD Ryzen 5 5600X 6-Core Processor. Libraries: liboqs 0.16.0; OpenSSL 3.5.9 29 Sep 2026. liboqs revision `0.16.0-38-gadbeba1ef`, `icicle` build; GPU: NVIDIA GeForce RTX 3060 Ti, 617.42, 8.6.
Load average at start / end: `11.55 7.58 5.74 1/504 223711` / `5.68 6.60 5.50 2/507 224580`.
perf cycle counter available: yes (user-space only).

Times are medians over all samples from all runs; p10–p90 shows the spread. Between-run CV is the coefficient of variation of the per-run medians.

| impl | set | op | samples | median µs | p10–p90 µs | median TSC ticks | median perf cycles | between-run CV |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| liboqs | ML-KEM-512 | keygen | 10000 | 140.54 | 131.11–202.15 | 519813 | 571820 | 3.1% |
| liboqs | ML-KEM-512 | encaps | 10000 | 146.16 | 135.82–218.34 | 540607 | 585820 | 3.2% |
| liboqs | ML-KEM-512 | decaps | 10000 | 79.33 | 74.21–129.69 | 293318 | 302112 | 3.8% |
| liboqs | ML-KEM-768 | keygen | 10000 | 161.07 | 151.28–224.80 | 595737 | 681140 | 3.5% |
| liboqs | ML-KEM-768 | encaps | 10000 | 160.52 | 152.06–237.79 | 593702 | 670702 | 3.9% |
| liboqs | ML-KEM-768 | decaps | 10000 | 97.74 | 91.98–121.96 | 361453 | 400104 | 2.7% |
| liboqs | ML-KEM-1024 | keygen | 10000 | 177.36 | 166.65–257.30 | 656047 | 751735 | 3.0% |
| liboqs | ML-KEM-1024 | encaps | 10000 | 169.58 | 157.30–247.82 | 627261 | 698884 | 4.7% |
| liboqs | ML-KEM-1024 | decaps | 10000 | 108.34 | 99.74–142.24 | 400636 | 432081 | 6.7% |
