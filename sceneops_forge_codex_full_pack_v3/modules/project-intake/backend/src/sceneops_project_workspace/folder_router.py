"""Authenticated composition roots can expose bounded local-folder project intake."""
import sqlite3

from fastapi import APIRouter, HTTPException, Query, Request, Response

from .models import (FolderListing, FolderProject, FolderProjectCreate, FolderProjectDeleteFiles, FolderProjectIdentityInspection,
    FolderProjectInspect, FolderProjectList, FolderProjectRecover, WorkspaceError)
from .repository import (FolderProjectConflict, FolderProjectIdentityConflict,
    InvalidFolderPath, WorkspaceRepository)
from .git_projects import GitProjectError
from .errors import FolderProjectRequired, ProjectNotFound


def create_folder_router(repository: WorkspaceRepository):
    router = APIRouter(prefix="/api/workspace", tags=["workspace-folders"], responses={
        400: {"model": WorkspaceError}, 404: {"model": WorkspaceError},
        409: {"model": WorkspaceError},
    })

    @router.get("/folders", response_model=FolderListing, operation_id="workspaceListFolders")
    def list_folders(path: str | None = Query(default=None)):
        try:
            return repository.list_directory(path)
        except InvalidFolderPath as error:
            raise HTTPException(400, str(error)) from error

    @router.post("/folder-projects", response_model=FolderProject, status_code=201,
        operation_id="workspaceCreateFolderProject")
    def create_folder_project(body: FolderProjectCreate):
        try:
            return repository.create_folder_project(body.parent_path, body.name)
        except InvalidFolderPath as error:
            raise HTTPException(400, str(error)) from error
        except FolderProjectConflict as error:
            raise HTTPException(409, str(error)) from error
        except GitProjectError as error:
            raise HTTPException(409, f'{error} 已创建目录中的项目身份仍保留，可检查该目录后恢复登记。') from error
        except sqlite3.Error as error:
            raise HTTPException(409, '本机项目索引登记失败；已创建目录中的项目身份仍保留，可检查后恢复。') from error

    @router.get("/folder-projects", response_model=FolderProjectList,
        operation_id="workspaceListFolderProjects")
    def list_folder_projects():
        return FolderProjectList(projects=repository.list_folder_projects())

    @router.post("/folder-projects/inspect", response_model=FolderProjectIdentityInspection,
        operation_id="workspaceInspectFolderProject")
    def inspect_folder_project(body: FolderProjectInspect):
        try:
            return repository.inspect_folder_project(body.path)
        except InvalidFolderPath as error:
            raise HTTPException(400, str(error)) from error
        except FolderProjectIdentityConflict as error:
            raise HTTPException(409, str(error)) from error

    @router.post("/folder-projects/recover", response_model=FolderProject,
        operation_id="workspaceRecoverFolderProject")
    def recover_folder_project(body: FolderProjectRecover):
        try:
            return repository.recover_folder_project(body.path, body.resolution)
        except InvalidFolderPath as error:
            raise HTTPException(400, str(error)) from error
        except (FolderProjectConflict, FolderProjectIdentityConflict,
                GitProjectError, sqlite3.Error) as error:
            raise HTTPException(409, str(error)) from error

    @router.get("/folder-projects/{project_id}", response_model=FolderProject,
        operation_id="workspaceGetFolderProject")
    def get_folder_project(project_id: str):
        try:
            return repository.get_folder_project(project_id)
        except ProjectNotFound as error:
            raise HTTPException(404, "文件夹项目不存在。") from error
        except FolderProjectRequired as error:
            raise HTTPException(409, str(error)) from error
        except InvalidFolderPath as error:
            raise HTTPException(409, str(error)) from error

    @router.delete("/folder-projects/{project_id}", status_code=204,
        operation_id="workspaceForgetFolderProject")
    def forget_folder_project(project_id: str):
        try:
            repository.forget_folder_project(project_id)
        except ProjectNotFound as error:
            raise HTTPException(404, "文件夹项目不存在。") from error
        except FolderProjectRequired as error:
            raise HTTPException(409, str(error)) from error
        return Response(status_code=204)

    @router.post("/folder-projects/{project_id}/delete-files", status_code=204,
        operation_id="workspaceDeleteFolderProjectFiles")
    def delete_folder_project_files(project_id: str, body: FolderProjectDeleteFiles, request: Request):
        tasks = getattr(request.app.state, "agent_tasks", None)
        if tasks is not None and tasks.execution_status() == "running":
            raise HTTPException(409, "仍有制作任务正在执行，请先停止任务再删除本地项目文件。")
        try:
            repository.delete_folder_project_files(project_id, body.confirmed_root_path)
        except ProjectNotFound as error:
            raise HTTPException(404, "文件夹项目不存在。") from error
        except (FolderProjectRequired, FolderProjectConflict, FolderProjectIdentityConflict,
                InvalidFolderPath) as error:
            raise HTTPException(409, str(error)) from error
        return Response(status_code=204)

    return router
