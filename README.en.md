# Automotive Software Engineering Workbench

An artifact-based workbench for automotive configuration checks, communication experiments, change-impact analysis and evidence-backed engineering review.

Two public examples—window control and thermal control—share the same declared workflow. Current capabilities include DBC/contract checks, a limited communication object graph, scoped ARXML import, virtual CAN and separately validated OpenBSW POSIX experiments. Engineering review answers 30 fixed questions with replayable citations; lexical search navigates those questions. It is not a general-purpose language-model diagnostic system.

## Reproduce an installed release

Requirements: Python 3.11+, a build environment with setuptools and pip, and network access for initial dependency acquisition. No CAN hardware is required for the default demo.

```bash
python -m venv .venv
# Linux; on Windows use .venv\Scripts\python.exe
.venv/bin/python -m pip install '.[can,dev]'
.venv/bin/python scripts/check_installed_projects.py --output output/installed-projects
```

The script builds a wheel, collects compatible dependency wheels, installs them offline into a fresh second environment and runs the installed `workbench` outside the checkout. It executes both projects, introduces a real DBC scale mismatch, verifies static gating, identifies affected acceptance items and reviews the resulting regression. Finally it moves the evidence and replays integrity and citations with the original paths absent.

Inspect `summary.json`, `commands.json` and `portable/projects/*/bundle/index.html`. The archive retains dependency wheels, versions, input hashes and project evidence. `scale-failure` must fail (exit 2); accepting that expected failure is part of the delivery check. The original example files are never modified.

For a subsequent offline check on the same platform/Python:

```bash
.venv/bin/python scripts/check_installed_projects.py --wheelhouse output/installed-projects/wheelhouse --output output/installed-projects-replay
```

See the [Windows/Linux delivery guide](docs/project/p25-installed-delivery-guide.md), [active roadmap](docs/project/roadmap.md) and [actual progress record](docs/project/progress-log.md). The installed delivery flow at commit `911abc0` passed all seven [CI jobs](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36586481411), including Windows/Ubuntu execution and archive upload. P25 remains in progress: a measured narrated demo and real external-user feedback are still outstanding.

## Evidence boundaries

Default examples use synthetic public inputs and in-process virtual CAN. Vendor ECUC round-trip support, production certification and physical ECU acceptance are not claimed. Hashes and replay establish internal consistency, not producer identity. Existing SocketCAN/OpenBSW execution evidence has its own environment-specific acceptance record.

## ECUC engineering review and change impact

P26 now provides a combined DPA/ECUC review with explicit application ARXML, task-binding and BswM structural checks, separately labeled historical tool observations, and portable before/after impact evidence. See the [workflow guide](docs/project/p26-engineering-review-guide.md) and [acceptance record](docs/project/p26-acceptance.md). Implementation `6433e1c` passed all seven jobs in [run 36864006903](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36864006903). P27 declarative configuration acceptance is next; vendor generation, schedulability and physical ECU behavior remain outside this static scope.

P27 adds `workbench-project-0.6`: one declaration runs baseline/candidate ECUC review, structural change impact and explicit acceptance checks, with portable replay and existing project review/comparison consumers. Two synthetic projects and isolated-wheel workflows are under validation; see the [guide](docs/project/p27-ecuc-acceptance-guide.md) and [acceptance record](docs/project/p27-acceptance.md). Older project contracts remain supported.
