"""Alignment-bound preparation for stable project Demo tasks."""
import sqlite3

from sceneops_harness import HarnessError


def prepare_project_demo(task, request, context):
    validate_project_demo_alignment(request.alignment_id, context)
    token = request.alignment_id.removeprefix('direction_')
    task.id = 'task_project_demo_' + token
    task.observations['demo_request'] = request.model_dump(mode='json')
    task.observations['project_demo_context'] = context
    task.observations['demo_delivery'] = {
        'instruction': ('授权后通过公开资产、场景和固定工程运行服务建立钥匙门夹具；'
            '保存程序化配方与实例行为，物化到登记项目工作区，然后检查、构建并更新同一试玩。'),
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
