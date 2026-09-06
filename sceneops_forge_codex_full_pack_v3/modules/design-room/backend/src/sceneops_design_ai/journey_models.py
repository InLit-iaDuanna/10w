"""Single-user planning journey; production execution is deliberately separate."""
from typing import Literal
import re
from pydantic import BaseModel, ConfigDict, Field, model_validator


class JourneyModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Outline(JourneyModel):
    title: str = Field(min_length=1, max_length=200)
    experience: str = Field(min_length=1, max_length=8000)
    core_loop: str = Field(min_length=1, max_length=8000)
    scope: str = Field(min_length=1, max_length=8000)
    acceptance: str = Field(min_length=1, max_length=8000)
    assumptions: list[str] = Field(default_factory=list, max_length=30)


class ProductionCard(JourneyModel):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,80}$')
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    dependencies: list[str] = Field(default_factory=list, max_length=30)
    acceptance: str = Field(min_length=1, max_length=4000)
    status: Literal['planned'] = 'planned'


class CardProposal(JourneyModel):
    cards: list[ProductionCard] = Field(min_length=1, max_length=30)

    @model_validator(mode='after')
    def valid_graph(self):
        graph = {card.id: card.dependencies for card in self.cards}
        if any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', card.id) for card in self.cards):
            raise ValueError('制作卡片 ID 必须以字母或数字开头，以兼容 Git 分支。')
        if len(graph) != len(self.cards):
            raise ValueError('制作卡片 ID 不能重复。')
        visited, visiting = set(), set()
        def visit(node):
            if node not in graph or node in visiting:
                raise ValueError('制作卡片存在缺失依赖或循环依赖。')
            if node in visited: return
            visiting.add(node)
            for dependency in graph[node]: visit(dependency)
            visiting.remove(node)
            visited.add(node)
        for node in graph: visit(node)
        return self


class CompactCardProposal(CardProposal):
    """The four user-facing production lines; implementation details stay inside them."""
    cards: list[ProductionCard] = Field(min_length=4, max_length=4)

    @model_validator(mode='after')
    def one_card_per_workflow(self):
        expected = {'world-3d', 'core-gameplay', 'growth-feedback', 'demo-delivery'}
        actual = {card.id for card in self.cards}
        if actual != expected:
            raise ValueError('制作方案必须使用四个固定主线 ID：world-3d、core-gameplay、growth-feedback、demo-delivery。')
        return self


class QuestionOption(JourneyModel):
    label: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)


class PlanningQuestion(JourneyModel):
    prompt: str = Field(min_length=1, max_length=1200)
    options: list[QuestionOption] = Field(min_length=2, max_length=3)
    recommended_index: int = Field(ge=0, le=2)

    @model_validator(mode='after')
    def valid_recommendation(self):
        if self.recommended_index >= len(self.options): raise ValueError('推荐项不存在。')
        return self


class GrillReply(JourneyModel):
    text: str = Field(max_length=3000)
    question: PlanningQuestion


class AlignmentSummaryReply(JourneyModel):
    text: str = Field(min_length=1, max_length=3000)


class JourneyMessage(JourneyModel):
    id: str
    role: Literal['user', 'assistant']
    text: str
    created_at: str
    provider: str | None = None
    model: str | None = None
    mode: Literal['live', 'mock', 'planned'] = 'live'
    question: PlanningQuestion | None = None
    reply_to: str | None = None
    modeling_block: str | None = Field(default=None, max_length=80)


class CardModelingSession(JourneyModel):
    """A card-owned design conversation, never evidence of a produced model."""
    id: str
    card_id: str
    source: Literal['import', 'create']
    messages: list[JourneyMessage] = Field(default_factory=list)
    composer_draft: str = ''
    stage: Literal['brief', 'awaiting_import']
    mode: Literal['planned'] = 'planned'


class ArchitectureRecommendation(JourneyModel):
    code_architecture: Literal['object-component', 'ecs']
    rationale: str = Field(min_length=1, max_length=1200)
    tradeoffs: list[str] = Field(min_length=1, max_length=4)


class GameProjectScaffold(JourneyModel):
    root_path: str
    initialization_status: Literal['generated', 'existing']
    package_manager: Literal['pnpm'] | None = None
    entry_file: str | None = None
    generated_files: list[str] = Field(default_factory=list, max_length=30)
    check_command: str | None = None
    build_command: str | None = None
    preview_command: str | None = None


class GameTechnicalPlan(JourneyModel):
    target_platform: Literal['web'] = 'web'
    engine: Literal['threejs'] = 'threejs'
    code_architecture: Literal['object-component', 'ecs']
    architecture_label: str
    selection_method: Literal['manual', 'ai']
    rationale: str = Field(min_length=1, max_length=1200)
    tradeoffs: list[str] = Field(min_length=1, max_length=4)
    ecs_library: Literal['miniplex'] | None = None
    scaffold: GameProjectScaffold
    selected_at: str


class JourneyVersion(JourneyModel):
    number: int
    confirmed_at: str
    outline: Outline
    stack: Literal['threejs'] | None = None
    cards: list[ProductionCard] = Field(default_factory=list)


class GitVersion(JourneyModel):
    number: int
    commit: str
    tag: str


class CardBranch(JourneyModel):
    card_id: str
    branch: str
    worktree_path: str
    base_commit: str


class RevisionReply(JourneyModel):
    text: str = Field(max_length=8000)
    revised_outline: Outline | None = None
    revised_cards: list[ProductionCard] | None = Field(default=None, max_length=30)
    rationale: str = Field(default='', max_length=2000)


class JourneyChange(JourneyModel):
    id: str
    base_revision: int
    before_outline: Outline | None
    before_cards: list[ProductionCard]
    after_outline: Outline | None
    after_cards: list[ProductionCard]
    rationale: str
    status: Literal['pending', 'accepted', 'rejected'] = 'pending'


class PlanningJourney(JourneyModel):
    project_id: str
    root_path: str
    revision: int = 0
    collaboration: Literal['solo'] = 'solo'
    stage: Literal['idea', 'grill', 'outline', 'stack', 'cards'] = 'idea'
    messages: list[JourneyMessage] = Field(default_factory=list)
    outline: Outline | None = None
    versions: list[JourneyVersion] = Field(default_factory=list)
    stack: Literal['threejs'] | None = None
    technical_plan: GameTechnicalPlan | None = None
    architecture_recommendation: ArchitectureRecommendation | None = None
    cards: list[ProductionCard] = Field(default_factory=list)
    composer_draft: str = ''
    model_calls: int = 0
    git_versions: list[GitVersion] = Field(default_factory=list)
    card_branches: list[CardBranch] = Field(default_factory=list)
    active_card_id: str | None = None
    changes: list[JourneyChange] = Field(default_factory=list)
    modeling_sessions: list[CardModelingSession] = Field(default_factory=list)
    active_modeling_id: str | None = None
    cost_notice: str = '每次发送或生成最多调用一次所选模型；费用未知，不自动重试或切换提供方。'


class JourneyCommand(JourneyModel):
    request_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,100}$')
    expected_revision: int = Field(ge=0)
    operation: Literal['message', 'save_draft', 'start_grill', 'generate_outline', 'save_outline',
        'confirm_version', 'confirm_stack', 'recommend_architecture', 'confirm_technical_plan',
        'generate_cards', 'save_cards',
        'accept_change', 'reject_change', 'select_card', 'clear_card', 'enable_git',
        'choose_model_source', 'new_modeling', 'open_modeling', 'close_modeling']
    text: str = Field(default='', max_length=16000)
    outline: Outline | None = None
    cards: list[ProductionCard] | None = Field(default=None, max_length=30)
    accept_assumptions: bool = False
    question_message_id: str | None = None
    option_index: int | None = Field(default=None, ge=0, le=2)
    card_id: str | None = None
    change_id: str | None = None
    model_source: Literal['import', 'create'] | None = None
    modeling_id: str | None = None
    context_draft: str | None = Field(default=None, max_length=16000)
    code_architecture: Literal['object-component', 'ecs'] | None = None
    selection_method: Literal['manual', 'ai'] | None = None


class JourneyStreamEvent(JourneyModel):
    type: Literal['status', 'text_delta', 'reasoning_delta', 'complete', 'error']
    text: str = ''
    state: PlanningJourney | None = None
