# DTC redundant mirror and generation arbitration research

Date: 2026-08-20

## Question

What is the smallest deterministic experiment that proves selection of a usable DTC mirror when two persistent copies disagree or one copy is corrupted?

## Primary-source findings

- AUTOSAR NvM R24-11 defines `NVM_E_LOSS_OF_REDUNDANCY` for a redundant block whose copies differ, whose first instance is corrupted, or whose first instance cannot be read. The check is associated with reading a redundant block.
- The same specification says loss of redundancy is detected when reading the first instance fails and reading the second instance succeeds.
- The AUTOSAR NV Data Handling Guideline describes CRC validation, write verification, retry, and default recovery, but it does not prescribe the Workbench generation-counter algorithm used here.

Sources:

- [AUTOSAR CP R24-11 Specification of NVRAM Manager](https://www.autosar.org/fileadmin/standards/R24-11/CP/AUTOSAR_CP_SWS_NVRAMManager.pdf)
- [AUTOSAR CP R23-11 NV Data Handling Guideline](https://www.autosar.org/fileadmin/standards/R23-11/CP/AUTOSAR_CP_EXP_NVDataHandling.pdf)

## R4o decision

Use two in-process copies, `A` and `B`. Each envelope contains a DTC state, a monotonically increasing integer generation, and a SHA-256 checksum over both. The algorithm is Workbench policy:

1. A flush writes the lower-generation copy with `max(generation) + 1`.
2. Restore rejects copies with invalid checksums.
3. If both copies are valid and equal, either may be selected without a Finding.
4. If valid copies have different generations, the higher generation wins and the read emits `DTC-REDUNDANCY-LOSS` because the stored contents differ.
5. If only one copy is valid, it is restored and `DTC-REDUNDANCY-LOSS` is emitted.
6. Equal generations with divergent valid content are ambiguous; restore refuses to guess and emits `DTC-REDUNDANCY-ARBITRATION-FAILED`.
7. No valid copy produces `DTC-REDUNDANCY-RESTORE-FAILED` and an empty safe runtime state.

## Experiments

- Confirm a DTC, flush it to copy A at generation 1, then hard reset. Copy A must win over the valid but stale generation-0 copy B, while loss of redundancy is reported.
- Repeat the setup, corrupt copy A, then hard reset. The valid generation-0 copy B must be selected, restoring the older empty state while loss of redundancy is reported.
- Unit-test the equal-generation divergent-content guard independently.

Expected fault Findings are part of passing experiment evidence. A step passes only when state, both generations, both integrity results, selected copy, and exact Finding all match.

## Boundary

This stage does not implement AUTOSAR NvM jobs, configured redundant blocks, MemIf/Fee/Ea, CRC configuration, write retries, repair, flash atomicity, generation wraparound, power-loss timing, or safety qualification. SHA-256 and generation metadata exist only inside one deterministic process.
