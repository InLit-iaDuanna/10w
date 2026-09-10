import json
import tempfile
import unittest
from pathlib import Path

import yaml

from module_runtime import (
    ModuleAvailability,
    ModuleManifest,
    RepositoryValidationError,
    ScaffoldError,
    load_manifest,
    resolve_module_states,
    scaffold_module,
    validate_repository,
)
from module_runtime.catalog import generated_files
from module_runtime.import_boundaries import _typescript_imports
from pydantic import ValidationError


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def manifest_data(
    module_id,
    *,
    dependencies=(),
    feature_flag=None,
    editors=(),
    commands=(),
    events=(),
    jobs=(),
    frontend=True,
    backend=False,
):
    entrypoints = {}
    if frontend:
        entrypoints["frontend"] = "./frontend/src/index.ts"
    if backend:
        entrypoints["backend"] = module_id.replace("-", "_")
    return {
        "schema_version": 1,
        "id": module_id,
        "version": "0.1.0",
        "title": module_id,
        "description": f"Fixture module {module_id}.",
        "status": "experimental",
        "feature_flag": feature_flag or module_id.replace("-", "_"),
        "requires": {
            "modules": list(dependencies),
            "integrations": [],
            "optional_integrations": [],
        },
        "contributes": {
            "editors": list(editors),
            "commands": list(commands),
            "events": list(events),
            "jobs": list(jobs),
            "workflows": [],
            "policy_gates": [],
        },
        "permissions": [],
        "entrypoints": entrypoints,
    }


def create_module(
    root,
    directory_name,
    data,
    source="export const marker = true;\n",
    backend_source="PUBLIC = True\n",
):
    directory = root / "modules" / directory_name
    directory.mkdir(parents=True)
    (directory / "module.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
    )
    frontend = data["entrypoints"].get("frontend")
    if frontend:
        entrypoint = directory / frontend
        entrypoint.parent.mkdir(parents=True, exist_ok=True)
        entrypoint.write_text(source, encoding="utf-8")
    backend = data["entrypoints"].get("backend")
    if backend:
        entrypoint = directory / "backend" / "src" / Path(*backend.split(".")) / "__init__.py"
        entrypoint.parent.mkdir(parents=True, exist_ok=True)
        entrypoint.write_text(backend_source, encoding="utf-8")
    return directory


def diagnostic_codes(error):
    return {item.code for item in error.exception.diagnostics}


class ManifestSchemaTests(unittest.TestCase):
    def test_valid_schema_fixture(self):
        fixture = (
            REPOSITORY_ROOT
            / "modules"
            / "module-runtime"
            / "contracts"
            / "examples"
            / "valid-module.yaml"
        )
        source, diagnostics = load_manifest(fixture, REPOSITORY_ROOT)
        self.assertFalse(diagnostics)
        self.assertEqual(source.manifest.id, "example-module")

    def test_invalid_schema_fixture_has_readable_diagnostic(self):
        fixture = (
            REPOSITORY_ROOT
            / "modules"
            / "module-runtime"
            / "contracts"
            / "examples"
            / "invalid-permission-module.yaml"
        )
        source, diagnostics = load_manifest(fixture, REPOSITORY_ROOT)
        self.assertIsNone(source)
        self.assertEqual(diagnostics[0].code, "MANIFEST_SCHEMA_INVALID")
        self.assertIn("permissions", diagnostics[0].message)

    def test_generated_json_schema_captures_item_and_entrypoint_rules(self):
        schema_path = (
            REPOSITORY_ROOT
            / "modules"
            / "module-runtime"
            / "contracts"
            / "module-manifest.schema.json"
        )
        schema = json.loads(schema_path.read_text())
        module_items = schema["$defs"]["ModuleRequirements"]["properties"]["modules"]
        self.assertTrue(module_items["uniqueItems"])
        self.assertIn("pattern", module_items["items"])
        self.assertEqual(len(schema["$defs"]["ModuleEntrypoints"]["anyOf"]), 2)


class ImportSyntaxRegressionTests(unittest.TestCase):
    def test_member_import_and_literal_import_are_static(self):
        for source in ('client.import(projectId, file)', 'import( "./editor.ts")'):
            with self.subTest(source=source):
                self.assertFalse(_typescript_imports(source)[1])

    def test_computed_import_remains_forbidden(self):
        self.assertTrue(_typescript_imports('import( modulePath)')[1])

    def test_hierarchical_permissions_preserve_exact_security_names(self):
        data = manifest_data("permission-example")
        data["permissions"] = ["logic:code:review", "logic:code:approve"]
        self.assertEqual(ModuleManifest.model_validate(data).permissions, data["permissions"])
        for invalid in ("logic::approve", "logic:code:*", "logic:code:"):
            data["permissions"] = [invalid]
            with self.subTest(permission=invalid), self.assertRaises(ValidationError):
                ModuleManifest.model_validate(data)


class RepositoryValidationTests(unittest.TestCase):
    def test_repository_registration_order_is_dependency_order(self):
        graph = validate_repository(REPOSITORY_ROOT)
        positions = {module_id: index for index, module_id in enumerate(graph.module_ids)}
        self.assertLess(positions["core-kernel"], positions["module-runtime"])
        self.assertLess(positions["module-runtime"], positions["runtime-fixture"])
        for manifest in graph.manifests:
            for dependency in manifest.requires.modules:
                self.assertLess(positions[dependency], positions[manifest.id])

    def test_duplicate_module_id_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            create_module(root, "first-module", manifest_data("first-module"))
            create_module(root, "second-folder", manifest_data("first-module"))
            with self.assertRaises(RepositoryValidationError) as caught:
                validate_repository(root)
            self.assertIn("DUPLICATE_MODULE_ID", diagnostic_codes(caught))

    def test_duplicate_command_id_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            create_module(root, "first-module", manifest_data("first-module", commands=("fixture.run",)))
            create_module(root, "second-module", manifest_data("second-module", commands=("fixture.run",)))
            with self.assertRaises(RepositoryValidationError) as caught:
                validate_repository(root)
            self.assertIn("DUPLICATE_COMMAND_ID", diagnostic_codes(caught))

    def test_duplicate_editor_and_job_ids_fail(self):
        cases = (
            ("editors", {"editors": ("fixture.editor",)}, "DUPLICATE_EDITOR_ID"),
            ("jobs", {"jobs": ("fixture.execute",)}, "DUPLICATE_JOB_ID"),
        )
        for label, contributions, expected_code in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                create_module(root, "first-module", manifest_data("first-module", **contributions))
                create_module(root, "second-module", manifest_data("second-module", **contributions))
                with self.assertRaises(RepositoryValidationError) as caught:
                    validate_repository(root)
                self.assertIn(expected_code, diagnostic_codes(caught))

    def test_duplicate_feature_flag_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            create_module(root, "first-module", manifest_data("first-module", feature_flag="shared_flag"))
            create_module(root, "second-module", manifest_data("second-module", feature_flag="shared_flag"))
            with self.assertRaises(RepositoryValidationError) as caught:
                validate_repository(root)
            self.assertIn("DUPLICATE_FEATURE_FLAG", diagnostic_codes(caught))

    def test_dependency_cycle_fails_with_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            create_module(root, "cycle-a", manifest_data("cycle-a", dependencies=("cycle-b",)))
            create_module(root, "cycle-b", manifest_data("cycle-b", dependencies=("cycle-a",)))
            with self.assertRaises(RepositoryValidationError) as caught:
                validate_repository(root)
            self.assertIn("MODULE_DEPENDENCY_CYCLE", diagnostic_codes(caught))
            self.assertIn("cycle-a", str(caught.exception))

    def test_missing_entrypoint_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = create_module(root, "missing-entry", manifest_data("missing-entry"))
            (directory / "frontend" / "src" / "index.ts").unlink()
            with self.assertRaises(RepositoryValidationError) as caught:
                validate_repository(root)
            self.assertIn("ENTRYPOINT_MISSING", diagnostic_codes(caught))

    def test_public_cross_module_import_passes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            create_module(root, "base-module", manifest_data("base-module"))
            create_module(
                root,
                "consumer-module",
                manifest_data("consumer-module", dependencies=("base-module",)),
                'import { marker } from "../../../base-module/frontend/src/index.ts";\nexport { marker };\n',
            )
            graph = validate_repository(root)
            self.assertEqual(graph.module_ids, ("base-module", "consumer-module"))

    def test_undeclared_cross_module_import_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            create_module(root, "base-module", manifest_data("base-module"))
            create_module(
                root,
                "consumer-module",
                manifest_data("consumer-module"),
                'import { marker } from "../../../base-module/frontend/src/index.ts";\n',
            )
            with self.assertRaises(RepositoryValidationError) as caught:
                validate_repository(root)
            self.assertIn("UNDECLARED_MODULE_IMPORT", diagnostic_codes(caught))

    def test_internal_cross_module_import_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = create_module(root, "base-module", manifest_data("base-module"))
            (base / "frontend" / "src" / "internal.ts").write_text("export const secret = true;\n")
            create_module(
                root,
                "consumer-module",
                manifest_data("consumer-module", dependencies=("base-module",)),
                'import { secret } from "../../../base-module/frontend/src/internal.ts";\n',
            )
            with self.assertRaises(RepositoryValidationError) as caught:
                validate_repository(root)
            self.assertIn("INTERNAL_MODULE_IMPORT", diagnostic_codes(caught))

    def test_internal_python_module_import_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = create_module(
                root,
                "base-module",
                manifest_data("base-module", frontend=False, backend=True),
            )
            (base / "backend" / "src" / "base_module" / "internal.py").write_text(
                "secret = True\n", encoding="utf-8"
            )
            create_module(
                root,
                "consumer-module",
                manifest_data(
                    "consumer-module",
                    dependencies=("base-module",),
                    frontend=False,
                    backend=True,
                ),
                backend_source="from base_module.internal import secret\n",
            )
            with self.assertRaises(RepositoryValidationError) as caught:
                validate_repository(root)
            self.assertIn("INTERNAL_MODULE_IMPORT", diagnostic_codes(caught))

    def test_event_version_without_v1_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            create_module(root, "event-module", manifest_data("event-module", events=("fixture.completed@2",)))
            with self.assertRaises(RepositoryValidationError) as caught:
                validate_repository(root)
            self.assertIn("EVENT_VERSION_INVALID", diagnostic_codes(caught))


class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.graph = validate_repository(REPOSITORY_ROOT)

    def test_feature_flag_disables_module_and_blocks_dependents(self):
        states = resolve_module_states(
            self.graph.manifests, feature_flags={"module_runtime": False}
        )
        self.assertEqual(states["module-runtime"].availability, ModuleAvailability.DISABLED)
        self.assertEqual(states["runtime-fixture"].availability, ModuleAvailability.BLOCKED)

    def test_optional_integration_is_visible_without_blocking(self):
        states = resolve_module_states(self.graph.manifests)
        fixture = states["runtime-fixture"]
        self.assertEqual(fixture.availability, ModuleAvailability.ENABLED)
        self.assertEqual(fixture.missing_optional_integrations, ["fixture-renderer"])
        self.assertIn("可选集成不可用", fixture.message)

    def test_required_integration_blocks(self):
        core = self.graph.manifests[0]
        data = manifest_data("integration-feature", dependencies=("core-kernel",))
        data["requires"]["integrations"] = ["required-tool"]
        feature = ModuleManifest.model_validate(data)
        states = resolve_module_states((core, feature))
        self.assertEqual(states["integration-feature"].availability, ModuleAvailability.BLOCKED)
        self.assertEqual(
            states["integration-feature"].missing_required_integrations,
            ["required-tool"],
        )


class GenerationAndScaffoldTests(unittest.TestCase):
    def test_generated_catalog_snapshot_is_current_and_reproducible(self):
        graph = validate_repository(REPOSITORY_ROOT)
        first = generated_files(REPOSITORY_ROOT, graph)
        second = generated_files(REPOSITORY_ROOT, graph)
        self.assertEqual(first, second)
        for path, expected in first.items():
            self.assertTrue(path.is_file(), path)
            self.assertEqual(path.read_text(encoding="utf-8"), expected, path)

    def test_backend_composition_root_consumes_generated_catalog(self):
        from services.api.generated_module_catalog import (
            GENERATED_BACKEND_MODULE_IDS, GENERATED_BACKEND_MODULE_CATALOG,
        )

        catalog = json.loads(
            (REPOSITORY_ROOT / "generated" / "module-catalog.json").read_text()
        )
        expected = tuple(
            module["id"]
            for module in catalog["modules"]
            if module["entrypoints"].get("backend")
        )
        self.assertEqual(GENERATED_BACKEND_MODULE_IDS, expected)
        for entry in GENERATED_BACKEND_MODULE_CATALOG:
            self.assertEqual(entry["module"].__name__, entry["manifest"]["entrypoints"]["backend"])

    def test_scaffold_smoke_creates_only_selected_surfaces(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "modules").mkdir()
            target = scaffold_module(
                root,
                "smoke-module",
                "Smoke Module",
                "Scaffold smoke fixture.",
                surfaces=("backend",),
                include_core_dependencies=False,
            )
            self.assertTrue((target / "module.yaml").is_file())
            self.assertTrue((target / "backend" / "src" / "smoke_module" / "__init__.py").is_file())
            self.assertFalse((target / "frontend").exists())
            self.assertFalse((target / "workers").exists())
            self.assertEqual(validate_repository(root).module_ids, ("smoke-module",))

    def test_scaffold_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "modules" / "existing-module").mkdir(parents=True)
            with self.assertRaises(ScaffoldError):
                scaffold_module(
                    root,
                    "existing-module",
                    "Existing",
                    "Must not overwrite.",
                    include_core_dependencies=False,
                )


if __name__ == "__main__":
    unittest.main()
