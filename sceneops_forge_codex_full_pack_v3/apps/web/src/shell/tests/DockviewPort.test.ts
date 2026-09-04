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

function fakeApi() {
  const closed: string[] = [];
  const edgeMoves: Array<{ edge: string; panelId: string }> = [];
  const peekCalls: Array<{ edge: string; peek: boolean }> = [];
  const clears: number[] = [];
  const panels = new Map<string, ReturnType<typeof panel>>();
  const api = {
    groups: [] as ReturnType<typeof panel>['group'][],
    activePanel: undefined as ReturnType<typeof panel> | undefined,
    popoutRestorationPromise: Promise.resolve(),
    toJSON: () => ({ grid: { root: { type: 'branch' } } }),
    clear: () => { clears.push(1); panels.clear(); },
    fromJSON: () => undefined,
    getPanel: (id: string) => panels.get(id),
    addPanel: (options: { id: string; title: string }) => {
      const created = panel(options.id, options.title, closed);
      panels.set(options.id, created);
      api.activePanel = created;
      return created;
    },
    addPopoutGroup: async (_panel?: unknown, _options?: unknown) => true,
    addFloatingGroup: () => undefined,
    revealEdgeGroupWithData: (edge: string, data: { panelId: string }) => {
      edgeMoves.push({ edge, panelId: data.panelId });
    },
    peekEdgeGroup: (edge: string, peek: boolean) => { peekCalls.push({ edge, peek }); },
    exitMaximizedGroup: () => undefined,
  };
  const original = panel('original', 'original', closed);
  panels.set('original', original);
  api.activePanel = original;
  return { api, panels, closed, edgeMoves, peekCalls, clears };
}

function panel(id: string, title: string, closed: string[]) {
  const group = { api: { moveTo: () => undefined, setHeaderPosition: () => undefined } };
  return {
    id,
    title,
    group,
    api: {
      group,
      close: () => closed.push(id),
      moveTo: () => undefined,
      setTitle: () => undefined,
      updateParameters: () => undefined,
      maximize: () => undefined,
      setActive: () => undefined,
    },
  };
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

test('drawer placement transfers the live panel to a Dockview edge group', async () => {
  const { api, closed, edgeMoves } = fakeApi();
  const port = new DockviewPort(api as never);
  assert.equal(await port.open(instance('drawer'), { mode: 'drawer', edge: 'left' }), true);
  assert.deepEqual(edgeMoves, [{ edge: 'left', panelId: 'drawer' }]);
  assert.deepEqual(closed, []);
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

test('Peek mode invokes Dockview explicit edge-group peek API', () => {
  const { api, panels, peekCalls } = fakeApi();
  const drawerPanel = panel('drawer-panel', 'drawer', []);
  Object.assign(drawerPanel.group, { id: 'edge-left' });
  Object.assign(drawerPanel.group.api, {
    location: { type: 'edge', position: 'left' },
    setSize: () => undefined,
    setAutoHide: () => undefined,
    collapse: () => undefined,
    expand: () => undefined,
  });
  panels.set(drawerPanel.id, drawerPanel);
  api.groups.push(drawerPanel.group);
  const port = new DockviewPort(api as never);
  port.syncDrawer({
    edge: 'left', mode: 'peek', size: 280, lastOpenSize: 280,
    tabs: [drawerPanel.id], activeInstanceId: drawerPanel.id,
  });
  assert.deepEqual(peekCalls, [{ edge: 'left', peek: true }]);
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
