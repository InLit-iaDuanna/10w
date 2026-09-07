import assert from 'node:assert/strict';
import { test } from 'node:test';
import { initialDirectionDraft } from '../initial-direction-draft.ts';
import type { PlanningJourney } from '../journey-client';

test('direction draft reuses actual user context without guessing architecture or fixture content', () => {
  const state = {messages:[{role:'user',text:'做一个在海底收集珍珠的游戏'},
    {role:'assistant',text:'推荐 ECS 和两扇门'}]} as PlanningJourney;
  assert.deepEqual(initialDirectionDraft(state),{core_experience:'做一个在海底收集珍珠的游戏',
    perspective_style:'',simplified_scope:'',code_architecture:null});
  assert.deepEqual(initialDirectionDraft(),{core_experience:'',perspective_style:'',simplified_scope:'',code_architecture:null});
});

test('structured outline and explicit architecture are reusable draft values', () => {
  const state = {outline:{experience:'躲避风暴',scope:'只做一个岛屿'},
    technical_plan:{code_architecture:'ecs'}} as PlanningJourney;
  assert.deepEqual(initialDirectionDraft(state),{core_experience:'躲避风暴',
    perspective_style:'',simplified_scope:'只做一个岛屿',code_architecture:'ecs'});
  assert.equal(state.initial_demo_direction, undefined);
});

test('saved direction takes precedence and long conversation is a bounded excerpt', () => {
  const state = {initial_demo_direction:{core_experience:'已保存体验',perspective_style:'俯视',
    simplified_scope:'单关',code_architecture:'object-component'},outline:{experience:'旧策划'}} as PlanningJourney;
  assert.equal(initialDirectionDraft(state).core_experience, '已保存体验');
  assert.equal(initialDirectionDraft({messages:[{role:'user',text:'文'.repeat(1200)}]} as PlanningJourney).core_experience.length, 1000);
});
