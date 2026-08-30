# DTC redundancy repair and interrupted-write research

Date: 2026-08-31

## Question

What is the smallest deterministic follow-up to R4o that demonstrates restoration of redundancy without claiming AUTOSAR NvM or flash-level atomicity?

## Primary-source findings

- AUTOSAR CP R24-11 NvM reports `NVM_E_LOSS_OF_REDUNDANCY` when reading a redundant block shows that redundancy has been lost. The described cases include differing contents, a corrupted first instance, and a first-instance read failure followed by a successful second-instance read.
- The AUTOSAR standard-error description lists recovery of the corrupted NV block as the mitigation for loss of redundancy.
- The AUTOSAR NV Data Handling Guideline describes CRC validation, immediate read-back write verification, write retries, and default-data recovery.
- These sources do not define the Workbench generation counter, a scrub schedule, a commit-marker layout, or byte/sector-level power-loss atomicity. Those details remain implementation policy and must not be presented as standardized NvM behavior.

Sources:

- [AUTOSAR CP R24-11 Specification of NVRAM Manager](https://www.autosar.org/fileadmin/standards/R24-11/CP/AUTOSAR_CP_SWS_NVRAMManager.pdf)
- [AUTOSAR CP R24-11 Description of the AUTOSAR standard errors](https://www.autosar.org/fileadmin/standards/R24-11/CP/AUTOSAR_CP_EXP_ErrorDescription.pdf)
- [AUTOSAR CP R23-11 NV Data Handling Guideline](https://www.autosar.org/fileadmin/standards/R23-11/CP/AUTOSAR_CP_EXP_NVDataHandling.pdf)

## R4p decision

Add a deterministic in-process transaction model on top of the R4o copies. An envelope is selectable only when its checksum is valid and its commit marker is set. The commit marker is Workbench metadata, not an AUTOSAR NvM configuration claim.

1. A staged write targets the non-selected or older copy and uses `max(committed generation) + 1`.
2. Until commit, the staged copy is not selectable even if its payload checksum is valid.
3. An interrupted staged write may leave its target uncommitted, but it must not modify the other committed last-good source copy.
4. Repair is allowed only after restore selected one valid committed source copy.
5. Repair copies the selected state and generation into the peer, then commits the peer. The resulting envelopes agree exactly.
6. Repeating repair on two agreeing copies is a no-op, making repair idempotent.
7. Interrupted repair may leave the target uncommitted, but must not modify the selected source copy.
8. If no valid committed source exists, repair refuses to run and reports a structured Finding.

## Minimal experiments and acceptance criteria

### Interrupted normal write

- Start with two committed empty generation-0 copies.
- Confirm the runtime DTC and stage generation 1 into copy A without committing it.
- Hard reset must reject copy A, restore committed copy B, and report degraded redundancy.
- The older committed state is allowed to win; the experiment proves last-good preservation, not durability of the interrupted update.

### Successful repair after degraded restore

- Restore from one valid committed copy while its peer is corrupted or stale.
- Run repair and verify that both copies have the selected state, the selected generation, valid checksums, and committed markers.
- A second hard reset must restore without a loss-of-redundancy Finding.
- Repeating repair must not change state or generation.

### Interrupted repair

- Begin repair into the damaged peer and interrupt before commit.
- Hard reset must still select the original source copy.
- The source checksum, generation, state, and commit marker must remain unchanged.

Each step must compare runtime state, both generations, both integrity results, both commit markers, selected copy, repair outcome, and exact Finding. Expected injected faults are passing evidence only when every field matches.

## Proposed Findings

- `DTC-REDUNDANCY-WRITE-INTERRUPTED`: a staged normal write was intentionally left uncommitted.
- `DTC-REDUNDANCY-REPAIR-INTERRUPTED`: repair was intentionally left uncommitted.
- `DTC-REDUNDANCY-REPAIR-REFUSED`: no valid committed source exists.
- Existing R4o Findings remain responsible for corruption, loss of redundancy, ambiguous arbitration, and restore failure.

## Boundary

R4p will not model MemIf/Fee/Ea jobs, flash programming granularity, erase sectors, wear, retry timing, real power removal, hardware ECC, generation wraparound, concurrency, or safety qualification. A passing experiment only proves the Workbench state machine preserves a committed in-process last-good copy at the modeled interruption points.

## Implementation result

The three experiments were implemented in `dtc_redundancy_repair.py` and exposed through `run-dtc-redundancy-repair-lab`. All 25 trace steps pass, including six expected fault Findings. The implementation also unit-tests refusal without a selected committed source and rejection of an uncommitted newer copy during arbitration.
