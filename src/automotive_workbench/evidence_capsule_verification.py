from __future__ import annotations

import hashlib
import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from automotive_workbench.evidence_bundle import (
    _render_verification as _render_bundle_verification,
    load_evidence_bundle_manifest,
    verify_evidence_bundle,
)
from automotive_workbench.evidence_capsule import _load_delivery, _render_markdown


CAPSULE_KEYS = {
    "artifact_type", "schema_version", "created_at", "status",
    "source_delivery_status", "bundle_id", "bundle_path", "manifest_path",
    "receipt_path", "source_verification_path", "offline_verification_path",
    "manifest_sha256", "receipt_sha256", "source_verification_sha256",
    "offline_verification_sha256", "artifact_count", "verified_artifact_count",
    "dependency_count", "verified_dependency_count", "external_dependency_count",
    "copied_external_dependency_count", "external_dependencies",
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _relative_to(path: Path, parent: Path) -> str | None:
    try:
        return path.relative_to(parent).as_posix()
    except ValueError:
        return None


def _portable_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"{label} must be a portable relative path")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or pure.as_posix() != value:
        raise ValueError(f"{label} must be a portable relative path")
    return value


def _load_capsule_report(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Evidence capsule report must be a regular file")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != CAPSULE_KEYS:
        raise ValueError("Evidence capsule report must use the closed 0.1 schema")
    if payload["artifact_type"] != "evidence-capsule":
        raise ValueError("Unsupported evidence capsule artifact_type")
    if payload["schema_version"] != "evidence-capsule-0.1":
        raise ValueError("Unsupported evidence capsule schema_version")
    if payload["status"] != "passed":
        raise ValueError("Evidence capsule export status must be passed")
    if payload["source_delivery_status"] not in {"passed", "failed", "blocked"}:
        raise ValueError("Evidence capsule source delivery status is invalid")
    for field in ("created_at", "bundle_id"):
        if not isinstance(payload[field], str) or not payload[field].strip():
            raise ValueError(f"Evidence capsule report requires {field}")
    fixed_paths = {
        "bundle_path": "bundle",
        "manifest_path": "manifest.json",
        "receipt_path": "communication-evidence-delivery.json",
        "source_verification_path": "verification/evidence-bundle-verification.json",
        "offline_verification_path": "offline-verification/evidence-bundle-verification.json",
    }
    if any(payload[field] != expected for field, expected in fixed_paths.items()):
        raise ValueError("Evidence capsule report paths are invalid")
    for field in (
        "manifest_sha256", "receipt_sha256", "source_verification_sha256",
        "offline_verification_sha256",
    ):
        if not isinstance(payload[field], str) or re.fullmatch(
            r"[0-9a-f]{64}", payload[field]
        ) is None:
            raise ValueError(f"Evidence capsule report requires {field}")
    for field in (
        "artifact_count", "verified_artifact_count", "dependency_count",
        "verified_dependency_count", "external_dependency_count",
        "copied_external_dependency_count",
    ):
        if (
            not isinstance(payload[field], int)
            or isinstance(payload[field], bool)
            or payload[field] < 0
        ):
            raise ValueError(f"Evidence capsule report count is invalid: {field}")
    if payload["artifact_count"] < 1:
        raise ValueError("Evidence capsule artifact_count must be positive")
    if payload["verified_artifact_count"] != payload["artifact_count"]:
        raise ValueError("Evidence capsule artifact verification count is incomplete")
    if payload["verified_dependency_count"] != payload["dependency_count"]:
        raise ValueError("Evidence capsule dependency verification count is incomplete")
    dependencies = payload["external_dependencies"]
    if not isinstance(dependencies, list):
        raise ValueError("Evidence capsule external_dependencies must be a list")
    normalized: list[tuple[str, str]] = []
    for index, dependency in enumerate(dependencies):
        if not isinstance(dependency, dict) or set(dependency) != {"ref", "sha256"}:
            raise ValueError(f"Evidence capsule external dependency {index} is invalid")
        ref = _portable_path(dependency["ref"], f"external_dependencies[{index}].ref")
        sha256 = dependency["sha256"]
        if not isinstance(sha256, str) or re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
            raise ValueError(f"Evidence capsule external dependency hash is invalid: {ref}")
        normalized.append((ref, sha256))
    if normalized != sorted(normalized) or len(normalized) != len(set(normalized)):
        raise ValueError("Evidence capsule external dependencies must be sorted and unique")
    if payload["external_dependency_count"] != len(normalized):
        raise ValueError("Evidence capsule external dependency count does not match list")
    if payload["copied_external_dependency_count"] != len(normalized):
        raise ValueError("Evidence capsule copied dependency count does not match list")
    return payload


def _finding(code: str, category: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "category": category, "path": path, "message": message}


def _inventory(capsule: Path) -> tuple[dict[str, str], set[str], list[dict[str, str]]]:
    regular: dict[str, str] = {}
    observed: set[str] = set()
    findings: list[dict[str, str]] = []
    for path in sorted(capsule.rglob("*"), key=lambda item: item.relative_to(capsule).as_posix()):
        relative = path.relative_to(capsule).as_posix()
        if path.is_symlink():
            observed.add(relative)
            findings.append(
                _finding(
                    "CAPSULE-SYMLINK-DETECTED",
                    "unsafe-file",
                    relative,
                    "Capsule contains a symbolic link",
                )
            )
        elif path.is_dir():
            continue
        else:
            observed.add(relative)
            if not path.is_file():
                findings.append(
                    _finding(
                        "CAPSULE-SPECIAL-FILE-DETECTED",
                        "unsafe-file",
                        relative,
                        "Capsule contains a non-regular file",
                    )
                )
            else:
                regular[relative] = _sha256_file(path)
    return regular, observed, findings


def _render_verification(result: dict[str, Any]) -> str:
    lines = [
        "# Evidence Capsule Verification",
        "",
        f"- Capsule: `{result['bundle_id']}`",
        f"- Status: **{result['status']}**",
        f"- Files: {result['verified_file_count']}/{result['expected_file_count']} verified",
        f"- Bundle artifacts: {result['verified_artifact_count']}/{result['artifact_count']} verified",
        f"- Dependencies: {result['verified_dependency_count']}/{result['dependency_count']} verified",
        "",
        "## Findings",
        "",
    ]
    if result["findings"]:
        lines.extend(
            f"- `{item['code']}` `{item['path']}`: {item['message']}"
            for item in result["findings"]
        )
    else:
        lines.append("- None.")
    return "\n".join(lines) + "\n"


def verify_evidence_capsule(capsule: Path, output: Path) -> dict[str, Any]:
    if capsule.is_symlink() or not capsule.is_dir():
        raise ValueError("Evidence capsule must be a regular directory")
    if output.is_symlink():
        raise ValueError("Evidence capsule verification output must not be a symlink")
    capsule = capsule.resolve()
    output = output.resolve()
    if _relative_to(output, capsule) is not None:
        raise ValueError("Evidence capsule verification output must be outside the capsule")

    report_path = capsule / "evidence-capsule-report.json"
    report = _load_capsule_report(report_path)
    manifest_path = capsule / report["manifest_path"]
    manifest = load_evidence_bundle_manifest(manifest_path)

    expected: dict[str, str | None] = {
        "evidence-capsule-report.json": None,
        "evidence-capsule-report.md": _sha256_bytes(
            _render_markdown(report).encode("utf-8")
        ),
        report["manifest_path"]: report["manifest_sha256"],
        report["receipt_path"]: report["receipt_sha256"],
        report["source_verification_path"]: report["source_verification_sha256"],
        report["offline_verification_path"]: report["offline_verification_sha256"],
    }
    offline_markdown_sha256: str | None = None
    offline_payload_path = capsule / report["offline_verification_path"]
    if offline_payload_path.is_file() and not offline_payload_path.is_symlink():
        try:
            offline_payload = json.loads(offline_payload_path.read_text(encoding="utf-8"))
            if isinstance(offline_payload, dict):
                offline_markdown_sha256 = _sha256_bytes(
                    _render_bundle_verification(offline_payload).encode("utf-8")
                )
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            pass
    expected["offline-verification/evidence-bundle-verification.md"] = (
        offline_markdown_sha256
    )
    for artifact in manifest["artifacts"]:
        expected[f"bundle/{artifact['relative_path']}"] = artifact["sha256"]
    for dependency in report["external_dependencies"]:
        if dependency["ref"] in expected:
            raise ValueError(f"Capsule dependency collides with reserved inventory: {dependency['ref']}")
        expected[dependency["ref"]] = dependency["sha256"]

    regular, observed, findings = _inventory(capsule)
    file_valid: dict[str, bool] = {}
    for relative in sorted(expected.keys() - observed):
        findings.append(
            _finding(
                "CAPSULE-FILE-MISSING", "missing", relative,
                "Expected capsule file is missing",
            )
        )
        file_valid[relative] = False
    for relative in sorted(observed - expected.keys()):
        findings.append(
            _finding(
                "CAPSULE-FILE-UNEXPECTED", "unexpected", relative,
                "Unlisted capsule file is present",
            )
        )
    for relative in sorted(expected.keys() & observed):
        if relative not in regular:
            file_valid[relative] = False
            continue
        expected_sha256 = expected[relative]
        if expected_sha256 is not None and regular[relative] != expected_sha256:
            findings.append(
                _finding(
                    "CAPSULE-SHA256-MISMATCH", "tampered", relative,
                    "Capsule file SHA-256 differs from its bound value",
                )
            )
            file_valid[relative] = False
        else:
            file_valid[relative] = True

    manifest_external: dict[str, str] = {}
    for artifact in manifest["artifacts"]:
        for dependency in artifact["depends_on"]:
            if dependency["kind"] != "external":
                continue
            prior = manifest_external.get(dependency["ref"])
            if prior is not None and prior != dependency["sha256"]:
                raise ValueError(
                    f"Manifest external dependency has conflicting hashes: {dependency['ref']}"
                )
            manifest_external[dependency["ref"]] = dependency["sha256"]
    report_external = {
        item["ref"]: item["sha256"] for item in report["external_dependencies"]
    }
    if report_external != manifest_external:
        findings.append(
            _finding(
                "CAPSULE-DEPENDENCY-CATALOG-MISMATCH",
                "contract",
                "evidence-capsule-report.json",
                "Capsule dependency catalog differs from manifest dependencies",
            )
        )

    if report["bundle_id"] != manifest["bundle_id"]:
        findings.append(
            _finding(
                "CAPSULE-BUNDLE-ID-MISMATCH", "contract", "manifest.json",
                "Capsule report bundle ID differs from manifest",
            )
        )
    count_fields = (
        ("artifact_count", manifest["artifact_count"]),
        ("external_dependency_count", len(manifest_external)),
    )
    for field, expected_count in count_fields:
        if report[field] != expected_count:
            findings.append(
                _finding(
                    "CAPSULE-COUNT-MISMATCH", "contract",
                    "evidence-capsule-report.json",
                    f"{field} differs from capsule inventory",
                )
            )

    receipt_relative = report["receipt_path"]
    if file_valid.get(receipt_relative, False):
        try:
            receipt = _load_delivery(capsule / receipt_relative)
            receipt_pairs = (
                (receipt["status"], report["source_delivery_status"]),
                (receipt["manifest_sha256"], report["manifest_sha256"]),
                (receipt["verification_sha256"], report["source_verification_sha256"]),
                (receipt["artifact_count"], report["artifact_count"]),
                (receipt["verified_artifact_count"], report["verified_artifact_count"]),
                (receipt["dependency_count"], report["dependency_count"]),
                (
                    receipt["verified_dependency_count"],
                    report["verified_dependency_count"],
                ),
            )
            if any(actual != expected for actual, expected in receipt_pairs):
                raise ValueError("source delivery receipt differs from capsule report")
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            findings.append(
                _finding(
                    "CAPSULE-RECEIPT-INVALID", "contract", receipt_relative, str(exc)
                )
            )

    for field, label in (
        ("source_verification_path", "source"),
        ("offline_verification_path", "offline"),
    ):
        relative = report[field]
        if not file_valid.get(relative, False):
            continue
        try:
            verification = json.loads((capsule / relative).read_text(encoding="utf-8"))
            if (
                not isinstance(verification, dict)
                or verification.get("status") != "passed"
                or verification.get("manifest_sha256") != report["manifest_sha256"]
                or verification.get("verified_artifact_count")
                != report["verified_artifact_count"]
                or verification.get("dependency_count") != report["dependency_count"]
                or verification.get("verified_dependency_count")
                != report["verified_dependency_count"]
            ):
                raise ValueError(f"{label} verification is not passed and manifest-bound")
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            findings.append(
                _finding(
                    "CAPSULE-VERIFICATION-INVALID", "contract", relative, str(exc)
                )
            )

    try:
        with tempfile.TemporaryDirectory() as directory:
            content_verification = verify_evidence_bundle(
                capsule / report["bundle_path"],
                manifest_path,
                Path(directory),
                base=capsule,
            )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        verified_artifacts = sum(
            file_valid.get(f"bundle/{item['relative_path']}", False)
            for item in manifest["artifacts"]
        )
        verified_dependencies = 0
        dependency_count = 0
        for artifact in manifest["artifacts"]:
            for dependency in artifact["depends_on"]:
                dependency_count += 1
                relative = (
                    f"bundle/{dependency['ref']}"
                    if dependency["kind"] == "artifact"
                    else dependency["ref"]
                )
                verified_dependencies += int(file_valid.get(relative, False))
        content_verification = {
            "status": "failed",
            "verified_artifact_count": verified_artifacts,
            "dependency_count": dependency_count,
            "verified_dependency_count": verified_dependencies,
        }
        findings.append(
            _finding(
                "CAPSULE-CONTENT-VERIFICATION-ERROR",
                "dependency",
                "bundle",
                str(exc),
            )
        )
    if content_verification["status"] != "passed":
        findings.append(
            _finding(
                "CAPSULE-CONTENT-VERIFICATION-FAILED",
                "dependency",
                "bundle",
                "Bundle artifacts or dependencies failed P5 verification",
            )
        )

    verified_file_count = sum(file_valid.values())
    timestamp = datetime.now(timezone.utc)
    result = {
        "artifact_type": "evidence-capsule-verification",
        "schema_version": "evidence-capsule-verification-0.1",
        "bundle_id": report["bundle_id"],
        "verified_at": timestamp.isoformat(),
        "capsule_report_sha256": _sha256_file(report_path),
        "manifest_sha256": _sha256_file(manifest_path),
        "source_delivery_status": report["source_delivery_status"],
        "status": "passed" if not findings else "failed",
        "expected_file_count": len(expected),
        "actual_file_count": len(observed),
        "verified_file_count": verified_file_count,
        "artifact_count": manifest["artifact_count"],
        "verified_artifact_count": content_verification["verified_artifact_count"],
        "dependency_count": content_verification["dependency_count"],
        "verified_dependency_count": content_verification["verified_dependency_count"],
        "finding_count": len(findings),
        "findings": findings,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "evidence-capsule-verification.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output / "evidence-capsule-verification.md").write_text(
        _render_verification(result), encoding="utf-8", newline="\n"
    )
    return result
