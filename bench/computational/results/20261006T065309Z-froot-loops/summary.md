# API harness results — froot-loops

CPU: Intel(R) Xeon(R) W-1270 CPU @ 3.40GHz. Libraries: liboqs 0.16.0; OpenSSL 3.5.9 29 Sep 2026. liboqs revision `0.16.0-38-gadbeba1ef`.
Load average at start / end: `6.34 5.03 2.29 1/831 566105` / `1.04 2.45 1.92 1/821 567422`.
perf cycle counter available: no.

Times are medians over all samples from all runs; p10–p90 shows the spread. Between-run CV is the coefficient of variation of the per-run medians.

| impl | set | op | samples | median µs | p10–p90 µs | median TSC ticks | median perf cycles | between-run CV |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| liboqs | ML-KEM-512 | keygen | 10000 | 5.55 | 5.40–5.77 | 18836 | — | 2.7% |
| liboqs | ML-KEM-512 | encaps | 10000 | 6.19 | 6.08–6.40 | 21032 | — | 2.4% |
| liboqs | ML-KEM-512 | decaps | 10000 | 7.64 | 7.20–7.67 | 25976 | — | 2.2% |
| liboqs | ML-KEM-768 | keygen | 10000 | 9.53 | 9.49–9.62 | 32414 | — | 0.2% |
| liboqs | ML-KEM-768 | encaps | 10000 | 9.91 | 9.85–9.98 | 33694 | — | 0.4% |
| liboqs | ML-KEM-768 | decaps | 10000 | 11.94 | 11.90–12.38 | 40614 | — | 1.3% |
| liboqs | ML-KEM-1024 | keygen | 10000 | 13.47 | 13.41–13.95 | 45822 | — | 0.2% |
| liboqs | ML-KEM-1024 | encaps | 10000 | 14.34 | 14.28–15.23 | 48804 | — | 2.0% |
| liboqs | ML-KEM-1024 | decaps | 10000 | 17.14 | 17.09–17.29 | 58333 | — | 0.4% |
| liboqs | Classic-McEliece-348864 | keygen | 322 | 29225.44 | 25808.31–39578.68 | 99601357 | — | 3.5% |
| liboqs | Classic-McEliece-348864 | encaps | 10000 | 10.75 | 9.92–14.67 | 36522 | — | 3.1% |
| liboqs | Classic-McEliece-348864 | decaps | 10000 | 28.51 | 27.95–29.94 | 97079 | — | 2.7% |
| liboqs | Classic-McEliece-348864f | keygen | 379 | 26828.71 | 26571.02–27199.59 | 91433170 | — | 0.3% |
| liboqs | Classic-McEliece-348864f | encaps | 10000 | 10.76 | 9.91–14.78 | 36559 | — | 3.3% |
| liboqs | Classic-McEliece-348864f | decaps | 10000 | 28.55 | 27.95–29.84 | 97220 | — | 2.4% |
| liboqs | Classic-McEliece-460896 | keygen | 96 | 101645.96 | 79799.61–161875.40 | 346413217 | — | 16.8% |
| liboqs | Classic-McEliece-460896 | encaps | 10000 | 24.52 | 19.90–39.01 | 83429 | — | 3.0% |
| liboqs | Classic-McEliece-460896 | decaps | 10000 | 55.65 | 54.35–56.38 | 189582 | — | 1.3% |
| liboqs | Classic-McEliece-460896f | keygen | 130 | 79776.54 | 79263.92–81158.89 | 271881475 | — | 0.7% |
| liboqs | Classic-McEliece-460896f | encaps | 10000 | 24.60 | 19.91–38.39 | 83712 | — | 4.1% |
| liboqs | Classic-McEliece-460896f | decaps | 10000 | 56.71 | 55.29–59.06 | 193172 | — | 2.0% |
| liboqs | Classic-McEliece-6688128 | keygen | 68 | 157034.46 | 114077.51–228867.94 | 535179570 | — | 11.4% |
| liboqs | Classic-McEliece-6688128 | encaps | 10000 | 43.40 | 35.36–64.04 | 147796 | — | 3.5% |
| liboqs | Classic-McEliece-6688128 | decaps | 10000 | 66.19 | 64.53–66.89 | 225502 | — | 1.4% |
| liboqs | Classic-McEliece-6688128f | keygen | 99 | 110427.51 | 109146.76–111334.07 | 376341108 | — | 0.5% |
| liboqs | Classic-McEliece-6688128f | encaps | 10000 | 43.86 | 36.11–64.65 | 149344 | — | 2.4% |
| liboqs | Classic-McEliece-6688128f | decaps | 10000 | 66.41 | 64.60–69.27 | 226226 | — | 2.4% |
| liboqs | Classic-McEliece-6960119 | keygen | 73 | 125863.10 | 106277.42–200827.85 | 428946274 | — | 17.8% |
| liboqs | Classic-McEliece-6960119 | encaps | 10000 | 42.90 | 37.46–57.85 | 146051 | — | 2.0% |
| liboqs | Classic-McEliece-6960119 | decaps | 10000 | 61.45 | 60.28–62.04 | 209342 | — | 1.1% |
| liboqs | Classic-McEliece-6960119f | keygen | 100 | 106320.99 | 105316.57–107081.24 | 362345865 | — | 0.4% |
| liboqs | Classic-McEliece-6960119f | encaps | 10000 | 43.03 | 38.65–58.87 | 146492 | — | 1.4% |
| liboqs | Classic-McEliece-6960119f | decaps | 10000 | 61.29 | 60.06–62.27 | 208811 | — | 1.3% |
| liboqs | Classic-McEliece-8192128 | keygen | 59 | 168283.34 | 122710.66–278526.33 | 573516016 | — | 15.3% |
| liboqs | Classic-McEliece-8192128 | encaps | 10000 | 46.87 | 42.72–58.78 | 159619 | — | 2.0% |
| liboqs | Classic-McEliece-8192128 | decaps | 10000 | 65.61 | 64.24–66.09 | 223478 | — | 1.1% |
| liboqs | Classic-McEliece-8192128f | keygen | 90 | 121620.69 | 120815.30–122909.82 | 414487889 | — | 0.4% |
| liboqs | Classic-McEliece-8192128f | encaps | 10000 | 46.87 | 42.75–59.49 | 159621 | — | 2.7% |
| liboqs | Classic-McEliece-8192128f | decaps | 10000 | 65.52 | 64.40–66.47 | 223167 | — | 1.1% |
| liboqs | NTRU-HPS-2048-509 | keygen | 10000 | 39.31 | 38.57–40.97 | 133868 | — | 1.8% |
| liboqs | NTRU-HPS-2048-509 | encaps | 10000 | 12.65 | 12.44–13.19 | 43022 | — | 1.6% |
| liboqs | NTRU-HPS-2048-509 | decaps | 10000 | 7.40 | 7.24–7.71 | 25150 | — | 1.9% |
| liboqs | NTRU-HPS-2048-677 | keygen | 10000 | 65.65 | 62.82–67.40 | 223640 | — | 2.9% |
| liboqs | NTRU-HPS-2048-677 | encaps | 10000 | 17.36 | 17.15–18.02 | 59060 | — | 1.9% |
| liboqs | NTRU-HPS-2048-677 | decaps | 10000 | 11.42 | 11.11–11.96 | 38822 | — | 2.9% |
| liboqs | NTRU-HPS-4096-821 | keygen | 10000 | 85.83 | 83.91–89.67 | 292402 | — | 2.0% |
| liboqs | NTRU-HPS-4096-821 | encaps | 10000 | 20.00 | 19.66–20.91 | 68084 | — | 1.9% |
| liboqs | NTRU-HPS-4096-821 | decaps | 10000 | 14.26 | 13.97–14.71 | 48516 | — | 1.6% |
| liboqs | NTRU-HPS-4096-1229 | keygen | 5605 | 1778.48 | 1737.44–1845.59 | 6060982 | — | 1.0% |
| liboqs | NTRU-HPS-4096-1229 | encaps | 10000 | 81.00 | 79.61–83.10 | 275963 | — | 1.8% |
| liboqs | NTRU-HPS-4096-1229 | decaps | 10000 | 90.03 | 88.17–90.88 | 306712 | — | 1.2% |
| liboqs | NTRU-HRSS-701 | keygen | 10000 | 56.58 | 55.92–57.76 | 192707 | — | 1.2% |
| liboqs | NTRU-HRSS-701 | encaps | 10000 | 9.66 | 9.53–10.03 | 32842 | — | 1.6% |
| liboqs | NTRU-HRSS-701 | decaps | 10000 | 12.01 | 11.69–12.33 | 40872 | — | 1.7% |
| liboqs | NTRU-HRSS-1373 | keygen | 4382 | 2275.97 | 2227.30–2349.70 | 7756387 | — | 0.4% |
| liboqs | NTRU-HRSS-1373 | encaps | 10000 | 58.55 | 57.13–59.17 | 199406 | — | 1.4% |
| liboqs | NTRU-HRSS-1373 | decaps | 10000 | 135.19 | 132.89–144.35 | 460664 | — | 1.4% |
| openssl | X25519 | keygen | 10000 | 24.31 | 23.89–25.53 | 82787 | — | 2.1% |
| openssl | X25519 | encaps | 10000 | 54.83 | 53.73–57.32 | 186752 | — | 2.7% |
| openssl | X25519 | decaps | 10000 | 27.56 | 26.99–28.79 | 93866 | — | 2.4% |
| openssl | P-256 | keygen | 10000 | 9.72 | 9.53–10.06 | 33024 | — | 1.8% |
| openssl | P-256 | encaps | 10000 | 63.23 | 60.68–63.76 | 215344 | — | 2.2% |
| openssl | P-256 | decaps | 10000 | 45.71 | 45.42–46.92 | 155693 | — | 1.0% |
| openssl | RSA-2048 | keygen | 280 | 31192.17 | 13950.62–66555.94 | 106303928 | — | 18.2% |
| openssl | RSA-2048 | encaps | 10000 | 13.59 | 13.15–14.48 | 46238 | — | 1.6% |
| openssl | RSA-2048 | decaps | 10000 | 401.58 | 399.92–431.10 | 1368534 | — | 2.1% |
| openssl | RSA-3072 | keygen | 81 | 118133.53 | 44674.08–254441.90 | 402603662 | — | 37.5% |
| openssl | RSA-3072 | encaps | 10000 | 26.61 | 26.14–28.42 | 90634 | — | 2.2% |
| openssl | RSA-3072 | decaps | 8045 | 1221.17 | 1195.61–1272.34 | 4161712 | — | 0.3% |
| openssl | ffdhe2048 | keygen | 10000 | 202.85 | 198.92–215.62 | 691256 | — | 1.1% |
| openssl | ffdhe2048 | encaps | 10000 | 405.13 | 393.06–426.83 | 1380557 | — | 1.5% |
| openssl | ffdhe2048 | decaps | 10000 | 197.79 | 193.83–209.31 | 674014 | — | 2.7% |
| openssl | ffdhe3072 | keygen | 10000 | 494.02 | 482.26–521.74 | 1683547 | — | 3.0% |
| openssl | ffdhe3072 | encaps | 9966 | 980.79 | 959.22–1031.78 | 3342425 | — | 2.1% |
| openssl | ffdhe3072 | decaps | 10000 | 486.37 | 475.23–509.47 | 1657456 | — | 1.6% |
| openssl | ML-KEM-512 | keygen | 10000 | 20.98 | 20.48–21.84 | 71392 | — | 2.0% |
| openssl | ML-KEM-512 | encaps | 10000 | 13.92 | 13.70–14.62 | 47374 | — | 2.5% |
| openssl | ML-KEM-512 | decaps | 10000 | 22.34 | 21.02–22.64 | 76054 | — | 3.2% |
| openssl | ML-KEM-768 | keygen | 10000 | 32.81 | 31.04–33.21 | 111712 | — | 2.2% |
| openssl | ML-KEM-768 | encaps | 10000 | 19.08 | 17.95–19.23 | 64954 | — | 2.8% |
| openssl | ML-KEM-768 | decaps | 10000 | 29.64 | 27.92–29.89 | 100952 | — | 2.7% |
| openssl | ML-KEM-1024 | keygen | 10000 | 47.60 | 46.95–50.31 | 162149 | — | 2.4% |
| openssl | ML-KEM-1024 | encaps | 10000 | 24.06 | 23.94–24.83 | 81938 | — | 2.0% |
| openssl | ML-KEM-1024 | decaps | 10000 | 37.55 | 36.84–39.31 | 127908 | — | 2.5% |
