# Benchmarked algorithms

This is the single list of parameter sets that every benchmark measures:
computational, memory and network. In total, there are 
25 parameter sets: 19 post-quantum KEMs from liboqs and 6 classical
baselines from OpenSSL.  To add or remove a set, change it
here first, then in each script's `ALGS` list:

- `computational/simple/speed_kem_totals.py`
- `memory/run_memory.py` and `computational/api/run_bench.py`, through
  `driver/kem_build.py`, which refuses to build if its list and this
  file disagree

The network tools should reference this list too.

## Security levels

NIST defines each post-quantum security level by comparison with a
problem believed to be equally hard:

| Level | At least as hard as | Classical strength (SP 800-57) |
| ---: | --- | --- |
| 1 | key search on AES-128 | 128 bits |
| 3 | key search on AES-192 | 192 bits |
| 5 | key search on AES-256 | 256 bits |

Levels 2 and 4 (collision search on SHA-256 / SHA-384) are not used by
any set here.

Note:
- The levels associated with the PQC levels are only claims. 
- These levels are in the context of classical attacks. 
A large quantum computer running Shor's algorithm breaks
  all of them, at any key size.

## ML-KEM (FIPS 203) — liboqs & OpenSSL

The number in the name is the dimension of the module lattice: `256 × k`
or `k` polynomials of 256 coefficients each. 

| Set | `k` | Level | Public key (bytes) | Secret key (bytes) | Ciphertext (bytes) |
| --- | ---: | ---: | ---: | ---: | ---: |
| ML-KEM-512 | 2 | 1 | 800 | 1,632 | 768 |
| ML-KEM-768 | 3 | 3 | 1,184 | 2,400 | 1,088 |
| ML-KEM-1024 | 4 | 5 | 1,568 | 3,168 | 1,568 |

Both liboqs & OpenSSL make all three levels available so we can use this data
to compare and evaluate API overhead. 

## Classic McEliece — liboqs

The name concatenates two code parameters. `348864` is `n = 3488`
(code length) and `t = 64` (number of errors the code corrects). `m` is
the bit width of the field the code is built over. These values are
`SYS_N`, `SYS_T` and `GFBITS` in each set's `params.h`. The public key is
the `mt × (n − mt)` bit matrix, which is why it is so large.

**`f` variants ("fast" key generation).** These have the same `n`, `t`
and `m` as the base set, and the same key and ciphertext sizes. Only key
generation differs.

Key generation turns a random matrix into the public key by row
reduction. This only works if the matrix's leading square block reduces
to the identity. When it doesn't, the base keygen discards the attempt
and starts over with fresh randomness. That retry loop is why McEliece
keygen time is heavy-tailed.

The `f` keygen rescues some of those failed attempts. For the last 32
rows, it does not require the pivots to sit in exactly the expected 32
columns. It searches a 64-column window for any 32 columns that work and
swaps them into place (`mov_columns` in
`pqclean_mceliece*f_clean/pk_gen.c`). It still starts over if that
window has no 32 usable columns, or if an earlier row fails.

The secret key records the swap in an 8-byte field at `sk + 32`. The `f`
keygen stores the chosen pivot positions there
(`pqclean_mceliece348864f_clean/operations.c:145`), and the base keygen
stores the fixed value `0xFFFFFFFF`, meaning no swap
(`pqclean_mceliece348864_clean/operations.c:144`). Both formats have the
field, so the secret key is the same size. *Observed for the portable
348864 pair:* the two variants' sources differ only in key generation
(`pk_gen.c`, `pk_gen.h` and the keygen part of `operations.c`), so
encaps and decaps are the same code.

Our interpretation: fewer restarts should make `f` keygen faster on
average and less heavy-tailed. 

| Set | `n` | `t` | `m` | Level | Public key (bytes) | Secret key (bytes) | Ciphertext (bytes) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Classic-McEliece-348864 | 3488 | 64 | 12 | 1 | 261,120 | 6,492 | 96 |
| Classic-McEliece-348864f | 3488 | 64 | 12 | 1 | 261,120 | 6,492 | 96 |
| Classic-McEliece-460896 | 4608 | 96 | 13 | 3 | 524,160 | 13,608 | 156 |
| Classic-McEliece-460896f | 4608 | 96 | 13 | 3 | 524,160 | 13,608 | 156 |
| Classic-McEliece-6688128 | 6688 | 128 | 13 | 5 | 1,044,992 | 13,932 | 208 |
| Classic-McEliece-6688128f | 6688 | 128 | 13 | 5 | 1,044,992 | 13,932 | 208 |
| Classic-McEliece-6960119 | 6960 | 119 | 13 | 5 | 1,047,319 | 13,948 | 194 |
| Classic-McEliece-6960119f | 6960 | 119 | 13 | 5 | 1,047,319 | 13,948 | 194 |
| Classic-McEliece-8192128 | 8192 | 128 | 13 | 5 | 1,357,824 | 14,120 | 208 |
| Classic-McEliece-8192128f | 8192 | 128 | 13 | 5 | 1,357,824 | 14,120 | 208 |

## NTRU — liboqs

Two variants, which name their parameters differently:

- HPS-`q`-`n`: `NTRU-HPS-2048-509` uses modulus `q ` and
  polynomials of degree `n `.
- HRSS-`n`: only `n` is in the name, because HRSS derives `q` from
  `n`.

`n` and `q` are `NTRU_N` and `2^NTRU_LOGQ` in each set's `params.h`. The
difference between the variants is described in
[`ntru.md`](../docs/algorithms/ntru.md).

| Set | `n` | `q` | Level | Public key (bytes) | Secret key (bytes) | Ciphertext (bytes) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| NTRU-HPS-2048-509 | 509 | 2,048 | 1 | 699 | 935 | 699 |
| NTRU-HPS-2048-677 | 677 | 2,048 | 3 | 930 | 1,234 | 930 |
| NTRU-HPS-4096-821 | 821 | 4,096 | 5 | 1,230 | 1,590 | 1,230 |
| NTRU-HPS-4096-1229 | 1229 | 4,096 | 5 | 1,842 | 2,366 | 1,842 |
| NTRU-HRSS-701 | 701 | 8,192 | 3 | 1,138 | 1,450 | 1,138 |
| NTRU-HRSS-1373 | 1373 | 16,384 | 5 | 2,401 | 2,983 | 2,401 |

## Classical baselines — OpenSSL

The first four are **level-matched**: they have 128-bit classical
strength, the level 1 equivalent, and are the like-for-like comparison
with the level 1 PQC sets.

The last two, RSA-2048 and ffdhe2048, are deployment baselines. They
have only 112-bit classical strength, below level 1, so they are not equivalent
strength to any PQC set. They are included because they are what
many deployed systems use today, which makes them what those systems
would be switching from. Consequently, they should be noticeably cheaper 
than their 3072-bit counterparts. 

There is no classical baseline at levels 3 or 5. P-384 could level 3. 
RSA and finite-field DH at those levels need
7680-bit and 15360-bit moduli, which are almost never deployed. 

| Set | What the name means | Matches level | Public key (bytes) | "Ciphertext" (bytes) | Shared secret (bytes) |
| --- | --- | ---: | ---: | ---: | ---: |
| X25519 | Diffie-Hellman on Curve25519, over the prime field `2^255 − 19` | 1 | 32 | 32 | 32 |
| P-256 | ECDH on the NIST curve over a 256-bit prime field | 1 | 65 | 65 | 32 |
| RSA-3072 | RSA with a 3072-bit modulus, as a KEM (RSASVE) | 1 | 384 (modulus) | 384 | 384 |
| ffdhe3072 | Finite-field DH in RFC 7919's 3072-bit group | 1 | 384 | 384 | 384 |
| RSA-2048 | RSA with a 2048-bit modulus, as a KEM (RSASVE) | below 1 (112-bit) | 256 (modulus) | 256 | 256 |
| ffdhe2048 | Finite-field DH in RFC 7919's 2048-bit group | below 1 (112-bit) | 256 | 256 | 256 |

For X25519 and P-256, the "ciphertext" is the ephemeral public key that
DHKEM sends. The P-256 sizes assume uncompressed points. The X25519 and
P-256 shared secrets are 32 bytes because DHKEM runs HKDF over the raw
Diffie-Hellman output.
