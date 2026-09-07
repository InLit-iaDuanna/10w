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
    if data.context_summary.get('task_profile') == 'project-demo-agent':
        paths.extend(['sceneops-demo-composer/SKILL.md',
                      'sceneops-editable-content/SKILL.md'])
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
