# NTRU

## Purpose

Key encapsulation. Historically important as the first practical
lattice-based public-key cryptosystem (1996/1998), and the oldest
lattice scheme still standing.

**Not standardised.** NTRU was a NIST Round 3 *finalist* and lost to
CRYSTALS-Kyber in July 2022. We study it as the main lattice
alternative to ML-KEM: it reaches comparable sizes and speeds from a
different assumption, and it has one property ML-KEM lacks (see
"perfect correctness" below).

The Round 3 submission called "NTRU" is a merger of two lines,
NTRUEncrypt and NTRU-HRSS-KEM, giving two parameter families, **HPS**
and **HRSS**. It is distinct from **NTRU Prime** (a separate submission
with different ring choices), and from the original patented
NTRUEncrypt — the core patents expired around 2017, which made NTRU the
patent-clear option during the NIST process.

## Cryptographic Family

Lattice-based, but **not** LWE. This is the key conceptual point.

ML-KEM adds explicit random error to a linear relation. NTRU does not:
it publishes a *quotient* of two small polynomials. The hardness comes
from the structure of the quotient, not from added noise. Different
assumption, different failure profile.

## Underlying Security Assumption

The **NTRU problem**: given `h = g/f mod q` with `f`, `g` small,
recover `f` and `g` (or any sufficiently short equivalent). Equivalently,
find an unusually short vector in the NTRU lattice — a `2n`-dimensional
lattice that contains `(f, g)` as a much shorter vector than a random
lattice of that determinant would have.

Our interpretation of how this compares to ML-KEM: the NTRU assumption
is older (1996 vs 2005 for LWE) and has survived direct attack, which is
a point in its favour. Against it, NTRU lacks a worst-case-to-
average-case reduction of the kind Regev gave for LWE, and the
"overstretched NTRU" attacks (Albrecht et al., Kirchner–Fouque, ~2016)
showed the problem becomes *much* easier when `q` is large relative to
`n`. Standard NTRU parameters are far from the overstretched regime, but
the episode is why NTRU is not usually described as the more
conservative lattice option despite being the older one.

## High-Level Operation

Ring `Z[x]/(Phi, q)`, with the exact quotient differing between HPS and
HRSS.

**KeyGen**
1. Sample small polynomials `f` and `g` (ternary coefficients, with a
   fixed-weight constraint in HPS and a structural constraint in HRSS).
2. Invert `f` in the ring mod `q` — and also mod 3, for decryption.
3. Public key `h = g/f` (up to a scheme-specific constant factor).

Step 2 is the reason NTRU keygen is slow relative to its other
operations: polynomial inversion is far more expensive than the
multiplications that encapsulation and decapsulation need. This is the
mirror image of ML-KEM, where keygen is the *cheapest* operation.

**Encaps**
1. Sample small `r` and `m`.
2. `c = h*r + m mod q`.
3. Shared secret from hashing `(r, m)`.

**Decaps**
1. `c*f mod q` — because `h*f = g`, this collapses to a small-coefficient
   expression in `g*r` and `m*f`.
2. Reduce mod 3 and multiply by `f^-1 mod 3` to recover `m`, then `r`.
3. Re-encrypt and compare for the CCA transform, with implicit
   rejection.

**Perfect correctness.** Both HPS and HRSS choose parameters so the
coefficients in step 1 provably never wrap mod `q`. The decryption
failure probability is **exactly zero**, not merely negligible. ML-KEM's
is around `2^-139` to `2^-174`.

Our interpretation of why that is worth more than the raw number
suggests: a nonzero failure rate is an attack surface, not just a
correctness footnote. Decryption-failure attacks recover keys by
submitting many ciphertexts and observing which fail. ML-KEM's margin is
wide enough that this is not a practical concern, but NTRU removes the
category rather than bounding it, which simplifies both the CCA security
proof and any constant-time argument.

## Parameter Sets

Sizes verified from
`implementations/liboqs/src/kem/ntru/kem_ntru.h:9-14, 69-74`; NIST
levels from `kem_ntru_hps2048509.c:18` and `kem_ntru_hrss701.c:18`.
liboqs also ships `hps2048677` and `hps4096821`.

| | NTRU-HPS-2048-509 | NTRU-HRSS-701 |
| --- | ---: | ---: |
| `n` / `q` | 509 / 2048 | 701 / 8192 |
| Public key | 699 B | 1138 B |
| Secret key | 935 B | 1450 B |
| Ciphertext | 699 B | 1138 B |
| Shared secret | 32 B | 32 B |
| Claimed NIST level | 1 | 3 |
| IND-CCA | yes | yes |

**Public key and ciphertext are the same size** in both sets, since both
are a single ring element mod `q`. ML-KEM's differ because of ciphertext
compression. The name `HPS-2048-509` encodes `q = 2048`, `n = 509`.

HPS vs HRSS: HPS ("Hoffstein–Pipher–Silverman") uses fixed-weight
sample spaces and supports a range of `(n, q)`; HRSS
("Hülsing–Rijneveld–Schanck–Schwabe") fixes one parameter set and
chooses the sample spaces so that no fixed-weight sampling is needed,
which makes constant-time implementation easier.

## Important Concepts

- **Inverted cost profile.** keygen >> encaps, decaps. Our data shows
  NTRU keygen at 7x (HPS-509 vs ML-KEM-512) and 6x (HRSS-701 vs
  ML-KEM-768) the corresponding ML-KEM keygen, while encaps and decaps
  are within a factor of ~1.3. NTRU therefore looks competitive for
  static keys and poor for ephemeral ones — the same *shape* of argument
  as Classic McEliece, three orders of magnitude less extreme.
- **`getrandom()` dominates encapsulation on Linux.** Our earlier harness
  work found roughly two thirds of NTRU encaps wall time is inside the
  `getrandom()` syscall, enough that a naive perf-to-TSC scaling
  understated its cycles by nearly 3x (see
  [liboqs notes](../implementations/liboqs.md#counting-only-userspace-cycles-distorts-rng-heavy-operations)).
  That harness was deleted and its source is no longer in the
  repository, so this must be re-measured with the API harness
  before it is cited. If it holds, it is a measurement hazard and also
  a real deployment cost.
- **No NTT in the standard parameter sets.** `n` is prime (509, 701),
  so the ring does not admit ML-KEM's power-of-two NTT. Implementations
  use Toom–Cook / Karatsuba instead. This is a large structural
  difference in the code, and part of why NTRU Prime exists.
- **Patent-free**, which mattered in 2020-2022 and is now mostly
  historical.

## Implementations Being Studied

- [liboqs](../implementations/liboqs.md) — `src/kem/ntru/`; our only
  source for NTRU at present.
- [PQClean](../implementations/pqclean.md).

No focused implementation is vendored in `implementations/`, and
since NTRU was not standardised, none of the `*-native` repositories
cover it.

## Relevant Papers / Standards

- [Hoffstein, Pipher & Silverman, "NTRU: A Ring-Based Public Key
  Cryptosystem" (ANTS 1998)](../../papers/notes/hoffstein-pipher-silverman-1998.md)
  — the original.
- NTRU NIST Round 3 submission (Chen, Danba, Hoffstein, Hülsing,
  Rijneveld, Schanck, Schwabe, Whyte, Zhang).
- [Peikert, "A Decade of Lattice Cryptography" (2016)](../../papers/notes/peikert-2016.md)
  — places NTRU against LWE-based schemes.
- No FIPS standard. This is the main practical argument against
  deploying it.

## Measured Performance

From `bench/computational/results/simple-speed_kem-grape-nuts.csv`, wall-clock
microseconds per operation:

| | keygen | encaps | decaps |
| --- | ---: | ---: | ---: |
| NTRU-HPS-2048-509 | 39.55 | 12.47 | 7.42 |
| NTRU-HRSS-701 | 56.77 | 9.79 | 11.97 |

Two things to note. HPS-509 decapsulates *faster* than it encapsulates,
the only algorithm in our set that does. And HRSS-701 encapsulates
faster than HPS-509 despite being the larger parameter set, which we do
not currently have an explanation for.

## Open Questions

- Why is HRSS-701 encaps (9.79 µs) faster than HPS-509 encaps
  (12.47 µs), given HRSS-701 is the larger, higher-security set? Likely
  HPS' fixed-weight sampling, which needs rejection or sorting, but this
  is a guess — needs the liboqs source read.
- Why does HPS-509 decaps beat its own encaps, while HRSS-701 does the
  opposite?
- How much of the `getrandom()` cost is liboqs' RNG plumbing rather than
  NTRU itself? If it is the former, the comparison against ML-KEM is
  distorted, since both go through the same `OQS_randombytes`.
- ~~Is NTRU worth a Phase 2 implementation slot given it is unstandardised,
  or is its value purely as a Phase 4 comparison point against ML-KEM?~~
  **Answered 2026-09-28**: the implementation phase was dropped from the
  project scope. NTRU's value is as a comparison point against ML-KEM in
  the Phase 2 measurements and the Phase 3 report.
