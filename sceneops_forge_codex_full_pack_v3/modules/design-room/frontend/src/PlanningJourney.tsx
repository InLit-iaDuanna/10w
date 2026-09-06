import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { workspaceClient } from '../../../../packages/workspace-client/frontend/src/index.ts';
import { journeyClient, journeyKey, type JourneyCommand, type JourneyOutline, type JourneyCard, type JourneyMessage } from './journey-client';
import './planning-journey.css';
import { MarkdownMessage } from '../../../../packages/core-ui/frontend/src/index.ts';
import { PlanningQuestionCard } from './PlanningQuestionCard';
import { JourneyChangeReview } from './JourneyChangeReview';
import { CardModelingEntry } from './CardModelingEntry';

const architectureOptions = [
  {id:'object-component' as const,title:'对象／组件式',plain:'玩家、道具和场景对象各自管理行为，像搭积木一样逐步扩展。',
    tradeoff:'适合快速开始和直观调试；项目变大后要持续整理对象之间的关系。'},
  {id:'ecs' as const,title:'ECS · Miniplex',plain:'数据放在组件里，移动、收集、计分等规则由独立系统批量更新。',
    tradeoff:'适合大量同类实体和组合玩法；需要理解实体、组件和系统的分工。'},
];

type SharedProjectMemory = { project_title: string; experience: string; core_loop: string; scope: string;
  technical_plan: string; active_card: string };
type ModelBuildInput = { projectId:string;cardId:string;sessionId:string;triggerMessageId:string;
  modelingBlock:string;transcript:{role:string;text:string}[] };
type ModelBuildResult = {version:number;reused:boolean};
export type WorldCreationMode = 'model' | 'environment' | null;

export function WorldCreationActions({mode, busy, memoryLabel, onNewModel, onEnvironment}: {
  mode: WorldCreationMode; busy: boolean; memoryLabel: string;
  onNewModel: () => void; onEnvironment: () => void;
}) {
  return <section className="journey-creation-shortcuts"><nav className="journey-conversation-modes" aria-label="3D 世界制作方式">
    <button type="button" aria-pressed={mode === 'model'} disabled={busy} onClick={onNewModel}>＋ 新建模型</button>
    <button type="button" aria-pressed={mode === 'environment'} disabled={busy} onClick={onEnvironment}>搭建世界</button>
  </nav><small className="journey-shared-memory">公共上下文 · {memoryLabel}</small></section>;
}

export type JourneySurfaceRequest = { surface: 'modeling' | 'environment'; hosted: boolean; revision: number;
  action?: {id:string;type:'new-asset';source:'import'|'create'} };

export function ExistingProjectAdoptionNotice({fallback, onOpenProjects}:{fallback:ReactNode;onOpenProjects:()=>void}) {
  return <div className="journey-legacy"><div className="journey-start" role="status">
    <strong>这个副本已登记，尚未采用为可开发工程</strong>
    <span>SceneOps 不会自动提交、重建或复制其中的源码。已有工程采用流程将在下一里程碑接通。</span>
    <button onClick={onOpenProjects}>查看项目身份</button>
  </div>{fallback}</div>;
}

type Props = { projectId: string | null; fallback: ReactNode; modelPicker: (busy: boolean) => ReactNode;
  onDirtyChange?: (dirty: boolean) => void; onOpenProjects: () => void;
  surfaceRequest?: JourneySurfaceRequest | null;
  onOpenSurface?: (surface: JourneySurfaceRequest['surface']) => void;
  onSurfaceActionHandled?: (id:string) => void;
  onCloseSurfaces?: () => void;
  development?: { prepare: (projectId: string, cardId: string, goal: string,
      options: { allowGameExecution: boolean; allowDependencyInstall: boolean }) => Promise<void>;
    renderTasks: (projectId: string, cardId?: string, onContinue?: () => void) => ReactNode };
  assets?: { render: (input: {projectId:string;cardId:string;source:'import'|'create';sessionId:string;
    messages:{id:string;role:string;text:string;replyTo?:string;modelingBlock?:string}[]; observeConversation?: boolean;
    onCreateAnother:()=>void;onOpenEnvironment:()=>void}) => ReactNode;
    build?: (input:ModelBuildInput) => Promise<ModelBuildResult> };
  environment?: { render: (input:{projectId:string;aiBusy:boolean;onCreateAsset:(source:'import'|'create')=>void}) => ReactNode;
    read: (projectId:string) => Promise<{messages:JourneyMessage[]}>;
    build: (input:{projectId:string;text:string;requestId:string;retryFailed:boolean;sharedMemory:SharedProjectMemory}) =>
      Promise<{summary:string;provider:string;model:string;messages:JourneyMessage[]}> } };

export function PlanningJourneyGate(props: Props) {
  const folders = useQuery({ queryKey: ['workspace-folder-projects'], queryFn: () => workspaceClient.folderProjects(), retry: false });
  if (folders.isPending) return <p role="status">读取项目入口…</p>;
  if (folders.error) return <p role="alert">{folders.error.message} <button onClick={() => void folders.refetch()}>重试</button></p>;
  const bound = folders.data?.projects.find(project => project.project_id === props.projectId);
  if (bound?.project_kind === 'existing_unadopted') return <ExistingProjectAdoptionNotice
    fallback={props.fallback} onOpenProjects={props.onOpenProjects} />;
  if (bound) return <PlanningJourneyChat key={bound.project_id} {...props} projectId={bound.project_id} />;
  return <div className="journey-legacy">{!props.projectId && <div className="journey-start"><strong>从一个文件夹开始你的游戏</strong>
    <span>选择文件夹，和 AI 聊 idea，再一起对齐策划。</span><button onClick={props.onOpenProjects}>选择文件夹 · 单人协作</button></div>}{props.fallback}</div>;
}

function PlanningJourneyChat({ projectId, modelPicker, onDirtyChange, onOpenProjects, development, assets, environment,
  surfaceRequest, onOpenSurface, onSurfaceActionHandled, onCloseSurfaces }: Props & { projectId: string }) {
  const cache = useQueryClient();
  const query = useQuery({ queryKey: journeyKey(projectId), queryFn: ({ signal }) => journeyClient.get(projectId, signal), retry: false });
  const [draft, setDraft] = useState('');
  const [initialized, setInitialized] = useState(false);
  const [outgoing, setOutgoing] = useState('');
  const [notice, setNotice] = useState('');
  const [outline, setOutline] = useState<JourneyOutline | null>(null);
  const [cards, setCards] = useState<JourneyCard[]>([]);
  const [editing, setEditing] = useState<'outline' | 'cards' | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [workMode, setWorkMode] = useState<'discuss' | 'develop'>('discuss');
  const [allowGameExecution, setAllowGameExecution] = useState(true);
  const [allowDependencyInstall, setAllowDependencyInstall] = useState(true);
  const [previewOpen, setPreviewOpen] = useState(true);
  const [environmentOpen, setEnvironmentOpen] = useState(false);
  const [environmentTurns, setEnvironmentTurns] = useState<JourneyMessage[]>([]);
  const [environmentFailed, setEnvironmentFailed] = useState<{requestId:string;text:string;sharedMemory:SharedProjectMemory}|null>(null);
  const [builtModel, setBuiltModel] = useState<{sessionId:string;triggerMessageId:string;version:number}|null>(null);
  const environmentConversationKey = ['journey-environment-conversation', projectId] as const;
  const environmentConversation = useQuery({queryKey:environmentConversationKey,
    queryFn:() => environment!.read(projectId), enabled:environmentOpen && !!environment, retry:false});
  const prepareDevelopment = useMutation({
    mutationFn: ({ goal, cardId }: { goal: string; cardId: string }) => {
      if (!development) throw new Error('当前宿主没有连接分支开发服务。');
      return development.prepare(projectId, cardId, goal, {
        allowGameExecution, allowDependencyInstall: allowGameExecution && allowDependencyInstall,
      });
    },
    onSuccess: async (_task, variables) => {
      setDraft(current => current.trim() === variables.goal ? '' : current);
    },
    onError: error => setNotice(error.message),
  });
  const environmentBuild = useMutation({
    mutationFn: ({text,requestId,retryFailed,sharedMemory}:{text:string;requestId:string;retryFailed:boolean;sharedMemory:SharedProjectMemory}) => {
      if (!environment) throw new Error('当前宿主没有连接环境场景服务。');
      return environment.build({projectId,text,requestId,retryFailed,sharedMemory});
    },
    onSuccess: (result, variables) => {
      setEnvironmentTurns(result.messages);
      cache.setQueryData(environmentConversationKey, {messages:result.messages});
      setOutgoing(''); setEnvironmentFailed(null); setNotice('');
    },
    onError: (error, variables) => {
      setOutgoing(''); setDraft(current => current || variables.text);
      setEnvironmentFailed({requestId:variables.requestId,text:variables.text,sharedMemory:variables.sharedMemory});
      setNotice(error.message);
    },
  });
  const modelBuild = useMutation({
    mutationFn: (input:ModelBuildInput) => {
      if (!assets?.build) throw new Error('当前宿主没有连接模型生成服务。');
      return assets.build(input);
    },
    onSuccess: (result, variables) => {
      setBuiltModel({sessionId:variables.sessionId,triggerMessageId:variables.triggerMessageId,version:result.version});
      setEnvironmentOpen(false); setEnvironmentTurns([]); setEnvironmentFailed(null); setPreviewOpen(true); setNotice('');
      onOpenSurface?.('environment');
    },
    onError: error => setNotice(error.message),
  });
  const [liveText, setLiveText] = useState('');
  const [liveReasoning, setLiveReasoning] = useState('');
  const [liveStatus, setLiveStatus] = useState('');
  const input = useRef<HTMLTextAreaElement>(null);
  const controller = useRef<AbortController | null>(null);
  const editBase = useRef<number | null>(null);
  const transcript = useRef<HTMLDivElement>(null);
  const handledSurfaceAction = useRef<string | null>(null);
  const mutation = useMutation({
    mutationFn: (input: Pick<JourneyCommand, 'operation'> & Partial<JourneyCommand>) => {
      if (!query.data) throw new Error('请先读取策划。');
      controller.current = new AbortController();
      const body: JourneyCommand = { request_id: crypto.randomUUID(), expected_revision:
        ['save_outline', 'save_cards'].includes(input.operation) ? editBase.current ?? query.data.revision : query.data.revision,
        text: '', accept_assumptions: false, ...input };
      if (['message', 'start_grill', 'generate_outline', 'recommend_architecture', 'generate_cards'].includes(input.operation)) {
        setLiveText(''); setLiveReasoning(''); setLiveStatus('正在连接…');
        return journeyClient.stream(projectId, body, event => {
          if (event.type === 'text_delta') { setLiveText(text => text + event.text); setLiveStatus('正在回复'); }
          if (event.type === 'reasoning_delta') { setLiveReasoning(text => text + event.text); setLiveStatus('正在思考'); }
          if (event.type === 'status') setLiveStatus(event.text);
        }, controller.current.signal);
      }
      return journeyClient.command(projectId, body, controller.current.signal);
    },
    onSuccess: (state, input) => {
      cache.setQueryData(journeyKey(projectId), state);
      setLiveText(''); setLiveStatus('');
      if (input.operation === 'message') { setOutgoing(''); setDraft(current => current === input.text ? '' : current); }
      if (['save_outline', 'save_cards', 'generate_outline', 'generate_cards'].includes(input.operation)) { setEditing(null); editBase.current = null; }
      if (input.operation === 'select_card' && input.card_id === 'world-3d') onOpenSurface?.('environment');
      if (input.operation === 'clear_card' || (input.operation === 'select_card' && input.card_id !== 'world-3d')) onCloseSurfaces?.();
    },
    onError: (error, input) => { setNotice(error.name === 'AbortError' ? '已停止。未完成的内容没有作为正式回复保存。' : error.message); setLiveStatus(''); if (input.operation === 'message') { setOutgoing(''); setDraft(current => current || input.text || ''); } },
    onSettled: () => { controller.current = null; void cache.invalidateQueries({ queryKey: journeyKey(projectId) }); },
  });
  const state = query.data;
  const modeling = state?.modeling_sessions?.find(item => item.id === state.active_modeling_id);
  const storedDraft = environmentOpen ? '' : modeling ? modeling.composer_draft : state?.composer_draft;
  const activeCardId = state?.active_card_id ?? null;
  const environmentAvailable = !!environment;
  const draftScope = useRef<string | null>(null);
  const busy = mutation.isPending || prepareDevelopment.isPending || environmentBuild.isPending || modelBuild.isPending;
  const replying = environmentBuild.isPending || (mutation.isPending && ['message', 'start_grill', 'generate_outline', 'recommend_architecture', 'generate_cards'].includes(mutation.variables?.operation ?? ''));
  useEffect(() => {
    if (!state) return;
    const scope = environmentOpen ? 'environment' : modeling?.id ?? 'main';
    if (draftScope.current !== scope) {
      draftScope.current = scope; setDraft(storedDraft ?? ''); setInitialized(true);
      setLiveText(''); setLiveReasoning(''); setOutgoing('');
    }
  }, [state, modeling?.id, storedDraft, environmentOpen]);
  useEffect(() => { setWorkMode('discuss'); }, [state?.active_card_id, modeling?.id]);
  useEffect(() => { if (modeling || environmentOpen) setPreviewOpen(true); }, [modeling?.id, environmentOpen]);
  useEffect(() => {
    setEnvironmentTurns([]);
    setEnvironmentFailed(null);
    if (activeCardId === 'world-3d' && environmentAvailable && !modeling) {
      setEnvironmentOpen(true);
      setPreviewOpen(true);
      onOpenSurface?.('environment');
      return;
    }
    setEnvironmentOpen(false);
  }, [activeCardId, environmentAvailable, modeling?.id]);
  useEffect(() => {
    if (!surfaceRequest) return;
    const current = query.data;
    if (current?.active_card_id !== 'world-3d') {
      setEnvironmentOpen(false);
      setEnvironmentTurns([]);
      setEnvironmentFailed(null);
      if (surfaceRequest.action && handledSurfaceAction.current !== surfaceRequest.action.id) {
        handledSurfaceAction.current = surfaceRequest.action.id;
        onSurfaceActionHandled?.(surfaceRequest.action.id);
        setNotice('请先进入“3D 世界”制作卡片。');
      }
      return;
    }
    setPreviewOpen(true);
    if (!surfaceRequest.action || handledSurfaceAction.current === surfaceRequest.action.id || mutation.isPending) return;
    handledSurfaceAction.current = surfaceRequest.action.id;
    onSurfaceActionHandled?.(surfaceRequest.action.id);
    setEnvironmentOpen(false);
    setEnvironmentTurns([]);
    setEnvironmentFailed(null);
    mutation.mutate({operation:'new_modeling', card_id:current.active_card_id,
      model_source:surfaceRequest.action.source, context_draft:''});
  }, [surfaceRequest?.revision, query.data?.revision, mutation.isPending]);
  useEffect(() => { if (state && !editing) { setOutline(state.outline ?? null); setCards(state.cards ?? []); setAccepted(false); } }, [state, editing]);
  useEffect(() => {
    if (environmentOpen || !state || !initialized || busy || notice || draftScope.current !== (modeling?.id ?? 'main') || draft === storedDraft) return;
    const timer = setTimeout(() => mutation.mutate({ operation: 'save_draft', text: draft }), 900);
    return () => clearTimeout(timer);
  }, [draft, storedDraft, modeling?.id, initialized, busy, notice, environmentOpen]);
  useEffect(() => {
    if (!editing || busy || notice) return;
    const timer = setTimeout(() => {
      if (editing === 'outline' && outline && Object.values(outline).every(value => typeof value !== 'string' || value.trim())) mutation.mutate({ operation: 'save_outline', outline });
      if (editing === 'cards' && cards.length && cards.every(card => card.title.trim() && card.description.trim() && card.acceptance.trim())) mutation.mutate({ operation: 'save_cards', cards });
    }, 1000);
    return () => clearTimeout(timer);
  }, [editing, outline, cards, busy, notice]);
  const dirty = !!editing || busy || (!!state && draft !== storedDraft);
  useEffect(() => { onDirtyChange?.(dirty); }, [dirty, onDirtyChange]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (dirty) { event.preventDefault(); event.returnValue = ''; } };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);
  useEffect(() => () => { controller.current?.abort(); onDirtyChange?.(false); }, []);
  useEffect(() => {
    const node = transcript.current;
    if (node && node.scrollHeight - node.scrollTop - node.clientHeight < 180) node.scrollTop = node.scrollHeight;
  }, [state?.messages?.length, modeling?.messages?.length, environmentTurns.length, outgoing, liveText, liveStatus]);
  useEffect(() => {
    const node = transcript.current;
    if (!node || (!modeling?.id && !environmentOpen)) return;
    const frame = requestAnimationFrame(() => { node.scrollTop = node.scrollHeight; });
    return () => cancelAnimationFrame(frame);
  }, [modeling?.id, environmentOpen]);
  useEffect(() => { if (input.current) { input.current.style.height = '0px'; input.current.style.height = `${Math.min(144, Math.max(40, input.current.scrollHeight))}px`; } }, [draft]);
  if (query.isPending) return <p role="status">恢复策划进度…</p>;
  if (query.error || !state) return <p role="alert">{query.error?.message ?? '策划不存在'} <button onClick={() => void query.refetch()}>重新读取</button></p>;
  const act = (operation: JourneyCommand['operation'], extra: Partial<JourneyCommand> = {}) => {
    setNotice(''); mutation.mutate({ operation, ...extra,
      ...(['select_card', 'clear_card', 'choose_model_source', 'new_modeling', 'open_modeling', 'close_modeling'].includes(operation) ? { context_draft: draft } : {}) });
  };
  const stages = [['idea', '聊 idea'], ['grill', '对齐细节'], ['outline', '策划大纲'], ['stack', '技术路线'], ['cards', '制作卡片']];
  const focusedMessages = environmentOpen ? (environmentTurns.length ? environmentTurns : environmentConversation.data?.messages ?? [])
    : modeling ? modeling.messages ?? [] : [];
  const messages = activeCardId ? focusedMessages : state.messages ?? [];
  const modelMessages = modeling?.messages ?? [];
  const latestModelUser = modeling?.source === 'create'
    ? [...modelMessages].reverse().find(message => message.role === 'user' && message.text.trim())
    : undefined;
  const builtCurrentVersion = builtModel && builtModel.sessionId === modeling?.id && builtModel.triggerMessageId === latestModelUser?.id
    ? builtModel.version : null;
  const versions = state.versions ?? [];
  const activeCard = cards.find(card => card.id === state.active_card_id);
  const activeBranch = state.card_branches?.find(branch => branch.card_id === state.active_card_id);
  const technicalPlan = state.technical_plan;
  const recommendation = state.architecture_recommendation;
  const sharedMemory: SharedProjectMemory = {
    project_title:outline?.title ?? '', experience:outline?.experience ?? '', core_loop:outline?.core_loop ?? '',
    scope:outline?.scope ?? '',
    technical_plan:technicalPlan ? `${technicalPlan.engine} · ${technicalPlan.architecture_label} · ${technicalPlan.rationale}` : '',
    active_card:activeCard ? `${activeCard.title}：${activeCard.description}` : '',
  };
  const sharedMemoryLabel = [versions.length ? `策划 v${versions.at(-1)?.number}` : outline?.title,
    technicalPlan?.architecture_label, activeCard?.title].filter(Boolean).join(' · ');
  const creationMode: WorldCreationMode = environmentOpen ? 'environment' : modeling?.source === 'create' ? 'model' : null;
  const workspaceDescription = activeCard?.id === 'world-3d'
    ? '场景、资产库、模型新建与导入、归一化、空间点位和摆放都在这个工作区完成。'
    : activeCard?.id === 'core-gameplay'
      ? '在同一个上下文继续讨论并实现控制、战斗、怪物、武器、波次和经验循环。'
      : activeCard?.id === 'growth-feedback'
        ? '在同一个上下文继续完成成长选择、HUD、视觉反馈、音效和特效。'
        : activeCard?.id === 'demo-delivery'
          ? '在同一个上下文串联单局、性能检查、构建与交付，试玩仍由你发起。'
          : '';
  const beginEdit = (kind: 'outline' | 'cards') => { if (!editing) editBase.current = state.revision; setEditing(kind); };
  const latestQuestion = [...messages].reverse().find(message => message.question && !messages.some(answer => answer.reply_to === message.id));
  const send = () => {
    if (!draft.trim() || busy) return;
    const text = draft.trim();
    if (environmentOpen) {
      setOutgoing(text); setDraft(''); setNotice('');
      environmentBuild.mutate({text,requestId:crypto.randomUUID(),retryFailed:false,sharedMemory});
      return;
    }
    if (activeCard && !modeling && workMode === 'develop') {
      if (text.length > 8000) { setNotice('开发目标最多 8000 字符。'); return; }
      setNotice('');
      prepareDevelopment.mutate({ goal: text, cardId: activeCard.id });
      return;
    }
    setOutgoing(text); setDraft(''); act('message', { text, ...(latestQuestion ? { question_message_id: latestQuestion.id } : {}) });
  };
  const createAnotherModel = () => {
    if (!activeCard) return;
    setEnvironmentOpen(false); setEnvironmentTurns([]); setEnvironmentFailed(null);
    act('new_modeling', {card_id:activeCard.id,model_source:'create'});
  };
  const createAsset = (source: 'import'|'create') => {
    if (!activeCard) return;
    setEnvironmentOpen(false); setEnvironmentTurns([]); setEnvironmentFailed(null);
    act('new_modeling', {card_id:activeCard.id,model_source:source,context_draft:''});
  };
  const openEnvironment = () => {
    if (!environment) { setNotice('当前宿主没有连接环境场景服务。'); return; }
    setEnvironmentOpen(true); setEnvironmentTurns([]); setEnvironmentFailed(null); setPreviewOpen(true);
    onOpenSurface?.('environment');
    if (modeling) act('close_modeling');
  };
  const confirmAndBuildModel = () => {
    if (!modeling || modeling.source !== 'create' || !latestModelUser) return;
    const triggerIndex = modelMessages.findIndex(message => message.id === latestModelUser.id);
    modelBuild.mutate({projectId,cardId:modeling.card_id,sessionId:modeling.id,
      triggerMessageId:latestModelUser.id,modelingBlock:latestModelUser.modeling_block ?? 'refinement',
      transcript:modelMessages.slice(0,triggerIndex + 1)
        .filter(message => (message.role === 'user' || message.role === 'assistant') && message.text.trim())
        .map(message => ({role:message.role,text:message.text}))});
  };
  const beginNewModel = () => {
    if (!activeCard) return;
    setEnvironmentOpen(false); setEnvironmentTurns([]); setEnvironmentFailed(null); setNotice('');
    onOpenSurface?.('environment');
    act('new_modeling', {card_id:activeCard.id,model_source:'create'});
  };
  const assetHostedExternally = !!modeling && surfaceRequest?.hosted === true && surfaceRequest.surface === 'modeling';
  const environmentHostedExternally = environmentOpen && surfaceRequest?.hosted === true && surfaceRequest.surface === 'environment';
  const assetPreview = modeling && !onOpenSurface && !assetHostedExternally && assets?.render({projectId,cardId:modeling.card_id,source:modeling.source,
    sessionId:modeling.id,messages:(modeling.messages ?? []).map(message=>({id:message.id,role:message.role,text:message.text,
      ...(message.reply_to ? {replyTo:message.reply_to} : {}),
      ...(message.modeling_block ? {modelingBlock:message.modeling_block} : {})})),
      onCreateAnother:createAnotherModel,onOpenEnvironment:openEnvironment});
  const environmentPreview = environmentOpen && !onOpenSurface && !environmentHostedExternally && environment?.render({projectId,aiBusy:environmentBuild.isPending,onCreateAsset:createAsset});
  const sidePreview = environmentPreview || assetPreview;
  return <section className={`planning-journey${activeCard ? ' has-card-workspace' : ''}${activeCard?.id === 'world-3d' ? ' world-3d-workspace' : ''}${sidePreview && previewOpen ? ' has-model-preview' : ''}`} aria-label={activeCard ? `${activeCard.title}工作流` : '单人策划工作流'}>
    <header><div><strong>{activeCard?.title ?? '协作'}</strong><small>{activeCard ? '独立工作流' : `${stages.find(([id]) => id === state.stage)?.[1]}${versions.length ? ` · v${versions.length}` : ''}`}</small></div><button onClick={onOpenProjects}>文件夹</button></header>
    <div className="journey-scroll" ref={transcript}>
      {activeCard && <section className="journey-card-workspace-header">
        <button type="button" disabled={busy} onClick={() => act('clear_card')}>← 制作卡片</button>
        <div><strong>{activeCard.title}</strong><span>{workspaceDescription}</span></div>
        <nav aria-label="工作流操作">
          {activeCard.id === 'world-3d' && onOpenSurface && !surfaceRequest?.hosted && <button type="button" onClick={() => onOpenSurface('environment')}>打开工作区</button>}
          {activeBranch && <details><summary>Git 分支</summary><p>{activeBranch.branch}</p><p>{activeBranch.worktree_path}</p>
            <small>不会自动提交或合并。</small></details>}
        </nav>
      </section>}
      {activeCard && activeCard.id !== 'world-3d' && !environmentOpen && <CardModelingEntry state={state} busy={busy || !!editing} onCommand={act} onOpenEnvironment={openEnvironment} />}
      {activeCard && !technicalPlan && <p role="status" className="journey-architecture-missing">这个旧项目还没有明确游戏代码架构。返回制作卡片后选择架构，已有代码不会被重建或覆盖。</p>}
      {!messages.length && !outgoing && !modeling && !environmentOpen && !activeCard && <div className="journey-empty"><h2>你想做一个什么样的游戏？</h2><p>先聊 idea，等你说完，我们再一起对齐细节。</p></div>}
      {messages.map(message => <article key={message.id} className={`journey-message ${message.role}`}>
        {message.role === 'user' ? <p>{message.text}</p> : <MarkdownMessage text={message.text} />}
        {message.question && <PlanningQuestionCard question={message.question} disabled={busy} answered={messages.some(answer => answer.reply_to === message.id)}
          onAnswer={index => { setOutgoing(message.question!.options[index].label); act('message', { question_message_id: message.id, option_index: index }); }}
          onCustom={() => input.current?.focus()} />}
      </article>)}
      {outgoing && <article className="journey-message user"><small>你 · 等待回复</small><p>{outgoing}</p></article>}
      {(replying || liveText || liveReasoning) && <article className="journey-live" aria-live="polite">
        {replying && <div className="journey-working"><span className="journey-working-dot" />{environmentBuild.isPending ? 'AI 正在安排资产并生成场景版本…' : liveStatus || '正在生成…'}</div>}
        {liveReasoning && <details className="journey-reasoning"><summary>思考过程 <small>提供方返回</small></summary><MarkdownMessage text={liveReasoning} /></details>}
        {liveText && <MarkdownMessage text={liveText} />}
      </article>}
      {!activeCard && !modeling && !environmentOpen && <><div className="journey-actions">
        {state.stage === 'idea' && !!messages.length && <button disabled={busy} onClick={() => act('start_grill')}>我说完了 · 开始对齐</button>}
        {state.stage === 'grill' && <><p>grill-me：一次一个问题，逐步确认设计。</p><button disabled={busy} onClick={() => act('generate_outline')}>细节已对齐 · 生成大纲</button></>}
      </div>
      {(state.changes ?? []).filter(change => change.status === 'pending').map(change => <JourneyChangeReview key={change.id} change={change} disabled={busy || !!editing}
        onResolve={accept => act(accept ? 'accept_change' : 'reject_change', { change_id: change.id })} />)}
      {outline && <details className="journey-document journey-attachment"><summary>策划大纲 · {outline.title} <small>{editing ? '未保存修改' : '查看与确认'}</small></summary>
        {(['title', 'experience', 'core_loop', 'scope', 'acceptance'] as const).map((field, index) => <label key={field}>{['标题', '目标体验', '核心循环', '范围与边界', '验收条件'][index]}<textarea value={outline[field]} disabled={busy || editing === 'cards'} onChange={event => { beginEdit('outline'); setOutline({ ...outline, [field]: event.target.value }); }} /></label>)}
        {!!outline.assumptions?.length && <div><strong>待确认假设</strong><ul>{outline.assumptions.map((item, i) => <li key={i}>{item}</li>)}</ul><label><input type="checkbox" checked={accepted} onChange={e => setAccepted(e.target.checked)} />我已审阅并接受这些假设</label></div>}
        <div className="journey-actions"><button disabled={busy || editing !== 'outline'} onClick={() => act('save_outline', { outline })}>保存大纲修改</button>
          <button disabled={busy || !!editing || (!!outline.assumptions?.length && !accepted)} onClick={() => act('confirm_version', { accept_assumptions: accepted })}>确认正式版本 v{versions.length + 1}</button></div>
      </details>}
      {!technicalPlan && (state.stage === 'stack' || state.stage === 'cards') && <section className="journey-next journey-architecture">
        <header><div><strong>选择游戏工程的代码架构</strong><p>不用先懂专业名词。两种方案都会创建可运行的 Three.js 工程，后续 Agent 会沿用你的选择。</p></div>
          <button disabled={busy} onClick={() => act('recommend_architecture')}>让 AI 根据策划推荐</button></header>
        <dl className="journey-tech-targets"><div><dt>目标平台</dt><dd>浏览器 Web</dd></div><div><dt>引擎／渲染</dt><dd>Three.js</dd></div><div><dt>代码架构</dt><dd>由你选择</dd></div></dl>
        {recommendation && <section className="journey-architecture-recommendation"><small>AI 推荐</small><strong>{architectureOptions.find(item => item.id === recommendation.code_architecture)?.title}</strong>
          <p>{recommendation.rationale}</p><ul>{recommendation.tradeoffs.map(item => <li key={item}>{item}</li>)}</ul>
          <button disabled={busy} onClick={() => act('confirm_technical_plan', {code_architecture:recommendation.code_architecture,selection_method:'ai'})}>采用推荐并创建工程</button></section>}
        <div className="journey-architecture-options">{architectureOptions.map(option => <article key={option.id}>
          <strong>{option.title}</strong><p>{option.plain}</p><small>{option.tradeoff}</small>
          <button disabled={busy} onClick={() => act('confirm_technical_plan', {code_architecture:option.id,selection_method:'manual'})}>选择并创建工程</button>
        </article>)}</div>
      </section>}
      {technicalPlan && !activeCard && <details className="journey-attachment journey-technical-plan" open={!cards.length}>
        <summary>游戏技术方案 · {technicalPlan.architecture_label} <small>{technicalPlan.selection_method === 'ai' ? 'AI 推荐后选择' : '手动选择'} · 已创建</small></summary>
        <dl className="journey-tech-targets"><div><dt>目标平台</dt><dd>浏览器 Web</dd></div><div><dt>引擎／渲染</dt><dd>Three.js</dd></div><div><dt>代码架构</dt><dd>{technicalPlan.architecture_label}</dd></div></dl>
        <p>{technicalPlan.rationale}</p><p><small>工程：{technicalPlan.scaffold.root_path}</small></p>
        {technicalPlan.scaffold.initialization_status === 'generated' ? <p><code>{technicalPlan.scaffold.preview_command}</code> · <code>{technicalPlan.scaffold.build_command}</code></p> : <p>检测到已有源码，仅保存架构选择，没有重建或覆盖工程。</p>}
      </details>}
      {state.stage === 'cards' && <section className="journey-next">
        {!cards.length && <button disabled={busy || !technicalPlan} onClick={() => act('generate_cards')}>根据技术方案生成制作卡片</button>}
        {!!cards.length && <><p className="journey-card-summary">四条主制作线；具体实现留在对应工作流里，不再平铺成十几张卡。</p><section className="journey-production-cards" aria-label="制作卡片">
          {cards.map((card, index) => <article className="journey-plan-item" key={card.id} data-selected={state.active_card_id === card.id}>
            <button type="button" className="journey-card-select" aria-pressed={state.active_card_id === card.id} disabled={busy || !!editing}
              onClick={() => act('select_card', { card_id: card.id })}>
              <span className="journey-card-heading"><small>{String(index + 1).padStart(2, '0')}</small><strong>{card.title}</strong></span>
              <span className="journey-card-description">{card.description}</span>
              <span className="journey-card-entry">{state.active_card_id === card.id ? '当前分支' : state.card_branches?.some(branch => branch.card_id === card.id) ? '进入 Git 分支 →' : '创建 Git 分支并进入 →'}</span>
            </button><details><summary>完成条件与依赖</summary><MarkdownMessage text={card.acceptance} />
              {!!card.dependencies?.length && <p>依赖：{card.dependencies.map(id => cards.find(item => item.id === id)?.title ?? id).join('、')}</p>}</details></article>)}
        </section></>}
      </section>}
      {!!versions.length && <details className="journey-attachment"><summary>版本记录 · {versions.length}</summary>{versions.map(version => {
        const git = state.git_versions?.find(item => item.number === version.number);
        return <p key={version.number}>v{version.number} · {version.outline.title} · {new Date(version.confirmed_at).toLocaleString()}<br/>
          <small>{git ? `${git.tag} · ${git.commit.slice(0, 10)}` : '旧版记录尚未建立 Git 提交'}</small></p>;
      })}{!state.git_versions?.length && <button type="button" disabled={busy} onClick={() => act('enable_git')}>将已确认版本纳入 Git</button>}</details>}
      {development?.renderTasks(projectId)}
      </>}
      {activeCard && development?.renderTasks(projectId, activeCard.id, () => {
        setWorkMode('develop');
        requestAnimationFrame(() => input.current?.focus());
      })}
    </div>
    {sidePreview && <aside className="journey-model-preview-pane" data-open={previewOpen} aria-label={environmentOpen ? '环境场景预览' : '实时模型预览'}>
      <header><div><strong>{environmentOpen ? '3D 世界' : modeling?.source === 'create' ? '模型生成' : '模型导入'}</strong><small>Three.js</small></div>
        <span className="journey-preview-actions"><button type="button" aria-expanded={previewOpen} onClick={() => setPreviewOpen(value => !value)}>{previewOpen ? '收起' : '展开'}</button></span></header>
      <div className="journey-model-preview-body" hidden={!previewOpen}>{sidePreview}</div>
    </aside>}
    {notice && <p role="alert" className="journey-notice">{notice} {environmentFailed && <button onClick={() => {setOutgoing(environmentFailed.text);setDraft('');setNotice('');environmentBuild.mutate({...environmentFailed,retryFailed:true});}}>重试本次 AI 搭建</button>} <button onClick={() => { void query.refetch(); }}>重新读取（保留本地修改）</button>
      {editing && <button onClick={async () => { if (window.confirm('放弃未保存的文档修改，重新读取已保存版本？')) { await query.refetch(); setEditing(null); editBase.current = null; setNotice(''); } }}>放弃本地文档修改</button>}
      {!editing && <button onClick={() => setNotice('')}>关闭提示 / 允许重试</button>}</p>}
    {activeCard && !modeling && !environmentOpen && workMode === 'develop' && <section className="journey-development-permissions" aria-label="开发执行范围">
      <label><input type="checkbox" checked={allowGameExecution} disabled={busy} onChange={event => {
        setAllowGameExecution(event.target.checked);
        if (!event.target.checked) setAllowDependencyInstall(false);
      }} />允许 Agent 执行类型检查、构建和本地预览</label>
      <label><input type="checkbox" checked={allowDependencyInstall} disabled={busy || !allowGameExecution}
        onChange={event => setAllowDependencyInstall(event.target.checked)} />允许在当前游戏工程内准备依赖</label>
      <small>发送后仍会先展示具体授权卡；取消运行权限时保留原有的仅源码修改流程。</small>
    </section>}
    {activeCard?.id === 'world-3d' && <WorldCreationActions mode={creationMode} busy={busy}
      memoryLabel={sharedMemoryLabel || '当前项目'} onNewModel={beginNewModel} onEnvironment={openEnvironment} />}
    <form className="unified-ai-composer journey-composer" onSubmit={event => { event.preventDefault(); send(); }}>
      <textarea ref={input} aria-label={environmentOpen ? '3D 世界对话' : modeling ? '模型生成对话' : activeCard ? `${activeCard.title}对话` : '策划对话'} disabled={!environmentOpen && modeling?.source === 'import'} placeholder={environmentOpen ? '描述要构建的世界、场景或资产；右侧可以直接新建、导入和摆放…' : modeling ? modeling.source === 'create' ? '描述模型、风格、尺寸和用途；也可以在上方加参考图…' : '请在右侧选择 GLB 或 FBX 文件' : activeCard ? workMode === 'develop' ? `让 Agent 实现「${activeCard.title}」的什么内容？` : `继续讨论「${activeCard.title}」…` : state.stage === 'idea' ? '聊聊你的 idea…' : '补充想法，或告诉我大纲和卡片要怎么改…'} value={draft} rows={1} onChange={e => setDraft(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(); } }} />
      <div className="journey-composer-tools">{modelPicker(replying || prepareDevelopment.isPending || modelBuild.isPending)}
        {activeCard && !modeling && !environmentOpen && <select className="journey-work-mode" aria-label="分支协作方式" value={workMode} disabled={busy || !technicalPlan} onChange={event => setWorkMode(event.target.value as 'discuss' | 'develop')}><option value="discuss">卡片协作</option><option value="develop">高级 · 代码开发授权</option></select>}
        {latestModelUser && assets?.build && <button className="journey-confirm-model" type="button" disabled={busy || builtCurrentVersion !== null} onClick={confirmAndBuildModel}>{modelBuild.isPending ? '正在建模…' : builtCurrentVersion !== null ? `已生成 v${builtCurrentVersion}` : '确认并建模'}</button>}
        <span className="journey-draft-status">{modelBuild.isPending ? 'AI 生成方案，Blender 输出模型…' : prepareDevelopment.isPending ? '准备授权…' : !replying && (dirty ? '保存中' : '')}</span>
        {replying ? <button className="journey-submit" type="button" aria-label="停止回复" title="停止回复" onClick={() => controller.current?.abort()}>■</button> : <button className="journey-submit" type="submit" aria-label={activeCard && workMode === 'develop' ? '准备开发授权' : '发送'} title={activeCard && workMode === 'develop' ? '准备开发授权，不立即执行' : '发送'} disabled={busy || !draft.trim()}>↑</button>}</div>
    </form><small className="journey-cost" title={state.cost_notice}>{environmentOpen ? '3D 世界 · 场景与资产共用当前上下文' : modeling ? modeling.source === 'create' ? '模型生成 · 每轮保留版本' : '模型导入 · 原件保留' : activeCard && workMode === 'develop' ? '确认后写入当前工作流分支 · 不自动合并' : activeCard ? `${activeCard.title} · 独立工作流` : '单人协作 · 仅策划'} · 费用未知</small>
  </section>;
}
