"""Product export knowledge shared by structured chat and native execution."""
from dataclasses import dataclass
from importlib.resources import files

VERSION = 'sceneops-export-skills-1'
SKILLS = (
    ('sceneops-export-environment', '检查并补齐本机构建工具、SDK、依赖和路径配置'),
    ('sceneops-export-android', 'Capacitor Android APK/AAB 构建、诊断和设备验证'),
    ('sceneops-export-desktop', 'Electron macOS/Windows 包、架构、资源和独立启动'),
    ('sceneops-release-publish', '明确要求时准备签名、渠道、商店或公开发布'),
)
PLATFORMS = {'android', 'mac-arm64', 'mac-x64', 'win-x64'}

STRUCTURED_PROTOCOL = '''当前运行入口：导出页面的结构化对话，不是原生电脑执行会话。
只返回指定 JSON Schema。可执行动作只有 continue、cancel、configure、request_development。
configure 仅允许 app_name/ orientation；不能用它改变下载权限或注入命令。
这些动作没有 shell、安装器、浏览器或桌面工具。缺少 SDK 等环境能力时说明需要原生执行会话，
不能返回伪造命令或声称已安装。环境 skill 的操作步骤由具备真实工具的已授权原生会话执行。
在用户要求修复/继续时提出合适的动作；普通问答不执行。request_development 用于超出打包
范围的游戏代码需求。所有执行成功与否以运行器后续结果为准。'''

NATIVE_PROTOCOL = '''当前为原生执行提示词资源。先读取实际提供的工具与本次任务授权，
再使用对应技能完成导出。能够操作电脑时，常规缺项在授权范围内自行补齐、验证并继续，
无需把工作拆成让用户手动执行的命令列表。缺少真实工具不能由本提示词补出工具。
保留当前运行器的授权、取消、恢复、调用记录与输出登记，不绕过任务服务直接调用其他执行器。'''


@dataclass(frozen=True)
class ExportKnowledge:
    instructions: str
    loaded_skills: tuple[str, ...]


def load_export_knowledge(platforms, *, native=False, publish=False):
    selected_platforms = set(platforms)
    if selected_platforms - PLATFORMS:
        raise ValueError('导出技能只接受已登记的目标平台。')
    selected = ['sceneops-export-environment']
    if 'android' in selected_platforms:
        selected.append('sceneops-export-android')
    if selected_platforms & {'mac-arm64', 'mac-x64', 'win-x64'}:
        selected.append('sceneops-export-desktop')
    if publish:
        selected.append('sceneops-release-publish')
    root = files('sceneops_ai_agents')
    blocks = [root.joinpath('prompts/export-agent.md').read_text(encoding='utf-8')]
    for name in selected:
        resource = root.joinpath(f'skills/{name}/SKILL.md')
        # Include the resource location so native agents can read relative references.
        blocks.append(f'技能来源：{resource}\n' + resource.read_text(encoding='utf-8'))
    blocks.append(NATIVE_PROTOCOL if native else STRUCTURED_PROTOCOL)
    return ExportKnowledge('\n\n'.join(blocks), tuple(selected))


def native_export_skill_catalog():
    """Discoverable in existing native tasks; discovery is not a loaded-skill claim."""
    root = files('sceneops_ai_agents')
    lines = ['按需技能：只有用户目标涉及应用导出、打包环境或发布时才读取以下资料。'
             '普通游戏开发不要因此安装发布工具。技能不会扩大本次授权。',
             f'导出系统提示词：{root.joinpath("prompts/export-agent.md")}']
    lines.extend(f'- {name}：{description}。读取 {root.joinpath(f"skills/{name}/SKILL.md")}'
                 for name, description in SKILLS)
    return '\n'.join(lines)
