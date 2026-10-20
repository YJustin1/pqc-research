# Network benchmarks

`run_network.py` measures one key exchange over TCP for every parameter
set in [`../algorithms.md`](../algorithms.md). For each one it records the
bytes and packets in each direction, and how long it takes until both
sides know they hold the same key. So far it covers the bare KEM exchange
and layers 1 and 2 of [`proposal.md`](proposal.md). TLS 1.3 and the
real-path layers aren't built yet.

The client and server are subcommands of
[`../driver/kem_bench.c`](../driver/kem_bench.c), the driver the timing
and memory harnesses already use. The PQC KEMs (through liboqs) and the
classical baselines (through OpenSSL) therefore go through exactly the
same exchange.

```sh
python3 bench/network/run_network.py                         # everything, clean link
python3 bench/network/run_network.py --algs X25519 ML-KEM-768 --handshakes 100
python3 bench/network/run_network.py --netem "delay 10ms loss 1%"
python3 bench/network/run_network.py --netem "delay 10ms rate 10mbit" --competing 4
```

You need what the shared driver needs (see
[`../memory/README.md`](../memory/README.md)), plus `unshare`, `ip`, `tc`
and `ethtool`, and `iperf3` for `--competing`. You don't need root. The script re-runs itself inside an
unprivileged user namespace, where it can create its own network
namespaces, veth pairs and qdiscs. Results go to
`bench/network/results/<UTC stamp>-<host>/`:

| File | Contents |
| --- | --- |
| `summary.md` | the summary table, with the run's conditions |
| `summary.csv` | the same, per (impl, set, mode) |
| `handshakes.csv` | every handshake from both sides (gitignored) |
| `env.json` | host, library versions, build options, link setup (qdisc, offloads, TCP sysctls) |

## The exchange

Each TCP connection carries one key exchange, and every message is a
4-byte big-endian length followed by the payload. There are two modes:

| | ephemeral | cached-key |
| --- | --- | --- |
| client → server | public key | ciphertext |
| server → client | ciphertext, `confirm_S` | `confirm_S` |
| client → server | `confirm_C` | `confirm_C` |

In ephemeral mode the client generates a fresh keypair for every
handshake and the server encapsulates to it, the way a TLS 1.3 key share
works. In cached-key mode the client already has the server's long-term
public key (written by `kem_bench prepare`) and encapsulates to that.
This is how Classic McEliece is meant to be used.

`confirm_X` is SHA-256 over a label for its direction and the shared
secret. Each side checks the other's confirmation before it counts the
handshake, so every reported handshake ended with both sides holding the
same key. Then the client half-closes, the server closes, and the client
waits for that close before starting the next handshake, so handshakes
never overlap.

Each flight goes to the kernel in a single `sendmsg()` call with
`TCP_NODELAY` set. Corking the first message with `MSG_MORE` and sending
the rest separately isn't enough: if the peer's ACK arrives in between,
the kernel sends the corked tail on its own. In a packet trace, that
split ML-KEM-1024's server flight into 1448, 124 and 36 bytes.

### Wire formats

liboqs keys and ciphertexts go on the wire as the raw bytes liboqs uses.
OpenSSL public keys go as OpenSSL's encoded public key, which is what a
TLS 1.3 `key_share` carries. That means raw bytes for X25519 and ML-KEM,
an uncompressed point for P-256, and for ffdhe the public value padded to
the group size. RSA has no encoded public key, so it sends just the
modulus, padded to the key size, and the exponent is fixed at 65537.
Every one of these matches `public_key_bytes` in `sizes.csv`.

We checked the format by running the two libraries against each other.
An OpenSSL server and a liboqs client completed the ML-KEM-512 and
ML-KEM-1024 exchanges, confirmations included, and so did the reverse.

## The link

The namespaces form a dumbbell. The client (`kemcli`, 10.47.1.1), the
server (`kemsrv`, 10.47.2.1) and a traffic generator (`kemgen`, 10.47.3.1)
each have a veth link to a router namespace (`kemrtr`). The
router-server link is the bottleneck. Competing traffic runs between the
generator and the server, so it shares that bottleneck with the
handshakes but never crosses the client's link, and the client's
counters still see only handshakes. Until 2026-10-20 the client and
server were joined directly by one veth pair. The router adds a
forwarding hop, so clean-link times from before then aren't exactly
comparable; byte and packet counts are unchanged.

A few settings keep the counts honest:

- The MTU is 1500. Loopback's MTU of 65,536 would carry a McEliece key
  in a handful of packets.
- TSO, GSO and GRO are off on every interface, so every packet on the
  links is a real one of at most 1500 bytes.
- IPv6 is off, so neighbour discovery doesn't show up in the counters.
- `tcp_no_metrics_save` is 1. Otherwise the kernel would remember RTT and
  ssthresh from one connection and reuse them on the next, and the
  handshakes would no longer be independent.

`--netem ARGS` puts the same `tc netem` qdisc on both ends of the
bottleneck, outgoing, so a delay of `d` gives a round-trip time of `2d`.
`rate` caps the bandwidth each way, for example
`--netem "delay 10ms rate 10mbit"`.

`--competing N` starts `iperf3` with `N` parallel TCP streams from the
generator to the server (`--competing-reverse`: server to generator).
They run for 3 seconds before the first handshake, to get past slow
start, and keep running until the last. The `competing Mbit/s` column
gives their average rate during each row, from the generator's interface
counters. Without a `rate` in `--netem` there is no bottleneck to compete
for, and the script warns.

Under `rate`, the queue in front of the bottleneck matters as much as
the rate. netem's default queue holds 1,000 packets, about 1.2 s of data
at 10 Mbit/s. Bulk TCP flows keep a queue like that full, so every
handshake packet waits behind it, and packets that arrive when it is
full are dropped. `limit N` in `--netem` sets the queue length in
packets.

## What is measured

`kem_bench client` and `kem_bench server` record the following for each
handshake.

Packets and wire bytes in each direction come from the client
interface's `tx_*` and `rx_*` counters. The client reads them just before
each `connect()` and charges each handshake with the difference to the
next reading. That also catches anything netem was still holding when the
connection closed, but charges it to the next handshake, so under netem
one handshake's packet count can be a packet high and its neighbour's a
packet low. Totals are unaffected. All four counters come from one line
of `/proc/net/dev`, a single kernel snapshot. Reading the four sysfs files
one at a time let a packet netem released in between land in the bytes
but not the packets. The counts include the TCP handshake, the teardown and
pure ACKs, and wire bytes include the 14-byte Ethernet header. Under
netem, a packet the bottleneck drops on the way to the server has
already been counted as sent by the client, and its retransmission is
counted again. One dropped on the way back never reaches the client's
counter. (Before the dumbbell, netem sat on the client's own interface,
so packets it dropped on the way out were never counted.)

Application bytes sent and received are counted with the length prefixes
included. At the end of the handshake, `TCP_INFO` gives segments in and
out, total retransmissions, the smoothed RTT and the congestion window.

Times are in nanoseconds, from `CLOCK_MONOTONIC`:

| Field | Meaning |
| --- | --- |
| `connect_ns` | client only: the `connect()` call, which is the TCP handshake |
| `keygen_ns`, `encaps_ns`, `decaps_ns` | this side's KEM work. On the ephemeral server, encaps also includes reading the public key off the wire. For OpenSSL that means decoding and checking it; liboqs does its check inside encaps |
| `secret_ns` | from the start until this side holds the shared secret |
| `agreed_ns` | from the start until this side has checked the peer's confirmation |

The client starts its clock just before `connect()`, and the server
starts when `accept()` returns. The summary uses the client's
`agreed_ns` as the time to shared secret. Network time is that figure
minus the KEM compute on both sides.

`summary.md` discards one warm-up handshake, then reports medians over
the rest, plus the 95th percentile for time.

## Reading `summary.md`

In the column headings, B means bytes, C the client and S the server, so
`pkts C→S` is packets from client to server. Every value is a
per-handshake median, except `retrans` and `fail`, which are totals.
`summary.md` repeats this table above its results.

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

A median packet count can end in .5 when the handshakes split evenly
between two values. Medians are taken column by column, so when ACK
counts vary (ephemeral McEliece), a row's overhead won't exactly equal
its wire bytes minus its application bytes. The per-handshake check in
the next section is exact.

## Checks

Every row of the summary is checked, and any failure shows up in its
`problems` column. Application bytes must equal the payloads plus 4
bytes of prefix per message and two 36-byte confirmations. Public-key
and ciphertext sizes must match the newest
`bench/memory/results/*/sizes.csv`.

For every handshake where neither it nor the one before it had
retransmissions, wire bytes must equal
application bytes plus 66 bytes per packet (14 Ethernet, 20 IPv4, and 32
for TCP with timestamps), plus another 8 for each SYN, whose options are
longer. If offloads were handing the counters fewer, larger packets than
were actually sent, this check would fail. The previous handshake has
to be clean too because its late packets are charged to this one, and
after a loss those ACKs carry SACK options, 12 bytes longer.

## Layer 1: clean link (2026-10-13, workstation)

Everything in this section was measured in run
`20261013T082459Z-DESKTOP-JustinY`. It ran 20 handshakes per row with no
impairment, over all 56 rows (28 (impl, set) pairs in 2 modes). There
were no check failures, retransmissions or failed handshakes.

When each message fits in one 1448-byte segment, the exchange takes 7
packets from client to server and 4 back, with 742 bytes of framing.
That covers every classical baseline, ML-KEM-512 and 768, NTRU up to
HPS-4096-821 and HRSS-701, and cached-key McEliece, whose ciphertext is
only 96 to 208 bytes.

Messages that run one segment over (ML-KEM-1024, NTRU-HPS-4096-1229 and
NTRU-HRSS-1373) take 9 and 6 packets in ephemeral mode, and 8 and 5
cached. A packet trace shows why each extra data segment costs two
packets: Linux ACKs every segment immediately at the start of a
connection (quick-ACK).

Ephemeral McEliece sends this many packets from client to server:

| Set | Packets |
| --- | ---: |
| 348864 | 187 |
| 460896 | 368 |
| 6688128 and 6960119 | 728 to 730 |
| 8192128 | 944 |

That is the key at 1448 bytes per segment, plus the 7 fixed packets.
Between 24 and 210 packets come back. Almost all of them are pure ACKs,
and their number changes from run to run with ACK timing.

Counting both directions and the ACKs, framing adds a median of 14.3 to
14.7 KB to the 261 KB key (5.5%). For the 1.36 MB key it adds 67 to
68 KB (5.0%).

On a clean link the time is nearly all compute. The network share is
0.10 to 0.16 ms for exchanges that fit in one segment. For ephemeral
McEliece it is 0.6 to 1.9 ms, out of totals of 31 to 204 ms that are
almost entirely keygen. These times come from the WSL2 workstation, not
from an idle reference run. For compute costs, use
[`../computational/`](../computational/api/README.md).

A trial with `--netem "delay 10ms"` (a 20 ms round trip; results not
kept) showed what layer 2 is for. ML-KEM-768 and cached McEliece
finished in two round trips, about 40 ms. Ephemeral McEliece spent
121 ms on the network for 348864 and 162 ms for 8192128. That is roughly
6 and 8 round trips, spent while TCP slow start grew the congestion
window.

On 2026-10-13 we also checked the interface counters against a capture.
We ran `tcpdump` on `c0` during five ephemeral handshakes each of
X25519, ML-KEM-1024 and Classic-McEliece-348864, and counted each TCP
stream with `tshark`. Packets and bytes in each direction matched the
counters exactly, for every handshake. That includes McEliece's ACK
counts from server to client, which ranged from 34 to 89. The check was
a one-off script; `run_network.py` doesn't run it.

## Bandwidth caps and competing traffic (2026-10-20, workstation)

First runs of the dumbbell, liboqs, ephemeral mode, 20 handshakes per
row, with `--netem "delay 10ms rate 10mbit"`:
[`20261020T070558Z-DESKTOP-JustinY`](results/20261020T070558Z-DESKTOP-JustinY/summary.md)
without competing traffic, and
[`20261020T070612Z-DESKTOP-JustinY`](results/20261020T070612Z-DESKTOP-JustinY/summary.md)
with `--competing 4`.

| set | competing | median ms | p95 ms | retrans | competing Mbit/s |
| --- | --- | ---: | ---: | ---: | ---: |
| ML-KEM-768 | none | 42.5 | 42.6 | 0 | — |
| ML-KEM-768 | 4 streams | 2,144.2 | 2,471.7 | 35 | 10.3 |
| Classic-McEliece-348864 | none | 304.0 | 330.4 | 0 | — |
| Classic-McEliece-348864 | 4 streams | 8,367.7 | 18,413.6 | 100 | 9.9 |

Observed: the competing streams held the bottleneck at its 10 Mbit/s,
and every handshake slowed by seconds, with retransmissions in both rows.

Interpretation: with netem's default 1,000-packet queue, the bulk flows
keep about 1.2 s of data queued at the bottleneck, and the handshake's
packets wait behind it or are dropped when it overflows. ML-KEM-768's
2.1 s median fits a couple of those waits or one-second retransmission
timeouts; we haven't traced which. Either way it reflects the queue,
not the KEM. These numbers measure the queue
we happened to get, so they shouldn't be reported until the queue is
chosen deliberately.

## Not yet done

Counting doesn't need packet captures, as the cross-check shows.
Captures would still help with per-packet figures. Under netem loss,
capturing at both ends would also show which packets were dropped.
`run_network.py` has no capture option yet.

`--netem` works, but the layer 2 sweep and the public-data profiles
(proposal steps 5 and 7) haven't been run, and the harness can't yet set
upload and download separately. Competing `iperf3` traffic works
(`--competing`), but the bottleneck's queue length and discipline still
have to be chosen; see "Bandwidth caps and competing traffic" above.

The phone path, TLS 1.3 and server load (proposal steps 8 to 10) are
still to do.
