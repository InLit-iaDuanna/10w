import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createOpenLookdevCommand} from '../src/lookdev-open-command';
test('Open capability fixes project and validates asset versions',()=>{
  const command=createOpenLookdevCommand(async()=>{});
  assert.equal(command.validate({projectId:'p',target:{assetId:'a',assetVersion:2}}),true);
  assert.equal(command.validate({projectId:'p',target:{assetVersion:0}}),false);
  assert.equal(command.validate({projectId:'p',target:{materialSlot:0.5}}),false);
  const context={workbench:{projectId:'other'},permissions:new Set(),connectedIntegrations:new Set(),source:'button'} as Parameters<typeof command.canExecute>[0];
  assert.equal(command.canExecute(context,{projectId:'p',target:{}}).available,false);
});
