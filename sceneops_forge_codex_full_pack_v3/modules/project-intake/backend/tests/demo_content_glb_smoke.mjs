/** Real GLB parsing and runtime hinge/collision checks; deterministic geometry fixture, not Blender evidence. */
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
const require = createRequire(import.meta.url)
const ts = require('typescript')
const viewerRequire = createRequire(path.resolve('packages/scene-viewer/package.json'))
const threePath = path.resolve(path.dirname(viewerRequire.resolve('three')), '..')
const THREE = await import(pathToFileURL(path.join(threePath, 'build/three.module.js')))
let code = ts.transpileModule(fs.readFileSync(process.argv[2], 'utf8'), {compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText
code = code.replace("'three'", JSON.stringify(pathToFileURL(path.join(threePath,'build/three.module.js')).href))
code = code.replace("'three/examples/jsm/loaders/GLTFLoader.js'", JSON.stringify(pathToFileURL(path.join(threePath,'examples/jsm/loaders/GLTFLoader.js')).href))
const runtime = await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'))
const geo = new THREE.BoxGeometry(1,1,1).toNonIndexed()
const binary = Buffer.from(geo.attributes.position.array.buffer)
const document = {asset:{version:'2.0'},scene:0,scenes:[{nodes:[0,1,2]}],nodes:[
 {mesh:0,translation:[-1,1,0],scale:[.2,2,.2],extras:{sceneops_id:'frame-left',sceneops_role:'frame'}},
 {mesh:0,translation:[1,1,0],scale:[.2,2,.2],extras:{sceneops_id:'frame-right',sceneops_role:'frame'}},
 {translation:[-.9,0,0],children:[3],extras:{sceneops_id:'hinge-offset',sceneops_role:'hinge'}},
 {mesh:0,translation:[.9,1,0],scale:[1.8,2,.12],extras:{sceneops_id:'leaf-id',sceneops_role:'leaf'}}
],meshes:[{primitives:[{attributes:{POSITION:0}}]}],buffers:[{byteLength:binary.length}],bufferViews:[{buffer:0,byteLength:binary.length}],accessors:[{bufferView:0,componentType:5126,count:geo.attributes.position.count,type:'VEC3',min:[-.5,-.5,-.5],max:[.5,.5,.5]}]}
let json = Buffer.from(JSON.stringify(document)); json=Buffer.concat([json,Buffer.alloc((4-json.length%4)%4,32)])
const header=Buffer.alloc(20);header.writeUInt32LE(0x46546c67,0);header.writeUInt32LE(2,4);header.writeUInt32LE(28+json.length+binary.length,8);header.writeUInt32LE(json.length,12);header.writeUInt32LE(0x4e4f534a,16)
const chunk=Buffer.alloc(8);chunk.writeUInt32LE(binary.length,0);chunk.writeUInt32LE(0x004e4942,4)
const glb=Buffer.concat([header,json,chunk,binary])
const originalFetch=globalThis.fetch
let requested=''
globalThis.ProgressEvent ??= class {constructor(type,values){this.type=type;Object.assign(this,values)}}
globalThis.fetch=async request=>{requested=typeof request==='string'?request:request.url;return new Response(glb,{headers:{'Content-Length':String(glb.length)}})}
// Node's Request requires an absolute URL; the browser resolves the same public URL against its origin.
const OriginalRequest=globalThis.Request
globalThis.Request=class extends OriginalRequest {constructor(url,options){super(new URL(url,'http://localhost'),options)}}
const asset={source_kind:'blender',runtime_artifacts:[{artifact_type:'render',project_relative_path:'public/sceneops-assets/test.glb'}]}
const root=await runtime.createDemoAsset(asset)
assert.equal(requested,'http://localhost/sceneops-assets/test.glb')
const nodes=[];root.traverse(node=>nodes.push(node))
const frameNode=nodes.find(node=>node.userData.sceneops_id==='frame-left')
const leaf=nodes.find(node=>node.userData.sceneops_id==='leaf-id')
const fixed=frameNode.getWorldPosition(new THREE.Vector3()).clone()
const leafBefore=leaf.getWorldPosition(new THREE.Vector3()).clone()
assert.equal(runtime.demoAssetBlocksPlayer(root,new THREE.Vector3(0,0,0)),true)
runtime.setDemoDoorOpen(root,Math.PI/2)
assert.deepEqual(frameNode.getWorldPosition(new THREE.Vector3()).toArray(),fixed.toArray())
assert.ok(leaf.getWorldPosition(new THREE.Vector3()).distanceTo(leafBefore)>1)
assert.equal(runtime.demoAssetBlocksPlayer(root,new THREE.Vector3(0,0,0)),false)
assert.equal(runtime.demoAssetBlocksPlayer(root,new THREE.Vector3(-1,0,0)),true)
runtime.setDemoDoorOpen(root,0)
assert.ok(leaf.getWorldPosition(new THREE.Vector3()).distanceTo(leafBefore)<1e-6)
await assert.rejects(runtime.createDemoAsset({...asset,runtime_artifacts:[]}),/GLB/)
assert.throws(()=>runtime.prepareDemoAsset(new THREE.Group()),/语义/)
globalThis.fetch=originalFetch;globalThis.Request=OriginalRequest
console.log('GLB runtime smoke passed: binary loader, semantic identities, offset hinge, fixed frame, collision, bad model.')
