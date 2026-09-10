"""Canonical production taxonomy shared by every game and editor entry."""
from typing import Literal

ProductionDomainId = Literal['planning', 'assets-animation', 'world', 'gameplay', 'lookdev', 'ui-audio', 'delivery']
PRODUCTION_DOMAINS = (
    dict(id='planning', title='策划与制作', description='游戏目标、范围、功能包、制作安排与验收要求。'),
    dict(id='assets-animation', title='资产与动画', description='模型、角色、道具、可编辑源、骨骼与动画。'),
    dict(id='world', title='场景与关卡', description='场景布局、关卡空间、对象摆放与碰撞。'),
    dict(id='gameplay', title='玩法与交互', description='控制、战斗、规则、任务与对象行为。'),
    dict(id='lookdev', title='材质与画面', description='材质、灯光、Shader、特效与画面风格。'),
    dict(id='ui-audio', title='界面与声音', description='HUD、菜单、交互提示、音效与音乐。'),
    dict(id='delivery', title='试玩与交付', description='构建试玩、问题验证、版本管理与导出。'),
)
DOMAINS = tuple(domain['id'] for domain in PRODUCTION_DOMAINS)
