import assert from 'node:assert/strict';
import test from 'node:test';
import { createDemoProject } from '../src/core/lookdev.ts';
import { editLookdev, moveLookdevHistory } from '../src/lookdev-history.ts';
test('material editing preserves identity and undo/redo restores exact project states', () => {
  const project=createDemoProject(); const initial={past:[],present:project,future:[]};
  const changed=editLookdev(initial,[{kind:'material.update',targetId:'mat-shell',patch:{roughness:.25}}],'manual','磨砂调整');
  assert.equal(changed.present.materials[0].roughness,.25);
  assert.deepEqual(changed.present.objects,project.objects);
  const undone=moveLookdevHistory(changed,'undo');
  assert.equal(undone.present,project);
  assert.equal(moveLookdevHistory(undone,'redo').present,changed.present);
});
test('out-of-scope AI operations fail without changing the current project', () => {
  const project=createDemoProject();const initial={past:[],present:project,future:[]};
  assert.throws(()=>editLookdev(initial,[{kind:'material.update',targetId:'mat-glass',patch:{roughness:.25}}],'ai','修改',{materialIds:['mat-shell'],lightIds:[],lighting:false}),/范围/);
  assert.equal(initial.present,project);
  assert.equal(initial.past.length,0);
});

test('saved history restores undo and redo snapshots and rejects another asset', async () => {
  const {storeLookdevHistory,restoreLookdevHistory}=await import('../src/lookdev-history.ts');
  const project=createDemoProject();
  const changed=editLookdev({past:[],present:project,future:[]},[{kind:'material.update',targetId:'mat-shell',patch:{roughness:.3}}],'manual','edit');
  const records=JSON.parse(JSON.stringify(storeLookdevHistory(changed)));
  const restored=restoreLookdevHistory(changed.present,records);
  assert.equal(moveLookdevHistory(restored,'undo').present.materials[0].roughness,project.materials[0].roughness);
  records[0].past[0].objects[0].id='another-asset-object';
  assert.throws(()=>restoreLookdevHistory(changed.present,records),/绑定/);
});
