"""Minimal, ownership-preserving module scaffold generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, Tuple

import yaml
from pydantic import ValidationError

from .catalog import (
    _render_module_python_manifest,
    _render_module_typescript_manifest,
)
from .manifest import ModuleManifest


class ScaffoldError(ValueError):
    pass


def _python_package(module_id: str) -> str:
    return module_id.replace("-", "_")


def _manifest(
    module_id: str,
    title: str,
    description: str,
    surfaces: Tuple[str, ...],
    include_core_dependencies: bool,
) -> ModuleManifest:
    entrypoints = {}
    if "frontend" in surfaces:
        entrypoints["frontend"] = "./frontend/src/index.ts"
    if "backend" in surfaces:
        entrypoints["backend"] = _python_package(module_id)
    return ModuleManifest.model_validate(
        {
            "schema_version": 1,
            "id": module_id,
            "version": "0.1.0",
            "title": title,
            "description": description,
            "status": "experimental",
            "feature_flag": module_id.replace("-", "_"),
            "requires": {
                "modules": ["core-kernel", "module-runtime"]
                if include_core_dependencies
                else [],
                "integrations": [],
                "optional_integrations": [],
            },
            "contributes": {
                "editors": [],
                "commands": [],
                "events": [],
                "jobs": [],
                "workflows": [],
                "policy_gates": [],
            },
            "permissions": [],
            "entrypoints": entrypoints,
        }
    )


def _readme(manifest: ModuleManifest, surfaces: Tuple[str, ...]) -> str:
    commands = []
    if "backend" in surfaces:
        commands.append(
            f"PYTHONPATH=modules/{manifest.id}/backend/src python3 -m unittest discover "
            f"-s modules/{manifest.id}/backend/src/{_python_package(manifest.id)}/tests"
        )
    if "frontend" in surfaces:
        commands.append(
            f"node --experimental-strip-types --test modules/{manifest.id}/frontend/src/tests/module.test.ts"
        )
    rendered_commands = "\n".join(f"- `{command}`" for command in commands)
    return f"""# {manifest.title}

{manifest.description}

## 公共表面

- 模块 ID：`{manifest.id}`
- 前端入口：{manifest.entrypoints.frontend or '无'}
- 后端入口：{manifest.entrypoints.backend or '无'}
- 初始 contributions 为空；新增贡献时必须同步 `module.yaml` 与测试。

## 状态与 fixture

`contracts/examples/mock-success.json` 与 `mock-failure.json` 是确定性 Mock。公开 fixture runner 返回 `succeeded`，或以明确错误进入 `failed`；不得标记为 Live/Cached。

## 集成与降级

当前不要求外部集成。新增集成必须通过 typed adapter 声明，并由模块运行时显示缺失状态。

## 测试

{rendered_commands}

## 限制

这是最小模块骨架，尚未包含业务 Editor、Command、Event 或 Job。
"""


def _agents(manifest: ModuleManifest) -> str:
    package_name = _python_package(manifest.id)
    return f"""# {manifest.id} module rules

- Ownership is limited to `modules/{manifest.id}/**` and directly related generated catalog entries.
- Public frontend imports go through `frontend/src/index.ts` only.
- Public backend imports go through `{package_name}/__init__.py` only.
- Keep Live, Cached, Mock, Planned, and Blocked labels truthful.
- Generated files: `frontend/src/generated/module-manifest.ts` and backend `generated_manifest.py`.
- Run this module's tests and `scripts/module-validate` before handoff.
"""


def _frontend_index() -> str:
    return """import { generatedModuleManifest } from "./generated/module-manifest.ts";

export interface FixtureResult {
  readonly status: "succeeded";
  readonly mode: "mock";
  readonly value: string;
}

export function runFixture(shouldFail = false): FixtureResult {
  if (shouldFail) {
    throw new Error("FIXTURE_REQUESTED_FAILURE");
  }
  return { status: "succeeded", mode: "mock", value: "deterministic" };
}

export const moduleContribution = {
  manifest: generatedModuleManifest,
  editors: [],
  commands: [],
  events: [],
  jobs: [],
} as const;
"""


def _frontend_test() -> str:
    return """import assert from "node:assert/strict";
import test from "node:test";

import { runFixture } from "../index.ts";

test("deterministic fixture succeeds as mock", () => {
  assert.deepEqual(runFixture(), {
    status: "succeeded",
    mode: "mock",
    value: "deterministic",
  });
});

test("fixture failure is explicit", () => {
  assert.throws(() => runFixture(true), /FIXTURE_REQUESTED_FAILURE/);
});
"""


def _backend_index() -> str:
    return """from .generated_manifest import GENERATED_MODULE_MANIFEST


class FixtureExecutionError(RuntimeError):
    pass


def run_fixture(should_fail=False):
    if should_fail:
        raise FixtureExecutionError("FIXTURE_REQUESTED_FAILURE")
    return {"status": "succeeded", "mode": "mock", "value": "deterministic"}


backend_module_contribution = {
    "manifest": GENERATED_MODULE_MANIFEST,
    "router": None,
    "jobs": (),
    "event_handlers": (),
    "policy_gates": (),
}
"""


def _backend_test(package_name: str) -> str:
    return f"""import unittest

from {package_name} import FixtureExecutionError, run_fixture


class FixtureTests(unittest.TestCase):
    def test_success_is_deterministic_mock(self):
        self.assertEqual(
            run_fixture(),
            {{"status": "succeeded", "mode": "mock", "value": "deterministic"}},
        )

    def test_failure_is_explicit(self):
        with self.assertRaisesRegex(FixtureExecutionError, "FIXTURE_REQUESTED_FAILURE"):
            run_fixture(True)


if __name__ == "__main__":
    unittest.main()
"""


def scaffold_module(
    repository_root: Path,
    module_id: str,
    title: str,
    description: str,
    *,
    surfaces: Iterable[str] = ("frontend", "backend"),
    include_core_dependencies: bool = True,
) -> Path:
    selected = tuple(dict.fromkeys(surfaces))
    invalid = sorted(set(selected) - {"frontend", "backend"})
    if invalid or not selected:
        raise ScaffoldError("surfaces must contain frontend, backend, or both")
    try:
        manifest = _manifest(
            module_id, title, description, selected, include_core_dependencies
        )
    except ValidationError as exc:
        raise ScaffoldError(str(exc)) from exc

    repository_root = repository_root.resolve()
    modules_root = repository_root / "modules"
    target = modules_root / module_id
    if target.exists():
        raise ScaffoldError(f"module directory already exists: {target}")

    manifest_text = yaml.safe_dump(
        manifest.model_dump(mode="json"),
        sort_keys=False,
        allow_unicode=True,
    )
    files: Dict[Path, str] = {
        target / "AGENTS.md": _agents(manifest),
        target / "README.md": _readme(manifest, selected),
        target / "module.yaml": manifest_text,
        target / "contracts" / "examples" / "mock-success.json": json.dumps(
            {"status": "succeeded", "mode": "mock", "value": "deterministic"},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        target / "contracts" / "examples" / "mock-failure.json": json.dumps(
            {
                "status": "failed",
                "mode": "mock",
                "error": {"code": "FIXTURE_REQUESTED_FAILURE", "retryable": False},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    }
    if "frontend" in selected:
        files.update(
            {
                target / "frontend" / "package.json": json.dumps(
                    {
                        "name": f"@sceneops/{module_id}",
                        "version": "0.1.0",
                        "private": True,
                        "type": "module",
                        "exports": {".": "./src/index.ts"},
                    },
                    indent=2,
                )
                + "\n",
                target / "frontend" / "src" / "index.ts": _frontend_index(),
                target
                / "frontend"
                / "src"
                / "generated"
                / "module-manifest.ts": _render_module_typescript_manifest(manifest),
                target / "frontend" / "src" / "tests" / "module.test.ts": _frontend_test(),
            }
        )
    if "backend" in selected:
        package_name = _python_package(module_id)
        package_root = target / "backend" / "src" / package_name
        files.update(
            {
                target / "backend" / "pyproject.toml": f"""[build-system]
requires = ["hatchling>=1.26"]
build-backend = "hatchling.build"

[project]
name = "sceneops-{module_id}"
version = "0.1.0"
requires-python = ">=3.9"

[tool.hatch.build.targets.wheel]
packages = ["src/{package_name}"]
""",
                package_root / "__init__.py": _backend_index(),
                package_root
                / "generated_manifest.py": _render_module_python_manifest(manifest),
                package_root / "tests" / "__init__.py": "",
                package_root / "tests" / "test_module.py": _backend_test(package_name),
            }
        )

    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return target
