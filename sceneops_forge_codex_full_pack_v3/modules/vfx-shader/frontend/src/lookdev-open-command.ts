import type { WorkbenchCommandDefinition } from '@sceneops/core-ui';
import type { LookdevEditorState } from './lookdev-contract';
export interface OpenLookdevInput { projectId:string; target:LookdevEditorState; relativeToInstanceId?:string }
/** Host supplies docking; every caller shares the same typed, project-bound entry. */
export function createOpenLookdevCommand(open:(input:OpenLookdevInput)=>Promise<void>):WorkbenchCommandDefinition<OpenLookdevInput,void>{
  return {id:'lookdev.open',title:'编辑材质',requiredPermissions:['workbench:write','vfx:read'],
    validate(value):value is OpenLookdevInput {
      if(!value || typeof value!=='object')return false;
      const input=value as OpenLookdevInput;
      if(typeof input.projectId!=='string'||!input.projectId||!input.target||typeof input.target!=='object')return false;
      const target=input.target;
      return (input.relativeToInstanceId===undefined||typeof input.relativeToInstanceId==='string')
        && ['assetId','assetTitle','sceneInstanceId','sceneopsId'].every(key=>target[key as keyof LookdevEditorState]===undefined||typeof target[key as keyof LookdevEditorState]==='string')
        && ['assetVersion','sceneVersion','materialSlot'].every(key=>{const n=target[key as keyof LookdevEditorState];return n===undefined||(typeof n==='number'&&Number.isInteger(n)&&n>=(key==='assetVersion'?1:0));});
    },
    canExecute(context,input){return context.workbench.projectId===input.projectId?{available:true}:{available:false,reason:'材质目标不属于当前项目。'};},
    execute:(_context,input)=>open(input),
  };
}
