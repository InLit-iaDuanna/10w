import assert from 'node:assert/strict';
import {readFileSync,writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {createRequire} from 'node:module';
const here=path.dirname(fileURLToPath(import.meta.url));
const repo=path.resolve(here,'../../../..');
const require=createRequire(path.join(repo,'apps/web/package.json'));
const THREE=await import(require.resolve('three'));
const {GLTFLoader}=await import(require.resolve('three/examples/jsm/loaders/GLTFLoader.js'));
const root=path.resolve(here,'../../backend/src/asset_library/builtin_assets');
const catalog=JSON.parse(readFileSync(path.join(root,'catalog.json')));
const results=[];
const motionBytes=readFileSync(path.join(root,'revisions/v5/glb/shared-motions-v1.glb'));
const sharedMotion=await new GLTFLoader().parseAsync(motionBytes.buffer.slice(motionBytes.byteOffset,motionBytes.byteOffset+motionBytes.byteLength),'');
const sharedClips=sharedMotion.animations;let sharedSkeleton=null;const sourceId='sceneops-basic-locomotion-v1';
for(const entry of catalog.entries.filter(item=>item.kind==='character')){
 const bytes=readFileSync(path.join(root,entry.glb_path));
 const raw=JSON.parse(bytes.subarray(20,20+bytes.readUInt32LE(12)).toString());
 assert.equal(raw.skins.length,1,entry.label);
 assert.equal(raw.skins[0].joints.length,16,entry.label);
 const gltf=await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'');
 assert.deepEqual(gltf.animations.map(a=>a.name).sort(),['Idle','Run','Walk','Wave']);
 const meshes=[];gltf.scene.traverse(o=>{if(o.isSkinnedMesh)meshes.push(o);});
 assert.ok(meshes.length,entry.label);
 for(const mesh of meshes){
  const weights=mesh.geometry.getAttribute('skinWeight');
  for(let i=0;i<weights.count;i++)assert.ok(Math.abs(weights.getX(i)+weights.getY(i)+weights.getZ(i)+weights.getW(i)-1)<1e-5);
 }
 const skeleton=meshes[0].skeleton.bones.map(b=>({name:b.name,parent:b.parent?.isBone?b.parent.name:null,rest:[...b.position.toArray(),...b.quaternion.toArray(),...b.scale.toArray()]}));
 if(!sharedSkeleton)sharedSkeleton=skeleton;
 assert.deepEqual(skeleton.map(b=>[b.name,b.parent]),sharedSkeleton.map(b=>[b.name,b.parent]));
 for(let i=0;i<skeleton.length;i++)assert.ok(skeleton[i].rest.every((v,j)=>Math.abs(v-sharedSkeleton[i].rest[j])<1e-6),'incompatible rest transform');
 const mixer=new THREE.AnimationMixer(gltf.scene);
 const clips=[];
 const points=()=>{gltf.scene.updateMatrixWorld(true);return meshes.flatMap(mesh=>{
  mesh.skeleton.update();const values=[];
  for(let i=0;i<mesh.geometry.getAttribute('position').count;i++)values.push(mesh.getVertexPosition(i,new THREE.Vector3()).applyMatrix4(mesh.matrixWorld));
  return values;
 });};
 const restBounds=new THREE.Box3().setFromPoints(points()).getSize(new THREE.Vector3()).toArray();
 assert.ok(restBounds.every((v,i)=>Math.abs(v-entry.dimensions_m[i])<.005), `${entry.label} rest bounds ${restBounds} vs ${entry.dimensions_m}`);
 // Apply the geometry-free shared action library directly, without retargeting.
 for(const clip of sharedClips){
  mixer.stopAllAction();mixer.clipAction(clip).reset().play();mixer.setTime(0);const rest=points();
  mixer.setTime(clip.duration*.25);const moved=points();
  const deformation=Math.max(...rest.map((p,i)=>p.distanceTo(moved[i])));
  assert.ok(deformation>.001,`${entry.label}/${clip.name} has no actual skin deformation`);
  assert.ok(moved.every(p=>Number.isFinite(p.x)&&Number.isFinite(p.y)&&Number.isFinite(p.z)));
  clips.push({name:clip.name,duration_seconds:clip.duration,max_deformation_m:deformation});
 }
 mixer.stopAllAction();mixer.uncacheRoot(gltf.scene);
 results.push({asset_id:entry.asset_id,bones:16,normalized_weights:true,clips});
}
writeFileSync(path.join(here,'../rig-verification.json'),JSON.stringify({characters:results.length,shared_skeleton:true,shared_clip_source:sourceId,retargeting_required:false,checks:results},null,2)+'\n');
console.log('RIG_RUNTIME_VERIFIED',results.length);
