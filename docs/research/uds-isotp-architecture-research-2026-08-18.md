# UDS/ISO-TP Architecture Research

Date: 2026-08-18  
Status: architecture selected for R4 implementation

## Goal

Select the first diagnostic architecture for Automotive Workbench after the CAN
runtime, log replay, SocketCAN backend, and OpenBSW POSIX spike are stable.

The goal is a deterministic engineering lab for UDS over ISO-TP, not a full DCM,
DEM, security access, flash programming, or commercial diagnostic tool clone.

## Current Workbench Shape

Existing CAN layers:

- `can_io.BusConfig` defines backend-neutral CAN bus access.
- `can_io.open_bus()` opens `python-can` buses for `virtual` and `socketcan`.
- `can_io.capture_log()`, `decode_log()`, and `replay_log()` persist raw evidence.
- `can_backend.probe_can_backend()` classifies backend availability as
  `available` or `blocked` with a structured reason.
- `run_backend_lab()` already proves the same contract on virtual CAN and
  SocketCAN when `vcan0` exists.

Implication: UDS should be added as another runtime layer above the same CAN
backend concept. It should not bypass the artifact/result/finding model.

## Source Findings

### python-can

Official `python-can` documentation describes `Bus` as the common wrapper around
physical or virtual CAN interfaces, with `send()` and `recv()` as the shared
message API. Its virtual interface is explicitly intended for OS- and
driver-independent tests in one process, where buses on the same channel receive
each other's messages.

Project implication:

- Keep `python-can virtual` as the default CI-safe diagnostic lab backend.
- Keep SocketCAN as the Linux integration backend.
- Do not add hardware-specific diagnostic code in R4.

Sources:

- https://python-can.readthedocs.io/en/v4.2.2/bus.html
- https://python-can.readthedocs.io/en/v4.2.2/interfaces/virtual.html

### can-isotp

`can-isotp` v2.x provides a pure Python ISO-TP implementation that can be coupled
with `python-can`, plus a wrapper around Linux SocketCAN ISO-TP sockets. Its
v2.x documentation notes better timing behavior than v1.x, blocking I/O, and
`NotifierBasedCanStack` support to avoid starving other bus readers.

Project implication:

- Use `isotp.NotifierBasedCanStack` for the first portable path.
- Keep `isotp.socket` / kernel ISO-TP as an optional Linux-specific transport.
- Configure R4 for classic CAN first with `tx_data_length=8`; postpone CAN FD.

Sources:

- https://can-isotp.readthedocs.io/en/latest/
- https://can-isotp.readthedocs.io/en/latest/isotp/socket.html
- https://github.com/pylessard/python-can-isotp/releases

### udsoncan

`udsoncan` treats UDS as an application layer over a separate transport
connection. It provides `PythonIsoTpConnection` for a `can-isotp` transport layer
and `IsoTPSocketConnection` for Linux SocketCAN ISO-TP sockets. Its examples show
UDS over `python-can` + `can-isotp` and DID reads through
`read_data_by_identifier`.

Project implication:

- Use `udsoncan` for UDS client behavior instead of hand-encoding all positive
  and negative response rules.
- Keep the first service set narrow: `DiagnosticSessionControl` may be optional;
  `ReadDataByIdentifier` is the main smoke service.
- Build a tiny deterministic ECU responder locally instead of depending on a
  full server stack or external ECU.

Sources:

- https://udsoncan.readthedocs.io/en/latest/udsoncan/connection.html
- https://udsoncan.readthedocs.io/en/latest/udsoncan/examples.html
- https://github.com/pylessard/python-udsoncan/blob/master/doc/source/udsoncan/examples.rst

### Linux kernel ISO-TP

The Linux kernel documentation describes ISO-TP as part of SocketCAN using
`PF_CAN`, `SOCK_DGRAM`, and `CAN_ISOTP`; user space sends and receives ISO-TP
payloads while the kernel handles transport segmentation. The kernel path is
Linux-specific and tied to CAN interface availability.

Project implication:

- Treat kernel ISO-TP as the later SocketCAN integration path for WSL/Linux.
- Do not make it mandatory for CI or Windows development.
- Reuse the existing `probe` pattern to classify missing kernel/interface
  support as `blocked`, not `failed`.

Source:

- https://cdn.kernel.org/doc/html/latest/networking/iso15765-2.html

## Architecture Options

### Option A: hand-written UDS and ISO-TP

Rejected for R4.

It would maximize control but duplicates protocol behavior that existing
libraries already implement. It also risks turning the project into a protocol
implementation exercise instead of an artifact/evidence workbench.

### Option B: udsoncan + can-isotp + python-can, virtual first

Selected as the primary R4 architecture.

This path matches the existing Workbench split:

```text
UDS intent / diagnostic scenario
        ↓
UDS client orchestration          udsoncan
        ↓
ISO-TP transport                  can-isotp NotifierBasedCanStack
        ↓
CAN backend                       python-can Bus via BusConfig
        ↓
Evidence                          JSON/Markdown + Finding
```

Strengths:

- works with `python-can virtual` for deterministic local tests;
- can later target SocketCAN through the same `BusConfig` idea;
- keeps UDS behavior at the application layer and ISO-TP behavior at the
  transport layer;
- avoids implementing segmentation, flow control, and UDS response parsing by
  hand.

Weaknesses:

- user-space ISO-TP timing is not a production conformance baseline;
- a small local responder is still needed because `udsoncan` is primarily a
  client-side library;
- concurrency around `python-can.Notifier` must be owned carefully.

### Option C: udsoncan + Linux kernel ISO-TP socket first

Deferred.

This is the better Linux integration path once `vcan0`/SocketCAN is available,
but it is not portable to Windows and would make the first diagnostic lab depend
on host network interface state.

### Option D: OpenBSW DoCAN first

Deferred.

OpenBSW DoCAN is useful as a source-learning and later comparison path, but R3
showed that Workbench should not couple its first deterministic diagnostic lab to
OpenBSW runtime behavior. The Workbench baseline should remain Python-based
until the diagnostic contract is stable.

## Selected R4 Architecture

### Dependency Model

Add a new optional dependency group:

```toml
[project.optional-dependencies]
diag = [
  "cantools>=41.4,<42",
  "python-can>=4.6,<5",
  "can-isotp>=2.0,<3",
  "udsoncan>=1.26,<2",
]
```

Keep the existing `can` extra unchanged for users who only need CAN/DBC.

### Modules

Proposed files:

```text
src/automotive_workbench/diag_intent.py
src/automotive_workbench/uds_runtime.py
src/automotive_workbench/uds_report.py      optional if report rendering grows
schemas/uds-intent.schema.json
examples/window_control/uds_intent.json
tests/test_uds_runtime.py
```

`diag_intent.py`:

- loads and validates a small vendor-neutral diagnostic intent;
- defines ECU logical name, request/response CAN IDs, DID definitions,
  expected codecs, and scenario definitions.

`uds_runtime.py`:

- opens the selected `BusConfig`;
- creates an ISO-TP transport pair;
- runs a deterministic local ECU responder thread for the first lab;
- drives `udsoncan.Client` through `PythonIsoTpConnection`;
- emits `TestResult`-shaped dictionaries and `Finding` records.

`uds_report.py`:

- only split out when Markdown rendering becomes large.

### Minimal UDS Intent

First schema should stay small:

```json
{
  "artifact_type": "uds-intent",
  "ecu": "WindowController",
  "transport": {
    "addressing": "normal_11bit",
    "request_id": 1792,
    "response_id": 1800,
    "tx_data_length": 8
  },
  "dids": [
    {
      "id": 61840,
      "name": "VehicleIdentificationNumber",
      "codec": "ascii",
      "length": 17,
      "value": "AWBDEMO0123456789"
    }
  ],
  "scenarios": [
    {"name": "read_vin", "service": "ReadDataByIdentifier", "did": 61840},
    {"name": "unknown_did_nrc", "service": "ReadDataByIdentifier", "did": 4660},
    {"name": "response_timeout", "service": "ReadDataByIdentifier", "did": 61841}
  ]
}
```

Use decimal IDs in JSON to avoid ambiguity, and render hexadecimal IDs in
reports.

### First Lab Scenarios

R4 should initially prove:

1. `read_vin`: request `0x22 F190`, receive positive response `0x62 F190 ...`.
2. `unknown_did_nrc`: request unsupported DID, receive NRC such as
   `0x31 requestOutOfRange`.
3. `response_timeout`: intentionally no response, classify timeout as expected.
4. `malformed_payload`: optional second step, inject bad response length and
   emit a deterministic `Finding`. Completed in R4g with
   `UDS-MALFORMED-PAYLOAD`.

### CLI

Add:

```bash
python -m automotive_workbench.cli run-uds-lab \
  examples/window_control/uds_intent.json \
  --interface virtual \
  --channel workbench-uds \
  --output output/uds-lab
```

Later SocketCAN run:

```bash
python -m automotive_workbench.cli probe-uds-backend --interface socketcan --channel vcan0
python -m automotive_workbench.cli run-uds-lab examples/window_control/uds_intent.json --interface socketcan --channel vcan0
```

### Evidence Output

Persist:

```text
output/uds-lab/uds-lab-report.json
output/uds-lab/uds-lab-report.md
```

Include:

- run ID, timestamps, duration;
- `BusConfig`;
- ISO-TP params;
- request/response CAN IDs;
- service ID, DID, raw request/response payload hex;
- decoded values;
- scenario status;
- findings for timeout, NRC, malformed payload, transport setup failure.

### Finding Codes

Initial deterministic codes:

```text
UDS-BACKEND-BLOCKED
UDS-TRANSPORT-SETUP-FAILED
UDS-POSITIVE-RESPONSE-MISMATCH
UDS-NEGATIVE-RESPONSE
UDS-RESPONSE-TIMEOUT
UDS-DID-DECODE-ERROR
UDS-UNEXPECTED-FRAME
```

## Implementation Risks

- `python-can` virtual buses work inside one process; R4 tests should keep the
  client and fake ECU responder in one process.
- `can-isotp.NotifierBasedCanStack` needs notifier lifecycle cleanup; tests must
  stop notifier/transport/bus objects in `finally`.
- `udsoncan` exception classes should be mapped into deterministic Workbench
  `Finding` codes instead of leaking library-specific tracebacks into reports.
- SocketCAN kernel ISO-TP support depends on Linux kernel and interface state;
  probe failures should be `blocked`.
- Keep UDS intent separate from DBC/canonical contract. A DID may reference a
  canonical signal later, but R4 should not force that cross-link.

## Recommendation

Use Option B for R4:

```text
udsoncan Client
  over PythonIsoTpConnection
  over can-isotp NotifierBasedCanStack
  over python-can BusConfig virtual/socketcan
  producing Workbench TestResult/Finding evidence
```

Do not start with OpenBSW DoCAN or kernel ISO-TP as the primary route. Keep them
as later validation/comparison backends once the Python diagnostic contract is
stable.

## R4 Slice

### R4a: Architecture and dependency decision

This document. Status: complete.

### R4b: Intent and schema

Add `schemas/uds-intent.schema.json` and
`examples/window_control/uds_intent.json`.

### R4c: Virtual UDS lab

Implement `run_uds_lab()` with a local deterministic ECU responder and the three
core scenarios: positive DID read, NRC, timeout.

### R4d: Evidence and CLI

Persist JSON/Markdown reports and expose `run-uds-lab` in the CLI.

### R4e: SocketCAN probe

Add a Linux-specific ISO-TP probe once the virtual lab is green.
