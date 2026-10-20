# PQClean

## Overview

> **Status:** the upstream repository is **archived/retired**
> (`README.md:3-15`), pointing users at successor projects including
> mlkem-native and liboqs. A workflow auto-comments on new issues/PRs. Treat
> it as a historical reference, not an actively maintained target.

## Upstream Repository

https://github.com/PQClean/PQClean

## Repository Structure

## Build System

## Tests

PQClean's distinguishing property is that it is a *test harness for
implementation hygiene* more than a functional test suite. Most of its
~24 test modules check properties of the **source code**, not the
cryptographic output.

### Running the Tests

Pure pytest, run from inside `test/`:

```sh
git submodule update --init      # test/pycparser is a submodule
cd test
pytest -n=auto                   # recommended
```

There is **no `conftest.py`**; parameterization is done per-module with
`pytest.mark.parametrize` over an object model in `test/pqclean.py` that
walks `crypto_kem/*` (and the out-of-scope `crypto_sign/*`) on disk,
then filters by
`META.yml`'s `supported_platforms` against `py-cpuinfo`.

Subset selection is by environment variable (`test/helpers.py:198-289`):
`PQCLEAN_ONLY_TESTS`, `PQCLEAN_SKIP_TESTS`, `PQCLEAN_ONLY_TYPES`,
`PQCLEAN_SKIP_TYPES`, `PQCLEAN_ONLY_SCHEMES`, `PQCLEAN_SKIP_SCHEMES`, and
`PQCLEAN_ONLY_DIFF` (runs `git diff --name-only origin/master` and tests
only touched schemes — unless a change falls outside `crypto_*/`, in which
case everything runs).

Each parametrized case is copied into a random temp directory
(`helpers.isolate_test_files`) so `-n auto` is safe; the docstring notes
Windows *"will create .obj files EVERYWHERE"*.

`helpers.ensure_available(exe)` skips a module when a tool is missing —
**unless `CI` is set**, in which case it hard-fails. Useful to know before
trusting a green local run.

### Test Files

The KEM C drivers live in `test/crypto_kem/`: `functest.c`, `nistkat.c`,
`testvectors.c`, `printparams.c` (plus `hqckat.c` for HQC). Three RNGs
in `test/common/`: `nistkatrng.c` (NIST AES256-CTR-DRBG),
`hqckatrng.c`, and `notrandombytes.c` — a *deterministic* "surf" PRNG
seeded with digits of π, whose header warns it generates *"a PREDICTABLE
and NOT AT ALL RANDOM sequence of bytes"*.

### What Is Actually Tested?

**KEMs are checked by one hashed-output mechanism, with the expected
digest in `META.yml`:** `nistkat-sha256` — NIST KAT, **first test case
only**. `nistkat.c` seeds the CTR-DRBG with `entropy_input[i] = i`, draws a
48-byte seed, re-seeds with it (exactly what NIST's `PQCgenKAT` does for
record 0), then prints `count/seed/pk/sk/ct/ss`. Python SHA-256s that
stdout and compares. The docstring gives the derivation from an original
submission file:
```sh
cat PQCkemKAT_whatever.rsp | head -n 8 | tail -n 6 | sha256sum
```

PQClean's second mechanism, `testvectors-sha256` (its own deterministic
vectors from `notrandombytes.c`), is required only for signatures; see
Open Questions for the unused KEM driver. CI runs the suite in a 32-bit
big-endian PowerPC container, backing the README claim of consistent
vectors *across big-endian and little-endian, 32-bit and 64-bit
machines*.

**`functest.c` checks buffer discipline**, not just correctness: an
8-byte canary `{0x01,0x23,…,0xEF}` is written before and after every
buffer and re-checked after each call, and buffers are `malloc`'d
deliberately misaligned by one byte.

**Source-hygiene checks (the bulk of the suite):**

| Module | Property |
| --- | --- |
| `test_char.py` | no bare `char` (ambiguous signedness) — parses each `.c` with pycparser and walks the AST |
| `test_boolean.py` | no comparison/logical operators or ternaries **in assignments, initialisers or call arguments** — a static constant-time proxy |
| `test_symbol_namespace.py` | every exported symbol starts with `PQCLEAN_<SCHEME>_<IMPL>_` |
| `test_required_symbols.py` | the API must be real symbols, not macros |
| `test_duplicate_consistency.py` | files shared between schemes must be identical after namespace substitution |
| `test_metadata.py` / `test_metadata_sizes.py` | `META.yml` schema; unknown keys are a hard error; sizes cross-checked against compiled `CRYPTO_*BYTES` |
| `test_preprocessor.py` | no `#if*` after code has begun (header guards exempt) |
| `test_makefile_dependencies.py` | touches each source and asserts `make -q` flips — catches missing header deps |
| `test_dynamic_memory.py` | no undefined `malloc/free/realloc/calloc` in the archive |
| `test_linter.py`, `test_format.py` | clang-tidy, astyle (no cppcheck anywhere) |
| `test_api_h.py`, `test_license.py`, `test_no_symlinks.py`, `test_makefiles_present.py` | structural |

**Dynamic analysis**: `test_valgrind.py` runs functest under
`valgrind --error-exitcode=1 --leak-check=yes`;
`test_functest.py::test_functest_sanitizers` rebuilds with
`-fsanitize=address,undefined -fno-sanitize-recover=undefined`.

**No constant-time testing for KEMs.** There is no
`test_no_secret_dependent_branches.py`, and `test/crypto_kem/` contains no
valgrind poisoning at all. PQClean's only `VALGRIND_MAKE_MEM_UNDEFINED`
calls are in the signature driver (`test/crypto_sign/functest.c:164-177`),
and even there they mark the output buffer tail, not the secret key.
Consistent with this, `README.md:92-93` lists *"No branching on secret
data"* and *"No access to secret memory locations"* as **unchecked**
boxes. `test_boolean.py` is the only (static) stand-in.

**CI**: GitHub Actions, one generated workflow per scheme (38 files) from
a Jinja2 template, each with four jobs — `test-native` (amd64/i386 ×
gcc/clang containers), `test-emulated` (qemu-user-static: armhf and
`unstable-ppc`, i.e. 32-bit **big-endian** PowerPC), `test-windows`
(x64/x86 MSVC), `test-macos` (clang + Homebrew gcc11). Travis covered
arm64. `test_workflows.py` fails if the generated workflows drift from
the template.

## Benchmarking

**PQClean does not benchmark, by design.** `README.md:33-37`:

> What PQClean is **not** aiming for is
> * a build system producing an integrated library of all schemes;
> * **including benchmarking of implementations**; and
> * including integration into higher-level applications or protocols.

There is no speed/cycle-counting code anywhere in the tree. Benchmarking
is deferred to downstream consumers, which the README lists as explicit
*goals* (`README.md:27-28`): the code should integrate easily into
**SUPERCOP** and into **pqm4** for embedded targets. PQClean follows the
SUPERCOP layout and the NIST reference API for exactly this reason.

One caveat if these implementations are ever used as a performance
baseline — `README.md:180` warns that the shared `common/` primitives
*"may not be the most performant implementations and may do unnecessary
things (like heap allocations) for our testing purposes."*

## Supported Algorithms / Parameter Sets

Of the algorithms in this project's scope, `crypto_kem/` holds ML-KEM
(`ml-kem-{512,768,1024}`) and Classic McEliece (ten parameter sets,
`mceliece348864` through `mceliece8192128f`). There is **no NTRU**.

## Important Source Files

## Key Generation Call Path

## Encapsulation Call Path

## Decapsulation Call Path

## Randomness

## Hash / XOF Primitives

## Polynomial / Data Representation

## Optimized vs Reference Implementations

## Interesting Observations

## Open Questions

- Given the archival notice, is PQClean still worth studying as anything
  other than a source of test-methodology ideas? Its hygiene checks
  (`test_boolean.py`, `test_duplicate_consistency.py`,
  `test_makefile_dependencies.py`) have no equivalent in the other repos.
- `test_boolean.py` forbids comparisons in assignments/initialisers/call
  arguments as a constant-time proxy. How much does that actually buy,
  given the README leaves the real CT boxes unchecked?
- `test/crypto_kem/testvectors.c` exists but no test module consumes it,
  and `META.yml` only requires `testvectors-sha256` for signatures. Was
  the KEM path abandoned, or is it consumed somewhere we missed?
