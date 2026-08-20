# DTC Extended Data and Negative Scenarios Research (R4l)

## Scope

R4l extends the deterministic DTC experiment with minimal event-related extended data and explicit negative UDS evidence. It does not implement a production AUTOSAR Dem event memory, NVRAM, displacement, OBD policy, OEM record layout, or conformance test suite.

## Primary Sources

- [AUTOSAR CP R24-11 Specification of Diagnostic Event Manager](https://www.autosar.org/fileadmin/standards/R24-11/CP/AUTOSAR_CP_SWS_DiagnosticEventManager.pdf) describes event-related extended data, configurable internal data elements such as occurrence and aging counters, and removal of event-related data when an event ages out.
- [python-udsoncan client source](https://github.com/pylessard/python-udsoncan/blob/master/udsoncan/client.py) exposes `get_dtc_extended_data_by_dtc_number(dtc, record_number, data_size)` for `ReadDTCInformation.reportDTCExtendedDataRecordByDTCNumber`.
- [python-udsoncan project documentation](https://udsoncan.readthedocs.io/en/latest/udsoncan/client.html) states that extended data is ECU-specific raw data and that its size must be supplied by the client configuration or call.

The installed implementation used by this repository is `udsoncan 1.26.1`. Its decoder expects a positive `0x19/0x06` response containing the echoed subfunction, DTC, status byte, then one or more record-number/raw-data pairs of the configured size.

## Decisions

1. Add two one-byte records to the research DTC: record `0x01` is `occurrence_counter`; record `0x02` is `aging_counter`.
2. The public UDS starting state is healed (`status=0x28`) with both counters set to `1`. These are explicit sample values, not inferred OEM values.
3. The deterministic lifecycle increments occurrence only on the first transition into confirmed. Aged-out and clear transitions remove the stored snapshot and extended-data records. The counter policy is deliberately narrower than configurable production Dem behavior.
4. Read records individually with `data_size=1`. This avoids claiming a vendor-neutral multi-record layout where UDS leaves record contents and size ECU-specific.
5. Unknown DTC and unknown record requests return `requestOutOfRange` (`NRC 0x31`). These are responder policies for the lab and are asserted as raw `7F1931` evidence.
6. Clearing the DTC removes its extended-data records; a record read after clear also returns `7F1931`.
7. A malformed snapshot scenario returns an incomplete positive payload and passes only when `udsoncan` rejects it. The report retains a `UDS-DTC-SNAPSHOT-MALFORMED` Finding even though the negative test behaves as expected.
8. The existing cycle-sequence negative test remains authoritative: monitor events outside an active operation cycle produce `DTC-CYCLE-SEQUENCE`.

## Expected Wire Evidence

- Occurrence record: `1906C0010001 -> 5906C00100280101`.
- Aging record: `1906C0010002 -> 5906C00100280201`.
- Unknown DTC or record: `... -> 7F1931`.
- Malformed snapshot: request `1904C0010003`, response `5904C00100`, rejected as incomplete.

## Acceptance

- Intent/schema validation distinguishes positive scenarios from deliberate unknown-DTC/record negative scenarios.
- Virtual and SocketCAN UDS labs pass all scenarios with identical application payloads.
- Lifecycle traces expose occurrence, aging, snapshot storage, and extended-data storage state.
- Full regression, JSON parsing, Python compilation, shell syntax, and diff checks pass.
