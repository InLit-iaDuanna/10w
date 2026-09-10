"""Select product-owned knowledge from task intent and actual action outcomes."""
from dataclasses import dataclass, field
from importlib.resources import files
import logging
import re

VERSION = "sceneops-s1.1"
PRODUCT_VERSION = "sceneops-d3.0"
UPSTREAM = "e5f301d548bb18c530afbece78cd25082f4cda9c"
LOGGER = logging.getLogger(__name__)
CHECKS = {"code.project.check", "code.project.build", "code.project.build_test",
          "code.preview.start", "code.browser.observe", "code.browser.interact"}
CONSULT = re.compile(r"^(?:请|帮我|please\s+)?(?:解释|讨论|比较|分析方案|explain\b|discuss\b|compare\b)", re.I)
VERIFY = re.compile(r"^(?:请|帮我|please\s+)?(?:检查|验证|验收|复查|测试|check\b|verify\b|test\b|review\b)", re.I)
TIMING = re.compile(r"冷却|冲刺|暂停|重开|计时|cooldown|dash|sprint|pause|restart|timer", re.I)

PRODUCTION_SKILLS = {
    'sceneops-demo-composer': {'path': 'sceneops-demo-composer/SKILL.md', 'summary': '组合可编辑的游戏 Demo 内容、源码和试玩交付。', 'production_kinds': ['game_create', 'game_modify', 'planning']},
    'sceneops-editable-content': {'path': 'sceneops-editable-content/SKILL.md', 'summary': '在现有作品中保留可编辑内容与稳定引用。', 'production_kinds': ['game_create', 'game_modify', 'modeling', 'scene']},
    'sceneops-threejs-gameplay': {'path': 'sceneops-threejs-gameplay/SKILL.md', 'summary': '实现 Three.js 游戏控制、状态、时间和玩法反馈。', 'production_kinds': ['game_create', 'game_modify', 'planning'], 'platforms': ['web']},
    'sceneops-threejs-qa': {'path': 'sceneops-threejs-qa/SKILL.md', 'summary': '基于实际构建与浏览器证据检查 Three.js 游戏。', 'production_kinds': ['game_create', 'game_modify'], 'platforms': ['web']},
    'sceneops-threejs-debug': {'path': 'sceneops-threejs-debug/SKILL.md', 'summary': '定位并修复 Three.js 运行、画面与交互问题。', 'production_kinds': ['game_modify'], 'platforms': ['web']},
    'sceneops-blender-technical-artist': {'path': 'sceneops-blender-technical-artist/SKILL.md', 'summary': '制作、修改并验证可用于游戏的 Blender 资产。', 'production_kinds': ['modeling', 'scene', 'game_create', 'game_modify']},
    'sceneops-unity-project-engineer': {'path': 'sceneops-unity-project-engineer/SKILL.md', 'summary': '在已登记 Unity 工程中导入、修改并回读内容。', 'production_kinds': ['modeling', 'scene', 'game_modify'], 'platforms': ['unity']},
    'sceneops-export-environment': {'path': 'sceneops-export-environment/SKILL.md', 'summary': '检查并补齐本地导出环境。', 'production_kinds': ['export']},
    'sceneops-export-android': {'path': 'sceneops-export-android/SKILL.md', 'summary': '导出 Android APK 或 AAB 并处理平台问题。', 'production_kinds': ['export'], 'platforms': ['android']},
    'sceneops-export-desktop': {'path': 'sceneops-export-desktop/SKILL.md', 'summary': '导出 macOS 或 Windows 桌面应用。', 'production_kinds': ['export'], 'platforms': ['mac-arm64', 'mac-x64', 'win-x64']},
    'sceneops-release-publish': {'path': 'sceneops-release-publish/SKILL.md', 'summary': '在明确发布要求下处理签名、渠道与上线。', 'production_kinds': ['export']},
}


def production_skill_catalog():
    return [{'id': skill_id, **{key: value for key, value in item.items() if key != 'path'}}
            for skill_id, item in PRODUCTION_SKILLS.items()]


def production_skill_detail(skill_id):
    item = PRODUCTION_SKILLS.get(skill_id)
    if item is None:
        raise KeyError(skill_id)
    return files('sceneops_ai_agents').joinpath('skills', item['path']).read_text(encoding='utf-8')


@dataclass
class SkillContext:
    phase: str
    blocks: list[str] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)


def _evidence(entry):
    result = entry.get("result_summary", entry.get("result", {}))
    return result.get("evidence", {}) if isinstance(result, dict) else {}


def _failed(entry):
    run = _evidence(entry).get("run", {})
    return (entry.get("state") == "failed" or
            (isinstance(run, dict) and not run.get("source_stale") and
             (run.get("status") == "failed" or run.get("passed") is False)))


def select_skills(data):
    """Only explicit request prefixes and structured outcomes select a phase.

    Source text and tool logs are never searched for instruction keywords.
    A later result for the same operation supersedes its earlier failure.
    """
    capabilities = {item["id"] for item in data.capabilities}
    if CONSULT.search(data.goal.strip()):
        return "consultation", []
    if not any(item.startswith("code.") for item in capabilities):
        return "other", []
    latest = {}
    last = None
    for entry in data.history:
        capability = entry.get("action", {}).get("capability_id", "")
        if capability.startswith("code."):
            latest[capability] = entry
            last = entry
        # Status reads carry newer snapshots of check/build, including source_stale.
        project = _evidence(entry).get("project", {})
        if capability == "code.project.status" and isinstance(project, dict):
            for operation in ("check", "build"):
                run = project.get(operation)
                if isinstance(run, dict):
                    latest[f"code.project.{operation}"] = {
                        "result_summary": {"evidence": {"run": run}}}
    diagnostics = data.context_summary.get("game_diagnostics", {})
    current_browser = diagnostics.get("latest", {}) if isinstance(diagnostics, dict) else {}
    browser_status = current_browser.get("evidence_status") if isinstance(current_browser, dict) else None
    browser_issues = set(current_browser.get("issue_types", [])) if isinstance(current_browser, dict) else set()
    failures = any(_failed(entry) for entry in latest.values())
    verify = bool(VERIFY.search(data.goal.strip()))
    last_capability = last.get("action", {}).get("capability_id") if last else None
    if browser_status == "fail" and browser_issues & {"behavior_issue", "browser_errors", "tool_failure"}:
        return "diagnosis", (["qa"] if verify else ["gameplay"]) + ["debug"]
    if failures:
        return "diagnosis", (["qa"] if verify else ["gameplay"]) + ["debug"]
    if browser_status == "stale":
        return "verification", ["qa"]
    if verify or (last and last.get("state") == "succeeded" and
                  (last_capability in CHECKS or
                   (last_capability == "code.file.write" and CHECKS & capabilities))):
        return "verification", ["qa"]
    if "code.file.write" in capabilities:
        return "implementation", ["gameplay"]
    return "consultation", []


def load_skill_context(data) -> SkillContext:
    phase, selected = select_skills(data)
    context = SkillContext(phase=phase)
    paths = []
    if data.context_summary.get('task_profile')=='unity-asset-edit':
        paths.append("sceneops-unity-project-engineer/SKILL.md")
    if data.context_summary.get('task_profile') == 'project-demo-agent':
        paths.extend(['sceneops-demo-composer/SKILL.md',
                      'sceneops-editable-content/SKILL.md'])
    if data.context_summary.get("task_profile") != "unity-asset-edit" and any(item["id"].startswith("blender.asset.") for item in data.capabilities):
        paths.append("sceneops-blender-technical-artist/SKILL.md")
    preparation = data.context_summary.get('production_preparation', {})
    recommendation = preparation.get('recommendation', {}) if isinstance(preparation, dict) else {}
    recommended_skills = recommendation.get('skills', []) if isinstance(recommendation, dict) else []
    for selection in recommended_skills if isinstance(recommended_skills, list) else []:
        skill_id = selection.get('candidate_id') if isinstance(selection, dict) else None
        item = PRODUCTION_SKILLS.get(skill_id)
        if item is not None:
            paths.append(item['path'])
    paths.extend(f"sceneops-threejs-{name}/SKILL.md" for name in selected)
    if "gameplay" in selected and TIMING.search(data.goal):
        paths.append("sceneops-threejs-gameplay/references/time-and-state.md")
    root = files("sceneops_ai_agents").joinpath("skills")
    for path in dict.fromkeys(paths):
        try:
            text = root.joinpath(path).read_text(encoding="utf-8")
            if not text.strip():
                raise ValueError("empty resource")
        except (OSError, UnicodeError, ValueError) as error:
            diagnostic = f"SKILL_RESOURCE_UNAVAILABLE skills/{path}: {type(error).__name__}"
            LOGGER.warning(diagnostic)
            context.logs.append(diagnostic)
            context.blocks.append(diagnostic + "；该资料未加载，继续不依赖它的工作，不推断其内容。")
            continue
        context.blocks.append(text)
        if path.startswith('sceneops-threejs-'):
            context.logs.append(f"skill.loaded {VERSION} upstream={UPSTREAM} skills/{path}")
        else:
            context.logs.append(f"skill.loaded {PRODUCT_VERSION} source=sceneops-product skills/{path}")
    context.logs.insert(0, f"skill.phase {phase}")
    return context
