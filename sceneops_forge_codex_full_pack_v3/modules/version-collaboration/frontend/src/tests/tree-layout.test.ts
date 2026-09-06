import { test } from 'node:test';
import assert from 'node:assert/strict';
import { layoutTree } from '../tree/layout.ts';
const commit = (id: string, parents: string[]) => ({ commit_id: id, parent_ids: parents, author: 'fixture', authored_at: '2026-09-06T00:00:00Z', subject: id });
test('version tree keeps branches distinct and parents above merges', () => {
  const commits = [commit('merge', ['main', 'feature']), commit('feature', ['root']), commit('main', ['root']), commit('root', [])];
  const { positions } = layoutTree(commits);
  assert.notEqual(positions.get('feature')!.x, positions.get('main')!.x);
  for (const item of commits) for (const parent of item.parent_ids) assert.ok(positions.get(parent)!.y < positions.get(item.commit_id)!.y);
});
test('empty and truncated history do not invent parent nodes', () => {
  assert.equal(layoutTree([]).positions.size, 0);
  assert.equal(layoutTree([commit('tip', ['outside'])]).positions.has('outside'), false);
});

test('project branches remain separate when they point to the same commit', () => {
  const branches = [
    { name: 'feature/world', commit_id: 'root', current: false },
    { name: 'feature/gameplay', commit_id: 'root', current: true },
  ];
  const graph = layoutTree([commit('root', [])], branches);
  assert.equal(graph.branchTips.length, 2);
  assert.notEqual(graph.branchTips[0].x, graph.branchTips[1].x);
  assert.ok(graph.branchTips.every(tip => tip.y > graph.positions.get('root')!.y));
});

test('responsive tree keeps every branch inside the pane and reserves rows before later commits', () => {
  const branches = Array.from({ length: 5 }, (_, index) => ({ name: `feature/${index}`, commit_id: 'root', current: index === 0 }));
  for (const width of [300, 440, 1000]) {
    const graph = layoutTree([commit('tip', ['root']), commit('root', [])], branches, width);
    for (const tip of graph.branchTips) {
      assert.ok(tip.x - 16 >= 0 && tip.x + 204 <= graph.width);
      assert.ok(tip.y + 36 < graph.positions.get('tip')!.y - 27);
    }
    for (const [index, a] of graph.branchTips.entries()) for (const b of graph.branchTips.slice(index + 1)) {
      assert.ok(Math.abs(a.x - b.x) >= 220 || Math.abs(a.y - b.y) >= 60);
    }
  }
});
