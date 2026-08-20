# DTC Persistence Integrity Fault Research (R4n)

## Scope

R4n adds deterministic fault evidence around the R4m in-process persistent mirror. It does not implement AUTOSAR NvM block management, redundant blocks, write retries, ROM defaults, flash drivers, asynchronous jobs, or safety qualification.

## Primary Sources

- [AUTOSAR CP R24-11 NvM specification](https://www.autosar.org/fileadmin/standards/R24-11/CP/AUTOSAR_CP_SWS_NVRAMManager.pdf) distinguishes request failure, integrity failure, wrong block ID, write verification failure, and loss of redundancy as separate production errors.
- [AUTOSAR CP R24-11 NV Data Handling Guideline](https://www.autosar.org/fileadmin/standards/R24-11/CP/AUTOSAR_CP_EXP_NVDataHandling.pdf) describes CRC-based integrity handling, write verification/retries, and recovery with configured default data.
- [AUTOSAR CP R24-11 Dem specification](https://www.autosar.org/fileadmin/standards/R24-11/CP/AUTOSAR_CP_SWS_DiagnosticEventManager.pdf) defines event-memory data as a consumer of non-volatile storage behavior while leaving NvM mechanisms to the memory stack.

## Decisions

1. Wrap the in-process mirror in a deterministic envelope containing a canonical JSON payload and SHA-256 checksum. SHA-256 is a lab integrity marker, not an AUTOSAR NvM CRC configuration.
2. `inject_flush_failure` emits `DTC-PERSISTENCE-FLUSH-FAILED` and leaves the previous mirror unchanged and valid.
3. `corrupt_mirror` changes only the stored checksum and emits `DTC-PERSISTENCE-MIRROR-CORRUPTED`.
4. A subsequent `hard_reset` validates the envelope before restore. Invalid integrity emits `DTC-PERSISTENCE-RESTORE-FAILED` and loads an empty safe runtime state.
5. The corrupted mirror remains observable as invalid; the lab does not silently repair or overwrite evidence.
6. Expected fault findings are acceptance evidence. A fault experiment passes only when the exact expected Finding and state transition both occur.

## Experiments

- Flush failure: confirm DTC in runtime, inject a failed flush, then reset and verify the last valid empty mirror is restored.
- Corrupt mirror: confirm and flush DTC, corrupt the checksum, then reset and verify the confirmed payload is rejected and runtime falls back to empty.

## Acceptance

- Intent/schema validation accepts only the three R4n Finding codes.
- Report traces include runtime/persistent status, data presence, checksum, integrity, and Finding code.
- Both fault experiments pass without changing R4m or UDS behavior.
- Full regression and static checks pass.

