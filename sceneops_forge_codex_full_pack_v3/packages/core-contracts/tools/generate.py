#!/usr/bin/env python3
"""Generate JSON Schema and TypeScript declarations from Pydantic contracts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, Mapping, MutableMapping, Optional, Sequence

from pydantic import TypeAdapter


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT / "src"))

from sceneops_core_contracts.ids import ID_PATTERNS  # noqa: E402
from sceneops_core_contracts.models import (  # noqa: E402
    CONTRACT_VERSION,
    PUBLIC_ENUMS,
    PUBLIC_MODELS,
)


GENERATED_HEADER = "// Generated from Python Pydantic contracts. Do not edit."


def _schema_filename(model_name: str) -> str:
    words = re.sub(r"(?<!^)(?=[A-Z])", "-", model_name).lower()
    return f"{words}.schema.json"


def render_json_schemas() -> Dict[Path, str]:
    rendered: Dict[Path, str] = {}
    for model in PUBLIC_MODELS:
        schema = model.model_json_schema(ref_template="#/$defs/{model}")
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = f"https://sceneops.local/schemas/core/v1/{_schema_filename(model.__name__)}"
        path = PACKAGE_ROOT / "schemas" / "v1" / _schema_filename(model.__name__)
        rendered[path] = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    return rendered


def _literal(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return json.dumps(value, ensure_ascii=False)


def _typescript_type(schema: Mapping[str, object]) -> str:
    reference = schema.get("$ref")
    if isinstance(reference, str):
        return reference.rsplit("/", 1)[-1]

    pattern = schema.get("pattern")
    if isinstance(pattern, str):
        for name, candidate in ID_PATTERNS.items():
            if pattern == candidate:
                return name

    if "const" in schema:
        return _literal(schema["const"])

    enum_values = schema.get("enum")
    if isinstance(enum_values, list):
        return " | ".join(_literal(value) for value in enum_values)

    variants = schema.get("anyOf") or schema.get("oneOf")
    if isinstance(variants, list):
        rendered = []
        for variant in variants:
            if isinstance(variant, dict):
                value = _typescript_type(variant)
                if value not in rendered:
                    rendered.append(value)
        return " | ".join(rendered) if rendered else "unknown"

    schema_type = schema.get("type")
    if schema_type == "string":
        return "string"
    if schema_type in {"integer", "number"}:
        return "number"
    if schema_type == "boolean":
        return "boolean"
    if schema_type == "null":
        return "null"
    if schema_type == "array":
        items = schema.get("items")
        item_type = _typescript_type(items) if isinstance(items, dict) else "unknown"
        return f"Array<{item_type}>"
    if schema_type == "object":
        properties = schema.get("properties")
        if isinstance(properties, dict):
            required = set(schema.get("required", []))
            fields = []
            for name, value in properties.items():
                if not isinstance(value, dict):
                    continue
                marker = "" if name in required else "?"
                fields.append(f"{json.dumps(name)}{marker}: {_typescript_type(value)}")
            return "{ " + "; ".join(fields) + " }"
        additional = schema.get("additionalProperties")
        if isinstance(additional, dict):
            return f"Record<string, {_typescript_type(additional)}>"
        return "Record<string, unknown>"
    return "unknown"


def _collect_definitions() -> Dict[str, Mapping[str, object]]:
    definitions: MutableMapping[str, Mapping[str, object]] = {}
    for model in PUBLIC_MODELS:
        schema = model.model_json_schema(ref_template="#/$defs/{model}")
        nested = schema.pop("$defs", {})
        for name, value in nested.items():
            if name in definitions and definitions[name] != value:
                raise RuntimeError(f"conflicting schema definition for {name}")
            definitions[name] = value
        definitions[model.__name__] = schema
    for public_enum in PUBLIC_ENUMS:
        schema = TypeAdapter(public_enum).json_schema()
        existing = definitions.get(public_enum.__name__)
        if existing is not None and existing != schema:
            raise RuntimeError(f"conflicting schema definition for {public_enum.__name__}")
        definitions[public_enum.__name__] = schema
    return dict(definitions)


def _render_definition(name: str, schema: Mapping[str, object]) -> str:
    if name == "JsonValue":
        return (
            "export type JsonValue = null | boolean | number | string | "
            "JsonValue[] | { [key: string]: JsonValue };"
        )
    if schema.get("type") == "object" and isinstance(schema.get("properties"), dict):
        required = set(schema.get("required", []))
        lines = [f"export interface {name} {{"]
        properties = schema["properties"]
        assert isinstance(properties, dict)
        for field_name, value in properties.items():
            if not isinstance(value, dict):
                continue
            marker = "" if field_name in required else "?"
            lines.append(
                f"  {json.dumps(field_name)}{marker}: {_typescript_type(value)};"
            )
        lines.append("}")
        return "\n".join(lines)
    return f"export type {name} = {_typescript_type(schema)};"


def render_typescript() -> str:
    definitions = _collect_definitions()
    lines = [
        GENERATED_HEADER,
        "",
        f"export const CORE_CONTRACT_VERSION = {CONTRACT_VERSION} as const;",
        "",
    ]
    for name, pattern in ID_PATTERNS.items():
        escaped = pattern.replace("*/", "* /")
        lines.extend(
            [
                f"/** Stable identifier matching `{escaped}`. */",
                f"export type {name} = string & {{ readonly __brand: {json.dumps(name)} }};",
                "",
            ]
        )
    for name in sorted(definitions):
        lines.append(_render_definition(name, definitions[name]))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _write_or_check(files: Mapping[Path, str], check: bool) -> Sequence[Path]:
    changed = []
    for path, content in files.items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == content:
            continue
        changed.append(path)
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    return changed


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when generated files differ")
    args = parser.parse_args(list(argv) if argv is not None else None)

    files = render_json_schemas()
    files[PACKAGE_ROOT / "frontend" / "src" / "index.ts"] = render_typescript()
    changed = _write_or_check(files, args.check)
    if args.check and changed:
        for path in changed:
            print(f"out of date: {path.relative_to(PACKAGE_ROOT)}", file=sys.stderr)
        return 1
    print(f"{'Checked' if args.check else 'Generated'} {len(files)} core contract files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
