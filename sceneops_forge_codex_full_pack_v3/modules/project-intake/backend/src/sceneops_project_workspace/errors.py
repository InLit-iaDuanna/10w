"""Project scope failures shared by repository consumers and HTTP composition."""


class ProjectScopeError(Exception):
    def __init__(self, project_id: str):
        self.project_id = project_id
        super().__init__(self.message)

    def __str__(self):
        return self.message


class ProjectNotFound(ProjectScopeError, KeyError):
    code = "PROJECT_NOT_FOUND"
    status_code = 404
    message = "项目不存在，请创建或选择已有项目。"


class FolderProjectRequired(ProjectScopeError, ValueError):
    code = "FOLDER_PROJECT_REQUIRED"
    status_code = 409
    message = "此操作需要文件夹项目，请选择已绑定文件夹的项目。"
