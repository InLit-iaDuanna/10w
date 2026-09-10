/** Copy into the existing Three.js game, not the React workbench DOM. */
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {AtlasRuntime} from './atlas-runtime.mjs';
export async function addAtlasScene({scene,camera,sceneId='atlas100-s001',baseURL='/builtin/atlas100-v2/',onEvent}){
  const runtime=new AtlasRuntime({THREE,loader:new GLTFLoader(),scene,camera,baseURL,onEvent});
  const catalog=await runtime.json('catalog.json');const manifest=await runtime.json(`scenes/${sceneId}.json`);
  await runtime.loadScene(manifest,catalog);
  // In your existing loop: runtime.update(deltaSeconds). Do not create another render loop.
  // Bind actual player input with reach checks, e.g.:
  // runtime.interact(instanceId,'equip',{actorPosition:player.position,mount:rightHandSocket});
  // runtime.interact(instanceId,'use',{actorPosition:player.position});
  // runtime.interact(instanceId,'drop',{actorPosition:player.position,velocity:[0,1,2]});
  return runtime;
}
