# Classical Baselines

## Purpose

These are the pre-quantum algorithms we measure alongside ML-KEM, Classic
McEliece and NTRU. They show what a PQC migration actually costs: the
same keygen/encaps/decaps measurements, taken on the algorithms each KEM
would replace.

The baselines are limited to **key establishment**, because all three
PQC algorithms in this project are KEMs. That gives two kinds:

- **Key agreement**: both parties contribute and each computes the same
  secret (Diffie-Hellman, ECDH, X25519). This is what KEMs replace in
  TLS 1.3 and SSH today, so it is the main baseline.
- **Key transport**: one party chooses the secret and encrypts it to the
  other's public key (RSA). This is structurally the closest match to a
  KEM, and it is the legacy baseline.

## Selected Algorithms

The measured list, with sizes and security levels, is
[`bench/algorithms.md`](../../bench/algorithms.md).

| Algorithm | Kind | Why |
| --- | --- | --- |
| X25519 | EC key agreement | TLS 1.3 and OpenSSH default; what ML-KEM replaces in practice |
| ECDH P-256 | EC key agreement | NIST curve; second most common TLS group; FIPS settings |
| RSA-3072, as a KEM (RSASVE) | key transport | legacy baseline; inverted cost profile (cheap encaps, expensive decaps and keygen) |
| FFDH `ffdhe3072` (RFC 7919) | finite-field key agreement | "classic" Diffie-Hellman; rarely deployed |
| RSA-2048, as a KEM (RSASVE) | key transport | deployment baseline: the most common RSA size in use |
| FFDH `ffdhe2048` (RFC 7919) | finite-field key agreement | deployment baseline: the most common DH group size |

The first four are level-matched at 128-bit classical strength (level
1). RSA-2048 and `ffdhe2048` are only 112-bit, below level 1. They are
included because the project asks what switching costs, and they are
what many systems would be switching from. They must not be presented
as an equal-strength comparison. NIST SP 800-57 still permits 112-bit
strength through 2030. NIST's transition plan (IR 8547, an initial
public draft when this was written; check its current status before
citing) deprecates 112-bit strength after 2030. It disallows
quantum-vulnerable algorithms at any size after 2035.

ECDH P-384 would give a level 3 comparison point for ML-KEM-768 and
NTRU-HRSS-701. It is left out for now.

### What is deliberately excluded

- **AES.** A PQC migration does not replace it. Grover's algorithm
  roughly halves its effective key strength, so AES-256 remains
  adequate, and the bulk encryption after a handshake is the same before
  and after migration. Its role here is as the reference that defines
  NIST's security levels (see Parameter Sets). It is not a benchmark
  target.
- **Signatures** (Ed25519, ECDSA, RSA-PSS). These provide authentication,
  not key establishment. Their PQC replacements are signature schemes
  (ML-DSA, FN-DSA, SLH-DSA), which this project does not study. Adding
  them would be a scope decision, not an extension of this list.
- **Hybrid key exchanges** (X25519MLKEM768 and similar, which run a
  classical and a PQC exchange together). TLS deployments use them, and
  OpenSSL 3.5.5 lists them as KEMs (observed), but they are not pure
  versions of any scheme in this project, so they are not measured.
- **Large RSA/FFDH moduli (7680, 15360).** These are the nominal level 3
  and 5 equivalents, but they are almost never deployed. Their absence
  from practice is the finding, and timing them adds little.

## Underlying Security Assumption

- X25519, P-256: hardness of the elliptic-curve discrete logarithm
  problem.
- `ffdhe2048`, `ffdhe3072`: hardness of the finite-field discrete logarithm problem.
- RSA: hardness of factoring, via the RSA problem.

Shor's algorithm solves all three in polynomial time on a large enough
quantum computer. That is the reason for the migration. Any security
levels below are against **classical** attackers only.

## High-Level Operation

All baselines are measured as keygen / encaps / decaps, so their rows
line up with the PQC KEMs. OpenSSL exposes X25519, the EC curves and RSA
directly as KEMs through `EVP_PKEY_encapsulate` / `EVP_PKEY_decapsulate`.
This is observed in OpenSSL 3.5.5's man pages `EVP_KEM-X25519(7)`,
`EVP_KEM-EC(7)` and `EVP_KEM-RSA(7)`.

**X25519, P-256: DHKEM (RFC 9180).** Per the OpenSSL man pages,
encapsulate "generates an ephemeral keypair", does the key exchange
against the recipient's public key, and runs HKDF to produce the shared
secret. It returns the secret and the ephemeral public key. Decapsulate
redoes the exchange with the recipient's private key. So:

| KEM operation | Diffie-Hellman equivalent |
| --- | --- |
| keygen | recipient generates a keypair |
| encaps | sender generates an ephemeral keypair, derives, then HKDF |
| decaps | recipient derives, then HKDF |

The HKDF step is part of DHKEM, not of raw ECDH. TLS 1.3 runs raw ECDH
and applies its own key schedule afterwards. DHKEM's encaps and decaps
are therefore slightly more expensive than the ECDH step inside a TLS
handshake. *Our interpretation:* HKDF over 32 bytes should be small next
to a scalar multiplication. That needs measuring before it is assumed.

**RSA: RSASVE (NIST SP 800-56B rev. 2, §7.2.1).** Per `EVP_KEM-RSA(7)`,
encapsulate "generates a secret using random bytes and then encrypts the
secret using the RSA public key (with no padding)". Decapsulate recovers
it with the private key. Deployed RSA key transport (TLS 1.2 and
earlier) used PKCS#1 v1.5 or OAEP padding instead. *Our interpretation:*
in both cases the cost is dominated by the same modular exponentiation,
so RSASVE timings stand in for deployed RSA key transport.

**`ffdhe2048`, `ffdhe3072`.** OpenSSL lists no KEM for finite-field DH. (Observed:
`openssl list -kem-algorithms` on 3.5.5 shows RSA, EC, X25519, X448 and
ML-KEM, but not DH.) It has to be measured with `EVP_PKEY_derive` and
mapped onto keygen/encaps/decaps by hand, following the table above
without the HKDF step. It is the only baseline whose keygen/encaps/decaps
split is our own mapping rather than an OpenSSL KEM.

## Parameter Sets

NIST defines PQC security levels 1, 3 and 5 as at least as hard to break
as key search on AES-128, -192 and -256. NIST SP 800-57 Part 1 gives the
classical equivalents. Pairing them with the parameter sets this project
studies:

| Level | Classical strength | PQC sets studied | EC | RSA / FFDH |
| --- | --- | --- | --- | --- |
| below 1 | 112-bit | none | none | 2048 (deployment baseline only) |
| 1 | 128-bit | ML-KEM-512, mceliece348864(f), NTRU-HPS-2048-509 | X25519, P-256 | 3072 |
| 3 | 192-bit | ML-KEM-768, mceliece460896(f), NTRU-HPS-2048-677, NTRU-HRSS-701 | P-384 (not measured, for now) | 7680 (not measured) |
| 5 | 256-bit | ML-KEM-1024, mceliece6688128(f) / 6960119(f) / 8192128(f), NTRU-HPS-4096-821 / 4096-1229, NTRU-HRSS-1373 | P-521 (not measured) | 15360 (not measured) |

PQC levels are those claimed in liboqs' sources; see
[`bench/algorithms.md`](../../bench/algorithms.md). The comparison is
"at equal classical strength". This is how deployments choose
parameters, but it says nothing about quantum resistance, where every
classical entry is broken.

Object sizes are listed in
[`bench/algorithms.md`](../../bench/algorithms.md). The classical sizes
there come from RFC 9180 (Table 2) and the standards above, not from our
own measurements. They should be confirmed from OpenSSL's API output once
the harness exists. That is how the PQC sizes were obtained, from
liboqs' `dump_alg_info`.

## Important Concepts

- **Cost profiles differ in shape, not just size.** EC key agreement has
  roughly symmetric, cheap operations. RSA has cheap encaps (public
  exponent 65537), expensive decaps, and very expensive keygen. RSA
  keygen is heavy-tailed, because it searches for primes until it finds
  them. That is the same measurement problem as Classic McEliece keygen,
  and it needs the same median and percentile treatment.
- **SSH already shows the KEM-first order.** OpenSSH made the hybrid
  `sntrup761x25519-sha512` its default key exchange in 9.0 and
  `mlkem768x25519-sha256` in 10.0, while host and user keys remain
  Ed25519 signatures (upstream release notes). `sntrup761` is
  Streamlined NTRU Prime, which is a different scheme from the NTRU in
  this project.

## Implementations Being Studied

- **OpenSSL 3.5+**, for every baseline. On the workstation, the system
  OpenSSL is 3.5.5 (observed 2026-10-05). It is not a submodule under
  `implementations/`. See Open Questions.
- OpenSSL's own **ML-KEM**, measured as a same-library control. OpenSSL
  has no Classic McEliece or NTRU, and neither does `oqs-provider` per
  its `ALGORITHMS.md` (checked 2026-10-05). Those two can only come from
  liboqs, so every comparison that involves them crosses libraries.
  *Our interpretation:* comparing liboqs ML-KEM (vendored mlkem-native)
  with OpenSSL ML-KEM mixes API overhead with implementation
  differences. API overhead has to be measured separately, for example
  by profiling where an operation's cycles go.

## Relevant Papers / Standards

- RFC 7748 — X25519.
- FIPS 186-5 and SP 800-186 — the P-256 curve.
- NIST SP 800-56A rev. 3 — (EC)DH key agreement.
- NIST SP 800-56B rev. 2 — RSA key establishment, including RSASVE.
- RFC 7919 — the `ffdhe` groups.
- RFC 9180 — HPKE, which defines DHKEM.
- NIST SP 800-57 Part 1 rev. 5 — comparable security strengths.

## Measured Performance

None yet. The API harness,
[`bench/computational/api/`](../../bench/computational/api/README.md),
times them, but no clean run has been recorded.

## Open Questions

- **How is OpenSSL pinned?** Options: the system 3.5.5, recorded per
  host; a source build at a fixed tag (a submodule under
  `implementations/`, or a version recorded in `env.json`); or both. The
  PQC side is pinned by submodule commit, so the classical side should
  be reproducible to the same standard.
- How large is OpenSSL's per-call `EVP` overhead (provider dispatch, key
  object allocation) relative to an X25519 or ML-KEM operation, once
  algorithm fetches are hoisted out of the timed loop?
- Does DHKEM's HKDF step measurably separate DHKEM-X25519 from raw
  X25519 derivation?
- ~~Memory: how can the baselines be measured?~~ **Answered
  2026-10-06**: in-process, by the shared driver's memory build, for
  both libraries (see [`bench/memory/README.md`](../../bench/memory/README.md)).
  massif's whole-process peak could not separate OpenSSL's one-time
  first-use setup from the operation. OpenSSL code size is not measured:
  its algorithms cannot be separated inside `libcrypto`.
