"""Explicit local drafts; saving never calls a domain execution service."""
from fastapi import APIRouter, HTTPException

from .models import (DocumentSave, ModuleDocument, ModuleId, ModuleList, Project,
    ProjectCreate, ProjectList, SampleImport, WorkbenchRegistration, WorkspaceError)
from .repository import RevisionConflict, WorkspaceRepository

WORKBENCHES = (
    ("shell", "对话与工作区"), ("project-planning", "项目与制作规划"),
    ("concept-assets", "概念与资产"), ("character-animation", "角色与动画"),
    ("world-logic", "场景与玩法逻辑"), ("ui-audio-vfx", "界面、音频与特效"),
    ("render-ops", "渲染工作台"), ("unity-build", "Unity 与构建发布"),
    ("version-review", "版本与协作评审"), ("ai-playtest", "AI 测试与问题回溯"),
    ("integration-ops", "集成与运行观察"),
)


def create_workspace_router(repository: WorkspaceRepository, import_sample=None):
    sample_loader = import_sample
    router = APIRouter(prefix="/api/workspace", tags=["workspace"],
        responses={404: {"model": WorkspaceError}, 409: {"model": WorkspaceError}})

    def document(project_id, module_id):
        try:
            return repository.get_document(project_id, module_id)
        except KeyError as error:
            raise HTTPException(404, "项目不存在，请明确创建或选择项目。") from error

    def save(value, revision):
        try:
            return repository.save_document(value, revision)
        except RevisionConflict as error:
            raise HTTPException(409, str(error)) from error

    @router.get("/projects", response_model=ProjectList, operation_id="workspaceListProjects")
    def projects():
        return ProjectList(projects=repository.list_projects())

    @router.post("/projects", response_model=Project, status_code=201, operation_id="workspaceCreateProject")
    def create_project(body: ProjectCreate):
        return repository.create_project(body.name)

    @router.get("/modules", response_model=ModuleList, operation_id="workspaceListModules")
    def modules():
        return ModuleList(modules=[WorkbenchRegistration(module_id=id, title=title) for id, title in WORKBENCHES])

    @router.get("/projects/{project_id}/modules/{module_id}", response_model=ModuleDocument,
        operation_id="workspaceGetModuleDocument")
    def get_document(project_id: str, module_id: ModuleId):
        return document(project_id, module_id)

    @router.put("/projects/{project_id}/modules/{module_id}", response_model=ModuleDocument,
        operation_id="workspaceSaveModuleDocument")
    def save_document(project_id: str, module_id: ModuleId, body: DocumentSave):
        current = document(project_id, module_id)
        return save(current.model_copy(update={"payload": body.payload}), body.expected_revision)

    @router.post("/projects/{project_id}/modules/{module_id}/sample", response_model=ModuleDocument,
        operation_id="workspaceImportModuleSample")
    def import_sample(project_id: str, module_id: ModuleId, body: SampleImport):
        current = document(project_id, module_id)
        if current.revision != body.expected_revision:
            raise HTTPException(409, "草稿版本已变化，请重新加载后再导入。")
        if current.sample_id:
            raise HTTPException(409, "此工作台已导入样例；请创建新项目以保留现有数据。")
        if sample_loader:
            sample_loader(project_id, module_id, body.sample_id)
        # Import only a reference to static sample data. No demo service or pipeline is invoked.
        payload = {"mode": "mock", "sample_id": body.sample_id,
            "title": "回家之路" if body.sample_id == "remember-home" else "仓库逃生",
            "note": "手动导入的 Mock 样例草稿；未执行生产、测试或审批。"}
        return save(current.model_copy(update={"sample_id": body.sample_id, "payload": payload}), body.expected_revision)

    return router
