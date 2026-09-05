"""Read only explicit current-project sources; do not crawl the user's filesystem."""
import json
from sceneops_harness import ContextBundle, ContextItem, ProductionIntent, ResourceRef


class ContextEngine:
    def __init__(self, workspace):
        self.workspace = workspace

    def build(self, intent: ProductionIntent, module_ids: list[str], selection: dict):
        project = self.workspace.get_project(intent.project_id)
        items = [ContextItem(ref=ResourceRef(id=project.project_id, kind="project",
            source_version=project.updated_at.isoformat()), content=project.model_dump(mode="json"),
            inclusion_reason="用户当前选中的项目", execution_mode="live")]
        for module_id in dict.fromkeys(module_ids):
            document = self.workspace.get_document(intent.project_id, module_id)
            if document.revision == 0:
                continue
            items.append(ContextItem(ref=ResourceRef(id=module_id, kind="saved_module_draft",
                source_version=str(document.revision)), content=document.model_dump(mode="json"),
                inclusion_reason="用户明确允许附带的本项目已保存草稿",
                execution_mode="mock" if document.sample_id else "planned"))
        if selection:
            items.append(ContextItem(ref=ResourceRef(id="current-selection", kind="selection"),
                content=selection, inclusion_reason="明确选中的场景、对象或任务 ID；不代表已读取对象内容"))
        bundle = ContextBundle(project_id=intent.project_id, intent_id=intent.id, items=items)
        if len(json.dumps(bundle.model_dump(mode="json"), ensure_ascii=False)) > 64000:
            raise ValueError("所选上下文超过 64,000 字符，请减少附带的模块草稿。没有静默截断。")
        return bundle


__all__ = ["ContextEngine"]
