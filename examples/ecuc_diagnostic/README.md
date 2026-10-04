# Configuration / independent diagnostic acceptance

Two synthetic ECUC configurations use project 0.9 to require a same-run independent diagnostic after their static object policies pass. This is an explicit acceptance dependency, not a Dcm/CanTp or generated-code mapping.

The committed build is deliberately synthetic and its executable is absent: normal offline runs return blocked (exit 3). No binary, private configuration or historical success is bundled as a runnable target.

See [the guide](../../docs/project/p29-diagnostic-link-guide.md) for offline, installed and fresh OpenBSW build scenarios. Use the scenario script's `--build` only with a real verified P23 build record.
