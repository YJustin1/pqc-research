# Network results: DESKTOP-JustinY

Link: veth pair between two network namespaces, MTU 1500, TSO/GSO/GRO off. netem on both directions: `delay 10ms`. Libraries: liboqs 0.16.0; OpenSSL 3.5.9 29 Sep 2026. liboqs revision `0.16.0-38-gadbeba1ef`.
Load average at start / end: `0.21 0.05 0.01 1/303 44894` / `0.38 0.18 0.07 1/295 44935`.
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
| liboqs | ML-KEM-768 | ephemeral | 1,184 | 1,088 | 7 | 4 | 1,694 | 1,400 | 742 | 0 | 0 | 40.560 | 40.774 | 0.078 / 0.038 | 40.436 |  |
| liboqs | Classic-McEliece-6688128 | ephemeral | 1,044,992 | 208 | 729 | 89 | 1,093,154 | 6,130 | 54,004 | 0 | 1 | 324.356 | 506.426 | 162.205 / 0.154 | 162.126 |  |
| openssl | X25519 | ephemeral | 32 | 32 | 7 | 4 | 542 | 344 | 742 | 0 | 0 | 40.613 | 40.848 | 0.135 / 0.117 | 40.346 |  |
| openssl | ML-KEM-768 | ephemeral | 1,184 | 1,088 | 7 | 4 | 1,694 | 1,400 | 742 | 0 | 0 | 40.613 | 40.719 | 0.140 / 0.091 | 40.366 |  |
