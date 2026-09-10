"""Stage canonical production skills into native CLI discovery directories."""
from pathlib import Path
import shutil

SKILL_NAMES = tuple(f'sceneops-threejs-{name}' for name in ('gameplay', 'graphics', 'ui', 'debug', 'qa'))


def stage_native_skills(workspace_root, executor, selected_skills=SKILL_NAMES):
    directory = {'codex': '.agents/skills', 'codebuddy': '.codebuddy/skills'}[executor]
    root = Path(workspace_root).resolve()
    destination = root / directory
    canonical = Path(__file__).with_name('skills')
    selected = set(selected_skills)
    unknown = selected.difference(SKILL_NAMES)
    if unknown:
        raise ValueError('原生制作技能选择无效：' + '、'.join(sorted(unknown)))
    staged = []
    for name in SKILL_NAMES:
        source, target = canonical / name, destination / name
        # Never follow user-created links outside this registered workspace.
        for parent in (destination.parent, destination, target):
            if parent.is_symlink():
                raise ValueError(f'技能目录不能为符号链接：{parent.relative_to(root)}')
        if target.exists():
            if not (target / '.sceneops-owned').is_file():
                raise ValueError(f'已有同名用户技能，不能覆盖：{target.relative_to(root)}')
            shutil.rmtree(target)
        if name not in selected:
            continue
        shutil.copytree(source, target)
        (target / '.sceneops-owned').write_text('SceneOps canonical production skill\n')
        staged.append(str((target / 'SKILL.md').relative_to(root)))
    return staged
