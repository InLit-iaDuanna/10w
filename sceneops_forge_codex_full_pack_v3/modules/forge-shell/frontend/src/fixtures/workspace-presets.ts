import type { DrawerState, Edge, WorkspacePreset } from '../contracts.ts';

const tab = { mode: 'tab' } as const;
const splitRight = { mode: 'split', direction: 'right' } as const;
const splitLeft = { mode: 'split', direction: 'left' } as const;
const splitBelow = { mode: 'split', direction: 'below' } as const;

export const HOME_PRESET: WorkspacePreset = {
  id: 'home',
  title: '主页',
  editors: [{ editorId: 'assistant.conversation', placement: tab, executionMode: 'live' }],
  drawerModes: { left: 'hidden', right: 'hidden', top: 'hidden', bottom: 'hidden' },
};

export const DESIGN_PRESET: WorkspacePreset = {
  id: 'design',
  title: '设计',
  editors: [
    { editorId: 'assistant.conversation', placement: tab },
    { editorId: 'design.feature-spec', placement: splitRight },
    { editorId: 'production.task-graph', placement: splitBelow },
  ],
};

export const ASSETS_PRESET: WorkspacePreset = {
  id: 'assets',
  title: '资产',
  editors: [
    { editorId: 'asset.browser', placement: tab },
    { editorId: 'asset.preview.3d', placement: splitRight },
    { editorId: 'asset.inspector', placement: splitRight },
    { editorId: 'asset.qa', placement: splitBelow },
  ],
};

export const CHARACTER_PRESET: WorkspacePreset = {
  id: 'character',
  title: '角色',
  editors: [
    { editorId: 'character.view', placement: tab },
    { editorId: 'character.rig-animation', placement: splitRight },
    { editorId: 'character.inspector', placement: splitRight },
    { editorId: 'animation.timeline', placement: splitBelow },
  ],
};

export const WORLD_PRESET: WorkspacePreset = {
  id: 'world',
  title: '世界',
  editors: [
    { editorId: 'scene.outliner', placement: tab },
    { editorId: 'scene.viewport.3d', placement: splitRight },
    { editorId: 'scene.inspector', placement: splitRight },
    { editorId: 'scene.navigation-issues', placement: splitBelow },
  ],
};

export const LOGIC_PRESET: WorkspacePreset = {
  id: 'logic',
  title: '逻辑',
  editors: [
    { editorId: 'feature.tree', placement: tab },
    { editorId: 'logic.state-graph', placement: splitRight },
    { editorId: 'logic.code-diff', placement: splitRight },
    { editorId: 'logic.test-console', placement: splitBelow },
  ],
};

export const RENDER_PRESET: WorkspacePreset = {
  id: 'render',
  title: '渲染',
  editors: [
    { editorId: 'render.aov', placement: tab },
    { editorId: 'render.viewer', placement: splitRight },
    { editorId: 'render.recipe', placement: splitRight },
    { editorId: 'render.queue', placement: splitBelow },
  ],
};

export const BUILD_PRESET: WorkspacePreset = {
  id: 'build',
  title: '构建',
  editors: [
    { editorId: 'build.matrix', placement: tab },
    { editorId: 'build.console', placement: splitBelow },
    { editorId: 'build.profiler', placement: splitRight },
    { editorId: 'build.gates', placement: splitRight },
  ],
};

export const PLAYTEST_PRESET: WorkspacePreset = {
  id: 'playtest',
  title: '试玩测试',
  editors: [
    { editorId: 'playtest.game-view', placement: tab },
    { editorId: 'playtest.agent-monitor', placement: splitRight },
    { editorId: 'playtest.trajectory', placement: splitBelow },
    { editorId: 'issue.browser', placement: splitRight },
  ],
};

export const REVIEW_PRESET: WorkspacePreset = {
  id: 'review',
  title: '评审',
  editors: [
    { editorId: 'review.before-after', placement: tab },
    { editorId: 'changeset.review', placement: splitRight },
    { editorId: 'approval.queue', placement: splitBelow },
    { editorId: 'collaboration.comments', placement: splitLeft },
  ],
};

export const JUDGE_PRESET: WorkspacePreset = {
  id: 'judge',
  title: '评审演示',
  judgeMode: true,
  editors: [
    { editorId: 'assistant.conversation', placement: tab, locked: true, executionMode: 'mock' },
    { editorId: 'scene.viewport.3d', placement: splitRight, locked: true, executionMode: 'mock' },
    { editorId: 'playtest.game-view', placement: splitBelow, locked: true, executionMode: 'mock' },
    { editorId: 'issue.browser', placement: splitRight, executionMode: 'mock' },
  ],
  drawerModes: { left: 'peek', right: 'hidden', top: 'hidden', bottom: 'peek' },
};

export const BUILT_IN_WORKSPACE_PRESETS: WorkspacePreset[] = [
  HOME_PRESET,
  DESIGN_PRESET,
  ASSETS_PRESET,
  CHARACTER_PRESET,
  WORLD_PRESET,
  LOGIC_PRESET,
  RENDER_PRESET,
  BUILD_PRESET,
  PLAYTEST_PRESET,
  REVIEW_PRESET,
  JUDGE_PRESET,
];

export function createDefaultDrawers(
  modes: Partial<Record<Edge, DrawerState['mode']>> = {},
): Record<Edge, DrawerState> {
  return {
    left: createDrawer('left', modes.left),
    right: createDrawer('right', modes.right),
    top: createDrawer('top', modes.top),
    bottom: createDrawer('bottom', modes.bottom),
  };
}

function createDrawer(edge: Edge, mode: DrawerState['mode'] = 'hidden'): DrawerState {
  return {
    edge,
    mode,
    size: 280,
    lastOpenSize: 280,
    tabs: [],
    activeInstanceId: null,
  };
}
