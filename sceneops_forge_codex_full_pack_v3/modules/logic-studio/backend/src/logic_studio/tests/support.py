import json
from pathlib import Path

from logic_studio.models import CodeChangeProposal, CompileTemplateRequest
from logic_studio.templates import load_default_template_catalog


MODULE_ROOT = Path(__file__).resolve().parents[4]


def compile_example(name: str):
    path = MODULE_ROOT / "contracts" / "examples" / name
    request = CompileTemplateRequest.model_validate_json(path.read_text(encoding="utf-8"))
    return load_default_template_catalog().compile(request)


def load_json(relative_path: str):
    path = MODULE_ROOT / relative_path
    return json.loads(path.read_text(encoding="utf-8"))


def code_change_proposal(**updates):
    payload = {
        "proposal_id": "proposal_key_door_component",
        "graph_id": "graph_remember_home_key_door",
        "graph_version": 1,
        "base_version": "commit_base_001",
        "target_paths": ["Assets/SceneOps/Generated/KeyDoorBinding.cs"],
        "target_sceneops_ids": ["sobj_home_door_01"],
        "unified_diff": (
            "--- a/Assets/SceneOps/Generated/KeyDoorBinding.cs\n"
            "+++ b/Assets/SceneOps/Generated/KeyDoorBinding.cs\n"
            "@@ -1,1 +1,2 @@\n"
            " public sealed class KeyDoorBinding {}\n"
            "+// Generated from graph_remember_home_key_door v1\n"
        ),
        "rationale": "Bind the approved graph to an allowlisted Unity component.",
        "expected_result": "The configured door reads the canonical graph state.",
        "impact_scope": "One generated Unity component.",
        "risk": "medium",
        "validation_plan": ["Compile", "Run Edit Mode", "Run Play Mode"],
        "rollback_plan": ["Restore adapter snapshot"],
        "mode": "planned",
    }
    payload.update(updates)
    return CodeChangeProposal.model_validate(payload)
