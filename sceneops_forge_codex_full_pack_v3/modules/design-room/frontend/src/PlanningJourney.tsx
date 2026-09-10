import {ProductionDomains} from './ProductionDomains.tsx';
import { DomainConversationTarget, DomainConversationTurns, useDomainConversation, type DomainConversationPort } from '@sceneops/core-ui';
import { ExperiencePanel, ExperienceReferences, MemoryMessage, ProductionPreparationSummary } from '../../../ai-agent-runtime/frontend/src/index.ts';
import { JourneyComposerIcon } from './JourneyComposerIcon';
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { useIsMutating, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { workspaceClient } from '../../../../packages/workspace-client/frontend/src/index.ts';
import { journeyClient, journeyKey, type JourneyCommand, type JourneyOutline, type JourneyCard, type JourneyMessage } from './journey-client';
import './planning-journey.css';
import './card-workspace.css';
import { MarkdownMessage, ComposerMenu, ChatComposer } from '../../../../packages/core-ui/frontend/src/index.ts';
import { PlanningQuestionCard } from './PlanningQuestionCard';
import { JourneyChangeReview } from './JourneyChangeReview';
import { MessageActions } from './MessageActions';
import { OrganizeProductionButton } from './OrganizeProductionButton';
import { DemoExecutionRequest } from './DemoExecutionRequest';

const architectureOptions = [
  {id:'object-component' as const,title:'对象／组件式',plain:'玩家、道具和场景对象各自管理行为，像搭积木一样逐步扩展。',
    tradeoff:'适合快速开始和直观调试；项目变大后要持续整理对象之间的关系。'},
  {id:'ecs' as const,title:'ECS · Miniplex',plain:'数据放在组件里，移动、收集、计分等规则由独立系统批量更新。',
    tradeoff:'适合大量同类实体和组合玩法；需要理解实体、组件和系统的分工。'},
];

type SharedProjectMemory = { project_title: string; experience: string; core_loop: string; scope: string;
  technical_plan: string; active_card: string };
type ModelBuildInput = { projectId:string;cardId:string;sessionId:string;triggerMessageId:string;
  modelingBlock:string;transcript:{role:string;text:string}[];retryFailed:boolean };
type ModelBuildResult = {version:number;reused:boolean};
type ProductionInput = {path:string;name:string;kind:string;size_bytes:number};
export type WorldCreationMode = 'model' | 'environment' | null;

export function WorldCreationActions({mode, busy, onNewModel, onEnvironment}: {
  mode: WorldCreationMode; busy: boolean;
  onNewModel: () => void; onEnvironment: () => void;
}) {
  return <section className="journey-creation-shortcuts"><nav className="journey-conversation-modes" aria-label="3D 世界制作方式">
    <button type="button" aria-pressed={mode === 'model'} disabled={busy} onClick={onNewModel}>＋ 新建模型</button>
    <button type="button" aria-pressed={mode === 'environment'} disabled={busy} onClick={onEnvironment}>搭建世界</button>
  </nav></section>;
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

type Props = { domainConversation?: DomainConversationPort | null; domainHistory?: DomainConversationPort['history']; projectId: string | null; fallback: ReactNode; modelPicker: (busy: boolean) => ReactNode;
  onDirtyChange?: (dirty: boolean) => void; onOpenProjects: () => void;
  onOpenExport?: () => void; onOpenProductionTool?: (id:string) => void;
  exportDevelopmentRequest?: {id:string;projectId:string;text:string} | null;
  onExportDevelopmentAccepted?: () => void;
  surfaceRequest?: JourneySurfaceRequest | null;
  onOpenSurface?: (surface: JourneySurfaceRequest['surface']) => void;
  onSurfaceActionHandled?: (id:string) => void;
  onCloseSurfaces?: () => void;
  development?: { prepare: (projectId: string, cardId: string, goal: string,
      options: { allowGameExecution: boolean; allowDependencyInstall: boolean; allowBrowserObservation: boolean; allowBrowserInteraction: boolean;
        allowModelImageInput: boolean;
        authorizeOnSend?: boolean; includeDemoAssets?: boolean; alignmentId?: string }) => Promise<void>;
    renderSourceEditor?: (projectId: string, cardId: string, onDirtyChange: (dirty: boolean) => void) => ReactNode;
    prepareProjectDemo?: (projectId: string, directionId: string, goal: string, policy: 'ask' | 'full-access', continuation?: boolean, inputPaths?: string[], planningCardId?: string) => Promise<void>;
    uploadProjectInput?: (projectId:string, file:File) => Promise<ProductionInput>;
    cancel?: (taskId: string) => Promise<void>;
    renderProductionCard?: (projectId:string, card:JourneyCard, onRunPresence:(present:boolean,running?:{id:string;cancelRequested:boolean})=>void, conversationId:string) => ReactNode;
    renderProjectDemoTasks?: (projectId: string, onRunPresence?: (present: boolean, running?: {id: string; cancelRequested: boolean}) => void) => ReactNode;
    renderTasks: (projectId: string, cardId?: string, onRunPresence?: (present: boolean, running?: {id: string; cancelRequested: boolean}) => void,
      onContinue?: () => void, conversationId?: string) => ReactNode };
  assets?: { render: (input: {projectId:string;cardId:string;source:'import'|'create';sessionId:string;
    messages:{id:string;role:string;text:string;replyTo?:string;modelingBlock?:string}[]; observeConversation?: boolean;
    onCreateAnother:()=>void;onOpenEnvironment:()=>void}) => ReactNode;
    build?: (input:ModelBuildInput) => Promise<ModelBuildResult> };
  environment?: { render: (input:{projectId:string;aiBusy:boolean;onCreateAsset:(source:'import'|'create')=>void}) => ReactNode;
    read: (projectId:string) => Promise<{messages:JourneyMessage[]}>;
    build: (input:{projectId:string;text:string;requestId:string;retryFailed:boolean;sharedMemory:SharedProjectMemory}) =>
      Promise<{summary:string;provider:string;model:string;messages:JourneyMessage[];productionPreparation?:unknown}> } };

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

function PlanningJourneyChat({ domainHistory, domainConversation, projectId, modelPicker, onDirtyChange, onOpenProjects, development, assets, environment,
  surfaceRequest, onOpenSurface, onSurfaceActionHandled, onCloseSurfaces, onOpenExport, onOpenProductionTool,
  exportDevelopmentRequest, onExportDevelopmentAccepted }: Props & { projectId: string }) {
  const domain = useDomainConversation(domainConversation,domainHistory);
  const cache = useQueryClient();
  const organizing = useIsMutating({mutationKey:['organize-production',projectId]}) > 0;
  const query = useQuery({ queryKey: journeyKey(projectId), queryFn: ({ signal }) => journeyClient.get(projectId, signal), retry: false });
  const [draft, setDraft] = useState('');
  const [sourceDirty, setSourceDirty] = useState(false);
  const [initialized, setInitialized] = useState(false);
  const [outgoing, setOutgoing] = useState('');
  const [notice, setNotice] = useState('');
  const [outline, setOutline] = useState<JourneyOutline | null>(null);
  const [cards, setCards] = useState<JourneyCard[]>([]);
  const [editing, setEditing] = useState<'outline' | 'cards' | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [workMode, setWorkMode] = useState<'discuss' | 'develop'>('discuss');
  const [activeRun, setActiveRun] = useState<{id:string;cancelRequested:boolean} | null>(null);
  const [projectDemoPresent, setProjectDemoPresent] = useState(false);
  const [pendingProductionGoal, setPendingProductionGoal] = useState<string | null>(null);
  const [productionInputs, setProductionInputs] = useState<ProductionInput[]>([]);
  const [productionInputBusy, setProductionInputBusy] = useState(false);
  const handleProjectDemoPresence = useCallback((present:boolean, running?:{id:string;cancelRequested:boolean}) => {setProjectDemoPresent(present);setActiveRun(running ?? null);}, []);
  const handleDevelopmentPresence = useCallback((_present: boolean, running?: {id:string;cancelRequested:boolean}) => setActiveRun(running ?? null), []);
  const cancelExecution = useMutation({mutationFn: async () => {
    if (activeRun && development?.cancel) await development.cancel(activeRun.id);
  }});
  const addProductionInputs = async (files: FileList | null) => {
    if (!files?.length || !development?.uploadProjectInput) return;
    const available = Math.max(0, 12 - productionInputs.length);
    setProductionInputBusy(true); setNotice('');
    try {
      const uploaded: ProductionInput[] = [];
      for (const file of Array.from(files).slice(0, available)) {
        if (file.size > 10 * 1024 * 1024) throw new Error(`附件“${file.name}”超过 10 MiB。`);
        uploaded.push(await development.uploadProjectInput(projectId, file));
      }
      setProductionInputs(current => [...current, ...uploaded]);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : '制作附件上传失败。');
    } finally { setProductionInputBusy(false); }
  };
  const allowGameExecution = true;
  const allowDependencyInstall = true;
  const allowBrowserObservation = false;
  const allowBrowserInteraction = false;
  const allowModelImageInput = false;
  const [conversationSidebarOpen, setConversationSidebarOpen] = useState(true);
  const [previewOpen, setPreviewOpen] = useState(true);
  const [environmentOpen, setEnvironmentOpen] = useState(false);
  const [environmentTurns, setEnvironmentTurns] = useState<JourneyMessage[]>([]);
  const [environmentPreparation, setEnvironmentPreparation] = useState<unknown>(null);
  const [environmentFailed, setEnvironmentFailed] = useState<{requestId:string;text:string;sharedMemory:SharedProjectMemory}|null>(null);
  const [failedModelBuild, setFailedModelBuild] = useState<ModelBuildInput|null>(null);
  const [builtModel, setBuiltModel] = useState<{sessionId:string;triggerMessageId:string;version:number}|null>(null);
  const environmentConversationKey = ['journey-environment-conversation', projectId] as const;
  const environmentConversation = useQuery({queryKey:environmentConversationKey,
    queryFn:() => environment!.read(projectId), enabled:environmentOpen && !!environment, retry:false});
  const prepareDevelopment = useMutation({
    mutationFn: ({ goal, cardId }: { goal: string; cardId: string }) => {
      if (!development) throw new Error('当前宿主没有连接分支开发服务。');
      return development.prepare(projectId, cardId, goal, {
        authorizeOnSend: workMode === 'develop',
        allowGameExecution, allowDependencyInstall: allowGameExecution && allowDependencyInstall,
        allowBrowserObservation: allowGameExecution && allowBrowserObservation,
        allowBrowserInteraction: allowGameExecution && allowBrowserInteraction,
        allowModelImageInput: allowGameExecution && allowModelImageInput
          && (allowBrowserObservation || allowBrowserInteraction),
      });
    },
    onSuccess: async (_task, variables) => {
      setDraft('');
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
      setEnvironmentPreparation(result.productionPreparation ?? null);
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
      setFailedModelBuild(null); setEnvironmentOpen(false); setEnvironmentTurns([]); setEnvironmentFailed(null); setPreviewOpen(true); setNotice('');
      onOpenSurface?.('environment');
    },
    onError: (error, variables) => {
      setFailedModelBuild({...variables,retryFailed:true});
      setNotice(error.message);
    },
  });
  const [liveText, setLiveText] = useState('');
  const [liveReasoning, setLiveReasoning] = useState('');
  const [liveStatus, setLiveStatus] = useState('');
  const input = useRef<HTMLTextAreaElement>(null);
  const controller = useRef<AbortController | null>(null);
  const editBase = useRef<number | null>(null);
  const transcript = useRef<HTMLDivElement>(null);
  const [showLatest, setShowLatest] = useState(false);
  useEffect(() => {
    const node = transcript.current;
    if (!node) return;
    let following = true;
    const scroll = () => {
      following = node.scrollHeight - node.scrollTop - node.clientHeight < 100;
      setShowLatest(!following);
    };
    const observer = new MutationObserver(() => {
      if (following) node.scrollTop = node.scrollHeight;
      else scroll();
    });
    observer.observe(node, {childList:true, subtree:true, characterData:true});
    node.addEventListener('scroll', scroll, {passive:true});
    return () => { observer.disconnect(); node.removeEventListener('scroll', scroll); };
  }, [initialized]);
  const mainTranscriptScrollTop = useRef<number | null>(null);
  const restoreMainScroll = useRef(true);
  const handledSurfaceAction = useRef<string | null>(null);
  const mutation = useMutation({
    mutationFn: (input: Pick<JourneyCommand, 'operation'> & Partial<JourneyCommand>) => {
      if (!query.data) throw new Error('请先读取策划。');
      controller.current = new AbortController();
      const body: JourneyCommand = { request_id: crypto.randomUUID(), expected_revision:
        ['save_outline', 'save_cards'].includes(input.operation) ? editBase.current ?? query.data.revision : query.data.revision,
        text: '', accept_assumptions: false, ...input };
      if (['message', 'discuss_game', 'select_card', 'start_grill', 'start_card_alignment', 'finish_card_alignment', 'generate_outline', 'recommend_architecture', 'generate_cards', 'organize_production'].includes(input.operation)) {
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
      setLiveText(''); setLiveReasoning(''); setLiveStatus('');
      if (['message', 'discuss_game'].includes(input.operation)) { setOutgoing(''); setDraft(current => current === input.text ? '' : current); }
      if (['save_outline', 'save_cards', 'generate_outline', 'generate_cards'].includes(input.operation)) { setEditing(null); editBase.current = null; }
      if (input.operation === 'clear_card' || input.operation === 'select_card') onCloseSurfaces?.();
    },
    onError: (error, input) => {
      if (input.operation === 'select_card') {
        restoreMainScroll.current = false;
      }
      setNotice(error.name === 'AbortError' ? '已停止。未完成的内容没有作为正式回复保存。' : error.message);
      setLiveText(''); setLiveReasoning(''); setLiveStatus('');
      if (['message', 'discuss_game'].includes(input.operation)) { setOutgoing(''); setDraft(current => current || input.text || ''); }
    },
    onSettled: () => { controller.current = null; void cache.invalidateQueries({ queryKey: journeyKey(projectId) }); },
  });
  const startProduction = useMutation({
    mutationFn: async ({goal, continuation = false}: {goal?: string; continuation?: boolean}) => {
      let current = query.data;
      if (!current || !development?.prepareProjectDemo) throw new Error('制作服务尚未连接。');
      if (!continuation) {
        if (!current.demo_direction_draft) throw new Error('先在对话里确定要制作的内容。');
        current = await mutation.mutateAsync({operation:'confirm_demo_direction', ...current.demo_direction_draft});
      }
      const direction = current.initial_demo_direction;
      if (!direction) throw new Error('尚未确定制作内容，请继续讨论。');
      await development.prepareProjectDemo(projectId, direction.direction_id,
        goal ?? `制作可玩的游戏初版：${direction.core_experience}。${direction.perspective_style}；${direction.simplified_scope}。完成检查、构建与本地试玩。`,
        current.execution_policy ?? 'ask', continuation, productionInputs.map(item=>item.path),
        current.production_basis ? current.active_card_id ?? undefined : undefined);
    },
    onSuccess: () => { setDraft(''); setPendingProductionGoal(null); setProductionInputs([]); setNotice(''); },
    onError: error => setNotice(error.message),
  });
  const state = query.data;
  const modeling = state?.modeling_sessions?.find(item => item.id === state.active_modeling_id);
  const modelChannel=useQuery<'local'|'tripo'>({queryKey:['model-generation-channel',projectId,modeling?.id],initialData:'local',enabled:false});
  const storedDraft = environmentOpen ? '' : modeling ? modeling.composer_draft : state?.composer_draft;
  const activeCardId = state?.active_card_id ?? null;
  const draftScope = useRef<string | null>(null);
  const busy = organizing || domain.pending || startProduction.isPending || mutation.isPending || prepareDevelopment.isPending || environmentBuild.isPending || modelBuild.isPending;
  const replying = environmentBuild.isPending || (mutation.isPending && ['message', 'discuss_game', 'select_card', 'start_grill', 'start_card_alignment', 'finish_card_alignment', 'generate_outline', 'recommend_architecture', 'generate_cards', 'organize_production'].includes(mutation.variables?.operation ?? ''));
  useEffect(() => {
    if (!state) return;
    const scope = environmentOpen ? 'environment' : modeling?.id ?? `${activeCardId ?? 'main'}:${state.active_conversation_ids?.[activeCardId ?? ''] ?? 'original'}`;
    if (draftScope.current !== scope) {
      draftScope.current = scope; setDraft(storedDraft ?? ''); setInitialized(true);
      setLiveText(''); setLiveReasoning(''); setOutgoing('');
    }
  }, [state, modeling?.id, storedDraft, environmentOpen]);
  useEffect(() => { setWorkMode('discuss'); setPendingProductionGoal(null); }, [state?.active_card_id, state?.active_conversation_ids?.[activeCardId ?? ''], modeling?.id]);
  useEffect(() => { if (modeling || environmentOpen) setPreviewOpen(true); }, [modeling?.id, environmentOpen]);
  useEffect(() => {
    setEnvironmentTurns([]);
    setEnvironmentPreparation(null);
    setEnvironmentFailed(null);
    setEnvironmentOpen(false);
  }, [activeCardId, modeling?.id]);
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
    if (environmentOpen || !state || !initialized || busy || notice || draftScope.current !== (modeling?.id ?? `${activeCardId ?? 'main'}:${state.active_conversation_ids?.[activeCardId ?? ''] ?? 'original'}`) || draft === storedDraft) return;
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
  const dirty = sourceDirty || !!editing || busy || productionInputBusy || productionInputs.length > 0 || (!!state && draft !== storedDraft);
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
  }, [state?.messages?.length, state?.card_messages?.[activeCardId ?? '']?.length, modeling?.messages?.length, environmentTurns.length, outgoing, liveText, liveStatus]);
  useEffect(() => {
    const node = transcript.current;
    if (!node || (!modeling?.id && !environmentOpen)) return;
    const frame = requestAnimationFrame(() => { node.scrollTop = node.scrollHeight; });
    return () => cancelAnimationFrame(frame);
  }, [modeling?.id, environmentOpen]);
  useEffect(() => {
    if (!state) return;
    if (activeCardId) {
      restoreMainScroll.current = true;
      return;
    }
    if (!restoreMainScroll.current) return;
    const scrollTop = mainTranscriptScrollTop.current ?? state.main_scroll_top ?? 0;
    const frame = requestAnimationFrame(() => {
      transcript.current?.scrollTo({top:scrollTop,behavior:'auto'});
      restoreMainScroll.current = false;
    });
    return () => cancelAnimationFrame(frame);
  }, [activeCardId, state?.revision, state?.main_scroll_top]);
  useEffect(() => { if (input.current) { input.current.style.height = '0px'; input.current.style.height = `${Math.min(144, Math.max(40, input.current.scrollHeight))}px`; } }, [draft]);
  if (query.isPending) return <p role="status">恢复策划进度…</p>;
  if (query.error || !state) return <p role="alert">{query.error?.message ?? '策划不存在'} <button onClick={() => void query.refetch()}>重新读取</button></p>;
  const act = (operation: JourneyCommand['operation'], extra: Partial<JourneyCommand> = {}) => {
    if (operation === 'select_card' && !state.active_card_id) {
      mainTranscriptScrollTop.current = transcript.current?.scrollTop ?? 0;
      restoreMainScroll.current = true;
    }
    setNotice(''); mutation.mutate({ operation, ...extra,
      ...(operation === 'select_card' ? {main_scroll_top:mainTranscriptScrollTop.current ?? state.main_scroll_top ?? 0} : {}),
      ...(['select_card', 'clear_card', 'choose_model_source', 'new_modeling', 'open_modeling', 'close_modeling'].includes(operation) ? { context_draft: draft } : {}) });
  };
  const focusedMessages = environmentOpen ? (environmentTurns.length ? environmentTurns : environmentConversation.data?.messages ?? [])
    : modeling ? modeling.messages ?? [] : activeCardId ? state.card_messages?.[activeCardId] ?? [] : [];
  const messages = activeCardId ? focusedMessages : state.messages ?? [];
  const modelMessages = modeling?.messages ?? [];
  const latestModelUser = modeling?.source === 'create'
    ? [...modelMessages].reverse().find(message => message.role === 'user' && message.text.trim())
    : undefined;
  const builtCurrentVersion = builtModel && builtModel.sessionId === modeling?.id && builtModel.triggerMessageId === latestModelUser?.id
    ? builtModel.version : null;
  const failedCurrentModelBuild = failedModelBuild && failedModelBuild.sessionId === modeling?.id
    && failedModelBuild.triggerMessageId === latestModelUser?.id ? failedModelBuild : null;
  const versions = state.versions ?? [];
  const activeCard = cards.find(card => card.id === state.active_card_id);
  const activeCardDiscussion = activeCardId ? state.card_messages?.[activeCardId] ?? [] : [];
  const cardAlignmentSummary = activeCardId ? state.card_alignment_summaries?.[activeCardId] ?? '' : '';
  const cardAlignmentId = activeCardId ? state.card_alignment_summary_ids?.[activeCardId] ?? '' : '';
  const technicalPlan = state.technical_plan;
  const nativeCard = !!state.production_basis && !!activeCard;
  const reviewingProduction = !!state.production_basis && state.stage === 'outline' && !activeCard;
  const recommendation = state.architecture_recommendation;
  const sharedMemory: SharedProjectMemory = {
    project_title:outline?.title ?? '', experience:outline?.experience ?? '', core_loop:outline?.core_loop ?? '',
    scope:outline?.scope ?? '',
    technical_plan:technicalPlan ? `${technicalPlan.engine} · ${technicalPlan.architecture_label} · ${technicalPlan.rationale}` : '',
    active_card:activeCard ? `${activeCard.title}：${activeCard.description}` : '',
  };
  const creationMode: WorldCreationMode = environmentOpen ? 'environment' : modeling?.source === 'create' ? 'model' : null;
  const beginEdit = (kind: 'outline' | 'cards') => { if (!editing) editBase.current = state.revision; setEditing(kind); };
  const questionPhaseOpen = modeling || environmentOpen ? true
    : activeCardId ? !cardAlignmentSummary : true;
  const activeQuestionId = questionPhaseOpen
    ? [...messages].reverse().find(message => message.question && !messages.some(answer => answer.reply_to === message.id))?.id ?? null
    : null;
  const latestQuestion = activeQuestionId ? messages.find(message => message.id === activeQuestionId) : undefined;
  const send = () => {
    if (activeRun) return;
    if (!draft.trim() || busy) return;
    const text = draft.trim();
    if (domainConversation) { setDraft(''); void domain.submit(text); return; }
    if (nativeCard && !modeling && !environmentOpen && workMode === 'develop') {
      startProduction.mutate({goal:text, continuation:true});
      return;
    }
    if (!activeCard && !modeling && !environmentOpen && state.production_basis && state.stage === 'outline') {
      setOutgoing(text); setDraft(''); act('message', {text}); return;
    }
    if (!activeCard && !modeling && !environmentOpen && projectDemoPresent && state.initial_demo_direction) {
      if ((state.execution_policy ?? 'ask') === 'ask') setPendingProductionGoal(text);
      else startProduction.mutate({goal:text, continuation:true});
      return;
    }
    if (environmentOpen) {
      setOutgoing(text); setDraft(''); setNotice('');
      environmentBuild.mutate({text,requestId:crypto.randomUUID(),retryFailed:false,sharedMemory});
      return;
    }
    if (activeCard && !modeling && workMode === 'develop') {
      if (!cardAlignmentSummary) { setOutgoing(text); setDraft(''); act('message', {text}); return; }
      if (text.length > 8000) { setNotice('开发目标最多 8000 字符。'); return; }
      setNotice('');
      prepareDevelopment.mutate({ goal: `在「${activeCard.title}」当前分支继续一个可试玩增量切片：${text}\n\n本轮已确认范围：\n${cardAlignmentSummary}\n\n只完成这一个切片；执行相关类型检查、构建与预览验证，未达到可观察验收条件不得声称完成。`, cardId: activeCard.id });
      return;
    }
    setOutgoing(text); setDraft(''); act(activeCard || modeling ? 'message' : 'discuss_game', { text, ...(latestQuestion ? { question_message_id: latestQuestion.id } : {}) });
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
    if (!modeling || modeling.source !== 'create' || !latestModelUser || modelChannel.data==='tripo') return;
    const triggerIndex = modelMessages.findIndex(message => message.id === latestModelUser.id);
    modelBuild.mutate({projectId,cardId:modeling.card_id,sessionId:modeling.id,
      triggerMessageId:latestModelUser.id,modelingBlock:latestModelUser.modeling_block ?? 'refinement',
      transcript:modelMessages.slice(0,triggerIndex + 1)
        .filter(message => (message.role === 'user' || message.role === 'assistant') && message.text.trim())
        .map(message => ({role:message.role,text:message.text})),
      // This path only runs from the user's explicit confirmation button. It is
      // therefore also the explicit retry required for an earlier failed build.
      retryFailed:true});
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
  return <section className={`sceneops-chat planning-journey${activeCard ? ' has-card-workspace' : ''}${activeCard?.id === 'world-3d' ? ' world-3d-workspace' : ''}${sidePreview && previewOpen ? ' has-model-preview' : ''}${activeCard && !conversationSidebarOpen ? ' conversation-sidebar-collapsed' : ''}`} aria-label={activeCard ? `${activeCard.title}工作流` : '单人策划工作流'}>
    <header><div className="journey-header-title">{activeCard && !conversationSidebarOpen && <button type="button" className="journey-sidebar-toggle" aria-expanded={false} aria-label="展开侧边栏" title="展开侧边栏" onClick={() => setConversationSidebarOpen(true)}><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M4 4h16v16H4zM9 4v16" /></svg></button>}<strong>{activeCard?.title ?? '协作'}</strong><small>{activeCard ? '独立工作流' : activeRun ? '制作中' : reviewingProduction ? '策划审阅' : projectDemoPresent ? '制作与迭代' : '讨论'}</small></div><div className="journey-header-actions"><ExperiencePanel projectId={projectId} />{onOpenExport && <button type="button" onClick={onOpenExport}>导出</button>}{activeCard && !nativeCard && development?.renderSourceEditor?.(projectId, activeCard.id, setSourceDirty)}{activeCard ? <button type="button" className="journey-header-back" disabled={busy || sourceDirty} onClick={() => act('clear_card')} aria-label="返回制作卡片" title="返回制作卡片"><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M19 12H5M11 6l-6 6 6 6" /></svg></button> : <button type="button" onClick={onOpenProjects}>文件夹</button>}</div></header>
    {exportDevelopmentRequest?.projectId === projectId && <div className="journey-notice" role="status">
      <strong>来自专业工具的制作要求</strong><p>{exportDevelopmentRequest.text}</p>
      <button type="button" disabled={busy || !initialized} onClick={() => {
        setDraft(current => [current, exportDevelopmentRequest.text].filter(Boolean).join('\n\n'));
        setWorkMode('discuss'); onExportDevelopmentAccepted?.();
      }}>加入对话草稿</button>
    </div>}
    {activeCard && conversationSidebarOpen && <aside className="journey-conversations" aria-label="卡片对话列表">
      <div className="journey-conversation-toolbar">
        <button type="button" disabled={busy} onClick={() => act('new_conversation', {context_draft:draft})} className="journey-new-conversation"><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14" /></svg>新建对话</button>
        <button type="button" className="journey-sidebar-toggle" aria-expanded={conversationSidebarOpen} aria-label={conversationSidebarOpen ? '收起侧边栏' : '展开侧边栏'} title={conversationSidebarOpen ? '收起侧边栏' : '展开侧边栏'} onClick={() => setConversationSidebarOpen(open => !open)}>
          <svg aria-hidden="true" viewBox="0 0 24 24"><path d={conversationSidebarOpen ? 'M15 18l-6-6 6-6' : 'M9 18l6-6-6-6'} /></svg>
        </button>
      </div>
      <div className="journey-conversation-label"><span>工作流对话</span><small>{state.card_conversations?.[activeCard.id]?.length || 1}</small></div>
      <nav>{(state.card_conversations?.[activeCard.id]?.length ? state.card_conversations[activeCard.id] : [{id:'original',title:'原始对话'}]).map(conversation =>
        <div className="journey-conversation-item" key={conversation.id}>
          <button type="button" className="journey-conversation-select" aria-current={(state.active_conversation_ids?.[activeCard.id] ?? 'original') === conversation.id ? 'page' : undefined}
            disabled={busy} onClick={() => { if ((state.active_conversation_ids?.[activeCard.id] ?? 'original') !== conversation.id) act('select_conversation', {conversation_id:conversation.id, context_draft:draft}); }}>
            <svg className="journey-thread-icon" aria-hidden="true" viewBox="0 0 24 24"><path d="M7 5h10a3 3 0 0 1 3 3v6a3 3 0 0 1-3 3h-6l-5 3v-3a3 3 0 0 1-2-3V8a3 3 0 0 1 3-3Z"/><path d="M8 9h8M8 13h5"/></svg><span>{conversation.title}</span></button>
          <button type="button" className="journey-conversation-delete" disabled={busy} aria-label={`删除对话“${conversation.title}”`} title="删除对话"
            onClick={() => { if (window.confirm(`删除对话“${conversation.title}”？此操作无法撤销。`)) act('delete_conversation', {conversation_id:conversation.id}); }}>
            <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M4 7h16M9 7V4h6v3m-9 0 1 13h10l1-13M10 11v5m4-5v5" /></svg>
          </button>
        </div>)}</nav>
      <div className="journey-conversation-context"><svg aria-hidden="true" viewBox="0 0 24 24"><circle cx="6" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="6" r="2"/><path d="M6 7v10M18 8v2a5 5 0 0 1-5 5H6"/></svg><div><strong>项目上下文已关联</strong><span>{nativeCard ? '对话共用当前游戏与制作会话' : '对话共用当前项目与分支'}</span></div></div>
    </aside>}
    <div className="journey-scroll" ref={transcript}>
      {activeCard && !messages.length && !outgoing && <div className="journey-empty"><h2>接下来，我们做什么？</h2><p>讨论想法，或直接开始制作。</p></div>}
      {activeCard && !technicalPlan && <p role="status" className="journey-architecture-missing">这个旧项目还没有明确游戏代码架构。返回制作卡片后选择架构，已有代码不会被重建或覆盖。</p>}
      {!messages.length && !outgoing && !modeling && !environmentOpen && !activeCard && !projectDemoPresent && <div className="journey-empty"><h2>你想做一个什么样的游戏？</h2><p>说说你的想法，我会问清关键问题，然后直接进入制作。</p></div>}
      {[...messages.map(message=>({kind:'message' as const,createdAt:message.created_at,message})),...domain.turns.map(turn=>({kind:'material' as const,createdAt:turn.createdAt,turn}))].sort((a,b)=>a.createdAt.localeCompare(b.createdAt)).map(row => row.kind==='material' ? <DomainConversationTurns key={row.turn.id} turns={[row.turn]}/> : ((message)=><article key={message.id} id={`memory-message-${message.id}`} className={`journey-message ${message.role}`}>
        {message.role === 'user' ? <p>{message.text}</p> : <MarkdownMessage text={message.text} />}
        {message.question && <PlanningQuestionCard question={message.question} disabled={busy}
          answered={messages.some(answer => answer.reply_to === message.id)} locked={message.id !== activeQuestionId}
          onAnswer={index => { setOutgoing(message.question!.options[index].label); act(activeCard || modeling || environmentOpen ? 'message' : 'discuss_game', { question_message_id: message.id, option_index: index }); }}
          onCustom={() => input.current?.focus()} />}
        {message.role === 'assistant' && <><MessageActions text={message.text} /><ExperienceReferences projectId={projectId} useKey={`journey:${projectId}:message:${message.id}`} sourceId={messages.slice(0,messages.findIndex(item=>item.id===message.id)).filter(item=>item.role==='user').slice(-1).map(item=>`journey:${projectId}:message:${item.id}`)[0]}/></>}
        <MemoryMessage projectId={projectId} originKey={`journey:${projectId}:message:${message.id}`} sourceId={`journey:${projectId}:message:${message.id}`} text={message.role==='user'?message.text:undefined} correctionSourceId={message.role==='assistant'?messages.slice(0,messages.findIndex(item=>item.id===message.id)).filter(item=>item.role==='user').slice(-1).map(item=>`journey:${projectId}:message:${item.id}`)[0]:undefined}/>
      </article>)(row.message))}
      {domain.historyError && <p role="alert">材质记录读取失败：{domain.historyError}</p>}
      {!activeCard && !modeling && !environmentOpen && state.demo_direction_draft && !projectDemoPresent && !activeRun && !replying &&
        <div className="journey-production-start">
          <details><summary>制作摘要</summary>
            <p>{state.demo_direction_draft.core_experience}</p>
            <p>{state.demo_direction_draft.perspective_style}</p>
            <p>{state.demo_direction_draft.simplified_scope}</p>
          </details>
          <p>可以继续补充，或开始制作。</p>
          <button type="button" disabled={busy} onClick={() => startProduction.mutate({})}>
            {startProduction.isPending ? '正在开始…' : '开始制作'}
          </button>
        </div>}
      {outgoing && <article className="journey-message user"><small>你 · 等待回复</small><p>{outgoing}</p></article>}
      {(environmentPreparation ?? state.production_preparation) &&
        <ProductionPreparationSummary value={environmentPreparation ?? state.production_preparation} />}
      {!activeCard && development?.renderProjectDemoTasks?.(projectId, handleProjectDemoPresence)}
      {!activeCard && !modeling && !environmentOpen && projectDemoPresent && <OrganizeProductionButton state={state} disabled={busy || !!activeRun || !!editing} />}
      {nativeCard && !modeling && !environmentOpen && <section className="journey-actions"><h3>{activeCard.title}</h3><p>{activeCard.description}</p><details><summary>完成条件</summary><MarkdownMessage text={activeCard.acceptance} /></details><p>本卡关联当前游戏源码。讨论后可切换“完全访问”发送修改，或确认下面的本轮目标。</p>
        {!!draft.trim() && workMode === 'discuss' && <button type="button" disabled={busy || !!activeRun} onClick={()=>setPendingProductionGoal(draft.trim())}>按这段描述修改当前游戏</button>}
      </section>}
      {activeCard && !nativeCard && !modeling && !environmentOpen && !replying && !activeRun && <section className="journey-actions journey-coding-handoff">
        {!cardAlignmentSummary && activeCardDiscussion.some(message => message.role === 'user') && <button type="button" disabled={busy || !technicalPlan}
          onClick={() => act('finish_card_alignment')}>对齐好了 · 整理执行范围</button>}
        {cardAlignmentSummary && cardAlignmentId && development && <DemoExecutionRequest key={`${activeCard.id}:${cardAlignmentId}`}
          alignmentId={cardAlignmentId} prepare={() => development.prepare(projectId, activeCard.id,
            `实现「${activeCard.title}」当前已对齐的可试玩 Demo。\n\n${cardAlignmentSummary}\n\n沿用当前工程架构，优先使用随项目提供的基础资产；人物造型统一，以颜色区分玩家、敌人、NPC和友方。完成依赖准备、类型检查、构建及本地预览，按真实结果报告。`,
            {authorizeOnSend:true,allowGameExecution:true,allowDependencyInstall:true,allowBrowserObservation:true,allowBrowserInteraction:false,
              allowModelImageInput:false,
              includeDemoAssets:true,alignmentId:cardAlignmentId})} />}
        {cardAlignmentSummary && !cardAlignmentId && <button type="button" disabled={busy || !technicalPlan}
          onClick={() => act('finish_card_alignment')}>确认本轮范围并准备执行</button>}
      </section>}
      {(replying || liveText || liveReasoning) && <article className="journey-live" aria-live="polite">
        {replying && <div className="journey-working"><span className="journey-working-dot" />{environmentBuild.isPending ? 'AI 正在安排资产并生成场景版本…' : liveStatus || '正在生成…'}</div>}
        {liveReasoning && <details className="journey-reasoning"><summary>思考过程 <small>提供方返回</small></summary><MarkdownMessage text={liveReasoning} /></details>}
        {liveText && <MarkdownMessage text={liveText} />}
      </article>}
      {!activeCard && !modeling && !environmentOpen && <ProductionDomains onRequestDevelopment={goal=>setPendingProductionGoal(goal)} state={state} disabled={busy || !!editing} onSelectCard={id=>act('select_card',{card_id:id})} {...(onOpenProductionTool?{onOpenTool:onOpenProductionTool}:{})}/>}
      {!activeCard && !modeling && !environmentOpen && (!!outline || !!cards.length || !!versions.length) && <details className="journey-attachment" open={!!state.production_basis}><summary>{state.production_basis ? '完整策划与分项制作' : '项目资料与历史工作流'}</summary><div className="journey-actions">
        {state.stage === 'idea' && !!messages.length && <button disabled={busy} onClick={() => act('start_grill')}>我说完了 · 开始对齐</button>}
        {state.stage === 'grill' && <><p>grill-me：一次一个问题，逐步确认设计。</p><button disabled={busy} onClick={() => act('generate_outline')}>细节已对齐 · 生成大纲</button></>}
      </div>
      {(state.changes ?? []).filter(change => change.status === 'pending').map(change => <JourneyChangeReview key={change.id} change={change} disabled={busy || !!editing}
        onResolve={accept => act(accept ? 'accept_change' : 'reject_change', { change_id: change.id })} />)}
      {outline && <details className="journey-document journey-attachment" open={!!state.production_basis && state.stage === 'outline'}><summary>策划大纲 · {outline.title} <small>{editing ? '未保存修改' : '查看与确认'}</small></summary>
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
      {(state.stage === 'cards' || state.production_basis) && <section className="journey-next">
        {!cards.length && <button disabled={busy || !technicalPlan} onClick={() => act('generate_cards')}>根据技术方案生成制作卡片</button>}
        {!!cards.length && <><p className="journey-card-summary">{state.production_basis ? '以下为项目功能包，关联同一游戏的源码和对象。' : '以下为项目功能包，可同时关联上方多个生产领域。'}</p><section className="journey-production-cards" aria-label="制作卡片">
          {cards.map((card, index) => <article className="journey-plan-item" key={card.id} data-selected={state.active_card_id === card.id}>
            <button type="button" className="journey-card-select" aria-pressed={state.active_card_id === card.id} disabled={busy || !!editing || !versions.length}
              onClick={() => act('select_card', { card_id: card.id })}>
              <span className="journey-card-heading"><small>{String(index + 1).padStart(2, '0')}</small><strong>{card.title}</strong></span>
              <span className="journey-card-description">{card.description}</span>
              <span className="journey-card-entry">{state.production_basis ? '进入卡片 →' : state.active_card_id === card.id ? '当前分支' : state.card_branches?.some(branch => branch.card_id === card.id) ? '进入 Git 分支 →' : '创建 Git 分支并进入 →'}</span>
            </button><details><summary>完成条件与依赖</summary><MarkdownMessage text={card.acceptance} />
              {!!card.dependencies?.length && <p>依赖：{card.dependencies.map(id => cards.find(item => item.id === id)?.title ?? id).join('、')}</p>}</details></article>)}
        </section></>}
      </section>}
      {!!versions.length && <details className="journey-attachment"><summary>版本记录 · {versions.length}</summary>{versions.map(version => {
        const git = state.git_versions?.find(item => item.number === version.number);
        return <p key={version.number}>v{version.number} · {version.outline.title} · {new Date(version.confirmed_at).toLocaleString()}<br/>
          <small>{git ? `${git.tag} · ${git.commit.slice(0, 10)}` : '旧版记录尚未建立 Git 提交'}</small></p>;
      })}{!state.git_versions?.length && <button type="button" disabled={busy} onClick={() => act('enable_git')}>将已确认版本纳入 Git</button>}</details>}
      </details>}
      {activeCard && nativeCard && development?.renderProductionCard?.(projectId, activeCard, handleProjectDemoPresence, state.active_conversation_ids?.[activeCard.id] ?? 'original')}
      {activeCard && !nativeCard && development?.renderTasks(projectId, activeCard.id, handleDevelopmentPresence,
        () => { input.current?.focus(); }, state.active_conversation_ids?.[activeCard.id] ?? 'original')}

    </div>
    {sidePreview && <aside className="journey-model-preview-pane" data-open={previewOpen} aria-label={environmentOpen ? '环境场景预览' : '实时模型预览'}>
      <header><div><strong>{environmentOpen ? '3D 世界' : modeling?.source === 'create' ? '模型生成' : '模型导入'}</strong><small>Three.js</small></div>
        <span className="journey-preview-actions"><button type="button" aria-expanded={previewOpen} onClick={() => setPreviewOpen(value => !value)}>{previewOpen ? '收起' : '展开'}</button></span></header>
      <div className="journey-model-preview-body" hidden={!previewOpen}>{sidePreview}</div>
    </aside>}
    {pendingProductionGoal && !activeRun && <section className="journey-production-start" aria-label="修改权限确认" aria-live="polite">
      <p>继续修改当前游戏：确认后接着原制作会话执行。</p><p>{pendingProductionGoal}</p>
      <button type="button" disabled={busy} onClick={() => startProduction.mutate({goal:pendingProductionGoal, continuation:true})}>允许本次修改</button>
      <button type="button" disabled={busy} onClick={() => setPendingProductionGoal(null)}>取消</button>
    </section>}
    {notice && <section role="alert" className="journey-notice">
      <span className="journey-notice-icon" aria-hidden="true">!</span>
      <div className="journey-notice-copy"><strong>{failedCurrentModelBuild ? '模型草稿未生成' : environmentFailed ? '场景搭建未完成' : '本次操作未完成'}</strong><p>{notice}</p></div>
      <div className="journey-notice-actions">
        {failedCurrentModelBuild && modelChannel.data!=='tripo' && <button className="journey-notice-primary" disabled={busy} onClick={() => {setNotice('');modelBuild.mutate(failedCurrentModelBuild);}}>重试本轮草稿</button>}
        {environmentFailed && <button className="journey-notice-primary" disabled={busy} onClick={() => {setOutgoing(environmentFailed.text);setDraft('');setNotice('');environmentBuild.mutate({...environmentFailed,retryFailed:true});}}>重试本次 AI 搭建</button>}
        {!failedCurrentModelBuild && !environmentFailed && <button onClick={() => { void query.refetch(); }}>重新读取</button>}
        {editing && <button onClick={async () => { if (window.confirm('放弃未保存的文档修改，重新读取已保存版本？')) { await query.refetch(); setEditing(null); editBase.current = null; setNotice(''); } }}>放弃本地修改</button>}
        <button className="journey-notice-close" aria-label="关闭提示" title="关闭提示" onClick={() => setNotice('')}>×</button>
      </div>
    </section>}
    {!activeCard && !modeling && !environmentOpen && !reviewingProduction && state.execution_policy === 'full-access' && <p className="journey-native-permission-note">开始制作或发送后续修改即授权本次项目操作。Agent 原生执行默认不限模型请求和动作次数、不设总时限，可随时停止。中转 GPT 使用独立 Codex 配置和凭据通道；完全访问可操作文件、命令和网络，当前目录不是系统沙箱。模型费用可能未知。</p>}
    {activeCard && !modeling && !environmentOpen && workMode === 'develop' && <div className="journey-native-permission-note">
      发送即允许 Agent 读写文件、执行命令和访问网络。当前目录不是系统沙箱；仅授权本次项目任务。同一对话的上一轮若已停止，将保留当前文件并从同一分支继续。
    </div>}
    {reviewingProduction && <p className="journey-native-permission-note">当前正在审阅策划。发送消息只讨论大纲与卡片；确认版本后，进入具体卡片修改游戏。</p>}
    {activeCard?.id === 'world-3d' && !nativeCard && <WorldCreationActions mode={creationMode} busy={busy}
      onNewModel={beginNewModel} onEnvironment={openEnvironment} />}
    {!activeCard && !modeling && !environmentOpen && productionInputs.length > 0 && <div className="journey-production-inputs" aria-label="本轮制作附件">
      {productionInputs.map(item=><span key={item.path}>{item.kind==='image'?'图片':'文件'} · {item.name}<button type="button" aria-label={`移除${item.name}`} disabled={busy||productionInputBusy}
        onClick={()=>setProductionInputs(current=>current.filter(input=>input.path!==item.path))}>×</button></span>)}
    </div>}
    {showLatest && <button type="button" className="journey-jump-latest" aria-label="回到最新消息" title="回到最新消息" onClick={() => transcript.current?.scrollTo({top:transcript.current.scrollHeight,behavior:'smooth'})}>↓</button>}
    {domainConversation && <DomainConversationTarget port={domainConversation} disabled={domain.pending}/>}
    <ChatComposer className="journey-input-dock" onSubmit={event => { event.preventDefault(); send(); }} input={
      <textarea ref={input} aria-label={environmentOpen ? '3D 世界对话' : modeling ? '模型生成对话' : activeCard ? `${activeCard.title}对话` : '策划对话'} disabled={!domainConversation && !environmentOpen && modeling?.source === 'import'} placeholder={domainConversation ? '描述当前材质的外观或效果…' : environmentOpen ? '描述要构建的世界、场景或资产；右侧可以直接新建、导入和摆放…' : modeling ? modeling.source === 'create' ? '描述模型、风格、尺寸和用途；也可以在上方加参考图…' : '请在右侧选择 GLB 或 FBX 文件' : activeCard ? workMode === 'develop' ? `让 Agent 实现「${activeCard.title}」的什么内容？` : `继续讨论「${activeCard.title}」…` : reviewingProduction ? '讨论大纲或制作卡片需要调整的内容…' : projectDemoPresent ? '描述你想修改的地方…' : state.stage === 'idea' ? '聊聊你的 idea…' : '继续讨论想法…'} value={draft} rows={1} onChange={e => setDraft(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(); } }} />
      } options={<>{modelPicker(busy || replying || !!activeRun)}
        {!activeCard && !modeling && !environmentOpen && development?.uploadProjectInput && <label className="journey-input-attachment">
          <input type="file" multiple disabled={busy||!!activeRun||productionInputBusy||productionInputs.length>=12}
            accept="image/*,.txt,.md,.json,.pdf,.doc,.docx,.csv,.tsv,.zip,.glb,.gltf,.fbx"
            onChange={event=>{void addProductionInputs(event.target.files);event.currentTarget.value='';}} />
          {productionInputBusy?'正在附加…':'附加图片或文件'}
        </label>}
        {!activeCard && !modeling && !environmentOpen && !reviewingProduction && <ComposerMenu label="执行权限"
          value={state.execution_policy ?? 'ask'} disabled={busy || !!activeRun}
          onChange={value => act('set_execution_policy', {execution_policy:value as 'ask'|'full-access'})}
          icon={<JourneyComposerIcon kind="shield" />}
          options={[{value:'ask',label:'执行前询问',description:'讨论不改文件；制作前确认范围，范围内连续执行。'},
            {value:'full-access',label:'完全访问',description:'开始制作或发送修改后，可读写项目、运行命令和访问网络。'}]} />}
        {activeCard && !modeling && !environmentOpen && <ComposerMenu label="Agent 权限" value={workMode} disabled={busy || !technicalPlan} onChange={value=>setWorkMode(value as 'discuss'|'develop')}
          icon={<JourneyComposerIcon kind="shield" />}
          options={[{value:'discuss',label:'执行前询问',description:'开始执行前，先确认本次权限范围。'},{value:'develop',label:'完全访问',description:'发送后可读写文件、运行命令和访问网络。'}]} />}
        {modeling?.source==='create' && modelChannel.data==='tripo' && <span>Tripo 渠道：请在模型面板确认描述并点击生成</span>}
        {latestModelUser && assets?.build && modelChannel.data!=='tripo' && <button className="journey-confirm-model" type="button" disabled={busy || builtCurrentVersion !== null} onClick={confirmAndBuildModel}>{modelBuild.isPending ? '正在建模…' : builtCurrentVersion !== null ? `已生成 v${builtCurrentVersion}` : failedCurrentModelBuild ? '重试本轮草稿' : '确认并建模'}</button>}
        </>} actions={<><span className="journey-draft-status" role="status">{modelBuild.isPending ? 'AI 生成方案，Blender 输出模型…' : prepareDevelopment.isPending ? '准备授权…' : ''}</span>{!busy && !replying && !activeRun && <span className="journey-send-hint">Enter 发送</span>}
        {domain.pending ? <button className="journey-submit" type="button" aria-label="停止材质调整" onClick={domain.cancel}><JourneyComposerIcon kind="stop" /></button> : activeRun && development?.cancel ? <button className="journey-submit" type="button" aria-label="取消执行" title="取消执行" disabled={cancelExecution.isPending || activeRun.cancelRequested} onClick={() => cancelExecution.mutate()}><JourneyComposerIcon kind="stop" /></button> : replying ? <button className="journey-submit" type="button" aria-label="停止回复" title="停止回复" onClick={() => controller.current?.abort()}><JourneyComposerIcon kind="stop" /></button> : <button className="journey-submit" type="submit" aria-label={activeCard && workMode === 'develop' ? '发送并执行' : '发送'} title={activeCard && workMode === 'develop' ? '发送即授权当前项目操作，费用可能未知' : '发送'} disabled={busy || !draft.trim()}><JourneyComposerIcon kind="send" /></button>}</>} />
    {cancelExecution.error && <p className="journey-notice" role="alert">{cancelExecution.error.message}</p>}
  </section>;
}
