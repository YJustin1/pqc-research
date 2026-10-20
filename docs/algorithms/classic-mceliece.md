# Classic McEliece

## Purpose

Key encapsulation, same interface as ML-KEM, but aimed at a different
point on the tradeoff curve: the most conservative security assumption
available in PQC, bought with public keys measured in hundreds of
kilobytes to a megabyte.

**Not** selected for standardisation in NIST's main track. It advanced
to Round 4 and remains a candidate; ISO standardisation has been
pursued separately. Treat it as a deliberate alternative to ML-KEM, not
a peer standard.

## Cryptographic Family

Code-based. Specifically the **Niederreiter** dual form of the 1978
McEliece cryptosystem, instantiated with **binary Goppa codes**.

The Niederreiter form matters for the size profile: the ciphertext is a
*syndrome* (`mt` bits) rather than a corrupted codeword (`n` bits), which
is why ciphertexts are 96-208 bytes while public keys are enormous.

## Underlying Security Assumption

Two assumptions, both unusually well-aged:

1. **Syndrome decoding** of a random binary linear code is hard (proven
   NP-complete in the general case; the relevant average-case version is
   the actual assumption). The best attacks are information-set decoding
   (ISD), a line of work running from Prange (1962) through
   Stern/Dumer to BJMM and May–Ozerov.
2. **Indistinguishability**: the public matrix, derived from a Goppa
   code, cannot be distinguished from a random matrix.

Our interpretation of why this is the conservative choice: ISD cost
estimates have improved only marginally in ~60 years — the exponent has
barely moved — whereas lattice attack estimates are actively contested
and have shifted within the lifetime of the NIST process. Assumption 2
is the weaker link, since it is code-family-specific, and it is where
attacks on *other* code families (e.g. the various broken structured
variants) have historically landed.

## High-Level Operation

Parameters `m`, `n`, `t`. Field `F_{2^m}`, code length `n`, error weight
`t`, co-dimension `mt`.

**KeyGen**
1. Pick a monic irreducible `g(x)` of degree `t` over `F_{2^m}`.
2. Pick `n` distinct field elements `alpha_1..alpha_n` (the support).
3. Build the `t x n` parity-check matrix over `F_{2^m}`, expand to
   `mt x n` over `F_2`.
4. Gaussian-eliminate to systematic form `[I_mt | T]`. **Publish only
   `T`** — the identity block is implicit. Hence
   `|pk| = mt * (n - mt) / 8` bytes.
5. If step 4 fails (the leading block is singular), **restart from
   step 1**.

Step 5 is the origin of Classic McEliece's heavy-tailed key generation.
Our measurements show a coefficient of variation of 20-27% for keygen,
against 4-8% for every other operation across all three algorithm
families (`bench/computational/simple/README.md:160-164`).

**Encaps**
1. Pick a random vector `e` of length `n` and Hamming weight exactly
   `t`.
2. Ciphertext `C = He` — the syndrome, `mt` bits.
3. Shared secret `K = H(1, e, C)`.

Note there is no message being encrypted. The error vector *is* the
entropy, and the shared secret is hashed straight out of it.

**Decaps**
1. Decode the syndrome with the private Goppa structure
   (Berlekamp–Massey / Patterson) to recover `e`.
2. Recompute and check; on success `K = H(1, e, C)`.
3. On decoding failure, output `H(0, s, C)` with a stored secret `s` —
   implicit rejection, same idea as ML-KEM's, giving IND-CCA2.

**Correctness is unconditional.** Weight-`t` errors in a code designed
to correct `t` errors always decode. There is no failure probability,
unlike ML-KEM.

## Parameter Sets

Sizes verified from
`implementations/liboqs/src/kem/classic_mceliece/kem_classic_mceliece.h`;
NIST levels from the `kem_classic_mceliece_*.c` constructors, line 18.
The two below are the sets in our benchmark set; liboqs carries more.

| | 348864 | 6688128 |
| --- | ---: | ---: |
| `m` / `n` / `t` | 12 / 3488 / 64 | 13 / 6688 / 128 |
| `mt` | 768 | 1664 |
| Public key | 261,120 B (255 KiB) | 1,044,992 B (1020 KiB) |
| Secret key | 6,492 B | 13,932 B |
| Ciphertext | **96 B** | **208 B** |
| Shared secret | 32 B | 32 B |
| Claimed NIST level | 1 | 5 |
| IND-CCA | yes | yes |

The parameter-set name encodes the parameters: `348864` is `n = 3488`,
`t = 64`. The public-key sizes follow exactly from
`mt * (n - mt) / 8`, which is a useful check that the name, the formula
and the header agree — they do for both sets.

Note `keypair_seed` and `encaps_seed` are `0` in the liboqs header
(lines 13-14, 73-74), i.e. liboqs exposes no seed-based keygen API for
this family, unlike ML-KEM.

## Important Concepts

- **Static keys are the intended deployment.** ~32 ms (level 1) to
  ~158 ms (level 5) per keygen is unacceptable per-handshake and
  irrelevant if the key is generated once and used for months. The
  96-208 byte ciphertext is then the smallest of any PQC KEM, so the
  *per-session* bandwidth cost is the best of the three families studied
  here. The megabyte is paid once.
- **The public key does not fit in a TLS handshake.** This is the
  practical blocker, not the speed. 1 MB exceeds typical handshake
  buffers and interacts badly with QUIC's amplification limits.
- **Keygen dominates memory too.** The `mt x n` parity-check matrix for
  6688128 is `1664 * 6688 / 8 = 1,391,104` bytes bit-packed, before the
  systematic-form working copy. Our derivation from the parameters, not
  a measurement — nothing in this repo measures runtime footprint yet.
- **Decaps is more expensive than encaps** (roughly 2.5x at level 1),
  the reverse of the usual intuition, because encapsulation is little
  more than a matrix-vector product while decapsulation runs a full
  algebraic decoder.
- **Constant-time decoding is subtle.** The support permutation and the
  decoder's rejection behaviour are both places where timing can leak.

## Implementations Being Studied

- [liboqs](../implementations/liboqs.md) —
  `src/kem/classic_mceliece/`; our benchmark source.
- [PQClean](../implementations/pqclean.md).

No dedicated focused implementation is in `implementations/`, unlike
ML-KEM (mlkem-native).

## Relevant Papers / Standards

- [McEliece, "A Public-Key Cryptosystem Based on Algebraic Coding
  Theory" (1978)](../../papers/notes/mceliece-1978.md) — the original.
- [Bernstein & Lange, "Post-Quantum Cryptography" (2017)](../../papers/notes/bernstein-lange-2017.md)
  — context on why code-based is treated as the conservative option.
- Classic McEliece NIST Round 4 submission (Bernstein et al.).

## Measured Performance

From `bench/computational/results/simple-speed_kem-grape-nuts.csv`, wall-clock
microseconds per operation:

| | keygen | encaps | decaps |
| --- | ---: | ---: | ---: |
| 348864 | 31,774.76 | 11.47 | 28.79 |
| 6688128 | 157,912.53 | 46.52 | 66.40 |

**Do not quote the keygen figures.** They come from 95 and 19 iterations
respectively, because at ~32 ms and ~158 ms few fit a 3-second budget,
and the distribution is heavy-tailed from the restart loop. The reported
standard deviation mixes real algorithmic spread with sampling error
(`bench/computational/simple/README.md:165-169`). These need the
API harness (`bench/computational/api/`), which can give keygen a fixed sample count instead
of a time budget.

## Open Questions

- How many restarts does keygen actually average? That would separate
  the rejection loop's contribution from the Gaussian elimination's, and
  explain the tail shape directly.
- Does the `f`-variant ("fast" parameter sets, e.g. `348864f`) in liboqs
  change the tail, or only the mean?
- Runtime memory for keygen — derived above, never measured.
- Is there a deployment scenario in our project's scope where a static
  1 MB key is actually acceptable? (The earlier follow-up, whether to
  carry it into an implementation phase, is moot: that phase was dropped
  from scope on 2026-09-28. It stays in the Phase 2 measurements and the
  Phase 3 report as a comparison point.)
