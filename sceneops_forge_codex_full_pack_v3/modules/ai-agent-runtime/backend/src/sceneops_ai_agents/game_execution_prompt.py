"""Trusted game-production instructions selected from persisted design enums."""

CAMERA_INSTRUCTIONS = {
    'fit-scene': '相机策略：一屏取景。以可玩场景边界的包围盒中心为目标，按边界、视角与窗口宽高比计算距离或正交视锥，并留出角色半径和 HUD 安全边距。必须同时看到玩家、可到达目标和返回点；不让相机无故跟随玩家而丢失整图信息。',
    'follow-player': '相机策略：跟随玩家。相机以玩家世界坐标为跟随目标，位置与 lookAt 都随玩家更新；按选定视角保持偏移与观察距离，用 deltaTime 无关的指数平滑，并在移动、转向、重生后保持玩家可见。先更新玩家再更新相机；不得只移动相机却始终看向世界原点。处理场景边缘与遮挡，避免穿墙或裁掉玩家。',
    'first-person': '相机策略：第一人称。相机绑定玩家视点与眼高，朝向由输入控制，角色移动与观察方向一致。出生和重开时朝向主要玩法目标，默认水平视线、roll 为 0；鼠标控制 yaw/pitch，不沿用场景展示相机的斜侧俯视角。准星中心与相机中心射线必须对应同一个显示位置。明确近裁剪面与角色碰撞尺寸，避免看见自身模型内部；需要鼠标锁定时提供清楚的进入和退出交互。',
    'side-scroll': '相机策略：横向跟随。以玩家世界坐标为跟随目标，在玩法平面内平滑跟随，保持正交尺度或透视距离稳定，并按关卡边界限制取景。向移动方向留视野，跳跃时不裁掉玩家，不把未授权的镜头变化当作美术优化。',
}

GAME_PRESENTATION_INSTRUCTIONS = '''游戏生成必须同时设计玩法、相机、世界尺度和实际显示尺寸。先从已确认方向明确观察对象、视角、移动范围与关键目标；这些是实现责任，不把常规工程决策重新变成用户表单。
尺寸与缩放：区分 CSS 逻辑像素、canvas drawing buffer 像素和世界单位。WebGLRenderer.setPixelRatio 只提高渲染分辨率，不能让页面画布变大。使用 renderer.setSize(w,h,false) 时必须给 canvas 明确匹配宿主的 CSS 宽高（例如 width:100%;height:100%）；不能依赖 canvas 物理 width/height 属性决定布局。监听实际宿主尺寸变化，更新渲染器、camera.aspect/正交边界和投影矩阵，分区拖动和窗口变窄也必须适配。不要通过固定设备像素比或仅修改单一截图的相机距离掩盖布局问题。
排查偏移：先测量 canvas.getBoundingClientRect() 与宿主的宽高和中心，再检查相机。DPR 2 时 drawing buffer 可以是显示尺寸的两倍，但 canvas CSS 尺寸仍等于宿主；否则只显示画面左上部分，HTML 准星会偏离渲染中心。修复根因后复测，不能通过旋转相机、移动准星或降低 DPR 补偿裁切。使用 ResizeObserver 监听宿主尺寸。
世界与相机：统一场景坐标与单位；依据实际模型包围盒、角色尺寸、地图范围、相机 FOV/正交尺度来确定距离和近远裁剪面。相机跟随策略不等于观察角度；按用户确认的正面、俯视、第一人称或侧视实现，不默认添加斜侧角或镜头滚转。检查玩家出生点、地图边缘、交互目标和重生后的取景。HUD 不随世界缩放，在窄窗口换行或紧凑排列，不遮住玩家、开始/重开操作与关键提示。
输入与可玩性：WASD/方向键方向与画面一致。窗口失焦清空按键；重新开始重置状态、计时和输入。明确开始/结束/重开反馈，避免背景页面持续输入；如存在暂停需求应清楚呈现。修复视觉问题只改责任层，不重做玩法或增加无关功能。
验证：源码检查与构建通过不等于视觉或玩法通过。在当前已有浏览器权限和工具内，实际检查开始画面、运行画面、移动后玩家位置和重开；至少覆盖一个宽窗口与一个窄窗口、DPR 1 与 DPR 2。核对 canvas 的 CSS 包围盒与宿主一致，玩家和关键目标在相机中可见，HUD 不溢出。没有可用浏览器工具时明确标记未验证，不安装新工具或声称截图验收成功。任何修复后重新检查对应场景；不改测试或虚构结果。
所有以上要求服从用户当前目标、既有工程架构与本次执行授权，不扩大文件、网络、浏览器或模型权限。已有项目仅增量补齐相关要求。'''


def game_execution_instructions(camera_mode=None):
    camera = CAMERA_INSTRUCTIONS.get(camera_mode,
        '相机策略尚未单独记录：根据已确认的视角和玩法选择一屏取景、跟随玩家、第一人称或横向跟随，说明选择并在代码中落实。大型可移动关卡通常跟随玩家；一屏收集或棋盘场景应覆盖完整可玩范围，不机械套用同一种镜头。')
    return GAME_PRESENTATION_INSTRUCTIONS + '\n\n' + camera


def task_game_instructions(task):
    from .export_knowledge import native_export_skill_catalog
    context = task.observations.get('project_demo_context', {})
    return (game_execution_instructions(context.get('direction', {}).get('camera_mode'))
            + '\n\n' + native_export_skill_catalog())
