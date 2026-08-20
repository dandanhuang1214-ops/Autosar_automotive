# DTC Operation Cycle, Aging and Snapshot Research

Date: 2026-08-20

## Scope

This spike defines the R4k research boundary for explicit diagnostic operation cycles, DTC aging and snapshot evidence. It does not implement a production AUTOSAR Dem, event memory displacement, NVRAM, combined events, OBD legislation or OEM-specific policies.

## Sources

- [AUTOSAR Classic Platform R25-11](https://www.autosar.org/standards/classic-platform/) is the current public Classic Platform release as of this research.
- [AUTOSAR CP R24-11 Diagnostic Event Manager](https://www.autosar.org/fileadmin/standards/R24-11/CP/AUTOSAR_CP_SWS_DiagnosticEventManager.pdf) is the directly accessible public Dem specification used for the detailed behavior baseline.
- [udsoncan client documentation](https://udsoncan.readthedocs.io/en/latest/udsoncan/client.html) documents `ReadDTCInformation` snapshot APIs and DID-based snapshot decoding.
- [python-udsoncan source](https://github.com/pylessard/python-udsoncan/blob/master/udsoncan/client.py) is the primary implementation reference. The installed `udsoncan 1.26.1` source was also inspected locally for exact request and response parsing.

## Findings

1. Operation-cycle restart or transition is a calculation trigger for event failure handling and aging. R4k therefore requires explicit `operation_cycle_start` and `operation_cycle_end` events instead of treating repeated monitor samples as cycles.
2. Aging is meaningful only for a stored event that is qualified passed. The research model increments aging only at cycle end when the monitor ran and reported pass; a failed cycle resets the aging counter.
3. Reaching the configured aging threshold clears the confirmed state. The AUTOSAR Dem specification also removes associated snapshot and extended data when an event ages out. R4k removes the in-memory snapshot at the same transition.
4. Snapshot data represents operating conditions captured at malfunction detection. Trigger policy is configurable; R4k deliberately selects the first transition to confirmed and stores one record only.
5. `udsoncan.Client.get_dtc_snapshot_by_dtc_number()` supports UDS `0x19`, subfunction `0x04`. The request for DTC `0xC00100`, record `0x01` is `1904C0010001`. The response format is DTC, status, record number, DID count, DID and encoded data.

## Decision

- Keep the R4j threshold-only lifecycle unchanged as `experiments`.
- Extend `dtc-intent-0.1` with DTC-level `aging_threshold` and `snapshot`, plus separate `cycle_experiments`.
- Add a deterministic `run-dtc-aging-lab` runtime with explicit cycle state, aging counter and snapshot storage.
- Use UDS status bits in the cycle model: after clear/not tested `0x50`, pending failed `0x27`, confirmed failed `0x2F`, qualified pass before cycle end `0x2C`, healed after one aging cycle `0x28`, and aged-out `0x00` for this configured research policy.
- Capture snapshot record `0x01` on the first confirmed transition. The public sample stores DID `0xF111` (`WindowPositionSnapshot`) with value `42`.
- Extend the existing virtual/SocketCAN UDS lab with snapshot read before clear and snapshot read after clear. Expected payloads are `1904C0010001 -> 5904C00100280101F1112A` before clear and `1904C0010001 -> 5904C0010000` after clear.

## Exit Criteria

- Deterministic cycle experiment reaches confirmed, healed and aged-out with the expected status bytes.
- Aging advances only on tested, passed cycle end.
- Snapshot is captured once on confirmation and removed on aged-out or clear.
- `udsoncan` decodes the snapshot DID/value over virtual and SocketCAN backends.
- Reports retain raw request/response payloads and structured mismatch Findings.
