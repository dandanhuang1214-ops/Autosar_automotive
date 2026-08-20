# DTC Reset and Persistence Boundary Research (R4m)

## Scope

R4m verifies a deterministic distinction between volatile DTC runtime state and an in-process persistent mirror across a UDS hard reset. It does not implement AUTOSAR NvM, flash endurance, shutdown timing, power-loss atomicity, startup recovery, DCM/BswM/EcuM integration, or hardware reset behavior.

## Primary Sources

- [AUTOSAR CP R24-11 Diagnostic Event Manager](https://www.autosar.org/fileadmin/standards/R24-11/CP/AUTOSAR_CP_SWS_DiagnosticEventManager.pdf) defines event memory and configurable storage of event-related data in non-volatile memory.
- [AUTOSAR CP R24-11 Mode Management Guide](https://www.autosar.org/fileadmin/standards/R24-11/CP/AUTOSAR_CP_EXP_ModeManagementGuide.pdf) describes the DCM ECU-reset mode flow: the reset type is requested, the positive response transmission is started, and reset execution is triggered after transmit confirmation.
- [python-udsoncan client source](https://github.com/pylessard/python-udsoncan/blob/master/udsoncan/client.py) exposes `Client.ecu_reset(reset_type)` and validates that the positive response echoes the requested reset type.
- [python-udsoncan introduction](https://github.com/pylessard/python-udsoncan/blob/master/doc/source/udsoncan/intro.rst) distinguishes hard and soft reset requests while leaving the actual server reset mechanism to the ECU implementation.

The installed `udsoncan 1.26.1` identifies `hardReset` as type `0x01`. The application payload pair used by this lab is `1101 -> 5101`.

## Decisions

1. Add an explicit DTC persistence policy retaining `status`, `snapshot`, and `extended_data` across `hard_reset`.
2. Keep the persistent mirror in memory and scoped to one lab run. This tests state transitions without claiming file durability or NvM behavior.
3. Require an explicit `flush` event in the deterministic reset experiment. Runtime confirmation before flush must not silently update the persistent mirror.
4. A hard reset discards volatile state and reloads the last persistent mirror. A separate experiment resets a confirmed-but-unflushed DTC and verifies that status, snapshot, and extended data are lost. Any active operation cycle is closed by reset.
5. `clear_dtc` updates both runtime state and the persistent mirror so a later reset cannot resurrect cleared data.
6. Extend the UDS responder with `ECUReset.hardReset`. It sends `5101`, then reloads runtime DTC state from its persistent mirror. The transport remains connected; real bus interruption and boot timing are outside scope.
7. UDS acceptance reads DTC status, snapshot, and extended data after reset; it then clears, resets again, and proves all event-related data remains absent.

## Deterministic Experiment

The reset experiment performs:

1. Start an operation cycle and confirm the DTC in volatile state.
2. Verify the persistent status is still `0x00` before flush.
3. End the operation cycle and explicitly flush status/snapshot/extended data.
4. Hard reset and restore the confirmed record from the mirror.
5. Clear the DTC and its persistent mirror.
6. Hard reset again and verify the record remains absent.

## Expected Wire Evidence

- Hard reset: `1101 -> 5101`.
- After first reset: DTC `0xC00100` remains readable with status `0x28` in the public UDS starting state, together with snapshot and extended data.
- After clear and second reset: DTC status-mask read remains empty; snapshot remains empty; extended-data read returns `7F1931`.

## Acceptance

- Intent validation rejects unsupported persistence policies and reset sequences.
- Reset lab produces JSON/Markdown runtime-versus-persistent traces.
- Virtual and SocketCAN UDS labs produce identical application payload evidence.
- Full regression and static checks pass.
