"""Authenticated composition roots can expose bounded local-folder project intake."""
from fastapi import APIRouter, HTTPException, Query

from .models import (FolderListing, FolderProject, FolderProjectCreate,
    FolderProjectList, WorkspaceError)
from .repository import FolderProjectConflict, InvalidFolderPath, WorkspaceRepository
from .git_projects import GitProjectError


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
            raise HTTPException(409, f'{error} 已创建的文件夹项目仍保留，请重新读取项目列表后打开，不要重复创建。') from error

    @router.get("/folder-projects", response_model=FolderProjectList,
        operation_id="workspaceListFolderProjects")
    def list_folder_projects():
        return FolderProjectList(projects=repository.list_folder_projects())

    @router.get("/folder-projects/{project_id}", response_model=FolderProject,
        operation_id="workspaceGetFolderProject")
    def get_folder_project(project_id: str):
        try:
            return repository.get_folder_project(project_id)
        except KeyError as error:
            raise HTTPException(404, "文件夹项目不存在。") from error
        except InvalidFolderPath as error:
            raise HTTPException(409, str(error)) from error

    return router
