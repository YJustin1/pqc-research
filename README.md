# Post-Quantum Cryptography Research Project
https://docs.google.com/document/d/1h2IEJtxPzZ42d4AqH-J-92tZ6BEUV59pu4D_HvnkW54

## Project Goal

This project studies post-quantum cryptographic (PQC) algorithms and their
practical implementations. The goal is to compare the computational and
communication costs of selected PQC algorithms using existing
implementations, eventually producing a research report evaluating the 
tradeoffs and viability in industry.

## Scope

All measurements are taken against existing upstream implementations
(tracked under `implementations/`). Our own code is limited to the
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

Measure existing implementations of the selected algorithms and compare:

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

## Documentation
