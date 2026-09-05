import test from 'node:test';
import assert from 'node:assert/strict';
import { DockviewPort } from '../DockviewPort.ts';

function instance(instanceId: string, editorId = 'fixture.editor') {
  return {
    instanceId,
    editorId,
    title: editorId,
    localState: null,
    contextBinding: { mode: 'follow-global' as const },
    dirty: false,
    locked: false,
    lifecycle: 'loading' as const,
    executionMode: 'mock' as const,
    regions: [],
  };
}

type FakeGroup = {
  id: string;
  panels: FakePanel[];
  size?: { width?: number; height?: number };
  autoHide: boolean;
  collapsed: boolean;
  api: {
    id: string;
    location: { type: 'grid' | 'edge'; position?: string };
    moveTo: () => void;
    setHeaderPosition: () => void;
    setSize: (size: { width?: number; height?: number }) => void;
    setAutoHide: (value: boolean) => void;
    collapse: () => void;
    expand: () => void;
  };
};
type FakePanel = {
  id: string;
  title: string;
  group: FakeGroup;
  api: {
    close: () => void;
    moveTo: (options: { group: FakeGroup }) => void;
    setTitle: () => void;
    updateParameters: () => void;
    maximize: () => void;
    setActive: () => void;
  };
};

function fakeApi() {
  const closed: string[] = [];
  const additions: Array<{ id: string; groupId: string }> = [];
  const peekCalls: Array<{ edge: string; peek: boolean }> = [];
  const clears: number[] = [];
  const panels = new Map<string, FakePanel>();
  const groups: FakeGroup[] = [];
  const edges = new Map<string, FakeGroup>();
  function createGroup(id: string, edge?: string): FakeGroup {
    const group: FakeGroup = {
      id, panels: [], autoHide: false, collapsed: false,
      api: {
        id, location: edge ? { type: 'edge', position: edge } : { type: 'grid' },
        moveTo: () => undefined,
        setHeaderPosition: () => undefined,
        setSize: (size) => { group.size = size; },
        setAutoHide: (value) => { group.autoHide = value; },
        collapse: () => { group.collapsed = true; },
        expand: () => { group.collapsed = false; },
      },
    };
    groups.push(group);
    return group;
  }
  const api = {
    groups,
    activePanel: undefined as FakePanel | undefined,
    popoutRestorationPromise: Promise.resolve(),
    toJSON: () => ({ grid: { root: { type: 'branch' } } }),
    clear: () => { clears.push(1); panels.clear(); groups.length = 0; edges.clear(); api.activePanel = undefined; },
    fromJSON: () => undefined,
    getPanel: (id: string) => panels.get(id),
    getGroup: (id: string): FakeGroup | undefined => groups.find((group) => group.id === id),
    getEdgeGroup: (edge: string) => edges.get(edge)?.api,
    addEdgeGroup: (edge: string, options: { id: string; autoHide?: boolean; collapsed?: boolean }) => {
      assert.equal(edges.has(edge), false, 'an edge group is created only once');
      const group = createGroup(options.id, edge);
      group.autoHide = options.autoHide ?? false;
      group.collapsed = options.collapsed ?? false;
      edges.set(edge, group);
      return group.api;
    },
    addPanel: (options: { id: string; title: string; position?: { referenceGroup?: string; referencePanel?: string } }): FakePanel => {
      const position = options.position;
      const group = position?.referenceGroup
        ? api.getGroup(position.referenceGroup)!
        : position?.referencePanel
          ? panels.get(position.referencePanel)!.group
          : api.activePanel?.group ?? createGroup('grid');
      const created: FakePanel = {
        id: options.id, title: options.title, group,
        api: {
          close: () => {
            closed.push(created.id);
            created.group.panels.splice(created.group.panels.indexOf(created), 1);
            panels.delete(created.id);
          },
          moveTo: ({ group: destination }) => {
            created.group.panels.splice(created.group.panels.indexOf(created), 1);
            created.group = destination;
            destination.panels.push(created);
          },
          setTitle: () => undefined,
          updateParameters: () => undefined,
          maximize: () => undefined,
          setActive: () => { api.activePanel = created; },
        },
      };
      group.panels.push(created);
      additions.push({ id: created.id, groupId: group.id });
      panels.set(options.id, created);
      api.activePanel = created;
      return created;
    },
    addPopoutGroup: async (_panel?: unknown, _options?: unknown) => true,
    addFloatingGroup: () => undefined,
    peekEdgeGroup: (edge: string, peek: boolean) => { peekCalls.push({ edge, peek }); },
    exitMaximizedGroup: () => undefined,
  };
  api.addPanel({ id: 'original', title: 'original' });
  return { api, panels, closed, additions, edges, peekCalls, clears };
}

test('replace without explicit relative panel closes the pre-add active panel', async () => {
  const { api, closed } = fakeApi();
  const port = new DockviewPort(api as never);
  assert.equal(await port.open(instance('replacement'), { mode: 'replace' }), true);
  assert.deepEqual(closed, ['original']);
});

test('blocked popout closes the newly created panel and returns false', async () => {
  const { api, closed } = fakeApi();
  api.addPopoutGroup = async () => false;
  const port = new DockviewPort(api as never);
  assert.equal(await port.open(instance('popout'), { mode: 'popout' }), false);
  assert.deepEqual(closed, ['popout']);
});

test('drawer placement creates the panel directly in each native edge group', async () => {
  const { api, panels, closed, additions, edges } = fakeApi();
  const port = new DockviewPort(api as never);
  for (const edge of ['left', 'right', 'top', 'bottom'] as const) {
    assert.equal(await port.open(instance(edge), { mode: 'drawer', edge }), true);
    assert.equal(panels.get(edge)?.group, edges.get(edge));
    assert.deepEqual(additions.at(-1), { id: edge, groupId: edges.get(edge)!.id });
    assert.deepEqual(edges.get(edge)?.panels.map((panel) => panel.id), [edge]);
  }
  assert.deepEqual(panels.get('original')?.group.panels.map((panel) => panel.id), ['original']);
  assert.deepEqual(closed, []);
});

test('failed native edge creation does not leave the requested tool in the conversation group', async () => {
  const { api, panels, additions } = fakeApi();
  api.addEdgeGroup = () => { throw new Error('edge group unavailable'); };
  const port = new DockviewPort(api as never);
  await assert.rejects(port.open(instance('drawer'), { mode: 'drawer', edge: 'left' }), /edge group unavailable/);
  assert.equal(panels.has('drawer'), false);
  assert.deepEqual(additions, [{ id: 'original', groupId: 'grid' }]);
});

test('popout bounds use Dockview v8 position options', async () => {
  const { api } = fakeApi();
  let options: unknown;
  api.addPopoutGroup = async (_panel?: unknown, value?: unknown) => {
    options = value;
    return true;
  };
  const port = new DockviewPort(api as never);
  const bounds = { left: 10, top: 20, width: 800, height: 500 };
  assert.equal(await port.open(instance('popout-bounds'), { mode: 'popout', bounds }), true);
  assert.deepEqual(options, { popoutUrl: '/popout.html', position: bounds });
});

test('Peek mode invokes Dockview explicit edge-group peek API', async () => {
  const { api, peekCalls, edges } = fakeApi();
  const port = new DockviewPort(api as never);
  await port.open(instance('drawer-panel'), { mode: 'drawer', edge: 'left' });
  port.syncDrawer({
    edge: 'left', mode: 'peek', size: 280, lastOpenSize: 280,
    tabs: ['drawer-panel'], activeInstanceId: 'drawer-panel',
  });
  assert.deepEqual(peekCalls, [{ edge: 'left', peek: true }]);
  assert.equal(edges.get('left')?.collapsed, true);
  assert.equal(edges.get('left')?.autoHide, true);
  assert.deepEqual(edges.get('left')?.size, { width: 280 });
});

test('drawer replacement and moves preserve its native group, size and pin state', async () => {
  const { api, panels, edges, closed } = fakeApi();
  const port = new DockviewPort(api as never);
  await port.open(instance('library'), { mode: 'drawer', edge: 'left' });
  port.syncDrawer({
    edge: 'left', mode: 'pinned', size: 360, lastOpenSize: 360,
    tabs: ['library'], activeInstanceId: 'library',
  });
  const group = edges.get('left')!;
  api.activePanel = panels.get('original');
  await port.open(instance('tool'), { mode: 'replace', relativeToInstanceId: 'library' });
  assert.deepEqual(closed, ['library']);
  assert.equal(panels.get('tool')?.group, group);
  await port.move(instance('original'), { mode: 'drawer', edge: 'left' });
  await port.move(instance('original'), { mode: 'drawer', edge: 'left' });
  assert.equal(panels.get('original')?.group, group);
  assert.deepEqual(group.panels.map((panel) => panel.id), ['tool', 'original']);
  assert.equal(group.autoHide, false);
  assert.equal(group.collapsed, false);
  assert.deepEqual(group.size, { width: 360 });
});

test('moving an existing tool replaces only the referenced edge tab', async () => {
  const { api, panels, edges, closed } = fakeApi();
  const port = new DockviewPort(api as never);
  await port.open(instance('library'), { mode: 'drawer', edge: 'right' });
  await port.move(instance('original'), { mode: 'replace', relativeToInstanceId: 'library' });
  assert.deepEqual(closed, ['library']);
  assert.equal(panels.get('original')?.group, edges.get('right'));
  assert.deepEqual(edges.get('right')?.panels.map((panel) => panel.id), ['original']);
});

test('invalid Dockview JSON is rebuilt from validated workspace metadata', async () => {
  const { api, panels, clears } = fakeApi();
  api.fromJSON = () => { throw new Error('invalid Dockview snapshot'); };
  const port = new DockviewPort(api as never);
  const assistant = instance('assistant', 'assistant.conversation');
  const status = await port.restoreWorkspace({
    schemaVersion: 3,
    workspaceId: 'home',
    title: 'Home',
    customized: false,
    instances: { assistant },
    areas: [{
      areaId: 'home-area', tabs: ['assistant'], activeInstanceId: 'assistant', headerPosition: 'top',
    }],
    drawers: {
      left: { edge: 'left', mode: 'hidden', size: 280, lastOpenSize: 280, tabs: [], activeInstanceId: null },
      right: { edge: 'right', mode: 'hidden', size: 280, lastOpenSize: 280, tabs: [], activeInstanceId: null },
      top: { edge: 'top', mode: 'hidden', size: 220, lastOpenSize: 220, tabs: [], activeInstanceId: null },
      bottom: { edge: 'bottom', mode: 'hidden', size: 220, lastOpenSize: 220, tabs: [], activeInstanceId: null },
    },
    floatingGroups: [],
    popoutGroups: [],
    activeAreaId: 'home-area',
    maximizedAreaId: null,
    dockviewLayout: { malformed: true },
  });
  assert.equal(status, 'recovered');
  assert.ok(clears.length > 0);
  assert.ok(panels.has('assistant'));
});
