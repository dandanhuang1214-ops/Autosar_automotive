# OpenBSW P11 Drift Revalidation

Date: 2026-09-10

## Objective

Revalidate the frozen OpenBSW research patch and source anchors against the
current upstream `main` without changing the Workbench runtime architecture or
treating OpenBSW as an AUTOSAR Classic replacement.

## Fixed revisions

| Role | Commit | Commit date | Subject |
|---|---|---|---|
| Workbench R3 base | `dbd6e118a9aaa2db36e4461ce76655e8f285598d` | 2026-08-11 | `Fix common depending on configuration in CMake targets` |
| Revalidation target | `000520435cf5f3b287de7aea1a4b52bd005e48ce` | 2026-09-09 | `Add PLATFORM_SUPPORT feature flags to Bazel` |

Upstream comparison:
[`dbd6e118...00052043`](https://github.com/eclipse-openbsw/openbsw/compare/dbd6e118a9aaa2db36e4461ce76655e8f285598d...000520435cf5f3b287de7aea1a4b52bd005e48ce).

The clean target was cloned into `/tmp/openbsw-p11`; the historical clone at
`/home/dev/work/openbsw` and its uncommitted research test were not modified.
`LICENSE` is unchanged. `NOTICE.md` changed to record ETL 20.49.0, STM32 RTOS
ports and a fixed CodeCoverage revision.

## Scoped drift

The repository-wide comparison contains 904 changed files, so P11 inspected
only the source areas used by the R3 learning and patch evidence.

| Scope | Changed files | Insertions | Deletions | Relevance |
|---|---:|---:|---:|---|
| `libs/bsw/cpp2can` | 10 | 434 | 3 | Adds `MaskFilter`, CAN-FD build wiring and ten cpp2can tests |
| `libs/bsw/docan` | 24 | 4,199 | 4 | Adds extended, normal-fixed and range-extended addressing plus integration tests |
| POSIX referenceApp platform | 8 | 124 | 4 | Keeps `vcan0`; adds configurable CAN FD and Bazel metadata |
| referenceApp application | 45 | 2,970 | 174 | Expands DoCAN/UDS and SOME/IP demo behavior |
| `CMakePresets.json` | 1 | 104 | 0 | Adds current build presets, including CAN FD and board variants |

This is meaningful upstream growth, but it does not require Workbench to add
DoIP, SOME/IP, Rust, Bazel or a new board adapter. Those remain trigger-driven
future work.

## Source-anchor result

The original learning path remains observable:

- `CanDemoListener::run()` still filters `0x123` and `0x124`;
- `frameReceived()` still responds with `received ID + 1`, preserving the
  `0x123 -> 0x124` exercise;
- `DemoSystem::cyclic()` still sends `0x558` once per second;
- POSIX `CanSystem` still opens `vcan0` and services the transceiver from a
  fixed-rate task.

The POSIX configuration now explicitly selects classic CAN or CAN FD. The
classic path remains the default; `PLATFORM_CAN0_USE_FD` enables CAN FD and bit
rate switching. This is an adapter/configuration drift, not a break in the
classic learning path.

## Patch replay and tests

Patch under test:
`patches/openbsw/0001-cpp2can-add-classic-canframe-invariant-test.patch`.

Environment:

```text
Ubuntu 24.04
GCC/G++ 13.3.0
CMake/CTest 3.28.3
OpenBSW tests-posix-debug preset
```

Commands and results:

```text
git apply --check <patch>                         passed
cmake --preset tests-posix-debug                  passed
cmake --build --preset tests-posix-debug \
  --target cpp2canTest --parallel                 passed
ctest --preset tests-posix-debug \
  -R CANFrameTest --output-on-failure             7/7 passed
ctest --preset tests-posix-debug \
  -L cpp2canTest --output-on-failure              44/44 passed
cmake --build --preset tests-posix-debug \
  --parallel                                      passed (748 actions)
ctest --preset tests-posix-debug \
  --output-on-failure                             2572/2572 passed
Workbench unittest                               151 passed, 2 skipped
Workbench JSON Schema / instance gate             25 schemas, 45 instances passed
Workbench Ruff and git diff checks                passed
```

The old R3 baseline was 34 cpp2can tests and 1,879 total tests. The increase to
44 and 2,572 is upstream test growth; the replayed Workbench test contributes
one test in both totals.

## Applicability boundary

The patch remains valid for the `tests-posix-debug` classic CAN configuration.
It must not be cited as proof that every OpenBSW build has an eight-byte frame:
`CANFrame::MAX_FRAME_LENGTH` is 64 when `CPP2CAN_USE_64_BYTE_FRAMES` is defined.
The base and extended identifier limits remain semantically stable; upstream
now expresses the base maximum as `(1U << BASE_ID_BITS) - 1U`.

Therefore the historical patch remains unchanged as evidence. Before any
upstream issue or PR, its rationale should explicitly say “classic/non-FD
configuration” and should be discussed with the OpenBSW maintainers as required
by their contribution process.

## Decision

P11 drift revalidation is complete. The patch applies cleanly and all targeted
and full POSIX tests pass at the fixed target commit. No Workbench/OpenBSW
runtime adapter is added, no S32K148 hardware purchase is required, and no
upstream issue or PR is opened automatically.
