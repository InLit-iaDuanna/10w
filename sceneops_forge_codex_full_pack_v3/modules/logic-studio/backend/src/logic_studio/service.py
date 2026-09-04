from __future__ import annotations

from typing import Collection, Optional

from .changesets import CodeChangeCoordinator
from .models import (
    CodeChangeProposal,
    CodeChangeSet,
    CompileTemplateRequest,
    GameplayGraph,
    GeneratedTestPlan,
    GraphValidationReport,
)
from .templates import InteractionTemplateCatalog, load_default_template_catalog
from .test_generation import generate_test_plan
from .validation import validate_gameplay_graph


class InvalidGameplayGraph(ValueError):
    pass


class LogicStudioService:
    def __init__(
        self,
        *,
        catalog: Optional[InteractionTemplateCatalog] = None,
        changes: Optional[CodeChangeCoordinator] = None,
    ) -> None:
        self.catalog = catalog or load_default_template_catalog()
        self.changes = changes or CodeChangeCoordinator()

    def compile_template(self, request: CompileTemplateRequest) -> GameplayGraph:
        return self.catalog.compile(request)

    def validate_graph(self, graph: GameplayGraph) -> GraphValidationReport:
        return validate_gameplay_graph(graph)

    def generate_tests(self, graph: GameplayGraph) -> GeneratedTestPlan:
        report = self.validate_graph(graph)
        if not report.valid:
            codes = ", ".join(issue.code for issue in report.issues)
            raise InvalidGameplayGraph(f"Cannot generate tests: {codes}")
        return generate_test_plan(graph)

    def propose_code_change(self, proposal: CodeChangeProposal) -> CodeChangeSet:
        return self.changes.propose(proposal)

    def approve_code_change(
        self,
        change_set: CodeChangeSet,
        *,
        approver_id: str,
        permissions: Collection[str],
    ) -> CodeChangeSet:
        return self.changes.approve(
            change_set,
            approver_id=approver_id,
            permissions=permissions,
        )
