"""Alignment-bound preparation and explicitly authorized bundled demo installation."""
import sqlite3
from uuid import UUID
from sceneops_harness import HarnessError
from .task_models import AgentAction


def validate_demo_alignment(alignment_id, context):
    if context.get('card_alignment_id') != alignment_id:
        raise HarnessError('DEMO_ALIGNMENT_CHANGED', '卡片对齐总结已改变，请根据最新总结重新准备授权卡。')


def prepare_demo(task, request, context):
    if request.alignment_id is not None:
        validate_demo_alignment(request.alignment_id, context)
        task.id = 'task_demo_' + UUID(request.alignment_id).hex + ('_native' if request.execution_mode == 'agent-full-access' else '')
    task.observations['demo_request'] = request.model_dump(mode='json')
    task.observations['demo_delivery'] = {
        'instruction': ('在当前卡片技术架构内完成对齐目标。授权后系统先安装内置 Demo 素材；'
            '读取 demo_assets 返回的模块路径、exports 和集成说明，复用角色、房屋、树木等素材。'
            '先检查已有文件，保留用户修改；缺依赖且已授权时准备依赖。完成前必须运行 '
            'code.project.check、code.project.build、code.preview.start；'
            '允许浏览器观察时调用 code.browser.observe 检查当前预览，再以 agent.finish 提交真实结果。'),
    }


def prepare_project_demo(task, request, context):
    validate_project_demo_alignment(request.alignment_id, context)
    token = request.alignment_id.removeprefix('direction_')
    task.id = ('task_project_demo_agent_' if request.task_profile == 'project-demo-agent'
               else 'task_project_demo_') + token
    if request.execution_mode == 'agent-full-access':
        from uuid import uuid4
        task.id += '_native_' + uuid4().hex
    task.observations['demo_request'] = request.model_dump(mode='json')
    task.observations['project_demo_context'] = context
    task.observations['demo_goals'] = [{
        'request_id': 'initial_' + token, 'goal': request.goal.strip(),
        'kind': 'initial', 'accepted_at': task.created_at.isoformat(),
    }]
    task.observations['active_goal_action_start'] = 0
    task.observations['demo_delivery'] = {
        'instruction': (('授权后由真实制作模型读取已确认方向、登记工作区和现有内容；使用公开内容服务与'
            '受控源码工具完成可编辑初版，根据真实检查和浏览器结果修复，再更新同一试玩。')
            if request.task_profile == 'project-demo-agent' else
            ('授权后通过公开资产、场景和固定工程运行服务建立钥匙门夹具；'
             '保存程序化配方与实例行为，物化到登记项目工作区，然后检查、构建并更新同一试玩。')),
    }


def validate_project_demo_alignment(alignment_id, context):
    if context.get('direction_id') != alignment_id:
        raise HarnessError('DEMO_DIRECTION_CHANGED', '初版方向已改变，请根据最新方向重新准备执行范围。')


def create_demo_once(records, task):
    try:
        return records.create(task)
    except sqlite3.IntegrityError:
        existing = records.get(task.id)
        if (existing.project_id != task.project_id
                or existing.authorization_card.card_id != task.authorization_card.card_id
                or existing.authorization_card.workspace_id != task.authorization_card.workspace_id
                or existing.observations.get('demo_request') != task.observations['demo_request']):
            raise HarnessError('DEMO_PREPARE_CONFLICT', '此对齐总结已经准备过不同的 Demo 请求，请重新对齐后再准备。')
        return existing


async def install_authorized_demo(service, task_id):
    task = service.check_grant(task_id)
    if not task.grant.include_demo_assets:
        return
    from .task_loop import record_action, execute_action
    existing = next((entry for entry in task.actions if entry.action.action_id == 'install_demo_assets'), None)
    if existing is not None and existing.state == 'succeeded':
        return
    action = AgentAction(action_id='install_demo_assets', capability_id='code.demo_assets.install',
        rationale='按本次确认授权安装内置 Demo 素材，保留当前卡片分支已有文件。', inputs={})
    action_id = record_action(service, task_id, action)
    await execute_action(service, task_id, action_id)
    result = next(entry for entry in service.get(task_id).actions if entry.action.action_id == action_id)
    if result.state != 'succeeded':
        raise HarnessError('DEMO_ASSETS_NOT_READY', '内置 Demo 素材尚未安装完成，请检查该动作结果。')
