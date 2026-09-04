#!/usr/bin/env python3
"""Compile package sources against installed Unity reference assemblies without launching Editor."""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable, List


MODULE_ROOT = Path(__file__).resolve().parents[1]
PACK_ROOT = MODULE_ROOT.parents[1]
PACKAGE_ROOT = PACK_ROOT / "integrations" / "unity-package"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unity-app", type=Path, required=True)
    arguments = parser.parse_args()
    contents = arguments.unity_app.resolve(strict=True) / "Contents"
    mono = contents / "MonoBleedingEdge" / "bin" / "mono"
    compiler = (
        contents
        / "MonoBleedingEdge"
        / "lib"
        / "mono"
        / "msbuild"
        / "Current"
        / "bin"
        / "Roslyn"
        / "csc.exe"
    )
    managed = contents / "Managed"
    references = [
        contents / "NetStandard" / "ref" / "2.1.0" / "netstandard.dll",
        managed / "UnityEngine.dll",
        managed / "UnityEditor.dll",
    ]
    references.extend(
        sorted(
            (contents / "NetStandard" / "compat" / "2.1.0" / "shims" / "netfx").glob("*.dll")
        )
    )
    references.extend(sorted((managed / "UnityEngine").glob("UnityEngine*.dll")))
    references.extend(sorted((managed / "UnityEngine").glob("UnityEditor*.dll")))

    runtime_sources = sorted((PACKAGE_ROOT / "Runtime").glob("*.cs"))
    editor_sources = sorted((PACKAGE_ROOT / "Editor").glob("*.cs"))
    fixture_sources = sorted(
        (MODULE_ROOT / "fixtures" / "unity-projects" / "smoke-template" / "Assets" / "Editor").glob("*.cs")
    )
    with tempfile.TemporaryDirectory(prefix="sceneops-unity-compile-") as temporary:
        output = Path(temporary)
        runtime_dll = output / "SceneOps.Forge.Unity.Runtime.dll"
        editor_dll = output / "SceneOps.Forge.Unity.Editor.dll"
        fixture_dll = output / "SceneOps.Fixtures.Editor.dll"
        run_compiler(mono, compiler, runtime_dll, runtime_sources, references)
        run_compiler(mono, compiler, editor_dll, editor_sources, [*references, runtime_dll])
        run_compiler(mono, compiler, fixture_dll, fixture_sources, [*references, runtime_dll, editor_dll])
    print(
        f"Compiled {len(runtime_sources)} runtime, {len(editor_sources)} editor, "
        f"and {len(fixture_sources)} fixture source files."
    )
    return 0


def run_compiler(
    mono: Path,
    compiler: Path,
    output: Path,
    sources: Iterable[Path],
    references: Iterable[Path],
) -> None:
    command: List[str] = [
        str(mono),
        str(compiler),
        "-nologo",
        "-nostdlib+",
        "-target:library",
        "-langversion:9.0",
        f"-out:{output}",
    ]
    command.extend(f"-reference:{path}" for path in references if path.is_file())
    command.extend(str(path) for path in sources)
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout + completed.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
