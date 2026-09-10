"""User-reviewed handoff; source conversation remains data, never new requirements."""
import json
from typing import Literal
from pydantic import Field
from sceneops_harness import HarnessError
from .task_models import TaskModel, now


NativeProductionSkill = Literal['sceneops-threejs-gameplay', 'sceneops-threejs-graphics',
    'sceneops-threejs-ui', 'sceneops-threejs-debug', 'sceneops-threejs-qa']
DEFAULT_NATIVE_SKILLS: tuple[NativeProductionSkill, ...] = (
    'sceneops-threejs-gameplay', 'sceneops-threejs-graphics', 'sceneops-threejs-ui',
    'sceneops-threejs-debug', 'sceneops-threejs-qa')


class CreationBrief(TaskModel):
    version: int = 1
    content: str
    selected_skills: list[NativeProductionSkill] = Field(
        default_factory=lambda: list(DEFAULT_NATIVE_SKILLS), max_length=len(DEFAULT_NATIVE_SKILLS))
    confirmed_at: str | None = None


class SaveCreationBrief(TaskModel):
    expected_version: int = Field(ge=1)
    content: str = Field(min_length=1, max_length=128000)
    selected_skills: list[NativeProductionSkill] = Field(
        default_factory=lambda: list(DEFAULT_NATIVE_SKILLS), max_length=len(DEFAULT_NATIVE_SKILLS))


def initialize_brief(task):
    context = task.observations.get('project_demo_context', {})
    direction = context.get('direction', {})
    technical = context.get('technical_plan', {})
    sections = [('核心体验', direction.get('core_experience')),
                ('视觉与视角', direction.get('perspective_style')),
                ('首版范围', direction.get('simplified_scope')),
                ('技术架构', technical.get('architecture_label') or technical.get('code_architecture'))]
    confirmed = '\n\n'.join('### ' + title + '\n' + value for title, value in sections if isinstance(value, str) and value)
    excerpts = '\n\n'.join('> ' + item['text'][:1200].replace('\n', '\n> ')
        + ('\n> （原话较长，此处节选）' if len(item['text']) > 1200 else '')
        for item in context.get('user_excerpts', []) if isinstance(item.get('text'), str))
    preparation = context.get('production_preparation') or {}
    recommendation = preparation.get('recommendation') or {}
    references = '\n'.join('- ' + item['candidate_id'] + '：' + item.get('purpose', '')
        for item in recommendation.get('assets', [])[:30])
    content = ('# 初版制作简报\n\n## 本次制作目标（请核对）\n' + task.goal
        + '\n\n## 已确认方向与架构\n' + (confirmed or '以用户目标和登记工程架构为准。') + '\n'
        + ('\n## 对齐时的用户原话节选\n以下保留表达来源，早期想法可能已被修改，不自动作为必做项；以本次确认范围为准。\n' + excerpts + '\n' if excerpts else '')
        + '\n## 当前生产领域与功能包\n' + json.dumps({'domains':context.get('production_domains',{}),'feature_packages':context.get('feature_packages',[])},ensure_ascii=False) + '\n各领域制作阶段仅为制作安排，不是试玩验收结果。\n'
        + '\n## 素材与参考\n' + (references + '\n以上来自现有推荐，仍需核对可用性；推荐不是用户必做要求。' if references else '尚无已登记的素材推荐；使用已提供资料与实际可用资产，不虚构可用文件。')
        + '\n\n## 必做、非目标与自由细节\n必做：以上已确认核心体验和首版范围。'
          '非目标：未确认的新系统、已放弃方向及提交、合并、发布。未指定的可逆细节可自由发挥。'
          '不补充未经确认的必做项，不恢复已放弃方向。\n'
        + '\n## 技术与创作\n读取 .sceneops/game-architecture.json 和现有工程。'
          '该文件是本次已确认的游戏架构契约：实施计划与源码模块、状态流和场景组织必须逐项映射到该架构，不得自行替换。'
          '如真实工程与简报或架构契约冲突，先明确报告冲突，不得猜测或悄悄改成另一套架构。'
          '沿用 Three.js、TypeScript、Vite、pnpm 及已选架构。'
          '只加载确认页选中的 SceneOps 制作技能；未选技能不得作为本轮隐含要求。'
          '制作有一致视觉、明确反馈的代表性可玩场景，保留已有用户修改。\n'
        + '\n## 可编辑交付\n普通源码直接编辑；托管资产、场景实例和共享引用通过 SceneOps 工具。'
          '运行代码读取真实物化内容，复杂行为保留源码入口。不得直接编辑平台数据库。\n'
        + '\n## 检查\n在授权内实际检查、构建和试玩，修复实际问题。'
          '未观察的画面或玩法标明未验证。不得购买、发布、合并或提交无关内容。\n')
    task.observations.update(native_production=True,
        creation_brief=CreationBrief(content=content).model_dump(mode='json'))


def read_brief(service, task_id):
    task = service.get(task_id)
    value = task.observations.get('creation_brief')
    if not value:
        raise HarnessError('CREATION_BRIEF_MISSING', '此历史任务没有制作简报。')
    return CreationBrief.model_validate(value)


def save_brief(service, task_id, body):
    def save(task):
        if task.status != 'awaiting_authorization' or task.grant is not None:
            raise HarnessError('TASK_STATE_CONFLICT', '制作已开始，请通过续改提交新要求。')
        brief = CreationBrief.model_validate(task.observations['creation_brief'])
        if brief.version != body.expected_version:
            raise HarnessError('CREATION_BRIEF_CONFLICT', '简报已更新，请重新读取。')
        task.observations['creation_brief'] = CreationBrief(version=brief.version + 1,
            content=body.content, selected_skills=list(dict.fromkeys(body.selected_skills))).model_dump(mode='json')
    service.records.update(task_id, save, 'agent.creation_brief.saved')
    return read_brief(service, task_id)


def confirm_brief(task, version):
    if not task.observations.get('native_production'):
        return
    brief = CreationBrief.model_validate(task.observations['creation_brief'])
    if brief.confirmed_at is None:
        if version != brief.version:
            raise HarnessError('CREATION_BRIEF_CONFIRMATION_REQUIRED', '请先查看并确认当前版本制作简报。')
        brief.confirmed_at = now().isoformat()
        task.observations['creation_brief'] = brief.model_dump(mode='json')
