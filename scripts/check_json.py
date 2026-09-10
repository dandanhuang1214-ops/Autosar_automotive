from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import FormatChecker
from jsonschema.validators import validator_for
from referencing import Registry, Resource


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return payload


def _declared_versions(schema: dict[str, Any]) -> set[str]:
    version = schema.get("properties", {}).get("schema_version", {})
    declared: set[str] = set()
    if isinstance(version.get("const"), str):
        declared.add(version["const"])
    if isinstance(version.get("enum"), list):
        declared.update(item for item in version["enum"] if isinstance(item, str))
    return declared


def validate_checked_in_json(
    root: Path = Path("."), *, verbose: bool = True
) -> tuple[int, int, int]:
    schema_paths = sorted((root / "schemas").glob("*.json"))
    example_paths = sorted((root / "examples").rglob("*.json"))
    if not schema_paths or not example_paths:
        raise ValueError("No JSON schemas or examples found")

    schemas = {path: _load_object(path) for path in schema_paths}
    resources = [
        (schema["$id"], Resource.from_contents(schema))
        for schema in schemas.values()
        if isinstance(schema.get("$id"), str)
    ]
    registry = Registry().with_resources(resources)
    by_version: dict[str, tuple[Path, dict[str, Any]]] = {}

    for path, schema in schemas.items():
        validator_for(schema).check_schema(schema)
        for version in _declared_versions(schema):
            if version in by_version:
                raise ValueError(f"Duplicate schema_version declaration: {version}")
            by_version[version] = (path, schema)
        if verbose:
            print(f"valid schema: {path.relative_to(root)}")

    validated = 0
    syntax_only = 0
    for path in example_paths:
        payload = _load_object(path)
        instance_version = payload.get("schema_version")
        matched = (
            by_version.get(instance_version)
            if isinstance(instance_version, str)
            else None
        )
        if matched is None:
            syntax_only += 1
            if verbose:
                print(f"valid json (no declared schema): {path.relative_to(root)}")
            continue
        schema_path, schema = matched
        validator = validator_for(schema)(
            schema, registry=registry, format_checker=FormatChecker()
        )
        errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.path))
        if errors:
            error = errors[0]
            location = "/".join(str(item) for item in error.absolute_path) or "<root>"
            raise ValueError(
                f"Schema validation failed for {path.relative_to(root)} at {location} "
                f"against {schema_path.name}: {error.message}"
            )
        validated += 1
        if verbose:
            print(
                f"valid instance: {path.relative_to(root)} "
                f"({schema_path.name})"
            )

    return len(schemas), validated, syntax_only


def main() -> None:
    schema_count, validated, syntax_only = validate_checked_in_json()
    print(
        f"checked {schema_count} schemas, {validated} schema-bound examples, "
        f"{syntax_only} syntax-only examples"
    )


if __name__ == "__main__":
    main()
