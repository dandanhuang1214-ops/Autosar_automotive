from __future__ import annotations

import argparse
import json
from pathlib import Path

from automotive_workbench.adapters.generate_arxml import summarize_issue_report
from automotive_workbench.adapters.dbc import inspect_dbc, validate_dbc_intent
from automotive_workbench.adapters.canonical_contract import validate_contract_mapping
from automotive_workbench.bsw_intent import trace_signal
from automotive_workbench.experiment import run_suite
from automotive_workbench.can_runtime import run_can_lab
from automotive_workbench.can_supervision import run_can_supervision
from automotive_workbench.can_io import BusConfig, capture_log, decode_log, open_bus, replay_log, run_log_lab
from automotive_workbench.can_backend import probe_can_backend, run_backend_lab
from automotive_workbench.adapters.openbsw_patch import prepare_openbsw_patch
from automotive_workbench.diag_intent import summarize_uds_intent
from automotive_workbench.dtc_intent import summarize_dtc_intent
from automotive_workbench.dtc_lifecycle import run_dtc_lifecycle
from automotive_workbench.dtc_aging import run_dtc_aging_lab
from automotive_workbench.dtc_reset import run_dtc_reset_lab
from automotive_workbench.uds_runtime import probe_uds_backend, run_uds_lab


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="workbench")
    commands = parser.add_subparsers(dest="command", required=True)

    inspect_parser = commands.add_parser("inspect", help="Inspect a supported engineering artifact")
    inspect_parser.add_argument("artifact", type=Path)

    trace_parser = commands.add_parser("trace", help="Trace a signal through a BSW intent model")
    trace_parser.add_argument("intent", type=Path)
    trace_parser.add_argument("signal")

    validate_parser = commands.add_parser("validate-map", help="Validate DBC facts against a BSW intent model")
    validate_parser.add_argument("dbc", type=Path)
    validate_parser.add_argument("intent", type=Path)

    contract_parser = commands.add_parser("validate-contract", help="Validate DBC-to-canonical mappings")
    contract_parser.add_argument("dbc", type=Path)
    contract_parser.add_argument("contract", type=Path)
    contract_parser.add_argument("intent", type=Path)

    suite_parser = commands.add_parser("run-suite", help="Run baseline and fault-injection experiments")
    suite_parser.add_argument("dbc", type=Path)
    suite_parser.add_argument("contract", type=Path)
    suite_parser.add_argument("intent", type=Path)
    suite_parser.add_argument("--output", type=Path, default=Path("output") / "latest")

    can_parser = commands.add_parser("run-can-lab", help="Run virtual CAN send/receive and fault experiments")
    can_parser.add_argument("dbc", type=Path)
    can_parser.add_argument("--output", type=Path, default=Path("output") / "latest")

    supervision_parser = commands.add_parser("run-can-supervision", help="Run periodic CAN and timeout supervision experiments")
    supervision_parser.add_argument("dbc", type=Path)
    supervision_parser.add_argument("--output", type=Path, default=Path("output") / "latest")

    capture_parser = commands.add_parser("capture-log", help="Capture raw CAN frames as can-utils log")
    capture_parser.add_argument("--interface", default="virtual")
    capture_parser.add_argument("--channel", default="workbench")
    capture_parser.add_argument("--count", type=int, default=10)
    capture_parser.add_argument("--timeout", type=float, default=5.0)
    capture_parser.add_argument("--output", type=Path, default=Path("output") / "capture")

    decode_parser = commands.add_parser("decode-log", help="Decode and validate a raw CAN log with a DBC")
    decode_parser.add_argument("log", type=Path)
    decode_parser.add_argument("dbc", type=Path)
    decode_parser.add_argument("--output", type=Path, default=Path("output") / "decode")

    replay_parser = commands.add_parser("replay-log", help="Replay a CAN log to a selected backend")
    replay_parser.add_argument("log", type=Path)
    replay_parser.add_argument("--interface", default="virtual")
    replay_parser.add_argument("--channel", default="workbench")
    replay_parser.add_argument("--gap-ms", type=float)
    replay_parser.add_argument("--output", type=Path, default=Path("output") / "replay")

    log_lab_parser = commands.add_parser("run-log-lab", help="Run capture, decode and replay as one public experiment")
    log_lab_parser.add_argument("dbc", type=Path)
    log_lab_parser.add_argument("--output", type=Path, default=Path("output") / "log-lab")

    probe_parser = commands.add_parser("probe-can-backend", help="Probe a CAN backend without changing the host")
    probe_parser.add_argument("--interface", default="virtual")
    probe_parser.add_argument("--channel", default="workbench")
    probe_parser.add_argument("--output", type=Path, default=Path("output") / "backend-probe")

    backend_lab_parser = commands.add_parser("run-backend-lab", help="Run the same capture/decode/replay contract on a selected backend")
    backend_lab_parser.add_argument("dbc", type=Path)
    backend_lab_parser.add_argument("--interface", default="virtual")
    backend_lab_parser.add_argument("--channel", default="workbench")
    backend_lab_parser.add_argument("--output", type=Path, default=Path("output") / "backend-lab")

    openbsw_patch_parser = commands.add_parser("prepare-openbsw-patch", help="Package local OpenBSW spike changes as evidence")
    openbsw_patch_parser.add_argument("repo", type=Path)
    openbsw_patch_parser.add_argument("--output", type=Path, default=Path("output") / "openbsw-patch")

    uds_lab_parser = commands.add_parser("run-uds-lab", help="Run virtual UDS/ISO-TP diagnostic scenarios")
    uds_lab_parser.add_argument("intent", type=Path)
    uds_lab_parser.add_argument("--interface", default="virtual")
    uds_lab_parser.add_argument("--channel", default="workbench")
    uds_lab_parser.add_argument("--output", type=Path, default=Path("output") / "uds-lab")

    uds_probe_parser = commands.add_parser("probe-uds-backend", help="Probe UDS/ISO-TP diagnostic runtime dependencies and backend")
    uds_probe_parser.add_argument("--interface", default="virtual")
    uds_probe_parser.add_argument("--channel", default="workbench")
    uds_probe_parser.add_argument("--output", type=Path, default=Path("output") / "uds-backend-probe")

    dtc_lifecycle_parser = commands.add_parser(
        "run-dtc-lifecycle",
        help="Run deterministic DTC debounce, healing, read and clear experiments",
    )
    dtc_lifecycle_parser.add_argument("intent", type=Path)
    dtc_lifecycle_parser.add_argument(
        "--output", type=Path, default=Path("output") / "dtc-lifecycle"
    )

    dtc_aging_parser = commands.add_parser(
        "run-dtc-aging-lab",
        help="Run explicit DTC operation-cycle, aging and snapshot experiments",
    )
    dtc_aging_parser.add_argument("intent", type=Path)
    dtc_aging_parser.add_argument("--output", type=Path, default=Path("output") / "dtc-aging")

    dtc_reset_parser = commands.add_parser(
        "run-dtc-reset-lab",
        help="Run deterministic DTC hard-reset and persistence experiments",
    )
    dtc_reset_parser.add_argument("intent", type=Path)
    dtc_reset_parser.add_argument("--output", type=Path, default=Path("output") / "dtc-reset")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "inspect":
            if args.artifact.suffix.casefold() == ".dbc":
                result = inspect_dbc(args.artifact)
            elif args.artifact.name == "uds_intent.json":
                result = summarize_uds_intent(args.artifact)
            elif args.artifact.name == "dtc_intent.json":
                result = summarize_dtc_intent(args.artifact)
            else:
                result = summarize_issue_report(args.artifact)
        elif args.command == "trace":
            result = trace_signal(args.intent, args.signal).to_dict()
        elif args.command == "validate-map":
            result = validate_dbc_intent(args.dbc, args.intent)
        elif args.command == "validate-contract":
            result = validate_contract_mapping(args.dbc, args.contract, args.intent)
        elif args.command == "run-suite":
            result = run_suite(args.dbc, args.contract, args.intent, args.output)
        elif args.command == "run-can-lab":
            result = run_can_lab(args.dbc, args.output)
        elif args.command == "run-can-supervision":
            result = run_can_supervision(args.dbc, args.output)
        elif args.command == "capture-log":
            config = BusConfig(args.interface, args.channel)
            bus = open_bus(config)
            try:
                result = capture_log(bus, args.output, args.count, args.timeout, config)
            finally:
                bus.shutdown()
        elif args.command == "decode-log":
            result = decode_log(args.log, args.dbc, args.output)
        elif args.command == "replay-log":
            config = BusConfig(args.interface, args.channel)
            bus = open_bus(config)
            try:
                result = replay_log(
                    args.log,
                    bus,
                    timestamps=args.gap_ms is None,
                    gap_s=0.001 if args.gap_ms is None else args.gap_ms / 1000,
                    output=args.output,
                    config=config,
                )
            finally:
                bus.shutdown()
        elif args.command == "run-log-lab":
            result = run_log_lab(args.dbc, args.output)
        elif args.command == "probe-can-backend":
            result = probe_can_backend(BusConfig(args.interface, args.channel), args.output)
        elif args.command == "prepare-openbsw-patch":
            result = prepare_openbsw_patch(args.repo, args.output)
        elif args.command == "run-uds-lab":
            result = run_uds_lab(
                args.intent,
                BusConfig(args.interface, args.channel),
                args.output,
            )
        elif args.command == "probe-uds-backend":
            result = probe_uds_backend(BusConfig(args.interface, args.channel), args.output)
        elif args.command == "run-dtc-lifecycle":
            result = run_dtc_lifecycle(args.intent, args.output)
        elif args.command == "run-dtc-aging-lab":
            result = run_dtc_aging_lab(args.intent, args.output)
        elif args.command == "run-dtc-reset-lab":
            result = run_dtc_reset_lab(args.intent, args.output)
        else:
            result = run_backend_lab(
                args.dbc,
                BusConfig(args.interface, args.channel),
                args.output,
            )
    except (OSError, ValueError, KeyError, RuntimeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("status") == "failed":
        return 2
    if result.get("status") == "blocked":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
