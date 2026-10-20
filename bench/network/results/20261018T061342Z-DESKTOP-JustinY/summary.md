# Network results: DESKTOP-JustinY

Link: veth pair between two network namespaces, MTU 1500, TSO/GSO/GRO off. netem on both directions: `delay 10ms loss 5%`. Libraries: liboqs 0.16.0; OpenSSL 3.5.9 29 Sep 2026. liboqs revision `0.16.0-38-gadbeba1ef`.
Load average at start / end: `0.35 0.18 0.07 2/314 45020` / `0.16 0.14 0.08 2/281 45865`.
Reference sizes: `bench/memory/results/20261006T090107Z-DESKTOP-JustinY/sizes.csv`.

200 handshakes per row, after 1 discarded. Every value is a per-handshake median, except retrans and fail, which are totals. Packets and wire bytes come from the client interface's counters. Application bytes are the KEM payloads plus 4-byte length prefixes and two 36-byte confirmations.

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
| liboqs | ML-KEM-768 | ephemeral | 1,184 | 1,088 | 7 | 4 | 1,694 | 1,400 | 742 | 67 | 0 | 40.540 | 1047.898 | 0.078 / 0.038 | 40.430 | wire bytes do not match packets x headers |
| liboqs | Classic-McEliece-6688128 | ephemeral | 1,044,992 | 208 | 729 | 270 | 1,093,154 | 19,548 | 67,422 | 7705 | 1 | 2672.026 | 4361.711 | 156.642 / 0.169 | 2495.934 |  |
| openssl | X25519 | ephemeral | 32 | 32 | 7 | 4 | 542 | 344 | 742 | 89 | 0 | 40.613 | 1051.551 | 0.137 / 0.127 | 40.334 |  |
| openssl | ML-KEM-768 | ephemeral | 1,184 | 1,088 | 7 | 4 | 1,694 | 1,400 | 742 | 82 | 0 | 40.586 | 1065.230 | 0.133 / 0.086 | 40.349 |  |
