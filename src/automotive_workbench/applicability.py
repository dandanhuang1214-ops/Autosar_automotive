from __future__ import annotations

import hashlib
import json
from pathlib import Path


def build_runtime_applicability_profile(
    *,
    variant: str,
    software_version: str,
    inputs: list[Path],
    backend: str,
) -> dict[str, str]:
    fingerprints = [
        {
            "name": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in inputs
    ]
    calibration_identity = json.dumps(
        fingerprints, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "variant": variant,
        "software_version": software_version,
        "calibration_version": (
            f"sha256:{hashlib.sha256(calibration_identity).hexdigest()}"
        ),
        "backend": backend,
    }
