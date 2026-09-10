# P12 CI Job Topology

Date: 2026-09-10

## Objective

Split the growing cross-platform CI monolith into explicit responsibility
boundaries without changing Workbench business contracts, removing evidence or
allowing expected failures to hide ordinary failures.

## Frozen topology

```text
core-contracts (Windows, Ubuntu)
  |-- runtime-evidence (Windows, Ubuntu)
  `-- controlled-rejections (Windows, Ubuntu)

runtime-currency (Ubuntu, Python 3.14)
```

This produces seven concrete jobs from four job definitions.

### `core-contracts`

- resolved dependency inventory;
- all unit tests and test-summary artifact;
- trace, DBC/intent, canonical-contract and fault-suite checks;
- JSON Schema/instance validation;
- Ruff and scoped mypy gates.

### `runtime-evidence`

- virtual CAN and complete communication-chain evidence;
- one-command delivery and relocated capsule verification;
- bundle manifest and normal post-hoc verification;
- supervision, log replay, backend-neutral lab and fixed-report review cohort.

### `controlled-rejections`

- evidence bundle tamper rejection;
- capsule receipt tamper rejection;
- unavailable SocketCAN backend/blocked evidence;
- external review SHA mismatch rejection.

The job reconstructs its communication chain, manifest, delivery and capsule
prerequisites independently. It does not download mutable build directories
from `runtime-evidence`. Only the four expected CLI failures use
`continue-on-error`; each is followed by a mandatory checker and evidence
upload.

### `runtime-currency`

The existing Ubuntu/Python 3.14 full-regression, schema, Ruff, mypy and resolved
inventory lane remains independent.

## Topology guard

`scripts/check_ci_topology.py` is dependency-free and freezes:

- the four job identities;
- the two `needs: core-contracts` edges;
- ownership of critical core/runtime/rejection/currency steps;
- exactly four expected failures, all inside `controlled-rejections`;
- independent prerequisite reconstruction rather than `download-artifact`.

The guard is itself executed by `core-contracts`. Three unit tests cover the
valid workflow, an expected-failure step moved into runtime, and a removed core
dependency.

## Local acceptance

```text
CI topology guard                      passed (4 jobs, 3 matrices, 4 failures)
CI topology unit tests                 3/3 passed
Workbench unittest                     154 passed, 2 environment-skipped
JSON Schema/instance gate              25 schemas, 45 bound examples passed
Ruff                                   passed
scoped mypy                            passed
git diff --check                       passed
```

## Boundary

P12 changes orchestration only. Artifact names, schemas, CLI behavior, expected
exit codes and Windows/Linux coverage remain unchanged. It adds no CD,
attestation, remote artifact sharing, new protocol, OpenBSW adapter or hardware
dependency.
