"""A Unity target is a separate registered workspace and finite task grant."""
from pathlib import Path
from uuid import uuid4
from sceneops_harness import HarnessError
from .task_models import AgentTaskRecord, AuthorizationCard

UNITY_CONTENT_CAPABILITIES = ['agent.next_action','agent.history.read',
    'blender.scene.inspect','unity.scene.inspect','blender.asset.derive_unity','unity.content.import','unity.content.inspect',
    'unity.content.edit','unity.content.focus','unity.content.save','unity.content.play',
    'agent.finish','agent.report_blocked']


def prepare_unity_task(service, source_task_id, request):
    source = service.get(source_task_id)
    if source.authorization_card.task_profile not in ('project-demo','project-demo-agent'):
        raise HarnessError('TASK_SCOPE_DENIED','请从已登记 Demo 的实际资产入口准备 Unity 目标。')
    asset = service.project_assets.get(source.project_id, request.asset_id)
    if asset.workspace_id != source.authorization_card.workspace_id:
        raise HarnessError('TASK_SCOPE_DENIED','资产不属于所选作品工作区。')
    version = next((v for v in asset.versions if v.source_version==request.source_version),None)
    if version is None or version.source_kind!='blender' or not version.blend_path:
        raise HarnessError('UNITY_SOURCE_REQUIRED','请选择已有真实 Blender 编辑源的资产版本。')
    # The registered task/card is the workspace record, not a second scene database.
    for prior in service.records.list(source.project_id):
        target = prior.observations.get('unity_target',{})
        if target.get('source_task_id')==source_task_id and target.get('asset_id')==asset.id:
            if (prior.status=='failed' and service.records.safe_to_release(prior)
                    and not any(a.effect_state in ('COMMITTED','APPLIED','STAGED','UNKNOWN') for a in prior.actions)):
                continue
            return prior
    workspace_id = 'unity_ws_' + uuid4().hex
    root = service.workspace_base / 'unity-targets' / workspace_id / source.project_id
    settings = service.provider.settings()
    card = AuthorizationCard(workspace_root=str(root),workspace_id=workspace_id,
        task_profile='unity-asset-edit',capability_ids=UNITY_CONTENT_CAPABILITIES,
        allow_game_execution=True,max_model_calls=16,max_duration_seconds=1800,
        scope=('仅本项目所选 Blender 资产与此独立 Unity 2022.3.62f3c1 工作区：从登记源派生 FBX，'
               '导入／升级模型、保存两个共享外观实例，读取和修改单个实例的位置、钥匙要求与交互距离；'
               '显式保存、重开、定位及 Editor Play Mode 输入验证。场景与组件归 Unity Editor，'
               '不改 Web 工程、不安装 Editor/插件、不生成任意 C#、不构建 Player、不发布。'),
        cost_notice='本次最多 16 次模型请求、64 个类型化动作、30 分钟；人工和 Agent 共用期限与用量，不自动续授。')
    task = AgentTaskRecord(project_id=source.project_id,
        goal=f'把已选资产“{asset.title}”源版本 {request.source_version} 导入本次 Unity 工作区，建立两个共享模型实例并回读。先派生 FBX，再导入；完成后保持可编辑，不修改 Web 工程。',
        authorization_card=card,provider_id=settings.provider,provider_model=settings.model)
    task.observations['unity_target']={'source_task_id':source.id,'source_workspace_id':asset.workspace_id,
        'asset_id':asset.id,'source_version':request.source_version,'workspace_id':workspace_id,
        'project_id':source.project_id,'workspace_root':str(root),'editor_version':'2022.3.62f3c1',
        'instance_ids':['inst_'+uuid4().hex,'inst_'+uuid4().hex]}
    task.observations['active_goal_action_start']=0
    return service.records.create(task)


def unity_target(service, task):
    target = task.observations.get('unity_target')
    card = task.authorization_card
    if card.task_profile!='unity-asset-edit' or not isinstance(target,dict):
        raise HarnessError('TASK_SCOPE_DENIED','此任务不是已登记 Unity 目标。')
    expected=service.workspace_base/'unity-targets'/card.workspace_id/task.project_id
    if (target.get('project_id')!=task.project_id or target.get('workspace_id')!=card.workspace_id
            or target.get('workspace_root')!=str(expected) or card.workspace_root!=str(expected)
            or card.capability_ids!=UNITY_CONTENT_CAPABILITIES or card.execution_mode!='typed-tools'):
        raise HarnessError('TASK_SCOPE_DENIED','Unity 工作区登记与当前授权卡不一致。')
    from .task_tools import contained
    contained(expected, service.workspace_base)
    return target


def unity_source(service, task, version_number):
    target=unity_target(service,task)
    asset=service.project_assets.get(task.project_id,target['asset_id'])
    if asset.workspace_id!=target['source_workspace_id']:
        raise HarnessError('TASK_SCOPE_DENIED','登记资产的源工作区已改变。')
    version=next((v for v in asset.versions if v.source_version==version_number),None)
    if version is None or version.source_kind!='blender' or not version.blend_path:
        raise HarnessError('UNITY_SOURCE_REQUIRED','所选版本没有真实 Blender 源。')
    source_workspace=service.project_demo_workspace(task.project_id,target['source_workspace_id'])
    from .task_tools import contained
    path=contained(version.blend_path,Path(source_workspace['workspace_root']))
    if path.suffix!='.blend' or not path.is_file():
        raise HarnessError('UNITY_SOURCE_REQUIRED','登记 Blender 源文件不存在。')
    return asset,version,path


def validate_unity_grant(service, task):
    from .task_models import now
    target=unity_target(service,task); grant=task.grant
    if (grant is None or grant.revoked or task.cancel_requested or grant.expires_at is None or grant.expires_at<=now()):
        raise HarnessError('TASK_GRANT_INVALID','本次 Unity 授权不存在、已撤销或已到期。')
    if (grant.task_id!=task.id or grant.project_id!=task.project_id
            or grant.workspace_id!=target['workspace_id'] or grant.workspace_root!=target['workspace_root']
            or grant.capability_ids!=UNITY_CONTENT_CAPABILITIES or grant.execution_mode!='typed-tools'):
        raise HarnessError('TASK_SCOPE_DENIED','Unity 授权与登记目标不一致。')
    return target
