"""Read the registered card worktree's current Git changes for review UI."""
import subprocess
from pathlib import Path

from .task_models import now


def git_workspace_changes(root: Path) -> dict:
    result = subprocess.run(
        ['git', 'status', '--porcelain=v1', '-z', '--untracked-files=all', '--no-renames'],
        cwd=root,
        capture_output=True,
        timeout=8,
        check=False,
    )
    if result.returncode != 0:
        return {
            'available': False,
            'source': 'git-status',
            'captured_at': now().isoformat(),
            'files': [],
            'reason': '无法读取当前卡片分支的 Git 状态。',
        }

    files = []
    totals = {'added': 0, 'modified': 0, 'deleted': 0}
    for raw_entry in result.stdout.split(b'\0'):
        if len(raw_entry) < 4:
            continue
        raw_status = raw_entry[:2].decode('ascii', errors='replace')
        path = raw_entry[3:].decode('utf-8', errors='replace')
        if raw_status == '??' or ('A' in raw_status and 'D' not in raw_status):
            change = 'added'
        elif 'D' in raw_status:
            change = 'deleted'
        else:
            change = 'modified'
        totals[change] += 1
        files.append({'path': path, 'change': change, 'git_status': raw_status})

    files.sort(key=lambda item: (item['path'].casefold(), item['path']))
    return {
        'available': True,
        'source': 'git-status',
        'captured_at': now().isoformat(),
        'files': files,
        'totals': totals,
    }
