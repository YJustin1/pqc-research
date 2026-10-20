# ML-KEM

## Purpose

Key encapsulation: establish a 32-byte shared secret between two parties
over a public channel, secure against an adversary with a quantum
computer. It replaces ECDH / RSA key transport, not signatures.

Standardised as **FIPS 203** (August 2024), derived from
CRYSTALS-Kyber, the KEM selected in NIST's PQC process in July 2022.

## Cryptographic Family

Lattice-based, **Module-LWE**. "Module" is the middle ground between
plain LWE (a large unstructured matrix; conservative but slow and large)
and Ring-LWE (a single ring element; fast and compact, but more algebraic
structure for an attacker to exploit). Module-LWE fixes a small ring and
scales security by changing the *rank* `k` of a matrix over that ring.

Practical consequence: the three parameter sets share one ring, one
modulus, and therefore one NTT and one set of hand-optimised primitives.
Only `k` and a few sampling widths change. This is why ML-KEM
implementations are small relative to the security range they cover.

## Underlying Security Assumption

Given `A` uniform over `R_q^{k x k}` and `t = A·s + e` with `s`, `e`
small, recover `s` (search-MLWE) or distinguish `t` from uniform
(decision-MLWE). Reduces to approximate shortest-vector problems on
module lattices, for which no efficient quantum algorithm is known —
Shor's algorithm does not apply, and Grover gives only a square-root
speedup on the search space.

Our interpretation: the caveat is that the best known attacks (lattice
reduction, BKZ with sieving) have *steadily improving* cost estimates, so
ML-KEM's security margin is a moving estimate in a way Classic
McEliece's is not. This is the central tradeoff between the two.

## High-Level Operation

Two layers. An IND-CPA public-key encryption scheme (**K-PKE**), wrapped
in the **Fujisaki–Okamoto transform with implicit rejection** to get an
IND-CCA2 KEM.

Ring: `R_q = Z_q[X]/(X^256 + 1)`, `q = 3329`, `n = 256`, fixed for all
parameter sets.

**KeyGen**
1. Sample seeds `(rho, sigma)` from 32 random bytes via SHA3-512.
2. Expand `A in R_q^{k x k}` from `rho` by rejection sampling on
   SHAKE-128 output. `A` is never stored — it is regenerated from
   `rho` whenever needed, which is why the public key holds a 32-byte
   seed instead of a `k x k` matrix.
3. Sample `s`, `e` from a centred binomial distribution (CBD) via
   SHAKE-256.
4. `t = A·s + e`. Public key is `(encode(t), rho)`; secret key holds `s`
   plus — for the FO transform — a copy of the public key, its hash, and
   a 32-byte implicit-rejection value `z`.

**Encaps**
1. `m` <- 32 random bytes.
2. `(K, r) = G(m || H(pk))` where `G` is SHA3-512.
3. Encrypt `m` under `pk` with randomness `r`, giving ciphertext `c`.
4. Shared secret is `K` directly. (Kyber round 3 instead output
   `KDF(K_bar || H(c))`, where `K_bar` is the first half of `G`'s
   output, hashing in the ciphertext; FIPS 203 dropped that final KDF.)

**Decaps**
1. Decrypt `c` with `s` to get `m'`.
2. Recompute `(K', r') = G(m' || H(pk))` and **re-encrypt** to get `c'`.
3. Constant-time compare `c'` to `c`. Equal -> output `K'`. Not equal ->
   output `J(z || c)`, a pseudorandom key derived from the secret `z`.

The implicit rejection in step 3 is what makes decapsulation failure
indistinguishable from success to an attacker, and it is the reason
decaps costs more than encaps in every measurement below: decaps does a
decryption *and* a full encryption.

**Compression.** Ciphertext coefficients are rounded to `d_u` / `d_v`
bits. This is where the ciphertext shrinks, and it is also the sole
source of decryption failure.

## Parameter Sets

Sizes verified from
`implementations/liboqs/src/kem/ml_kem/kem_ml_kem.h:9-44`; NIST levels
and the IND-CCA flag from the `kem_ml_kem_*.c` constructors, line 18-19
of each.

| | ML-KEM-512 | ML-KEM-768 | ML-KEM-1024 |
| --- | ---: | ---: | ---: |
| Module rank `k` | 2 | 3 | 4 |
| `eta1` / `eta2` | 3 / 2 | 2 / 2 | 2 / 2 |
| `d_u` / `d_v` | 10 / 4 | 10 / 4 | 11 / 5 |
| Public key | 800 B | 1184 B | 1568 B |
| Secret key | 1632 B | 2400 B | 3168 B |
| Ciphertext | 768 B | 1088 B | 1568 B |
| Shared secret | 32 B | 32 B | 32 B |
| Claimed NIST level | 1 | 3 | 5 |
| IND-CCA | yes | yes | yes |

The `eta1`, `d_u`, `d_v` rows are from the FIPS 203 / Kyber
specification, not from liboqs source. Decryption failure probabilities
claimed by the Kyber round-3 specification are roughly `2^-139`,
`2^-164` and `2^-174` respectively — negligible, but **nonzero**, unlike
NTRU.

liboqs also exposes a 64-byte `keypair_seed` and 32-byte `encaps_seed`
for each set (same header, lines 13-14 etc.), reflecting FIPS 203's
seed-based key expansion.

## Important Concepts

- **NTT.** `q = 3329` and `n = 256` are chosen so `X^256 + 1` factors
  mod `q` into 128 quadratic factors. The NTT is therefore *incomplete*:
  7 layers, with base multiplication of degree-1 polynomials rather than
  pointwise scalars. Public keys are stored already in NTT domain, so
  encapsulation skips a forward transform.
- **Rejection sampling for `A`** is data-independent (it samples from a
  public seed), so it does not need to be constant-time. Sampling of
  `s` and `e` does.
- **Re-encryption in decaps** is the FO transform's cost and the reason
  for the keygen < encaps < decaps ordering we measure.
- **`k` is the only real knob.** Scaling security does not change the
  ring, the NTT, or the hash usage.

## Implementations Being Studied

- [mlkem-native](../implementations/mlkem-native.md) — the focused,
  formally-verified implementation.
- [liboqs](../implementations/liboqs.md) — used as the comparison
  harness; `src/kem/ml_kem/`. Its ML-KEM code is vendored mlkem-native
  (`src/kem/ml_kem/mlkem-native_*`), so liboqs ML-KEM figures measure
  mlkem-native behind liboqs' API and SHA-3 layer.
- [PQClean](../implementations/pqclean.md) — reference/clean C.

## Relevant Papers / Standards

- FIPS 203, *Module-Lattice-Based Key-Encapsulation Mechanism Standard*
  (NIST, 2024).
- [Regev, "The Learning with Errors Problem" (2010)](../../papers/notes/regev-2010.md)
  — the base assumption.
- [Lyubashevsky, Peikert & Regev, "On Ideal Lattices and LWE over Rings" (2010)](../../papers/notes/lyubashevsky-peikert-regev-2010.md)
  — the ring structure ML-KEM's module version sits between.
- [Peikert, "A Decade of Lattice Cryptography" (2016)](../../papers/notes/peikert-2016.md).

## Measured Performance

From `bench/computational/results/simple-speed_kem-grape-nuts.csv`,
wall-clock microseconds per operation on the `grape-nuts` UTCS host;
harness and caveats in
[`bench/computational/simple/README.md`](../../bench/computational/simple/README.md):

| | keygen | encaps | decaps |
| --- | ---: | ---: | ---: |
| ML-KEM-512 | 5.54 | 6.03 | 7.27 |
| ML-KEM-768 | 9.22 | 9.65 | 11.74 |
| ML-KEM-1024 | 13.21 | 14.29 | 16.96 |

Cost scales close to linearly in `k`, as expected when the dominant term
is the `k x k` matrix-vector product over a fixed ring. Read
[experimental-environments.md](../experimental-environments.md) before
quoting these; `grape-nuts` is a shared departmental machine.

Memory, from
[`bench/memory/`](../../bench/memory/README.md) (`grape-nuts`,
2026-09-29), in bytes. Stack is for the AVX2 (`native`) build; the
portable build is 888–952 bytes smaller throughout.

| | keygen stack | encaps stack | decaps stack | heap, any op |
| --- | ---: | ---: | ---: | ---: |
| ML-KEM-512 | 10,048 | 12,672 | 13,440 | 832 |
| ML-KEM-768 | 14,432 | 17,536 | 18,624 | 832 |
| ML-KEM-1024 | 19,456 | 23,072 | 24,640 | 832 |

The 832 bytes of heap are one 4-way SHAKE-128 state allocated by
liboqs' SHA-3 layer, not by the ML-KEM code; see the memory README.

## Open Questions

- Do the three parameter sets differ in *cycles* the same way they
  differ in wall-clock time here? Needs the API harness (`bench/computational/api/`) on a
  host with usable counters.
- How much of encaps/decaps time is SHA3/SHAKE rather than arithmetic?
  This decides whether a hardware SHA-3 instruction would matter more
  than a better NTT.
- ~~What is the actual runtime stack/heap footprint?~~ **Answered
  2026-09-29**: see the memory table under Measured Performance.
- FIPS 203 changed the shared-secret derivation from Kyber round 3. Does
  liboqs' `src/kem/ml_kem/` implement the FIPS version or the round-3
  version, and does that affect cross-implementation test vectors?
  **Partly answered**: the FIPS version. Each `kem_ml_kem_*.c` sets
  `alg_version = "FIPS203"`, and the code is vendored mlkem-native. The
  test-vector half remains open.
