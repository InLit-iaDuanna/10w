/** Three.js integration via dependency injection: uses the host's THREE and GLTFLoader.
 * Explicit initialization only. No automatic scene replacement, SQL writes, or network providers.
 */
import {PropWorld,sub,finite3} from './physics-core.mjs';
const asArray=v=>Array.isArray(v)?v:[v.x,v.y,v.z];
export class AtlasRuntime{
  constructor({THREE,loader,scene,camera,baseURL,fetcher=fetch,onEvent=()=>{}}){
    if(!THREE||!loader||!scene||!camera)throw new Error('THREE, GLTFLoader, scene and camera are required');
    this.T=THREE;this.loader=loader;this.scene=scene;this.camera=camera;
    this.baseURL=new URL(baseURL,globalThis.location?.href??'http://127.0.0.1/');this.fetcher=fetcher;this.onEvent=onEvent;
    this.world=new PropWorld();this.instances=new Map();this.textureCache=new Map();this.paused=false;this.disposed=false;
  }
  url(path){if(typeof path!=='string'||path.startsWith('/')||path.includes('..')||/^[a-z]+:/i.test(path))throw new Error('Unsafe pack path');
    const u=new URL(path,this.baseURL);if(!u.href.startsWith(this.baseURL.href))throw new Error('Escaping pack root');return u.href;}
  async json(path){const r=await this.fetcher(this.url(path));if(!r.ok)throw new Error(`Cannot read ${path}: ${r.status}`);return r.json();}
  async addAsset(asset,{id=asset.id,position=[0,0,0],rotation=[0,0,0],scale=[1,1,1]}={}){
    if(this.disposed)throw new Error('Runtime disposed');if(this.instances.has(id))throw new Error('Duplicate instance ID');
    finite3(position);finite3(rotation);finite3(scale);if(scale.some(s=>s<=0))throw new Error('Nonpositive scale');
    if(Math.max(...scale)-Math.min(...scale)>1e-6)throw new Error('Physics requires uniform asset scale');
    const T=this.T,binding=await this.json(asset.physics_binding);const group=new T.LOD();group.name=id;group.position.fromArray(position);group.rotation.set(...rotation);group.scale.fromArray(scale);
    const item={id,asset,binding,group,levels:[],mixers:[],actions:new Map(),body:null,held:false,lightOn:true,open:false,active:false};
    try{
      // Separate parser results preserve independent skeletons; naive scene.clone() is unsafe for skins.
      for(const level of asset.lods){const gltf=await this.loader.loadAsync(this.url(level.path));
        gltf.scene.traverse(n=>{if(n.userData?.sceneops_id){n.userData.source_sceneops_id=n.userData.sceneops_id;n.userData.sceneops_id=n.userData.sceneops_id.replace(asset.id,id);}n.userData.atlas_instance_id=id;});
        group.addLevel(gltf.scene,level.distance_m*Math.max(...scale),.12);item.levels.push(gltf.scene);
        const mixer=new T.AnimationMixer(gltf.scene);item.mixers.push(mixer);
        for(const clip of gltf.animations){const a=mixer.clipAction(clip);if(!item.actions.has(clip.name))item.actions.set(clip.name,[]);item.actions.get(clip.name).push(a);}
      }
      this.scene.add(group);group.updateMatrixWorld(true);
      item.body=this.world.addBody({id,position,mode:binding.body.mode,mass:binding.body.mass_kg,sleeping:binding.body.initially_sleeping,linearDamping:binding.body.linear_damping,gravityScale:binding.body.gravity_scale,colliders:[]});
      this.instances.set(id,item);this.syncColliders(item);this.promoteMaterials(item);
      this.onEvent({type:'asset_added',sceneops_id:id,asset_id:asset.id});return item;
    }catch(error){for(const mixer of item.mixers)mixer.stopAllAction();group.removeFromParent();this.disposeObject(group);this.world.removeBody(id);this.instances.delete(id);throw error;}
  }
  promoteMaterials(item){
    const T=this.T;if(!T.TextureLoader)return;const loader=new T.TextureLoader(),replaced=new Set(),cached=new Set(this.textureCache.values());
    item.group.traverse(node=>{if(!node.material)return;for(const m of Array.isArray(node.material)?node.material:[node.material]){
      const role=m.name.split('_').at(-1);if(!['body','ivory','accent','glow','shadow'].includes(role))continue;
      const image=(channel,color)=>{const path=`textures/${item.asset.style}/${role}/${channel}.png`;
        if(!this.textureCache.has(path)){const t=loader.load(this.url(path),undefined,undefined,error=>this.onEvent({type:'texture_failed',path,error:String(error)}));
          t.flipY=false;t.wrapS=t.wrapT=T.RepeatWrapping;if(color)t.colorSpace=T.SRGBColorSpace;this.textureCache.set(path,t);}return this.textureCache.get(path);};
      for(const key of ['map','normalMap','roughnessMap','metalnessMap','aoMap','emissiveMap'])if(m[key]&&!cached.has(m[key])&&!new Set(this.textureCache.values()).has(m[key]))replaced.add(m[key]);
      m.map=image('basecolor',true);m.normalMap=image('normal',false);m.roughnessMap=m.metalnessMap=m.aoMap=image('orm',false);m.emissiveMap=image('emissive',true);m.needsUpdate=true;
    }});
    for(const texture of replaced)texture.dispose();
  }
  syncColliders(item){
    const T=this.T,group=item.group;group.updateMatrixWorld(true);const origin=group.getWorldPosition(new T.Vector3());
    const joints=new Map();item.levels[0].traverse(n=>{if(n.userData?.joint_role)joints.set(n.userData.joint_role,n);});
    item.body.colliders=item.binding.colliders.map(c=>{
      let matrix=group.matrixWorld.clone();const j=c.joint==null?null:item.binding.rig.joints[c.joint];
      if(j&&joints.has(j.name)){matrix=joints.get(j.name).matrixWorld.clone();matrix.multiply(new T.Matrix4().makeTranslation(...j.pivot.map(x=>-x)));}
      const center=new T.Vector3(...c.center_m).applyMatrix4(matrix);const axes=[],half=[];
      for(let i=0;i<3;i++){const axis=new T.Vector3(...c.axes[i]);const transformed=axis.clone().applyMatrix3(new T.Matrix3().setFromMatrix4(matrix));
        const size=transformed.length();axes.push(transformed.normalize().toArray());half.push(c.half_extents_m[i]*size);}
      return {id:c.id,center:sub(center.toArray(),origin.toArray()),axes,half};
    });
    item.body.position=origin.toArray();
  }
  play(item,name,{loop=false}={}){
    const actions=item.actions.get(name);if(!actions)throw new Error(`No animation '${name}' for ${item.asset.id}`);
    for(const m of item.mixers)m.stopAllAction();for(const a of actions){a.reset();a.clampWhenFinished=!loop;a.setLoop(loop?this.T.LoopRepeat:this.T.LoopOnce,loop?Infinity:1);a.play();}
    return name;
  }
  interact(id,action,{actorPosition,mount,velocity=[0,0,0]}={}){
    const item=this.instances.get(id);if(!item)throw new Error('Unknown instance');
    if(!item.binding.interaction.actions.includes(action))throw new Error(`Unsupported action: ${action}`);
    if(!actorPosition)throw new Error('Actor position required for reach validation');finite3(asArray(actorPosition));
    const p=new this.T.Vector3(...asArray(actorPosition));const world=item.group.getWorldPosition(new this.T.Vector3());
    if(!item.held&&p.distanceTo(world)>item.binding.interaction.reach_m)throw new Error('Object out of reach');
    if(['pick_up','equip'].includes(action)){
      if(!mount)throw new Error('Attachment mount required');if(item.held&&action==='pick_up')throw new Error('Object already held');
      item.body.enabled=false;item.held=true;mount.add(item.group);item.group.position.set(0,0,0);item.group.rotation.set(0,0,0);
      const grip=item.binding.interaction.attachment?.grip_position_m??[0,0,0];item.group.position.set(...grip.map((v,i)=>-v*item.group.scale.toArray()[i]));
      if(item.actions.has('equip'))this.play(item,'equip');
    }else if(['drop','unequip'].includes(action)){
      if(!item.held)throw new Error('Object is not held');finite3(velocity);
      this.scene.attach(item.group);for(const m of item.mixers){m.stopAllAction();m.update(0);}item.group.updateMatrixWorld(true);
      item.held=false;item.body.enabled=true;item.body.sleeping=false;item.body.velocity=[...velocity];item.body.position=item.group.getWorldPosition(new this.T.Vector3()).toArray();
      this.syncColliders(item);
    }else if(action==='use'){
      if(!item.held)throw new Error('Equip the item before use');this.play(item,'use');
    }else if(action==='open'||action==='close'){this.play(item,action);item.open=action==='open';}
    else if(action==='activate'){const name=item.actions.has('operate')?'operate':item.actions.keys().next().value;this.play(item,name,{loop:true});item.active=true;}
    else if(action==='deactivate'){for(const mixer of item.mixers){mixer.stopAllAction();mixer.update(0);}item.active=false;}
    else if(action==='toggle_light'){item.lightOn=!item.lightOn;item.group.traverse(n=>{for(const m of n.material?(Array.isArray(n.material)?n.material:[n.material]):[])if(m.emissive)m.emissiveIntensity=item.lightOn?1:0;});}
    const event={type:'interaction',sceneops_id:id,asset_id:item.asset.id,action};this.onEvent(event);return event;
  }
  update(dt){
    if(this.disposed||this.paused)return;if(!Number.isFinite(dt)||dt<0)throw new Error('Invalid dt');dt=Math.min(dt,.1);
    for(const item of this.instances.values()){for(const m of item.mixers)m.update(dt);item.group.updateMatrixWorld(true);this.syncColliders(item);item.group.update(this.camera);}
    this.world.advance(dt);
    for(const item of this.instances.values())if(item.body.enabled&&item.body.mode==='dynamic'&&!item.held){
      const p=new this.T.Vector3(...item.body.position);if(item.group.parent)item.group.parent.worldToLocal(p);item.group.position.copy(p);
    }
    for(const event of this.world.drainEvents())this.onEvent(event);
  }
  async loadScene(manifest,catalog){
    if(manifest.coordinate_system!=='RH_Y_UP_Z_FORWARD'||manifest.units!=='meter')throw new Error('Unsupported coordinate system');
    const index=new Map(catalog.assets.map(a=>[a.id,a]));const added=[];
    try{for(const object of manifest.objects){const asset=index.get(object.asset_id);if(!asset)throw new Error('Unknown asset reference');
      const item=await this.addAsset(asset,{id:object.sceneops_id,position:object.position_m,rotation:object.rotation_euler_rad,scale:object.scale});added.push(item.id);}
      return {instanceIds:added,dispose:()=>added.forEach(id=>this.remove(id))};
    }catch(e){for(const id of added)this.remove(id);throw e;}
  }
  remove(id){const item=this.instances.get(id);if(!item)return;for(const m of item.mixers){m.stopAllAction();m.uncacheRoot(m.getRoot());}
    item.group.removeFromParent();this.disposeObject(item.group);this.world.removeBody(id);this.instances.delete(id);}
  disposeObject(group){const seen=new Set();group.traverse(n=>{if(n.geometry&&!seen.has(n.geometry)){seen.add(n.geometry);n.geometry.dispose();}
    for(const m of n.material?(Array.isArray(n.material)?n.material:[n.material]):[]){if(!seen.has(m)){seen.add(m);for(const key of ['map','normalMap','roughnessMap','metalnessMap','aoMap','emissiveMap']){const texture=m[key];if(texture&&!seen.has(texture)&&!new Set(this.textureCache.values()).has(texture)){seen.add(texture);texture.dispose();}}m.dispose();}}});}
  dispose(){for(const id of [...this.instances.keys()])this.remove(id);for(const t of this.textureCache.values())t.dispose();this.textureCache.clear();this.disposed=true;}
}
