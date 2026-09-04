#!/usr/bin/env python3
"""Run package Edit Mode tests and build both example games with a real Unity Editor."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


MODULE_ROOT = Path(__file__).resolve().parents[1]
PACK_ROOT = MODULE_ROOT.parents[1]
BACKEND_SRC = MODULE_ROOT / "backend" / "src"
sys.path.insert(0, str(BACKEND_SRC))

from engine_unity.build_manifest import (  # noqa: E402
    BuildTestEvidence,
    UnityBuildManifest,
    artifact_record,
)
from engine_unity.contracts import ExecutionMode  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unity", required=True, help="Absolute path to the Unity editor executable")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=MODULE_ROOT / ".artifacts" / "live-smoke",
        help="Directory for live builds, logs, test XML, and evidence",
    )
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    arguments = parser.parse_args()

    unity = Path(arguments.unity).resolve(strict=True)
    output_root = arguments.output_root.resolve(strict=False)
    output_root.mkdir(parents=True, exist_ok=True)
    template = MODULE_ROOT / "fixtures" / "unity-projects" / "smoke-template"
    package = PACK_ROOT / "integrations" / "unity-package"

    with tempfile.TemporaryDirectory(prefix="sceneops-unity-smoke-") as temporary:
        project = Path(temporary) / "SceneOpsUnitySmoke"
        shutil.copytree(template, project)
        embedded_package = project / "Packages" / "com.sceneops.forge.unity"
        embedded_package.parent.mkdir(parents=True)
        shutil.copytree(package, embedded_package)
        (project / "Packages" / "manifest.json").write_text(
            json.dumps(
                {
                    "dependencies": {
                        "com.sceneops.forge.unity": "file:com.sceneops.forge.unity",
                        "com.unity.test-framework": "1.1.33",
                    },
                    "testables": ["com.sceneops.forge.unity"],
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        tests_path = output_root / "editmode-results.xml"
        test_log = output_root / "editmode-unity.log"
        test_command = [
            str(unity),
            "-batchmode",
            "-nographics",
            "-projectPath",
            str(project),
            "-runTests",
            "-testPlatform",
            "editmode",
            "-testResults",
            str(tests_path),
            "-logFile",
            str(test_log),
        ]
        test_run = subprocess.run(test_command, timeout=arguments.timeout_seconds, check=False)
        test_summary = parse_test_results(tests_path)
        if test_run.returncode != 0 or test_summary["failed"]:
            print(json.dumps({"mode": "live", "stage": "tests", "returnCode": test_run.returncode, **test_summary}))
            return 2

        smoke_result_path = output_root / "unity-smoke-result.json"
        build_log = output_root / "build-unity.log"
        build_command = [
            str(unity),
            "-batchmode",
            "-nographics",
            "-quit",
            "-projectPath",
            str(project),
            "-executeMethod",
            "SceneOps.Fixtures.Editor.SceneOpsFixtureBuilder.BuildAll",
            "-sceneopsOutputRoot",
            str(output_root / "Builds"),
            "-sceneopsSmokeResult",
            str(smoke_result_path),
            "-logFile",
            str(build_log),
        ]
        build_run = subprocess.run(build_command, timeout=arguments.timeout_seconds, check=False)
        if build_run.returncode != 0 or not smoke_result_path.is_file():
            print(json.dumps({"mode": "live", "stage": "build", "returnCode": build_run.returncode}))
            return 3

        unity_result = json.loads(smoke_result_path.read_text(encoding="utf-8"))
        if unity_result.get("executionMode") != "live":
            raise RuntimeError("Unity smoke result did not declare live execution")
        source_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PACK_ROOT,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        evidence = build_evidence(
            unity_result,
            output_root,
            source_commit,
            tests_path,
            test_summary,
            test_run.returncode,
            build_run.returncode,
        )
        evidence_path = output_root / "live-smoke-evidence.json"
        evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps({
            "mode": "live",
            "tests": test_summary,
            "builds": [item["build_id"] for item in evidence["build_manifests"]],
            "evidence": str(evidence_path),
        }, sort_keys=True))
    return 0


def parse_test_results(path: Path) -> Dict[str, int]:
    if not path.is_file():
        return {"total": 0, "passed": 0, "failed": 1, "skipped": 0}
    root = ET.parse(path).getroot()
    return {
        "total": int(root.attrib.get("total", root.attrib.get("testcasecount", "0"))),
        "passed": int(root.attrib.get("passed", root.attrib.get("passedcount", "0"))),
        "failed": int(root.attrib.get("failed", root.attrib.get("failedcount", "0"))),
        "skipped": int(root.attrib.get("skipped", root.attrib.get("skippedcount", "0"))),
    }


def build_evidence(
    unity_result: Dict[str, object],
    output_root: Path,
    source_commit: str,
    tests_path: Path,
    test_summary: Dict[str, int],
    test_return_code: int,
    build_return_code: int,
) -> Dict[str, object]:
    manifests: List[Dict[str, object]] = []
    for item in unity_result["builds"]:
        build = dict(item)
        artifact = artifact_record(output_root, Path(build["outputPath"]))
        project_id = (
            "prj_warehouse_escape"
            if build["buildId"] == "bld_warehouse_escape"
            else "prj_remember_home"
        )
        source_assets = (
            [{"source_asset_id": "ast_warehouse_switch", "source_asset_version_id": "astv_warehouse_switch_001"}]
            if project_id == "prj_warehouse_escape"
            else [{"source_asset_id": "ast_home_key", "source_asset_version_id": "astv_home_key_001"}]
        )
        manifest = UnityBuildManifest(
            build_id=build["buildId"],
            project_id=project_id,
            profile=build["profile"],
            execution_mode=ExecutionMode.LIVE,
            unity_version=unity_result["unityVersion"],
            package_version="0.1.0",
            source_commit=source_commit,
            scenes=[build["scenePath"]],
            source_assets=source_assets,
            settings={"target": "StandaloneOSX", "development": True},
            tests=[
                BuildTestEvidence(
                    run_id="testrun_unity_editmode_live",
                    status="passed",
                    mode=ExecutionMode.LIVE,
                    results_path=str(tests_path),
                )
            ],
            artifacts=[artifact],
            produced_at=datetime.now(timezone.utc),
        )
        manifests.append(manifest.model_dump(mode="json"))
    return {
        "schema_version": 1,
        "execution_mode": "live",
        "unity_version": unity_result["unityVersion"],
        "package_version": "0.1.0",
        "test_process_return_code": test_return_code,
        "build_process_return_code": build_return_code,
        "test_summary": test_summary,
        "build_manifests": manifests,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    raise SystemExit(main())
