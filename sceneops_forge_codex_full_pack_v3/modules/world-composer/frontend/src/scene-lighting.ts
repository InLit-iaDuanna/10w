import * as THREE from 'three/webgpu';
import type {SceneLighting} from './environment-client';

export function applySceneLighting(scene:THREE.Scene,renderer:{toneMappingExposure:number},settings:SceneLighting) {
  scene.background=new THREE.Color(settings.background??'#1b1b1b');
  renderer.toneMappingExposure=settings.exposure??1;
  for(const state of settings.lights??[]) {
    const light=state.type==='ambient'?new THREE.AmbientLight(state.color,state.intensity)
      :state.type==='hemisphere'?new THREE.HemisphereLight(state.color,state.ground_color,state.intensity)
      :state.type==='directional'?new THREE.DirectionalLight(state.color,state.intensity)
      :state.type==='point'?new THREE.PointLight(state.color,state.intensity,state.distance)
      :new THREE.SpotLight(state.color,state.intensity,state.distance,state.angle,state.penumbra);
    light.name=state.name;light.userData.sceneops_id=state.id;light.visible=state.enabled??true;
    light.position.fromArray(state.type==='hemisphere'?(state.sky_direction??[0,1,0]):(state.position??[0,0,0]));
    if(light instanceof THREE.DirectionalLight||light instanceof THREE.SpotLight){light.target.position.fromArray(state.target??[0,0,0]);scene.add(light.target);}
    if(state.shadow&&(light instanceof THREE.DirectionalLight||light instanceof THREE.PointLight||light instanceof THREE.SpotLight)){
      light.castShadow=true;light.shadow.mapSize.set(state.shadow.map_size??1024,state.shadow.map_size??1024);
      light.shadow.camera.near=state.shadow.near??1;light.shadow.camera.far=state.shadow.far??60;
      light.shadow.bias=state.shadow.bias??0;light.shadow.normalBias=state.shadow.normal_bias??0;
      if(light instanceof THREE.DirectionalLight){const extent=state.shadow.extent??14;Object.assign(light.shadow.camera,{left:-extent,right:extent,top:extent,bottom:-extent});}
    }
    scene.add(light);
  }
}
