# OpenBSW Patch Candidates

This directory stores patch candidates produced during Workbench research.
They are evidence artifacts first, not automatically submitted upstream PRs.

## cpp2can CANFrame classic invariants

- Patch: `0001-cpp2can-add-classic-canframe-invariant-test.patch`
- Source clone: `/home/dev/work/openbsw`
- Upstream remote: `https://github.com/eclipse-openbsw/openbsw.git`
- Base commit: `dbd6e118a9aaa2db36e4461ce76655e8f285598d`
- Target file: `libs/bsw/cpp2can/test/src/can/canframes/CANFrameTest.cpp`

Intent:

The test locks down classic CAN assumptions used by Workbench while reading
OpenBSW as a runtime/source reference:

- classic CAN payload length is 8 bytes;
- base CAN ID maximum matches `CanId::MAX_RAW_BASE_ID`;
- extended CAN ID maximum matches `CanId::MAX_RAW_EXTENDED_ID`;
- constructors preserve max base/extended raw ID and payload length.

Validation already recorded in `docs/project/progress-log.md`:

```bash
cmake --build --preset tests-posix-debug --target cpp2canTest --parallel
ctest --preset tests-posix-debug -R CANFrameTest --output-on-failure
ctest --preset tests-posix-debug -L cpp2canTest --output-on-failure
ctest --preset tests-posix-debug --output-on-failure
```

Results:

```text
CANFrameTest: 7/7 passed
cpp2canTest label: 34/34 passed
full tests-posix-debug CTest: 1879/1879 passed
```

P11 drift revalidation at upstream commit
`000520435cf5f3b287de7aea1a4b52bd005e48ce`:

```text
git apply --check: passed
CANFrameTest: 7/7 passed
cpp2canTest label: 44/44 passed
full tests-posix-debug CTest: 2572/2572 passed
```

The replay is valid for the classic/non-FD `tests-posix-debug` configuration.
`CANFrame::MAX_FRAME_LENGTH` may be 64 when
`CPP2CAN_USE_64_BYTE_FRAMES` is enabled, so the test must not be presented as a
universal CAN FD invariant. The historical patch is intentionally unchanged;
see `docs/research/openbsw-p11-drift-revalidation-2026-09-10.md` for the drift
report and current upstreaming decision.

Upstream readiness note:

OpenBSW's `CONTRIBUTING.md` asks contributors to discuss work with the team
through an issue before investing significant time in a PR, and accepted
contributions require the Eclipse Contributor Agreement. Because this patch is
a narrow Workbench research guardrail, the next upstream step should be opening
or joining an issue with this rationale before creating a PR.
