import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import {expect, test} from 'vitest';
import {ProductionPreparationSummary} from '../AgentTaskWorkbench';

Object.assign(globalThis, {IS_REACT_ACT_ENVIRONMENT: true});

test('shows recommendation, copy, source reference, and runtime evidence separately', async () => {
  const host = document.createElement('div');
  document.body.append(host);
  const root = createRoot(host);
  try {
    await act(async () => root.render(<ProductionPreparationSummary value={{
      status: 'succeeded',
      recommendation: {assets: [{candidate_id: 'builtin:cottage', reason: '场景入口'}],
        experiences: [], skills: []},
      materialization: [{candidate_id: 'builtin:cottage', copy_state: 'copied'},
        {candidate_id: 'builtin:tree', state: 'not_provided', reason: 'fixture'}],
      actual_usage: [{candidate_id: 'builtin:cottage', actual_reference: 'referenced',
        reference_paths: ['src/game.ts']}],
      adjustments: [{candidate_id: 'builtin:tree', state: 'provision_failed',
        reason: '源文件不可读取'}],
      runtime_validation: {project_pipeline: 'passed', asset_visual_validation: 'not_verified',
        reason: '需要实际游测'},
    }} />));
    const text = host.textContent ?? '';
    expect(text).toContain('推荐资产 1 项');
    expect(text).toContain('资产提供与复制');
    expect(text).toContain('已复制');
    expect(text).toContain('提供失败');
    expect(text).toContain('实际引用');
    expect(text).toContain('src/game.ts');
    expect(text).toContain('执行调整与缺口');
    expect(text).toContain('源文件不可读取');
    expect(text).toContain('资产画面：未验证');
  } finally {
    await act(async () => root.unmount());
    host.remove();
  }
});
