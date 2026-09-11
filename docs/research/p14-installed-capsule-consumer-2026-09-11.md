# P14 Installed Evidence Capsule Consumer

Date: 2026-09-11

## Objective

Connect two already frozen paths without expanding the product boundary: P8/P9
can export and verify a relocated evidence capsule, while P13 can execute a
wheel-installed CLI outside the checkout. P14 proves that the installed CLI is
itself a usable evidence consumer.

## Consumer path

```text
public DBC + BSW intent
  -> communication delivery
  -> self-contained evidence capsule
  -> relocated consumer directory
  -> ephemeral wheel and dependency-free virtual environment
  -> installed workbench verify-evidence-capsule
  -> hash-bound P14 summary
```

The producer runs in the current development environment because generating the
communication delivery needs the declared CAN adapter dependencies. The consumer
environment installs the wheel with `--no-deps --no-index`, removes
`PYTHONPATH/PYTHONHOME`, runs outside the repository, and rejects an installed
module path under the checkout. Capsule verification itself therefore remains a
dependency-free core consumer operation.

## Evidence contract

`installed-capsule-consumer-0.1` is closed and records the runtime, temporary
wheel SHA-256, relocated capsule-report SHA-256, installed verification SHA-256,
verified counts, and seven ordered checks. A successful run must verify all 16
capsule files, 7 artifacts, and 3 declared dependencies. Boolean values are not
accepted as counts by the JSON Schema.

The caller output must be empty or absent. The temporary wheel, producer tree,
relocated capsule, virtual environment, and detailed consumer verification are
deleted at the end; only `installed-capsule-consumer.json` remains.

## CI placement

Windows/Ubuntu Python 3.11 `core-contracts` owns the installed consumer check and
uploads only the P14 summary as
`installed-capsule-consumer-{OS}-python-3.11`. The topology guard fixes the step
owner. The existing runtime and controlled-rejection jobs remain independent.

## Local acceptance

```text
Installed capsule consumer                 passed (7/7 checks)
Capsule inventory/artifacts/dependencies   16/16, 7/7, 3/3
Workbench unittest                         159 passed, 2 environment-skipped
JSON Schema/instance gate                  27 schemas, 45 bound examples passed
CI topology guard                          passed (4 jobs, 3 matrices, 4 failures)
Ruff                                       passed
scoped mypy                                passed (7 sources)
compileall / pip check / diff check        passed
```

## Boundary

P14 does not upload or publish the wheel or capsule, authenticate producer
identity, add a signature or attestation, create CD, add runtime dependencies,
or change CAN/UDS/DTC behavior. Remote Windows/Ubuntu acceptance remains pending
until the implementation is committed and pushed.
