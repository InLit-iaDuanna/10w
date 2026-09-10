import type { EditorDefinition } from '../contracts.ts';

export interface ToolTreeNode {
  readonly id: string;
  readonly title: string;
  readonly description: string;
  readonly icon?: string;
  readonly sequence?: number;
  readonly editor: EditorDefinition;
}

export interface ToolTreeBranch {
  readonly id: string;
  readonly title: string;
  readonly description: string;
  readonly kind: 'production' | 'support';
  readonly nodes: readonly ToolTreeNode[];
}

export interface ToolLibraryCatalog {
  readonly title: string;
  readonly description: string;
  readonly entries: readonly ToolLibraryCatalogEntry[];
}

export interface ToolLibraryCatalogEntry {
  readonly group?: string;
  readonly editorId: string;
  readonly title: string;
  readonly description: string;
  readonly icon?: string;
}

interface ToolNodeDefinition {
  readonly editorId: string;
  readonly title: string;
  readonly description: string;
  readonly icon?: string;
}

const productionFlow: readonly ToolNodeDefinition[] = [
  { editorId: 'workbench.project-planning', title: '需求规划', description: '整理需求、任务与制作节奏。' },
  { editorId: 'workbench.concept-assets', title: '概念与资产', description: '衔接概念方向与资产生产。' },
  { editorId: 'workbench.character-animation', title: '角色与动画', description: '管理角色制作与动画交付。' },
  { editorId: 'workbench.world-logic', title: '世界与逻辑', description: '组织场景、玩法逻辑与交互。' },
  { editorId: 'workbench.ui-audio-vfx', title: '界面、音频与特效', description: '统一界面、声音与视觉特效。' },
  { editorId: 'workbench.render-ops', title: '渲染', description: '检查镜头、画面与渲染任务。' },
  { editorId: 'workbench.unity-build', title: 'Unity 构建', description: '推进 Unity 集成、构建与交付。' },
  { editorId: 'workbench.ai-playtest', title: 'AI 游测', description: '编排游测规格并查看已有证据。' },
  { editorId: 'workbench.version-review', title: '版本评审', description: '查看版本变化并进行评审。' },
] as const;

const supportGroups = [
  {
    id: 'starting-points',
    title: '项目起点',
    description: '建立对话、项目上下文与 AI 生产计划。',
    nodes: [
      { editorId: 'assistant.conversation', title: '对话', description: '描述目标、获取建议并打开所需功能。' },
      { editorId: 'workspace.projects', title: '本地项目', description: '浏览并切换当前电脑上的项目。' },
      { editorId: 'harness.pipeline', title: 'AI 生产计划', description: '将目标拆解为可追踪的生产计划。' },
    ],
  },
  {
    id: 'operations',
    title: '命令与运维',
    description: '管理工具选择、工作台命令与外部连接。',
    nodes: [
      { editorId: 'shell.tool-library', title: '工具库', description: '从当前区域选择并替换为其他功能。' },
      { editorId: 'shell.command-search', title: '命令搜索', description: '快速执行打开、保存与布局命令。' },
      { editorId: 'workbench.integration-ops', title: '集成与运维', description: '查看外部工具连接与运行状况。' },
    ],
  },
] as const;

function createNodes(definitions: readonly ToolNodeDefinition[], editorsById: ReadonlyMap<string, EditorDefinition>, numbered = false) {
  return definitions.flatMap((definition, index) => {
    const editor = editorsById.get(definition.editorId);
    return editor ? [{
      id: definition.editorId,
      title: definition.title,
      icon: definition.icon ?? editor.icon,
      description: definition.description,
      ...(numbered ? { sequence: index + 1 } : {}),
      editor,
    }] : [];
  });
}

function includesQuery(branch: Omit<ToolTreeBranch, 'nodes'>, node: ToolTreeNode, query: string) {
  return `${branch.title} ${branch.description} ${node.title} ${node.description} ${node.editor.title} ${node.editor.id} ${node.editor.category}`
    .toLocaleLowerCase()
    .includes(query);
}

export function createToolLibraryTree(
  editors: readonly EditorDefinition[],
  rawQuery = '',
  catalog?: ToolLibraryCatalog,
): ToolTreeBranch[] {
  const editorsById = new Map(editors.map(editor => [editor.id, editor]));
  if (catalog) {
    const groups = [...new Set(catalog.entries.map(entry => entry.group ?? catalog.title))];
    return filterBranches(groups.map((group,index) => ({
      id: groups.length === 1 ? 'current-workflow' : `current-workflow-${index}`,
      title: group,
      description: catalog.description,
      kind: 'production' as const,
      nodes: createNodes(catalog.entries.filter(entry => (entry.group ?? catalog.title) === group), editorsById, true),
    })), rawQuery);
  }
  const knownIds = new Set([
    ...productionFlow.map(node => node.editorId),
    ...supportGroups.flatMap(group => group.nodes.map(node => node.editorId)),
  ]);
  const branches: ToolTreeBranch[] = [
    {
      id: 'production-flow',
      title: '游戏生产流程',
      description: '从需求规划推进到版本评审。',
      kind: 'production',
      nodes: createNodes(productionFlow, editorsById, true),
    },
    ...supportGroups.map(group => ({
      id: group.id,
      title: group.title,
      description: group.description,
      kind: 'support' as const,
      nodes: createNodes(group.nodes, editorsById),
    })),
  ];
  const additionalNodes = editors
    .filter(editor => !knownIds.has(editor.id))
    .map(editor => ({ id: editor.id, title: editor.title, description: `打开${editor.title}。`, editor }));
  if (additionalNodes.length) branches.push({
    id: 'additional-tools',
    title: '扩展工具',
    description: '当前项目注册的其他专业工具。',
    kind: 'support',
    nodes: additionalNodes,
  });

  return filterBranches(branches, rawQuery);
}

function filterBranches(branches: ToolTreeBranch[], rawQuery: string): ToolTreeBranch[] {
  const query = rawQuery.trim().toLocaleLowerCase();
  return branches.flatMap(branch => {
    const nodes = query ? branch.nodes.filter(node => includesQuery(branch, node, query)) : branch.nodes;
    return nodes.length ? [{ ...branch, nodes }] : [];
  });
}
