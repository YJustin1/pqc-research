# Network results: DESKTOP-JustinY

Link: veth pair between two network namespaces, MTU 1500, TSO/GSO/GRO off. netem on both directions: `none (clean link)`. Libraries: liboqs 0.16.0; OpenSSL 3.5.9 29 Sep 2026. liboqs revision `0.16.0-38-gadbeba1ef`.
Load average at start / end: `0.36 0.19 0.08 1/278 5839` / `0.30 0.21 0.10 1/277 5988`.
Reference sizes: `bench/memory/results/20261006T090107Z-DESKTOP-JustinY/sizes.csv`.

20 handshakes per row, after 1 discarded. Every value is a per-handshake median, except retrans and fail, which are totals. Packets and wire bytes come from the client interface's counters. Application bytes are the KEM payloads plus 4-byte length prefixes and two 36-byte confirmations.

| Column | Meaning |
| --- | --- |
| impl | library: `liboqs` or `openssl` |
| set | parameter set |
| mode | `ephemeral`: the client sends a fresh public key. `cached`: the client already holds the server's public key and sends only a ciphertext |
| pk B, ct B | public key and ciphertext size, in bytes. In cached mode the public key is not sent; its size is shown for reference |
| pkts C→S, pkts S→C | packets from client to server, and from server to client, for the whole connection: TCP setup, data, ACKs and teardown |
| wire B C→S, wire B S→C | bytes on the link each way, Ethernet, IPv4 and TCP headers included |
| overhead B | wire bytes minus application bytes, both directions together |
| retrans | TCP retransmissions on both sides, summed over the measured handshakes |
| fail | measured handshakes that did not complete |
| median ms, p95 ms | median and 95th percentile of the time from the client's `connect()` until it has checked the server's confirmation |
| compute C / S ms | median KEM work on the client and on the server |
| network ms | median of that time minus both sides' KEM work |
| problems | checks that failed; empty means all passed |

| impl | set | mode | pk B | ct B | pkts C→S | pkts S→C | wire B C→S | wire B S→C | overhead B | retrans | fail | median ms | p95 ms | compute C / S ms | network ms | problems |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| liboqs | ML-KEM-512 | ephemeral | 800 | 768 | 7 | 4 | 1,310 | 1,080 | 742 | 0 | 0 | 0.140 | 0.166 | 0.021 / 0.010 | 0.106 |  |
| liboqs | ML-KEM-512 | cached | 800 | 768 | 7 | 4 | 1,278 | 308 | 742 | 0 | 0 | 0.135 | 0.169 | 0.011 / 0.013 | 0.111 |  |
| liboqs | ML-KEM-768 | ephemeral | 1,184 | 1,088 | 7 | 4 | 1,694 | 1,400 | 742 | 0 | 0 | 0.192 | 0.257 | 0.040 / 0.018 | 0.130 |  |
| liboqs | ML-KEM-768 | cached | 1,184 | 1,088 | 7 | 4 | 1,598 | 308 | 742 | 0 | 0 | 0.176 | 0.242 | 0.016 / 0.020 | 0.135 |  |
| liboqs | ML-KEM-1024 | ephemeral | 1,568 | 1,568 | 9 | 6 | 2,210 | 2,012 | 1,006 | 0 | 0 | 0.212 | 0.240 | 0.046 / 0.021 | 0.139 |  |
| liboqs | ML-KEM-1024 | cached | 1,568 | 1,568 | 8 | 5 | 2,144 | 374 | 874 | 0 | 0 | 0.155 | 0.186 | 0.022 / 0.025 | 0.110 |  |
| liboqs | Classic-McEliece-348864 | ephemeral | 261,120 | 96 | 187 | 35.5 | 273,510 | 2,487 | 14,701 | 0 | 0 | 31.108 | 47.476 | 30.519 / 0.023 | 0.604 |  |
| liboqs | Classic-McEliece-348864 | cached | 261,120 | 96 | 7 | 4 | 606 | 308 | 742 | 0 | 0 | 0.179 | 0.308 | 0.016 / 0.036 | 0.124 |  |
| liboqs | Classic-McEliece-348864f | ephemeral | 261,120 | 96 | 187 | 29 | 273,510 | 2,058 | 14,272 | 0 | 0 | 38.611 | 41.146 | 37.977 / 0.027 | 0.583 |  |
| liboqs | Classic-McEliece-348864f | cached | 261,120 | 96 | 7 | 4 | 606 | 308 | 742 | 0 | 0 | 0.162 | 0.266 | 0.016 / 0.035 | 0.117 |  |
| liboqs | Classic-McEliece-460896 | ephemeral | 524,160 | 156 | 368 | 57.5 | 548,496 | 3,999 | 28,099 | 0 | 0 | 109.295 | 166.112 | 108.259 / 0.043 | 0.971 |  |
| liboqs | Classic-McEliece-460896 | cached | 524,160 | 156 | 7 | 4 | 666 | 308 | 742 | 0 | 0 | 0.237 | 0.335 | 0.035 / 0.083 | 0.114 |  |
| liboqs | Classic-McEliece-460896f | ephemeral | 524,160 | 156 | 368 | 52 | 548,496 | 3,636 | 27,736 | 0 | 0 | 83.027 | 114.332 | 82.037 / 0.044 | 0.879 |  |
| liboqs | Classic-McEliece-460896f | cached | 524,160 | 156 | 7 | 4 | 666 | 308 | 742 | 0 | 0 | 0.209 | 0.272 | 0.031 / 0.063 | 0.112 |  |
| liboqs | Classic-McEliece-6688128 | ephemeral | 1,044,992 | 208 | 728 | 76 | 1,093,088 | 5,272 | 53,080 | 0 | 0 | 203.792 | 292.681 | 200.385 / 0.176 | 1.798 |  |
| liboqs | Classic-McEliece-6688128 | cached | 1,044,992 | 208 | 7 | 4 | 718 | 308 | 742 | 0 | 0 | 0.284 | 0.461 | 0.065 / 0.080 | 0.133 |  |
| liboqs | Classic-McEliece-6688128f | ephemeral | 1,044,992 | 208 | 728 | 77 | 1,093,088 | 5,338 | 53,146 | 0 | 0 | 115.663 | 151.712 | 114.096 / 0.111 | 1.433 |  |
| liboqs | Classic-McEliece-6688128f | cached | 1,044,992 | 208 | 7 | 4 | 718 | 308 | 742 | 0 | 0 | 0.238 | 0.338 | 0.047 / 0.072 | 0.107 |  |
| liboqs | Classic-McEliece-6960119 | ephemeral | 1,047,319 | 194 | 730 | 78.5 | 1,095,547 | 5,423 | 53,377 | 0 | 0 | 128.885 | 214.012 | 127.525 / 0.079 | 1.393 |  |
| liboqs | Classic-McEliece-6960119 | cached | 1,047,319 | 194 | 7 | 4 | 704 | 308 | 742 | 0 | 0 | 0.264 | 0.332 | 0.059 / 0.091 | 0.118 |  |
| liboqs | Classic-McEliece-6960119f | ephemeral | 1,047,319 | 194 | 730 | 71.5 | 1,095,547 | 4,961 | 52,915 | 0 | 0 | 97.878 | 111.676 | 96.554 / 0.088 | 1.235 |  |
| liboqs | Classic-McEliece-6960119f | cached | 1,047,319 | 194 | 7 | 4 | 704 | 308 | 742 | 0 | 0 | 0.292 | 0.350 | 0.064 / 0.084 | 0.130 |  |
| liboqs | Classic-McEliece-8192128 | ephemeral | 1,357,824 | 208 | 944 | 76.5 | 1,420,176 | 5,305 | 67,369 | 0 | 0 | 183.482 | 270.975 | 181.666 / 0.169 | 1.877 |  |
| liboqs | Classic-McEliece-8192128 | cached | 1,357,824 | 208 | 7 | 4 | 718 | 308 | 742 | 0 | 0 | 0.264 | 0.288 | 0.062 / 0.094 | 0.103 |  |
| liboqs | Classic-McEliece-8192128f | ephemeral | 1,357,824 | 208 | 944 | 88 | 1,420,176 | 6,064 | 68,128 | 0 | 0 | 113.528 | 125.521 | 111.625 / 0.093 | 1.643 |  |
| liboqs | Classic-McEliece-8192128f | cached | 1,357,824 | 208 | 7 | 4 | 718 | 308 | 742 | 0 | 0 | 0.288 | 0.387 | 0.062 / 0.079 | 0.139 |  |
| liboqs | NTRU-HPS-2048-509 | ephemeral | 699 | 699 | 7 | 4 | 1,209 | 1,011 | 742 | 0 | 0 | 0.227 | 0.278 | 0.064 / 0.018 | 0.142 |  |
| liboqs | NTRU-HPS-2048-509 | cached | 699 | 699 | 7 | 4 | 1,209 | 308 | 742 | 0 | 0 | 0.154 | 0.202 | 0.018 / 0.011 | 0.125 |  |
| liboqs | NTRU-HPS-2048-677 | ephemeral | 930 | 930 | 7 | 4 | 1,440 | 1,242 | 742 | 0 | 0 | 0.273 | 0.305 | 0.107 / 0.027 | 0.134 |  |
| liboqs | NTRU-HPS-2048-677 | cached | 930 | 930 | 7 | 4 | 1,440 | 308 | 742 | 0 | 0 | 0.181 | 0.318 | 0.026 / 0.020 | 0.137 |  |
| liboqs | NTRU-HPS-4096-821 | ephemeral | 1,230 | 1,230 | 7 | 4 | 1,740 | 1,542 | 742 | 0 | 0 | 0.361 | 0.794 | 0.160 / 0.032 | 0.162 |  |
| liboqs | NTRU-HPS-4096-821 | cached | 1,230 | 1,230 | 7 | 4 | 1,740 | 308 | 742 | 0 | 0 | 0.172 | 0.223 | 0.026 / 0.020 | 0.121 |  |
| liboqs | NTRU-HPS-4096-1229 | ephemeral | 1,842 | 1,842 | 9 | 6 | 2,484 | 2,286 | 1,006 | 0 | 0 | 2.512 | 3.221 | 2.246 / 0.109 | 0.151 |  |
| liboqs | NTRU-HPS-4096-1229 | cached | 1,842 | 1,842 | 8 | 5 | 2,418 | 374 | 874 | 0 | 0 | 0.388 | 0.449 | 0.107 / 0.145 | 0.127 |  |
| liboqs | NTRU-HRSS-701 | ephemeral | 1,138 | 1,138 | 7 | 4 | 1,648 | 1,450 | 742 | 0 | 0 | 0.238 | 0.316 | 0.087 / 0.014 | 0.130 |  |
| liboqs | NTRU-HRSS-701 | cached | 1,138 | 1,138 | 7 | 4 | 1,648 | 308 | 742 | 0 | 0 | 0.148 | 0.167 | 0.016 / 0.018 | 0.113 |  |
| liboqs | NTRU-HRSS-1373 | ephemeral | 2,401 | 2,401 | 9 | 6 | 3,043 | 2,845 | 1,006 | 0 | 0 | 3.434 | 3.737 | 3.193 / 0.084 | 0.146 |  |
| liboqs | NTRU-HRSS-1373 | cached | 2,401 | 2,401 | 8 | 5 | 2,977 | 374 | 874 | 0 | 0 | 0.390 | 0.432 | 0.075 / 0.179 | 0.122 |  |
| openssl | X25519 | ephemeral | 32 | 32 | 7 | 4 | 542 | 344 | 742 | 0 | 0 | 0.262 | 0.329 | 0.074 / 0.077 | 0.112 |  |
| openssl | X25519 | cached | 32 | 32 | 7 | 4 | 542 | 308 | 742 | 0 | 0 | 0.233 | 0.306 | 0.073 / 0.039 | 0.120 |  |
| openssl | P-256 | ephemeral | 65 | 65 | 7 | 4 | 575 | 377 | 742 | 0 | 0 | 0.321 | 0.360 | 0.098 / 0.096 | 0.123 |  |
| openssl | P-256 | cached | 65 | 65 | 7 | 4 | 575 | 308 | 742 | 0 | 0 | 0.269 | 0.343 | 0.084 / 0.067 | 0.117 |  |
| openssl | RSA-2048 | ephemeral | 256 | 256 | 7 | 4 | 766 | 568 | 742 | 0 | 0 | 54.950 | 98.441 | 54.669 / 0.060 | 0.210 |  |
| openssl | RSA-2048 | cached | 256 | 256 | 7 | 4 | 766 | 308 | 742 | 0 | 0 | 0.732 | 0.850 | 0.025 / 0.568 | 0.123 |  |
| openssl | RSA-3072 | ephemeral | 384 | 384 | 7 | 4 | 894 | 696 | 742 | 0 | 0 | 108.593 | 369.233 | 108.290 / 0.092 | 0.234 |  |
| openssl | RSA-3072 | cached | 384 | 384 | 7 | 4 | 894 | 308 | 742 | 0 | 0 | 1.831 | 2.589 | 0.045 / 1.617 | 0.156 |  |
| openssl | ffdhe2048 | ephemeral | 256 | 256 | 7 | 4 | 766 | 568 | 742 | 0 | 0 | 1.198 | 1.475 | 0.521 / 0.546 | 0.129 |  |
| openssl | ffdhe2048 | cached | 256 | 256 | 7 | 4 | 766 | 308 | 742 | 0 | 0 | 1.037 | 1.160 | 0.598 / 0.294 | 0.143 |  |
| openssl | ffdhe3072 | ephemeral | 384 | 384 | 7 | 4 | 894 | 696 | 742 | 0 | 0 | 3.078 | 3.306 | 1.461 / 1.453 | 0.157 |  |
| openssl | ffdhe3072 | cached | 384 | 384 | 7 | 4 | 894 | 308 | 742 | 0 | 0 | 2.334 | 2.568 | 1.461 / 0.716 | 0.148 |  |
| openssl | ML-KEM-512 | ephemeral | 800 | 768 | 7 | 4 | 1,310 | 1,080 | 742 | 0 | 0 | 0.243 | 0.260 | 0.070 / 0.045 | 0.127 |  |
| openssl | ML-KEM-512 | cached | 800 | 768 | 7 | 4 | 1,278 | 308 | 742 | 0 | 0 | 0.170 | 0.229 | 0.020 / 0.022 | 0.122 |  |
| openssl | ML-KEM-768 | ephemeral | 1,184 | 1,088 | 7 | 4 | 1,694 | 1,400 | 742 | 0 | 0 | 0.280 | 0.304 | 0.086 / 0.055 | 0.137 |  |
| openssl | ML-KEM-768 | cached | 1,184 | 1,088 | 7 | 4 | 1,598 | 308 | 742 | 0 | 0 | 0.198 | 0.246 | 0.028 / 0.037 | 0.133 |  |
| openssl | ML-KEM-1024 | ephemeral | 1,568 | 1,568 | 9 | 6 | 2,210 | 2,012 | 1,006 | 0 | 0 | 0.345 | 0.470 | 0.117 / 0.074 | 0.145 |  |
| openssl | ML-KEM-1024 | cached | 1,568 | 1,568 | 8 | 5 | 2,144 | 374 | 874 | 0 | 0 | 0.187 | 0.229 | 0.031 / 0.042 | 0.115 |  |
