import {test} from 'node:test';
import assert from 'node:assert/strict';
import {launchLatestGame} from '../launchLatestGame';

test('latest game starts its current build, rebuilds stale source, and rejects active production',async()=>{
 const calls:string[]=[];
 const task={id:'new',created_at:'2026-09-09',status:'review_required',grant:{},owner_pid:null,authorization_card:{allow_game_execution:true,task_profile:'project-demo-agent'}};
 let state:any={build:{id:'build-new',status:'succeeded',source_stale:false},preview:null};
 const runtime:any={list:async()=>({tasks:[{...task,id:'old',created_at:'2026-09-08'},task]}),
  gameStatus:async(id:string)=>{assert.equal(id,'new');return state;},
  gameOperation:async(id:string,op:string)=>{calls.push(`${id}:${op}`);return {preview:{status:'running',preview_url:'http://127.0.0.1:9000'}};},
  updateProjectDemo:async(id:string)=>{calls.push(`${id}:update`);return {id:'rebuilt'};}};
 assert.equal(await launchLatestGame('project',runtime),'new');
 assert.deepEqual(calls,['new:preview_start']);
 state.build.source_stale=true;
 assert.equal(await launchLatestGame('project',runtime),'rebuilt');
 task.status='running';
 await assert.rejects(launchLatestGame('project',runtime),/正在制作/);
 assert.deepEqual(calls,['new:preview_start','new:update']);
});
