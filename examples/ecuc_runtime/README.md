# Synthetic configuration-to-CAN examples

These are public synthetic fixtures, not vendor or customer exports. `integration` has Tx/Rx paths, application/task/mode inputs and two CAN vectors. `transmitter` has one Tx path and one vector. ECUC CanIf addresses are explicitly supplied for these fixtures; the DBC mapping does not prove vendor-generated BSW equivalence.

Run `workbench run-project examples/ecuc_runtime/integration.project.json --channel p29-demo --output output/p29-demo`. Project 0.8 gates the P20 runner on static policy and exact mapping checks. Copy candidate inputs before editing; baseline and candidate initially share the same files. See the [guide](../../docs/project/p29-runtime-link-guide.md) for review, replay, faults and installation.
