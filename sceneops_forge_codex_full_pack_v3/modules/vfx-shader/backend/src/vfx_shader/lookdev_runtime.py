"""Fixed compiler-owned migration for an already-authorized registered workspace."""
import json
import shutil
import subprocess
from pathlib import Path
from .lookdev_models import LookdevError


def requires_game_runtime(state):
    return (any(m.get('shaderGraph') or m.get('procedural',{}).get('type','none')!='none'
                for m in state.get('materials',[]))
            or any(op.get('kind') in ('light.add','light.update')
                   for entry in state.get('editLog',[]) for op in entry.get('operations',[])))


def prepare_lookdev_runtime(workspace_root):
    application_root = Path(__file__).resolve().parents[5]
    node = shutil.which('node')
    if node is None:
        raise LookdevError('VALIDATOR_UNAVAILABLE', 'Node 运行环境不可用。', 503)
    result = subprocess.run([node, '--import', 'tsx', str(application_root / 'modules/vfx-shader/scripts/migrate-lookdev-game.ts'),
        str(workspace_root), '--apply'], cwd=application_root / 'modules/vfx-shader/frontend',
        capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise LookdevError('LOOKDEV_RUNTIME_MIGRATION_FAILED', '游戏渲染适配失败：' + result.stderr[-1500:])
    report = json.loads(result.stdout)
    if not report['supported']:
        raise LookdevError('LOOKDEV_RUNTIME_REQUIRES_EDIT', '当前游戏需要先通过主对话完成 WebGPU 接入：' + '\n'.join(report['requirements']))
    return report
