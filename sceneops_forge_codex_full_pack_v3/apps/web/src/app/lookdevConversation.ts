import type { DomainConversationPort } from '@sceneops/core-ui';
import type { LookdevConversationSession } from '@sceneops/vfx-shader-frontend';

/** Sessions belong to editor instances; focus selects which one the main composer targets. */
export function createLookdevConversation() {
  const sessions = new Map<string,LookdevConversationSession>();
  const listeners = new Set<() => void>();
  let owner: string | null = null;
  let current: DomainConversationPort | null = null;
  let dismissed = false;
  const notify = () => {for (const listener of listeners) listener();};
  function publish() {
    const session = owner ? sessions.get(owner) : undefined;
    current = session ? {...session,clear(){owner=null;current=null;dismissed=true;notify();}} : null;
    notify();
  }
  return {
    update(instanceId:string, session:LookdevConversationSession | null) {
      if (!session) {sessions.delete(instanceId);if(owner===instanceId){owner=null;publish();}return;}
      sessions.set(instanceId,session);
      if(owner===instanceId) publish();
      else if(!owner && !dismissed){owner=instanceId;publish();}
    },
    activate(instanceId:string) {dismissed=false;owner=instanceId;publish();},
    clear() {owner=null;current=null;dismissed=true;notify();},
    snapshot:()=>current,
    subscribe(listener:()=>void) {listeners.add(listener);return()=>{listeners.delete(listener);};},
  };
}
