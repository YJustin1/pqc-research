# Network testing proposal

How we could measure what ML-KEM, Classic McEliece and NTRU cost on the
wire, from a clean link on one machine to real networks and a phone.
The metrics this covers are listed under "Network" in
[`../criteria.md`](../criteria.md).

Status on 2026-10-20: steps 1 to 3 of the build order below are built
and have been run (see [`README.md`](README.md)). The client and server
ended up as two subcommands, `kem_bench client` and `kem_bench server`,
instead of two programs, and `run_network.py` is the driver. Packet
counts come from interface counters rather than `tcpdump`. A one-off
`tcpdump`/`tshark` capture of the same handshakes matched them exactly.
The namespaces run inside an unprivileged user namespace, so no root is
needed. Since 2026-10-20 they form a dumbbell through a router
namespace, so competing traffic can share a capped bottleneck, and
`--netem "... rate ..."` and `--competing N` work.

The plan changed on 2026-10-20. The UTCS lab hosts are lightly loaded,
so a path to one adds no stress, and measuring our own paths for
profiles is replaced by public measurement data. The phone stays as the
one real path. The build order below is the revised one.

## What we want to know

For one key exchange between a client and a server:

- Bytes on the wire, per direction. The raw KEM contribution is
  public key plus ciphertext, which we already know from `sizes.csv`.
  What's new is the framing on top: TCP/IP headers and, if we use it,
  TLS.
- Packets per direction, at a realistic MTU of 1500 bytes.
- Round trips, and time to shared secret: from the moment the
  client connects until both sides hold the same key. Each side measures
  its own KEM compute, and network time is the rest.
- Retransmissions and failures: lost packets that had to be re-sent,
  and handshakes that timed out.

These split into two kinds. Bytes and packets are fixed by the protocol:
a 1 MB key is 1 MB on any network, and a clean link is the right place
to measure them. Time, retransmissions and failures depend entirely on
the network. On a clean link everything looks fast. On a real one, a
larger handshake takes more round trips while TCP ramps up, exposes more
packets to loss, and queues behind other traffic, so its cost grows
faster than its size. TCP starts with a congestion window of about 10
segments, roughly 14 KB. A 1 MB McEliece public key therefore needs
several round trips, while ML-KEM and NTRU fit in one or two packets
each way. Measuring that second kind realistically is what the layers
below are for.

## Two protocols

The first is a bare KEM exchange over TCP that we write ourselves. The
client generates a
keypair and sends the public key. The server encapsulates and sends back
the ciphertext. The client decapsulates. Both sides then exchange a hash
of the shared secret to confirm they agree; those bytes get counted
separately. Messages carry a 4-byte length prefix and nothing else. This
works for all three schemes and every parameter set in
[`../algorithms.md`](../algorithms.md), and it isolates the
KEM from everything a real protocol adds. It's a small C program against
liboqs and OpenSSL, which fits the "our code is benchmarking tooling"
rule. The OpenSSL side puts the classical baselines in
[`../algorithms.md`](../algorithms.md) through the same exchange, using
OpenSSL's KEM interface (see
[`classical-baselines.md`](../../docs/algorithms/classical-baselines.md)),
so every scheme is compared against what it would replace. It
mirrors TLS 1.3, where the client sends the key share and the server
encapsulates to it.

We'd also run a cached-key variant, where the server's long-term
public key is already on the client and only a ciphertext crosses the
wire. That's how Classic McEliece is meant to be used, and without it the
comparison is unfair to McEliece.

The second is TLS 1.3, for realism. OpenSSL 3.5 and later supports
ML-KEM natively. The Open Quantum Safe project's `oqs-provider` plugs other liboqs KEMs into
OpenSSL, but its `ALGORITHMS.md` lists only FrodoKEM, ML-KEM, BIKE and
HQC as KEMs, with no NTRU or Classic McEliece (checked 2026-10-05). The
TLS leg can therefore compare only the classical baselines and
ML-KEM. Hybrid key exchanges such as X25519MLKEM768 are out of scope,
because they are not pure versions of any scheme in
[`../algorithms.md`](../algorithms.md). `openssl s_server` and `openssl s_client`
are enough to drive it. Classic McEliece can't take part: TLS 1.3
limits a key share to 65,535 bytes (RFC 8446), and McEliece's smallest
public key is 261,120.
That's a finding for the report in its own right.

We'd start with the bare exchange, since it covers everything and
exercises the whole measurement pipeline. TLS comes second.

## Measuring

Wireshark is the right tool for looking at a handshake and for figures
in the report. For repeated runs we'd capture with `tcpdump` into pcap
files and count with `tshark`, the command-line half of Wireshark, so the
numbers come from a script rather than someone reading a GUI. The pcaps
can be opened in Wireshark any time.

Each run records:

- the pcap;
- the client's and server's own timings, each printed as one line of
  CSV;
- `ss -ti` output for TCP state, including retransmits and congestion
  window.

Captures go under `network/results/`, gitignored like the other raw
data. McEliece pcaps will be megabytes each.

Two things will give wrong packet counts if we're not careful:

- Loopback has an MTU of 65,536, so a 1 MB key crosses `lo` in a
  handful of giant packets. Local tests should run between two network
  namespaces joined by a `veth` pair with the MTU set to 1500.
- Segmentation offload (TSO, GSO and GRO) lets the kernel hand
  oversized segments to the capture point, so `tcpdump` on the sending
  host sees fewer, bigger packets than actually go out. We'd turn these
  off on the capture interface with `ethtool -K <if> tso off gso off gro off`,
  or count on the receiving side.

Timings vary run to run, so every timed condition needs many handshakes.
We'd report the median and the 95th percentile rather than the mean,
because loss produces a long tail that the mean hides.

## Layer 1: a clean link

Network namespaces on the WSL2 workstation, joined by `veth` links
with the MTU at 1500 and no impairment. This measures bytes and packets
for every parameter set, in both protocols and in the cached-key variant.
Byte counts are deterministic, so one run each is enough. They should
equal public key plus ciphertext plus a predictable amount of framing,
which checks the whole pipeline against `sizes.csv` before anything else
is trusted.

## Layer 2: emulated networks

The same namespaces, with `tc netem` imposing delay, jitter, loss and a
bandwidth cap on the router-server bottleneck. This doesn't need root:
inside an unprivileged user namespace we can add qdiscs to our own
interfaces. It runs in three stages.

First, a sweep with no competing traffic: bandwidth at 1, 10 and
100 Mbit/s and uncapped, round-trip time near 0, 20 and 100 ms, and
optionally 1% loss. This shows how each scheme's size turns into time:
where it starts paying extra round trips because its flight outgrows
TCP's initial window, and where sending time overtakes round-trip time.

Second, competing traffic. At a few points from the sweep, the
handshakes run once alone and once while `iperf3` bulk transfers share
the capped bottleneck. The queue in front of the cap decides how much
the handshakes suffer, so it is chosen deliberately, in two forms:

- a first-in-first-out queue sized to a fixed delay at the capped rate,
  around 50 to 100 ms, a common rule of thumb for router buffers;
- `fq_codel`, the default queue on many Linux systems, which keeps each
  flow separate, so a small handshake doesn't wait behind bulk traffic.

netem's default 1,000-packet queue, about 1.2 s at 10 Mbit/s, stays as
one deliberate worst case. First runs with it slowed ML-KEM-768 from
42 ms to over 2 s (see [`README.md`](README.md)).

Third, profiles from public measurement data instead of measuring our
own paths: three or four connection types (for example fiber, cable,
DSL, and satellite or mobile) from the FCC's Measuring Broadband America
published tables, with M-Lab's NDT data as a fallback. Each becomes a
`netem` profile: half the round-trip time as delay each way, upload and
download rates, and loss. Upload and download differ, so the harness
needs separate settings per direction. These profiles give the headline
"on realistic connections" results, and every scheme runs on them.

This layer gives the main results. It's controlled, so a difference
between schemes can be attributed to the scheme rather than to whatever
the network happened to be doing that minute.

## Layer 3: the phone, the one real path

A phone on mobile data, running our own client, talking to a server on
a small cloud VM. It is the most realistic path we can get, the one
closest to the professor's concern, and the only real path left in the
plan. It covers three things the emulation can't:

- whether a layer 2 profile predicts a real mobile path, by comparing
  the measured time to shared secret against the matching profile. Real
  networks can't be reproduced run to run, so this checks layer 2
  rather than replacing it;
- a limited client: the phone does its own KEM work (see "Devices"), so
  it shows what phone-class compute adds to the handshake;
- middleboxes. Firewalls and other network equipment sometimes
  mishandle a handshake that doesn't fit in a single packet. When Chrome
  started sending post-quantum key shares, some broken middleboxes
  dropped the larger TLS ClientHello. This was documented publicly at
  the time, and we should cite the original reports. A clean result on
  our path doesn't prove it can't happen elsewhere.

The cloud VM is needed because a phone on mobile data can't reach a
workstation behind home NAT. It also gives root at the server end, for
captures. A path from the workstation to a UTCS lab host was planned as
well, and is dropped: the hosts are lightly loaded, so the path adds no
stress, and it needed department firewall and policy questions answered.

Without more real paths, the report has to state two limits: the
emulation is checked against one path only, and middlebox behaviour is
checked on one carrier's network only.

## Layer 4: server load (stretch goal)

Many clients handshaking with one server at once, measuring completed
handshakes per second, the slowest handshakes, and server CPU. This is
the stress that matters to someone running a server: every connection
pays the KEM's compute cost and its bandwidth, multiplied by the number
of connections. It can run on the workstation with the clients in one
namespace and the server in the other.

## Devices

An Android phone running Termux can build liboqs and our client with
clang, natively on ARM64. An iPhone would need a proper app, which is a
lot more work. Phones throttle when hot and change clock speed with
battery state, so phone runs need more repetitions and should note
battery level and temperature. Android also usually blocks the hardware
counters we use for cycles, so phone compute is wall-clock time only.

Android Studio's emulator is useful for getting the Termux build and the
networking working before touching a real phone. Byte counts from it are
valid, but its timings aren't: it runs either on the desktop CPU or
through slow ARM translation. A Raspberry Pi 4 or 5 is a reasonable
stand-in for phone-class ARM hardware, and runs our existing Linux tools
unchanged.

## Minimum scope and build order

For the report, a defensible minimum is layer 1, the layer 2 sweep,
competing traffic under both queues, three or four public-data profiles,
and the phone check. TLS 1.3 depends on the open question below, and
layer 4 is a stretch goal.

1. Done: `kem_bench client` and `kem_bench server`, the bare KEM
   exchange.
2. Done: `run_network.py`, which sets up the namespaces and `netem`,
   runs the matrix and summarises. Interface counters replaced
   `tcpdump`; a capture option for report figures and loss analysis is
   still to do.
3. Done: layer 1 runs, with byte counts checked against `sizes.csv`.
4. Find out why one Classic McEliece handshake failed in each of the
   2026-10-18 netem runs, before the larger grids push McEliece against
   the 60-second socket timeout.
5. Layer 2 sweep: bandwidth and delay, no competing traffic.
6. Layer 2 competing traffic: `iperf3` through the cap, with a sized
   FIFO queue and with `fq_codel`, and the default queue as a worst case.
7. Layer 2 public-data profiles, with separate upload and download
   settings, run with every scheme.
8. Layer 3: the phone on mobile data to a cloud VM. Its setup (the VM,
   the phone, the Termux build, tried first on the Android emulator) can
   start alongside steps 5 to 7.
9. TLS 1.3 runs with OpenSSL: X25519 and P-256 as baselines, and
   ML-KEM, if the report needs them. Either way, Classic McEliece can't
   be used in TLS 1.3, which is a finding in itself.
10. Layer 4, if time allows.

Schemes are compared within each condition. For each one we report
the median and 95th-percentile time to a shared secret and its network
share; packets, retransmissions and failures; and its slowdown against
X25519 under the same condition. The large grids use a representative subset
(X25519, P-256, RSA-2048, ffdhe2048, the three ML-KEM sets, one or two
NTRU sets, and Classic-McEliece-348864 and -6688128 in both modes). The
full set runs on the public-data profiles.

As far as we know, Paquin, Stebila and Tamvada, "Benchmarking
Post-Quantum Cryptography in TLS" (PQCrypto 2020), measured TLS
handshakes over network namespaces with `netem` impairments in much the
same way. That needs confirming against the paper before we cite it.

## Open questions

- Is TLS 1.3 the protocol we want to report against, or is the bare
  exchange enough for the report? The answer decides whether step 9
  happens.
- Is a small cloud VM acceptable, cost-wise? Step 8 needs it.
- Which phone? It decides the CPU, and whether liboqs' optimised ARM code
  paths apply.
- Which connection types, and which percentiles of each, should the
  public-data profiles use?
