# P13 Installed Distribution Smoke

Date: 2026-09-11

## Objective

Close the gap between tests that import the source checkout and the way a real
consumer invokes the packaged CLI. P13 builds the declared wheel, installs it
without project dependencies into a new virtual environment, changes to a
directory outside the repository, and invokes the installed `workbench`
console script.

## Consumer path

```text
pyproject.toml + src/
  -> ephemeral wheel
  -> clean virtual environment
  -> installed console script
  -> workbench trace <absolute intent path> WindowPosition
  -> schema-bound smoke report
```

The smoke removes `PYTHONPATH` and `PYTHONHOME`, imports the installed package
with Python isolated mode, and rejects a module path under the checkout. It
also checks the distribution name/version, the command catalog, and the
eight-node public window-control trace.

## Evidence contract

`installed-distribution-smoke-0.1` records the tested wheel filename, byte
size and SHA-256; installed distribution name/version; runtime; and six
completed consumer checks. The output directory must be empty or absent so a
stale wheel cannot be mistaken for the current build. The wheel is deleted
after the checks; CI uploads only the JSON report.

## CI placement

The Windows/Ubuntu Python 3.11 `core-contracts` matrix owns the explicit smoke
and uploads `installed-distribution-smoke-{OS}-python-3.11`. The P12 topology
guard freezes this step in `core-contracts`. The Python 3.14 full-regression
lane exercises the same integration test but remains a runtime-currency lane.

## Local acceptance

```text
Installed wheel consumer smoke            passed (6/6 checks)
Workbench unittest                        156 passed, 2 environment-skipped
JSON Schema/instance gate                 26 schemas, 45 bound examples passed
CI topology guard                         passed (4 jobs, 3 matrices, 4 failures)
Ruff                                      passed
scoped mypy                               passed (6 sources)
compileall / pip check / diff check       passed
```

## Boundary

P13 is distribution readiness, not a release. It does not upload the wheel,
publish to an index, create CD, sign artifacts, issue attestations, authenticate
producer identity, add runtime dependencies, or change automotive behavior.
