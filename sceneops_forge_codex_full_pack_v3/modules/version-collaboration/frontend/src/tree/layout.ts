import type { GitBranch, GitCommit } from '../generated/api-types.ts';

/** Git's child-before-parent topological order is reversed for downward growth. */
export function layoutTree(commits: readonly GitCommit[], branches: readonly GitBranch[] = [], availableWidth = 640) {
  const lanes: (string | null)[] = [];
  const positions = new Map<string, { x: number; y: number; lane: number }>();
  for (const [index, commit] of commits.entries()) {
    let lane = lanes.indexOf(commit.commit_id);
    if (lane < 0) {
      lane = lanes.indexOf(null);
      if (lane < 0) lane = lanes.length;
    }
    lanes[lane] = null;
    positions.set(commit.commit_id, { x: 70 + lane * 240, y: 116 + (commits.length - 1 - index) * 92, lane });
    for (const [parentIndex, parent] of (commit.parent_ids ?? []).entries()) {
      if (lanes.includes(parent)) continue;
      let slot = parentIndex === 0 ? lane : lanes.indexOf(null);
      if (slot < 0 || lanes[slot]) slot = lanes.length;
      lanes[slot] = parent;
    }
  }
  // Reserve complete rows for branch labels before laying out the next commit.
  // Width comes from the editor viewport, not the browser window.
  const width = Math.max(280, availableWidth);
  const columns = Math.max(1, Math.floor((width - 64) / 248));
  const branchTips: { branch: GitBranch; x: number; y: number }[] = [];
  let y = 130;
  for (const commit of [...commits].reverse()) {
    const point = positions.get(commit.commit_id)!;
    point.x = 38 + Math.min(point.lane * 16, Math.max(0, width - 278));
    point.y = y;
    const refs = branches.filter(branch => branch.commit_id === commit.commit_id)
      .sort((a, b) => Number(b.current) - Number(a.current) || a.name.localeCompare(b.name));
    refs.forEach((branch, index) => branchTips.push({ branch,
      x: 54 + (index % columns) * 248, y: y + 86 + Math.floor(index / columns) * 76 }));
    y += 108 + Math.ceil(refs.length / columns) * 76;
  }
  const commitIds = new Set(commits.map(commit => commit.commit_id));
  const roots = commits.filter(commit => !commit.parent_ids?.length || commit.parent_ids.every(parent => !commitIds.has(parent)));
  return {
    positions,
    branchTips,
    roots,
    project: { x: 38, y: 42 },
    width,
    height: Math.max(320, y + 12),
  };
}
