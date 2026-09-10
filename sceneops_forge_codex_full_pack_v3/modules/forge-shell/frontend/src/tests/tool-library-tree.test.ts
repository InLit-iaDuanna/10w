import test from 'node:test';
import assert from 'node:assert/strict';
import type { EditorDefinition } from '../contracts.ts';
import { createToolLibraryTree } from '../components/tool-library-tree.ts';

function editor(id: string, title = id): EditorDefinition {
  return {
    id,
    title,
    icon: 'fixture',
    category: 'fixture',
    load: async () => ({ default: () => null }),
    defaultPlacement: { mode: 'tab' },
    initialState: () => ({}),
    serializeState: state => state,
    restoreState: value => value,
  };
}

const flowIds = [
  'workbench.project-planning',
  'workbench.concept-assets',
  'workbench.character-animation',
  'workbench.world-logic',
  'workbench.ui-audio-vfx',
  'workbench.render-ops',
  'workbench.unity-build',
  'workbench.ai-playtest',
  'workbench.version-review',
];

test('tool library keeps the game-production nodes in canonical order', () => {
  const tree = createToolLibraryTree(flowIds.map(id => editor(id)));
  const production = tree.find(branch => branch.id === 'production-flow');
  assert.deepEqual(production?.nodes.map(node => node.id), flowIds);
  assert.deepEqual(production?.nodes.map(node => node.title), [
    '需求规划', '概念与资产', '角色与动画', '世界与逻辑', '界面、音频与特效', '渲染', 'Unity 构建', 'AI 游测', '版本评审',
  ]);
});

test('search retains the readable parent branch and supports phase names', () => {
  const tree = createToolLibraryTree([
    editor('workbench.unity-build', 'Unity 与构建'),
    editor('assistant.conversation', '对话'),
  ], '构建');
  assert.equal(tree.length, 1);
  assert.equal(tree[0]?.title, '游戏生产流程');
  assert.deepEqual(tree[0]?.nodes.map(node => node.id), ['workbench.unity-build']);
  assert.equal(tree[0]?.nodes[0]?.sequence, 7);
});

test('unclassified registered tools remain available under an auxiliary branch', () => {
  const tree = createToolLibraryTree([editor('fixture.extra', '扩展调试器')]);
  assert.deepEqual(tree.map(branch => branch.id), ['additional-tools']);
  assert.equal(tree[0]?.nodes[0]?.editor.id, 'fixture.extra');
});

test('a progressive catalog hides registered tools that are not released yet', () => {
  const tree = createToolLibraryTree([
    editor('journey.modeling', '模型与资产'),
    editor('journey.environment', '环境场景'),
    editor('workbench.ai-playtest', 'AI 游测'),
  ], '', {
    title: '当前制作',
    description: '只显示当前旅程已经接通的工具。',
    entries: [
      { editorId: 'journey.modeling', title: '模型与资产', description: '导入或新建模型。' },
      { editorId: 'journey.environment', title: '环境场景', description: '人工或 AI 搭建。' },
    ],
  });
  assert.deepEqual(tree.map(branch => branch.id), ['current-workflow']);
  assert.deepEqual(tree[0]?.nodes.map(node => node.id), ['journey.modeling', 'journey.environment']);
});

test('catalog groups preserve order and never expose unregistered entries', () => {
  const catalog = {title:'项目工具',description:'fixture',entries:[
    {editorId:'journey.planning',title:'策划与制作卡片',description:'',group:'策划与制作'},
    {editorId:'journey.source',title:'架构与源码',description:'',group:'游戏内容'},
    {editorId:'journey.missing',title:'未接通',description:'',group:'游戏内容'},
    {editorId:'journey.game-preview',title:'游戏试玩',description:'',group:'试玩与版本'},
  ]};
  const entries = ['journey.planning','journey.source','journey.game-preview'].map(id=>editor(id));
  const tree=createToolLibraryTree(entries,'',catalog);
  assert.deepEqual(tree.map(group=>group.title),['策划与制作','游戏内容','试玩与版本']);
  assert.deepEqual(tree.flatMap(group=>group.nodes.map(node=>node.id)),entries.map(item=>item.id));
  assert.deepEqual(createToolLibraryTree(entries,'源码',catalog).map(group=>group.title),['游戏内容']);
});
