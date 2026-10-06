# Network testing proposal

How we could measure what ML-KEM, Classic McEliece and NTRU cost on the
wire, from a clean link on one machine to real networks and a phone.
Nothing here is built yet. The metrics this covers are listed under
"Network" in [`../criteria.md`](../criteria.md).

## What we want to know

For one key exchange between a client and a server:

- **Bytes on the wire**, per direction. The raw KEM contribution is
  public key plus ciphertext, which we already know from `sizes.csv`.
  What's new is the framing on top: TCP/IP headers and, if we use it,
  TLS.
- **Packets**, per direction, at a realistic MTU of 1500 bytes.
- **Round trips**, and **time to shared secret**: from the moment the
  client connects until both sides hold the same key. Each side measures
  its own KEM compute, and network time is the rest.
- **Retransmissions and failures**: lost packets that had to be re-sent,
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

**A bare KEM exchange over TCP, written by us.** The client generates a
keypair and sends the public key. The server encapsulates and sends back
the ciphertext. The client decapsulates. Both sides then exchange a hash
of the shared secret to confirm they agree; those bytes get counted
separately. Messages carry a 4-byte length prefix and nothing else. This
works for all three schemes and every parameter set in
[`../algorithms.md`](../algorithms.md), and it isolates the
KEM from everything a real protocol adds. It's a small C program against
liboqs and OpenSSL, which fits the "our code is benchmarking tooling"
rule. The OpenSSL side runs the classical baselines in
[`../algorithms.md`](../algorithms.md) through the same exchange, through OpenSSL's KEM interface
(see
[`classical-baselines.md`](../../docs/algorithms/classical-baselines.md)),
so every scheme is compared against what it would replace. It
mirrors TLS 1.3, where the client sends the key share and the server
encapsulates to it.

We'd also run a **cached-key** variant, where the server's long-term
public key is already on the client and only a ciphertext crosses the
wire. That's how Classic McEliece is meant to be used, and without it the
comparison is unfair to McEliece.

**TLS 1.3, for realism.** OpenSSL 3.5 and later supports ML-KEM
natively. The
Open Quantum Safe project's `oqs-provider` plugs other liboqs KEMs into
OpenSSL, but its `ALGORITHMS.md` lists only FrodoKEM, ML-KEM, BIKE and
HQC as KEMs, with no NTRU or Classic McEliece (checked 2026-10-05). The
TLS leg can therefore compare only the classical baselines and
ML-KEM. Hybrid key exchanges such as X25519MLKEM768 are out of scope,
because they are not pure versions of any scheme in
[`../algorithms.md`](../algorithms.md). `openssl s_server` and `openssl s_client`
are enough to drive it. **Classic McEliece can't take part.** TLS 1.3 limits a key share to
65,535 bytes (RFC 8446), and McEliece's smallest public key is 261,120.
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

- **Loopback has an MTU of 65,536**, so a 1 MB key crosses `lo` in a
  handful of giant packets. Local tests should run between two network
  namespaces joined by a `veth` pair with the MTU set to 1500.
- **Segmentation offload** (TSO, GSO and GRO) lets the kernel hand
  oversized segments to the capture point, so `tcpdump` on the sending
  host sees fewer, bigger packets than actually go out. We'd turn these
  off on the capture interface with `ethtool -K <if> tso off gso off gro off`,
  or count on the receiving side.

Timings vary run to run, so every timed condition needs many handshakes.
We'd report the median and the 95th percentile rather than the mean,
because loss produces a long tail that the mean hides.

## Layer 1: a clean link

Two network namespaces on the WSL2 workstation, joined by a `veth` pair
with the MTU at 1500 and no impairment. This measures bytes and packets
for every parameter set, in both protocols and in the cached-key variant.
Byte counts are deterministic, so one run each is enough. They should
equal public key plus ciphertext plus a predictable amount of framing,
which checks the whole pipeline against `sizes.csv` before anything else
is trusted.

## Layer 2: emulated networks, based on measured ones

The same namespaces, with `tc netem` imposing delay, jitter, loss and a
bandwidth cap. Root is needed, which we have on the workstation.

Rather than inventing numbers, we'd first measure a few real paths
with `ping` and `mtr`, recording round-trip time, jitter and loss:

- the campus LAN to a UTCS lab host;
- home broadband to the same host;
- a phone's mobile data connection.

Each measured path becomes a `netem` profile. We'd add one deliberately
lossy profile, as a stress case, and the clean link as a baseline.

**Competing traffic** is what separates this from a clean link. For each
profile we'd run the handshakes twice: once alone, and once while an
`iperf3` bulk transfer shares the same bandwidth-capped bottleneck. The
handshakes then queue behind real traffic, which is where a multi-round
trip McEliece exchange should suffer most.

This layer gives the main results. It's realistic because the profiles
come from real paths, and it's controlled, so a difference between
schemes can be attributed to the scheme rather than to whatever the
network happened to be doing that minute.

## Layer 3: real paths, to check the emulation

Real networks can't be reproduced run to run, so these runs check that
layer 2 predicts reality rather than serving as the main data. For each
real path, we'd compare the measured time to shared secret against the
matching `netem` profile.

**WSL2 to a UTCS lab host.** Some practical problems to sort out first:

- **We can only capture on our side.** `tcpdump` needs root, and we
  don't have root on UTCS machines. Server-side timings still come from
  the server program's own output.
- **The lab host must be reachable on a high port** from wherever the
  workstation is. The department probably blocks everything but SSH
  from outside, so this may only work on campus or over the VPN.
  Tunnelling through SSH would work but distorts both byte counts and
  timing, so it's a last resort.
- **The lab hosts are heavily loaded**, around 47 on 16 CPUs on
  grape-nuts, so server-side compute times there won't be clean. We'd
  report network time and treat server compute as indicative.
- **Policy.** Running a listening process on a shared department machine
  is probably fine for short tests on a high port, but it's worth
  checking with the department first.

**A small cloud VM in another region.** This avoids most of the UTCS
problems: we'd have root to capture at both ends, open ports, and a
genuinely long internet path. It's also the natural server for the phone,
since a phone on mobile data can't reach a workstation behind home NAT.

**A phone on mobile data**, talking to the cloud VM. This is the most
realistic path we can get, and the one closest to the professor's
concern.

**Middleboxes** are the one real-world effect no emulation shows.
Firewalls and other network equipment sometimes mishandle a handshake
that doesn't fit in a single packet. When Chrome started sending
post-quantum key shares, some broken middleboxes dropped the larger TLS
ClientHello. This was documented publicly at the time, and we should
cite the original reports. Real-path runs can check whether it happens
on the paths we use, though a clean result there doesn't prove it can't
happen elsewhere.

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

For the report, a defensible minimum is layer 1, layer 2 with three or
four measured profiles run with and without competing traffic, and one
real-path check. Layer 4 is a stretch goal.

1. `kem_client` and `kem_server`: the bare KEM exchange, parameter set on
   the command line, one CSV line of timings each.
2. A driver script that sets up the namespaces and `netem`, runs the
   matrix, captures with `tcpdump` and summarises with `tshark`.
3. Layer 1 runs, with byte counts checked against `sizes.csv`.
4. Measure the real paths and turn them into `netem` profiles.
5. Layer 2 runs, with and without `iperf3` competing traffic.
6. One layer 3 check: the phone on mobile data to a cloud VM, or WSL2 to
   a lab host if it's reachable.
7. TLS 1.3 runs with OpenSSL: X25519 and P-256 as baselines, and
   ML-KEM.
8. Layer 4, if time allows.

This follows established practice. As far as we know, Paquin, Stebila
and Tamvada, "Benchmarking Post-Quantum Cryptography in TLS" (PQCrypto
2020), measured TLS handshakes over network namespaces with `netem`
impairments in much the same way; that needs confirming against the
paper before we cite it.

## Open questions

- Is TLS 1.3 the protocol we want to report against, or is the bare
  exchange enough for the report? The answer decides how much of step 7
  we need.
- Is a small cloud VM acceptable, cost-wise? It's the easiest server for
  the phone and for a long real path.
- Which UTCS host and port can the workstation reach, and from where?
- Which phone? It decides the CPU, and whether liboqs' optimised ARM code
  paths apply.
