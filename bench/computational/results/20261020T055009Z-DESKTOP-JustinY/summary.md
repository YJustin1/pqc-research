# API harness results — DESKTOP-JustinY

CPU: AMD Ryzen 5 5600X 6-Core Processor. Libraries: liboqs 0.16.0; OpenSSL 3.5.9 29 Sep 2026. liboqs revision `0.16.0-38-gadbeba1ef`, `native` build.
Load average at start / end: `0.52 3.35 4.25 2/530 214739` / `0.64 3.32 4.24 1/526 214901`.
perf cycle counter available: yes (user-space only).

Times are medians over all samples from all runs; p10–p90 shows the spread. Between-run CV is the coefficient of variation of the per-run medians.

| impl | set | op | samples | median µs | p10–p90 µs | median TSC ticks | median perf cycles | between-run CV |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| liboqs | ML-KEM-512 | keygen | 10000 | 6.61 | 6.02–8.40 | 24309 | 27108 | 13.4% |
| liboqs | ML-KEM-512 | encaps | 10000 | 6.62 | 6.44–8.32 | 24346 | 29559 | 11.4% |
| liboqs | ML-KEM-512 | decaps | 10000 | 8.22 | 7.97–12.17 | 30266 | 38257 | 13.6% |
| liboqs | ML-KEM-768 | keygen | 10000 | 9.87 | 9.59–12.49 | 36371 | 44126 | 11.7% |
| liboqs | ML-KEM-768 | encaps | 10000 | 10.42 | 9.88–12.60 | 38406 | 46010 | 11.2% |
| liboqs | ML-KEM-768 | decaps | 10000 | 15.04 | 12.29–17.92 | 55500 | 63658 | 10.7% |
| liboqs | ML-KEM-1024 | keygen | 10000 | 13.97 | 13.39–17.72 | 51541 | 62201 | 11.7% |
| liboqs | ML-KEM-1024 | encaps | 10000 | 14.60 | 14.04–18.85 | 53872 | 66061 | 12.6% |
| liboqs | ML-KEM-1024 | decaps | 10000 | 21.23 | 17.28–25.02 | 78403 | 82667 | 11.3% |
