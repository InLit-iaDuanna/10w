"""Permanent deletion is bounded to an explicitly confirmed, registered project root."""
import os
from pathlib import Path
import shutil

from .repository import FolderProjectConflict, InvalidFolderPath


def delete_project_files(repository, project_id, confirmed_root_path):
    project = repository.get_folder_project(project_id)
    if confirmed_root_path != project.root_path:
        raise FolderProjectConflict("项目位置已变化，请重新确认完整路径。")
    root = repository._safe_existing_directory(Path(project.root_path))
    if any(path == root or root in path.parents for path in
           (Path.home().resolve(), Path.cwd().resolve(), repository.path.resolve())):
        raise InvalidFolderPath("不能删除用户主目录、应用目录或本机数据所在目录。")
    repository._safe_existing_directory(root / '.sceneops')
    identity = repository._read_project_identity(root)
    if identity is None or identity.project_id != project_id:
        raise FolderProjectConflict("目录的项目身份不匹配，不能删除本地文件。")
    with repository.connect() as connection:
        roots = connection.execute("SELECT project_id,root_path FROM workspace_folder_projects").fetchall()
        if any(row['project_id'] != project_id and root in Path(row['root_path']).parents for row in roots):
            raise FolderProjectConflict("目录中包含另一个已登记项目，请先处理子项目。")
        worktrees = connection.execute(
            "SELECT worktree_path FROM workspace_card_worktrees WHERE project_id=?", (project_id,)).fetchall()
        if any(root not in Path(row['worktree_path']).parents for row in worktrees):
            raise FolderProjectConflict("项目仍有关联的外置卡片工作区，请先处理这些工作区后再删除本地目录。")
    git = root / '.git'
    if git.is_symlink() or git.is_file():
        raise InvalidFolderPath("该目录使用外置 Git 存储，不能直接删除。")
    if (git / 'worktrees').exists():
        raise FolderProjectConflict("项目仍有 Git 工作区关联，请先移除关联后再删除。")
    if not shutil.rmtree.avoids_symlink_attacks:
        raise InvalidFolderPath("当前系统不支持安全的目录删除。")
    try:
        with_parent = os.open(root.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            shutil.rmtree(root.name, dir_fd=with_parent)
        finally:
            os.close(with_parent)
    except OSError as error:
        raise FolderProjectConflict("本地目录未能完整删除，可能有部分文件已删除；项目登记保留，请检查目录后重试。") from error
    repository.forget_folder_project(project_id)
