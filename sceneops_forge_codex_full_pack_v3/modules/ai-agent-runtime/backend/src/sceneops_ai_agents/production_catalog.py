"""Canonical projection from tool capabilities to existing workbench identities."""
from .production_models import ProductionModule

MODULE_TITLES = {
    'project-planning': '需求与规划', 'concept-assets': '概念与资产',
    'character-animation': '角色与动画', 'world-logic': '世界与玩法',
    'ui-audio-vfx': 'UI、音频与特效', 'render-ops': '渲染',
    'unity-build': 'Unity 集成与构建', 'ai-playtest': 'AI 游测',
    'version-review': '版本与交付', 'integration-ops': '集成与运维',
}
CAPABILITY_MODULES = {
    'agent.next_action': 'project-planning', 'agent.finish': 'version-review',
    'blender.asset.create': 'concept-assets', 'blender.asset.export': 'concept-assets',
    'blender.scene.inspect': 'concept-assets', 'unity.asset.import': 'unity-build',
    'unity.scene.inspect': 'unity-build', 'codex.task.execute': 'integration-ops',
    'unity.prototype.compose': 'world-logic', 'unity.prototype.inspect': 'unity-build',
    'unity.prototype.play': 'ai-playtest', 'unity.prototype.capture': 'ai-playtest',
    'unity.prototype.verify': 'ai-playtest',
    'agent.report_blocked': 'project-planning',
    'agent.history.read': 'project-planning',
    'code.workspace.inspect': 'world-logic', 'code.file.read': 'world-logic',
    'code.file.write': 'world-logic',
}


def module_for(capability: str) -> str:
    return CAPABILITY_MODULES.get(capability, 'integration-ops')


def module_catalog():
    notices = {
        'project-planning': '已接入逐动作观察与决策；完整生产步骤图规划仍待接入。',
        'concept-assets': '受控工具当前支持基础几何、FBX 导出与读回；原生图片需单独授权，真实图像与通用建模尚未实测。',
        'unity-build': '已接入资产导入和场景回读；不能据此视为开发包构建已接通。',
        'version-review': '当前支持基础交换任务的身份与尺寸检查；完整版本交付仍待接入。',
        'integration-ops': '显示实际 CLI 活动与已有工具连接记录；连接成功与业务验收分别记录。',
        'world-logic': '已接入固定生存配方，以及已登记卡片分支内的有界源码读写；源码交付须审阅，未运行或编译。',
        'ai-playtest': '已接入该配方的正式共享输入、真实帧确定性验证；不是通用视觉 AI 游测。',
    }
    return [ProductionModule(id=key, title=title,
        capability_ids=[capability for capability, module in CAPABILITY_MODULES.items() if module == key],
        readiness_notice=notices.get(key, '真实执行处理器尚未接入，不能以 Agent 计划或产物自述冒充完成。'),
        handler_status='implemented' if key in {'project-planning', 'concept-assets', 'unity-build',
            'version-review', 'integration-ops', 'world-logic', 'ai-playtest'} else 'not_connected') for key, title in MODULE_TITLES.items()]
