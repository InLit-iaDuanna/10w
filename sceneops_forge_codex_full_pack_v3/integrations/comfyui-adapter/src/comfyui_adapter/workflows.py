"""Trusted workflow registry and allowlisted command binding."""

from copy import deepcopy
import hashlib
import json
from pathlib import PurePosixPath
from typing import Dict, Iterable, Optional, Protocol, Set, Tuple

from .errors import ComfyAdapterError
from .models import ComfyEnqueueCommand, TrustedWorkflow


DEFAULT_ALLOWED_NODE_CLASSES = frozenset(
    {
        "CheckpointLoaderSimple",
        "CLIPTextEncode",
        "ControlNetApplyAdvanced",
        "ControlNetLoader",
        "EmptyLatentImage",
        "KSampler",
        "LoadImage",
        "SaveImage",
        "VAEDecode",
        "VAEEncode",
    }
)

ALLOWED_BINDING_TARGETS = {
    "prompt": frozenset({("CLIPTextEncode", "text")}),
    "negative_prompt": frozenset({("CLIPTextEncode", "text")}),
    "seed": frozenset({("KSampler", "seed")}),
    "model_reference": frozenset({("CheckpointLoaderSimple", "ckpt_name")}),
    "aov": frozenset({("LoadImage", "image")}),
}


def compute_workflow_checksum_sha256(graph: Dict[str, dict]) -> str:
    """Bind a trusted workflow reference to its canonical graph content."""

    canonical = json.dumps(
        graph,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class ArtifactInputResolver(Protocol):
    def resolve_staged_input(self, artifact_id: str) -> str:
        """Return an already-staged, project-scoped relative Comfy input name."""


def validate_staged_input(value: str) -> str:
    if not value or "\\" in value:
        raise ComfyAdapterError(
            "AOV_INPUT_REJECTED",
            "A staged AOV input must use a non-empty POSIX relative name.",
            retryable=False,
            suggested_actions=["artifact.stage"],
        )
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ComfyAdapterError(
            "AOV_INPUT_REJECTED",
            "A staged AOV input cannot be absolute or traverse parent directories.",
            retryable=False,
            suggested_actions=["artifact.stage"],
        )
    return value


class TrustedWorkflowRegistry:
    def __init__(
        self,
        workflows: Iterable[TrustedWorkflow],
        *,
        allowed_node_classes: Optional[Set[str]] = None,
    ) -> None:
        self._allowed_node_classes = frozenset(
            allowed_node_classes or DEFAULT_ALLOWED_NODE_CLASSES
        )
        self._workflows: Dict[str, TrustedWorkflow] = {}
        for workflow in workflows:
            workflow = TrustedWorkflow.model_validate(workflow.model_dump(mode="python"))
            if workflow.reference in self._workflows:
                raise ValueError("trusted workflow references must be unique")
            self._validate_trusted_workflow(workflow)
            self._workflows[workflow.reference] = workflow.model_copy(deep=True)

    @property
    def references(self):
        return tuple(sorted(self._workflows))

    def resolve(self, reference: str, checksum_sha256: str) -> TrustedWorkflow:
        workflow = self._workflows.get(reference)
        if workflow is None or workflow.checksum_sha256 != checksum_sha256:
            raise ComfyAdapterError(
                "WORKFLOW_NOT_ALLOWED",
                "The workflow reference/checksum pair is not configured.",
                retryable=False,
                details={"workflow_reference": reference},
                suggested_actions=["integration.configure_workflow"],
            )
        return workflow.model_copy(deep=True)

    def _validate_trusted_workflow(self, workflow: TrustedWorkflow) -> None:
        calculated = compute_workflow_checksum_sha256(workflow.graph)
        if calculated != workflow.checksum_sha256:
            raise ValueError("trusted workflow checksum does not match graph content")
        for node_id, node in workflow.graph.items():
            if not isinstance(node, dict):
                raise ValueError("trusted workflow nodes must be objects")
            class_type = node.get("class_type")
            inputs = node.get("inputs")
            if class_type not in self._allowed_node_classes:
                raise ValueError(
                    "trusted workflow node class is not allowlisted: " + str(class_type)
                )
            if not isinstance(inputs, dict):
                raise ValueError("trusted workflow node inputs must be objects")
        for binding in workflow.bindings:
            node = workflow.graph[binding.node_id]
            category = "aov" if binding.source.startswith("aov.") else binding.source
            target: Tuple[str, str] = (node["class_type"], binding.input_name)
            if target not in ALLOWED_BINDING_TARGETS[category]:
                raise ValueError(
                    "trusted workflow binding does not target an allowlisted input semantic"
                )

    def bind(
        self,
        command: ComfyEnqueueCommand,
        artifact_resolver: ArtifactInputResolver,
    ) -> dict:
        workflow = self.resolve(
            command.workflow_reference, command.workflow_checksum_sha256
        )
        if command.model_reference not in workflow.allowed_model_references:
            raise ComfyAdapterError(
                "MODEL_NOT_ALLOWED",
                "The requested model is not allowlisted for this workflow.",
                retryable=False,
                details={"model_reference": command.model_reference},
            )

        binding_sources = {binding.source for binding in workflow.bindings}
        command_aovs = {"aov." + key for key in command.aov_artifact_ids}
        workflow_aovs = {item for item in binding_sources if item.startswith("aov.")}
        if command_aovs != workflow_aovs:
            raise ComfyAdapterError(
                "AOV_INPUT_MISMATCH",
                "The command AOV inputs must exactly match trusted workflow bindings.",
                retryable=False,
                details={
                    "required": sorted(workflow_aovs),
                    "provided": sorted(command_aovs),
                },
            )

        values = {
            "prompt": command.prompt,
            "negative_prompt": command.negative_prompt,
            "seed": command.seed,
            "model_reference": command.model_reference,
        }
        for name, artifact_id in command.aov_artifact_ids.items():
            staged = artifact_resolver.resolve_staged_input(artifact_id)
            values["aov." + name] = validate_staged_input(staged)

        graph = deepcopy(workflow.graph)
        for binding in workflow.bindings:
            graph[binding.node_id]["inputs"][binding.input_name] = values[binding.source]
        return graph
