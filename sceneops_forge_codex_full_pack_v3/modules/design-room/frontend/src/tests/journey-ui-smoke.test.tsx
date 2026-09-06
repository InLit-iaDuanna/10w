import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, test } from 'vitest';
import { MarkdownMessage } from '../../../../../packages/core-ui/frontend/src/MarkdownMessage';
import { PlanningQuestionCard } from '../PlanningQuestionCard';
import { JourneyChangeReview } from '../JourneyChangeReview';
import { CardModelingEntry } from '../CardModelingEntry';
import { ExistingProjectAdoptionNotice } from '../PlanningJourney';
import type { PlanningJourney } from '../journey-client';
Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

test('unadopted copied project is visible and requires an explicit next flow', async () => {
  const host = document.createElement('div');
  const root = createRoot(host);
  let opened = 0;
  try {
    await act(async () => root.render(<ExistingProjectAdoptionNotice fallback={<span>对话</span>}
      onOpenProjects={() => { opened += 1; }} />));
    expect(host.textContent).toContain('尚未采用为可开发工程');
    expect(host.textContent).toContain('不会自动提交、重建或复制');
    await act(async () => host.querySelector('button')!.click());
    expect(opened).toBe(1);
  } finally { await act(async () => root.unmount()); }
});

test('model source entry uses explicit choices without another composer or fake upload', async () => {
  const host = document.createElement('div');
  const root = createRoot(host);
  const operations: string[] = [];
  let environmentOpens = 0;
  const state = {
    active_card_id: 'world-3d',
    active_modeling_id: null,
    cards: [{
      id: 'world-3d',
      title: '3D 世界',
      description: '场景、资产、模型与摆放共用一个工作流。',
      acceptance: '可以进入统一 3D 工作区。',
      dependencies: [],
      status: 'planned',
    }],
    modeling_sessions: [],
  } as unknown as PlanningJourney;
  try {
    await act(async () => root.render(<CardModelingEntry state={state} busy={false} onCommand={op => operations.push(op)} />));
    expect(host.querySelectorAll('textarea')).toHaveLength(0);
    expect(operations).toEqual([]);
    expect(host.textContent).toContain('新建模型');
    await act(async () => host.querySelector('button')!.click());
    expect(operations).toEqual(['choose_model_source']);
    await act(async () => root.render(<CardModelingEntry state={{ ...state, active_modeling_id: 'session', modeling_sessions: [{id:'session',card_id:'world-3d',source:'import',stage:'awaiting_import',messages:[],composer_draft:'',mode:'planned'}] }} busy={false} onCommand={() => {}} onOpenEnvironment={() => { environmentOpens += 1; }} />));
    expect(host.textContent).toContain('在右侧选择 GLB 或 FBX');
    expect(host.querySelector('input[type=file]')).toBeNull();
    const back = [...host.querySelectorAll('button')].find(button => button.textContent === '返回 3D 世界')!;
    await act(async () => back.click());
    expect(environmentOpens).toBe(1);
  } finally { await act(async () => root.unmount()); }
});

test('change proposal previews both sides and requires explicit adoption', async () => {
  const host = document.createElement('div');
  document.body.append(host);
  const root = createRoot(host);
  const choices: boolean[] = [];
  try {
    await act(async () => root.render(<JourneyChangeReview disabled={false} onResolve={accept => choices.push(accept)} change={{
      id:'change_fixture',base_revision:1,before_outline:null,after_outline:null,rationale:'改成森林',status:'pending',
      before_cards:[{id:'map',title:'旧地图',description:'平原',acceptance:'可行走',dependencies:[],status:'planned'}],
      after_cards:[{id:'map',title:'森林地图',description:'森林',acceptance:'可行走',dependencies:[],status:'planned'}],
    }} />));
    expect(host.textContent).toContain('旧地图');
    expect(host.textContent).toContain('森林地图');
    expect(choices).toEqual([]);
    const accept = [...host.querySelectorAll('button')].find(button => button.textContent === '确认采用修改')!;
    await act(async () => accept.click());
    expect(choices).toEqual([true]);
  } finally { await act(async () => root.unmount()); host.remove(); }
});

test('Markdown is real semantic content and does not execute HTML or load remote images', async () => {
  const host = document.createElement('div');
  document.body.append(host);
  const root = createRoot(host);
  try {
    await act(async () => root.render(<MarkdownMessage text={'## 标题\n\n**重点**\n\n- 第一项\n\n| 名称 | 状态 |\n| --- | --- |\n| 地图 | 待制作 |\n\n<script>alert(1)</script>\n\n![image](https://example.invalid/private)'} />));
    expect(host.querySelector('h2')?.textContent).toBe('标题');
    expect(host.querySelector('strong')?.textContent).toBe('重点');
    expect(host.querySelector('table')).not.toBeNull();
    expect(host.querySelector('script')).toBeNull();
    expect(host.querySelector('img')).toBeNull();
  } finally { await act(async () => root.unmount()); host.remove(); }
});

test('one selectable question requires explicit confirmation; custom answer uses the main composer', async () => {
  const host = document.createElement('div');
  document.body.append(host);
  const root = createRoot(host);
  const answers: number[] = [];
  let custom = false;
  try {
    await act(async () => root.render(<PlanningQuestionCard question={{prompt:'先确定哪种玩法？', recommended_index:0,
      options:[{label:'探索',description:'寻找出口'},{label:'战斗',description:'击败怪兽'}]}}
      disabled={false} answered={false} onAnswer={index => answers.push(index)} onCustom={() => { custom = true; }} />));
    expect(host.querySelectorAll('[role=radiogroup]')).toHaveLength(1);
    const radios = host.querySelectorAll<HTMLInputElement>('input[type=radio]');
    expect(radios[0].checked).toBe(true);
    await act(async () => radios[1].click());
    expect(answers).toEqual([]);
    const buttons = host.querySelectorAll('button');
    await act(async () => buttons[0].click());
    expect(custom).toBe(true);
    expect(host.querySelectorAll('textarea')).toHaveLength(0);
    await act(async () => buttons[1].click());
    expect(answers).toEqual([1]);
  } finally { await act(async () => root.unmount()); host.remove(); }
});
