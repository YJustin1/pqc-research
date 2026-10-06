# Post-Quantum Cryptography Research Project
https://docs.google.com/document/d/1h2IEJtxPzZ42d4AqH-J-92tZ6BEUV59pu4D_HvnkW54

## Project Goal

This project studies post-quantum cryptographic (PQC) algorithms and their
practical implementations. The goal is to compare the computational and
communication costs of selected PQC algorithms using existing
implementations, eventually producing a research report evaluating the 
tradeoffs and viability in industry. To show the cost of migrating, the
same measurements are taken on the classical (pre-quantum)
key-establishment algorithms they would replace: X25519, ECDH P-256,
RSA and finite-field DH at 3072 bits, and RSA and finite-field DH at the
weaker but widely deployed 2048 bits (see
[docs/algorithms/classical-baselines.md](docs/algorithms/classical-baselines.md)).
The exact parameter sets measured are listed in
[bench/algorithms.md](bench/algorithms.md).

## Scope

All measurements are taken against existing upstream implementations:
the PQC algorithms from the submodules under `implementations/`, and the
classical baselines from OpenSSL. Our own code is limited to the
benchmarking and analysis tooling needed to measure them (see `bench/`).

## Project Phases

### Phase 1 — Research

Research PQC algorithms, their mathematical foundations, security
assumptions, practical tradeoffs, and existing implementations.

Implementation research includes:

- repository organization
- key generation, encapsulation, and decapsulation
- parameter sets
- cryptographic primitives
- testing methodology
- known-answer tests and test vectors
- reference vs optimized implementations

### Phase 2 — Performance Evaluation

Measure existing implementations of the selected algorithms and of the
classical baselines, and compare:

- execution time
- processor overhead
- memory usage
- key sizes
- ciphertext sizes
- network overhead
- scalability where appropriate

### Phase 3 — Research Report

Document the research, benchmarking methodology, results, and
conclusions.

## Current Status

**Phase 1 — Research**

Current work is focused on understanding existing PQC implementations,
their internal structure, and how their tests validate correctness.

## Repository Structure

- `docs/` — technical notes on the different implementations
- `implementations/` — upstream PQC repositories included as Git submodules
- `papers/` — research papers and reading notes

## Current Implementations

- [mlkem-native](implementations/mlkem-native)
- [PQClean](implementations/pqclean)
- [liboqs](implementations/liboqs) not a PQC implementation itself; a benchmarking/comparison harness over multiple implementations
- OpenSSL 3.5+ (not a submodule) for the classical baselines, and a
  second ML-KEM for a same-library comparison

## Documentation
