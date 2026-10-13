#!/usr/bin/env python3
"""Bytes, packets and time of one key exchange over TCP, for every
parameter set in bench/algorithms.md, with `kem_bench server` and
`kem_bench client` (bench/driver/kem_bench.c).

The client and server run in two network namespaces joined by a veth
pair at MTU 1500, with segmentation offloads off so every packet on the
link is a real MTU-sized one. Everything runs inside an unprivileged
user namespace, so no root is needed. --netem adds an impairment to both
directions of the link (layer 2 of proposal.md); without it the link is
clean (layer 1).

    python3 bench/network/run_network.py                       # everything, clean link
    python3 bench/network/run_network.py --algs X25519 ML-KEM-768 --handshakes 100
    python3 bench/network/run_network.py --netem "delay 10ms loss 1%"

Results go to bench/network/results/<UTC stamp>-<host>/.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent            # bench/network
REPO = HERE.parent.parent
RESULTS = HERE / "results"
SIZES_GLOB = "bench/memory/results/*/sizes.csv"
sys.path.insert(0, str(HERE.parent / "driver"))
import kem_build as build  # noqa: E402  (bench/driver/kem_build.py)
from kem_build import log, output_of  # noqa: E402

VARIANT = "native"
MODES = ("ephemeral", "cached")
INSIDE = "KEM_NET_INSIDE_USERNS"   # set once we have re-executed under unshare

# The link: client namespace, server namespace, one veth pair.
CLIENT_NS, SERVER_NS = "kemcli", "kemsrv"
CLIENT_IF, SERVER_IF = "c0", "s0"
CLIENT_ADDR, SERVER_ADDR = "10.47.0.1", "10.47.0.2"
MTU = 1500
PORT = 4433
ETHERNET_HEADER = 14   # included in the interface byte counters
# Bytes each packet adds on the link: Ethernet, IPv4, and TCP with the
# timestamp option (Linux's default). The two SYNs carry 8 more bytes of
# options (MSS, SACK permitted, window scale).
PACKET_OVERHEAD = ETHERNET_HEADER + 20 + 32
SYN_EXTRA = 8

# Per-namespace sysctls. tcp_no_metrics_save stops the kernel carrying
# RTT and ssthresh from one connection to the next, so handshakes are
# independent of each other.
SYSCTLS = {
    "net.ipv6.conf.all.disable_ipv6": "1",
    "net.ipv6.conf.default.disable_ipv6": "1",
    "net.ipv4.tcp_no_metrics_save": "1",
}
OFFLOADS = ("tso", "gso", "gro")


# ---------- namespaces ----------

def sh(*cmd: str, ns: str | None = None, **kw) -> subprocess.CompletedProcess:
    full = ["ip", "netns", "exec", ns, *cmd] if ns else list(cmd)
    return subprocess.run(full, check=True, text=True, capture_output=True, **kw)


def reexec_in_userns() -> None:
    """Run this script again as root of a new user, network and mount
    namespace, which may create namespaces, veth pairs and qdiscs."""
    if not shutil.which("unshare"):
        sys.exit("ERROR: needs unshare (util-linux)")
    env = {**os.environ, INSIDE: "1"}
    os.execvpe("unshare", ["unshare", "--user", "--map-root-user", "--net", "--mount", "--",
                           sys.executable, *sys.argv], env)


def setup_link(netem: str | None) -> None:
    # `ip netns` keeps its handles under /run/netns, which only the real
    # root may create; a private tmpfs on /run in our mount namespace
    # gives us one.
    sh("mount", "-t", "tmpfs", "none", "/run")
    os.makedirs("/run/netns")
    for ns in (CLIENT_NS, SERVER_NS):
        sh("ip", "netns", "add", ns)
    sh("ip", "link", "add", CLIENT_IF, "netns", CLIENT_NS, "type", "veth",
       "peer", "name", SERVER_IF, "netns", SERVER_NS)
    for ns, iface, addr in ((CLIENT_NS, CLIENT_IF, CLIENT_ADDR), (SERVER_NS, SERVER_IF, SERVER_ADDR)):
        for key, value in SYSCTLS.items():
            sh("sysctl", "-qw", f"{key}={value}", ns=ns)
        sh("ip", "link", "set", "lo", "up", ns=ns)
        sh("ip", "link", "set", iface, "mtu", str(MTU), ns=ns)
        sh("ip", "addr", "add", f"{addr}/24", "dev", iface, ns=ns)
        sh("ethtool", "-K", iface, *(x for o in OFFLOADS for x in (o, "off")), ns=ns)
        if netem:
            sh("tc", "qdisc", "add", "dev", iface, "root", "netem", *netem.split(), ns=ns)
        sh("ip", "link", "set", iface, "up", ns=ns)
    # Wait for the link, so the first handshake doesn't race it.
    sh("ping", "-c", "1", "-W", "5", SERVER_ADDR, ns=CLIENT_NS)


def link_description() -> dict:
    def per_ns(ns: str, iface: str) -> dict:
        features = sh("ethtool", "-k", iface, ns=ns).stdout.splitlines()
        return {
            "qdisc": sh("tc", "qdisc", "show", "dev", iface, ns=ns).stdout.strip(),
            "offloads": [f.strip() for f in features if f.split(":")[0].strip() in (
                "tcp-segmentation-offload", "generic-segmentation-offload", "generic-receive-offload")],
            "sysctls": {k: sh("sysctl", "-n", k, ns=ns).stdout.strip() for k in (
                *SYSCTLS, "net.ipv4.tcp_congestion_control", "net.ipv4.tcp_timestamps",
                "net.ipv4.tcp_sack", "net.ipv4.tcp_window_scaling", "net.ipv4.tcp_wmem", "net.ipv4.tcp_rmem")},
        }
    return {"mtu": MTU, "client": per_ns(CLIENT_NS, CLIENT_IF), "server": per_ns(SERVER_NS, SERVER_IF)}


# ---------- running ----------

def parse_records(text: str) -> tuple[dict[str, str], list[dict], list[tuple[int, str]]]:
    """(metadata, handshakes, failures) from kem_bench's output."""
    meta, handshakes, failures = {}, [], []
    for line in text.splitlines():
        kind, _, rest = line.partition(",")
        if kind == "M":
            key, _, value = rest.partition(",")
            meta[key] = value
        elif kind == "H":
            names = meta["fields"].split(",")
            handshakes.append(dict(zip(names, map(int, rest.split(",")))))
        elif kind == "F":
            index, _, reason = rest.partition(",")
            failures.append((int(index), reason))
    return meta, handshakes, failures


def run_pair(exe: Path, impl: str, alg: str, mode: str, count: int, tmp: Path) -> dict:
    """One server and one client process for `count` handshakes."""
    keydir = "-"
    if mode == "cached":
        keydir = str(tmp / f"{impl}-{alg}")
        subprocess.run([str(exe), "prepare", impl, alg, keydir], check=True, capture_output=True)

    server = subprocess.Popen(["ip", "netns", "exec", SERVER_NS, str(exe), "server", impl, alg,
                               str(PORT), keydir], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    server_out = []
    try:
        for line in server.stdout:
            server_out.append(line)
            if line.startswith("M,ready"):
                break
        else:
            raise RuntimeError(f"server did not start: {server.stderr.read()}")
        client = subprocess.run(["ip", "netns", "exec", CLIENT_NS, str(exe), "client", impl, alg,
                                 SERVER_ADDR, str(PORT), str(count), keydir, CLIENT_IF],
                                capture_output=True, text=True, timeout=3600)
    finally:
        server.terminate()
        rest, server_err = server.communicate(timeout=30)
        server_out.append(rest)
        if server_err.strip():
            log(f"server stderr ({impl} {alg} {mode}): {server_err.strip()}")
    if client.returncode != 0:
        raise RuntimeError(f"client failed: {client.stderr}")

    _, client_hs, client_fail = parse_records(client.stdout)
    _, server_hs, server_fail = parse_records("".join(server_out))
    return {"client": client_hs, "server": server_hs,
            "failures": [("client", *f) for f in client_fail] + [("server", *f) for f in server_fail]}


# ---------- checks and statistics ----------

def reference_sizes() -> tuple[Path | None, dict[tuple[str, str], tuple[int, int]]]:
    """Public-key and ciphertext sizes from the newest memory run."""
    files = sorted(REPO.glob(SIZES_GLOB), key=lambda p: p.parent.name)
    if not files:
        return None, {}
    with files[-1].open() as f:
        sizes = {(r["impl"], r["alg"]): (int(r["public_key_bytes"]), int(r["ciphertext_bytes"]))
                 for r in csv.DictReader(f)}
    return files[-1], sizes


def expected_app_bytes(mode: str, pk: int, ct: int) -> tuple[int, int]:
    """Client->server and server->client application bytes: payloads,
    4-byte length prefixes and two 32-byte confirmations."""
    prefix, confirm = 4, 4 + 32
    if mode == "ephemeral":
        return prefix + pk + confirm, prefix + ct + confirm
    return prefix + ct + confirm, confirm


def quantile(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def compute_ns(h: dict) -> int:
    return sum(max(h[k], 0) for k in ("keygen_ns", "encaps_ns", "decaps_ns"))


def summarise(impl: str, alg: str, mode: str, result: dict, warmup: int,
              ref: dict[tuple[str, str], tuple[int, int]]) -> dict:
    server_by_index = {h["index"]: h for h in result["server"]}
    client = [h for h in result["client"] if h["index"] >= warmup]
    pairs = [(c, server_by_index[c["index"]]) for c in client if c["index"] in server_by_index]
    if not client:
        raise RuntimeError(f"no completed handshakes for {impl} {alg} {mode}")

    first = client[0]
    pk, ct = (first["public_key_bytes"], first["ciphertext_bytes"])
    if mode == "cached":
        pk = ref.get((impl, alg), (None, None))[0]   # not sent; reported for reference
    app_cs, app_sc = expected_app_bytes(mode, pk or 0, ct)
    problems = []
    if any((h["app_bytes_sent"], h["app_bytes_received"]) != (app_cs, app_sc) for h in client):
        problems.append("application bytes differ from expected")
    if (impl, alg) in ref:
        ref_pk, ref_ct = ref[(impl, alg)]
        if ct != ref_ct or (mode == "ephemeral" and first["public_key_bytes"] != ref_pk):
            problems.append(f"sizes differ from sizes.csv ({ref_pk}, {ref_ct})")
    # Without retransmissions, every byte on the link is application data
    # or per-packet headers. Anything else means packets were not counted
    # as sent (offloads on, say).
    clean = [c for c, s in pairs if c["tcp_total_retrans"] == 0 and s["tcp_total_retrans"] == 0]
    if any(c["if_tx_bytes"] + c["if_rx_bytes"] - app_cs - app_sc
           != PACKET_OVERHEAD * (c["if_tx_packets"] + c["if_rx_packets"]) + 2 * SYN_EXTRA for c in clean):
        problems.append("wire bytes do not match packets x headers")

    def med(key: str, rows=client) -> float:
        return statistics.median(h[key] for h in rows)

    agreed = [h["agreed_ns"] for h in client]
    network = [c["agreed_ns"] - compute_ns(c) - compute_ns(s) for c, s in pairs]
    wire_cs, wire_sc = med("if_tx_bytes"), med("if_rx_bytes")
    return {
        "impl": impl, "alg": alg, "mode": mode,
        "handshakes": len(client),
        "failures": sum(1 for side, index, _ in result["failures"] if side == "client" and index >= warmup),
        "public_key_bytes": pk, "ciphertext_bytes": ct,
        "app_bytes_c2s": app_cs, "app_bytes_s2c": app_sc,
        "packets_c2s": med("if_tx_packets"), "packets_s2c": med("if_rx_packets"),
        "packets_c2s_range": f"{min(h['if_tx_packets'] for h in client)}-{max(h['if_tx_packets'] for h in client)}",
        "packets_s2c_range": f"{min(h['if_rx_packets'] for h in client)}-{max(h['if_rx_packets'] for h in client)}",
        "wire_bytes_c2s": wire_cs, "wire_bytes_s2c": wire_sc,
        "overhead_bytes": wire_cs + wire_sc - app_cs - app_sc,
        "tcp_retrans": sum(h["tcp_total_retrans"] for h in client) + sum(s["tcp_total_retrans"] for _, s in pairs),
        "median_connect_ms": med("connect_ns") / 1e6,
        "median_agreed_ms": statistics.median(agreed) / 1e6,
        "p95_agreed_ms": quantile(agreed, 0.95) / 1e6,
        "median_client_compute_ms": statistics.median(compute_ns(h) for h in client) / 1e6,
        "median_server_compute_ms": statistics.median(compute_ns(s) for _, s in pairs) / 1e6 if pairs else None,
        "median_network_ms": statistics.median(network) / 1e6 if network else None,
        "problems": "; ".join(problems),
    }


# ---------- output ----------

def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fmt(x, spec: str) -> str:
    return "—" if x is None else format(x, spec)


def count(x) -> str:
    """A byte or packet count; medians of an even number can end in .5."""
    if x is None:
        return "—"
    return f"{x:,.0f}" if float(x).is_integer() else f"{x:,.1f}"


# Column headings of summary.md and what they mean. B is bytes, C the
# client, S the server. bench/network/README.md repeats this table.
SUMMARY_COLUMNS = [
    ("impl", "library: `liboqs` or `openssl`"),
    ("set", "parameter set"),
    ("mode", "`ephemeral`: the client sends a fresh public key. `cached`: the client already "
             "holds the server's public key and sends only a ciphertext"),
    ("pk B, ct B", "public key and ciphertext size, in bytes. In cached mode the public key "
                   "is not sent; its size is shown for reference"),
    ("pkts C→S, pkts S→C", "packets from client to server, and from server to client, for the "
                           "whole connection: TCP setup, data, ACKs and teardown"),
    ("wire B C→S, wire B S→C", "bytes on the link each way, Ethernet, IPv4 and TCP headers included"),
    ("overhead B", "wire bytes minus application bytes, both directions together"),
    ("retrans", "TCP retransmissions on both sides, summed over the measured handshakes"),
    ("fail", "measured handshakes that did not complete"),
    ("median ms, p95 ms", "median and 95th percentile of the time from the client's `connect()` "
                          "until it has checked the server's confirmation"),
    ("compute C / S ms", "median KEM work on the client and on the server"),
    ("network ms", "median of that time minus both sides' KEM work"),
    ("problems", "checks that failed; empty means all passed"),
]


def write_markdown(path: Path, rows: list[dict], env: dict) -> None:
    impairment = env["args"]["netem"] or "none (clean link)"
    lines = [
        f"# Network results: {env['host']}",
        "",
        f"Link: veth pair between two network namespaces, MTU {MTU}, TSO/GSO/GRO off. "
        f"netem on both directions: `{impairment}`. "
        f"Libraries: {'; '.join(env['libraries'])}. liboqs revision `{env['liboqs_revision']}`.",
        f"Load average at start / end: `{env['loadavg_start']}` / `{env['loadavg_end']}`.",
        f"Reference sizes: `{env['reference_sizes']}`.",
        "",
        f"{env['args']['handshakes']} handshakes per row, after {env['args']['warmup']} discarded. "
        "Every value is a per-handshake median, except retrans and fail, which are totals. "
        "Packets and wire bytes come from the client interface's counters. Application bytes are "
        "the KEM payloads plus 4-byte length prefixes and two 36-byte confirmations.",
        "",
        "| Column | Meaning |",
        "| --- | --- |",
        *(f"| {name} | {meaning} |" for name, meaning in SUMMARY_COLUMNS),
        "",
        "| impl | set | mode | pk B | ct B | pkts C→S | pkts S→C | wire B C→S | wire B S→C | overhead B "
        "| retrans | fail | median ms | p95 ms | compute C / S ms | network ms | problems |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for r in rows:
        lines.append(
            f"| {r['impl']} | {r['alg']} | {r['mode']} | {count(r['public_key_bytes'])} | {count(r['ciphertext_bytes'])} "
            f"| {count(r['packets_c2s'])} | {count(r['packets_s2c'])} "
            f"| {count(r['wire_bytes_c2s'])} | {count(r['wire_bytes_s2c'])} "
            f"| {count(r['overhead_bytes'])} | {r['tcp_retrans']} | {r['failures']} "
            f"| {r['median_agreed_ms']:.3f} | {r['p95_agreed_ms']:.3f} "
            f"| {r['median_client_compute_ms']:.3f} / {fmt(r['median_server_compute_ms'], '.3f')} "
            f"| {fmt(r['median_network_ms'], '.3f')} | {r['problems']} |")
    path.write_text("\n".join(lines) + "\n")


def read_text(path: str) -> str | None:
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def cpu_model() -> str | None:
    for line in (read_text("/proc/cpuinfo") or "").splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return None


# ---------- main ----------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--handshakes", type=int, default=20, help="measured handshakes per (impl, set, mode)")
    ap.add_argument("--warmup", type=int, default=1, help="handshakes run first and discarded")
    ap.add_argument("--algs", nargs="+", help="only these sets (default: all)")
    ap.add_argument("--impl", choices=["liboqs", "openssl"], help="only this implementation")
    ap.add_argument("--modes", nargs="+", choices=MODES, default=list(MODES))
    ap.add_argument("--netem", help='netem arguments for each direction, e.g. "delay 10ms loss 1%%"')
    ap.add_argument("--build-only", action="store_true")
    return ap.parse_args()


def select_combos(args: argparse.Namespace) -> list[tuple[str, str]]:
    combos = build.all_combos()
    if args.algs:
        unknown = set(args.algs) - {alg for _, alg in combos}
        if unknown:
            sys.exit(f"ERROR: unknown sets {sorted(unknown)}")
        combos = [(impl, alg) for impl, alg in combos if alg in args.algs]
    if args.impl:
        combos = [(impl, alg) for impl, alg in combos if impl == args.impl]
    return combos


def main() -> None:
    args = parse_args()
    if not os.environ.get(INSIDE):
        build.build_all([VARIANT])   # needs the internet the first time, so before unshare
        if not args.build_only:
            reexec_in_userns()
        return

    exe = build.driver_path(VARIANT)
    combos = select_combos(args)
    setup_link(args.netem)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = RESULTS / f"{stamp}-{socket.gethostname()}"
    out.mkdir(parents=True)
    ref_path, ref = reference_sizes()
    env = {
        "host": socket.gethostname(),
        "cpu": cpu_model(),
        "kernel": platform.release(),
        "libraries": output_of([str(exe), "version"]).splitlines(),
        **build.build_description([VARIANT]),
        "link": link_description(),
        "reference_sizes": str(ref_path.relative_to(REPO)) if ref_path else None,
        "loadavg_start": read_text("/proc/loadavg"),
        "args": vars(args),
    }

    jobs = [(impl, alg, mode) for impl, alg in combos for mode in args.modes]
    rows, total, started = [], len(jobs), time.monotonic()
    with tempfile.TemporaryDirectory() as tmp, (out / "handshakes.csv").open("w", newline="") as raw:
        writer = None
        for n, (impl, alg, mode) in enumerate(jobs):
            result = run_pair(exe, impl, alg, mode, args.warmup + args.handshakes, Path(tmp))
            for side in ("client", "server"):
                for h in result[side]:
                    record = {"impl": impl, "alg": alg, "mode": mode, "side": side,
                              "warmup": int(h["index"] < args.warmup), **h}
                    if writer is None:
                        writer = csv.DictWriter(raw, fieldnames=list(record))
                        writer.writeheader()
                    writer.writerow(record)
            row = summarise(impl, alg, mode, result, args.warmup, ref)
            rows.append(row)
            minutes_left = (time.monotonic() - started) / (n + 1) * (total - n - 1) / 60
            log(f"[{n + 1}/{total}] {impl:<7} {alg:<26} {mode:<9} "
                f"pkts {row['packets_c2s']:g}/{row['packets_s2c']:g}  median {row['median_agreed_ms']:.3f} ms"
                f"{'  ' + row['problems'] if row['problems'] else ''}  (~{minutes_left:.0f} min left)")

    env["loadavg_end"] = read_text("/proc/loadavg")
    (out / "env.json").write_text(json.dumps(env, indent=2) + "\n")
    write_csv(out / "summary.csv", rows)
    write_markdown(out / "summary.md", rows, env)
    log(f"\n-> {out.relative_to(REPO)}")


if __name__ == "__main__":
    main()
