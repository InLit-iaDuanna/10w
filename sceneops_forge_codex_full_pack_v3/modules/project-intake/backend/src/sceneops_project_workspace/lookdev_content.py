"""Materialize canonical Lookdev runtime modules inside a registered game workspace."""
import json
import shutil
from pathlib import Path
from vfx_shader import requires_game_runtime


def write_lookdev_content(root: Path, manifest: dict, replace_text):
    bindings = manifest.get('lookdev', [])
    if not bindings:
        return
    folder = root / 'src' / 'game' / 'sceneops-lookdev'
    public = root / 'public' / 'sceneops-assets'
    for path in (root / 'public', public, folder):
        if path.is_symlink():
            raise ValueError('材质输出目录不能是符号链接。')
        path.mkdir(exist_ok=True)
    imports, cases = [], []
    for index, binding in enumerate(bindings):
        relative = f'public/sceneops-assets/lookdev-{index}-{binding["asset_version"]}.glb'
        # Source paths originate from the project catalog, not model tool input.
        source = Path(binding.pop('source_path'))
        destination = root / relative
        if not source.is_file() or source.is_symlink() or destination.is_symlink():
            raise ValueError('材质资产文件不可用。')
        if destination.exists() and destination.read_bytes() != source.read_bytes():
            # Keep versioned assets immutable. A different binding receives a fresh path.
            from uuid import uuid4
            relative = f'public/sceneops-assets/lookdev-{uuid4().hex}.glb'
            destination = root / relative
        if not destination.exists():
            with source.open('rb') as original, destination.open('xb') as output:
                shutil.copyfileobj(original, output)
        for asset in manifest['assets']:
            if asset['asset_id']==binding['asset_id'] and asset['asset_version']==binding['asset_version']:
                asset['runtime_artifacts']=[{'artifact_id':binding['document_id'],'artifact_type':'render','project_relative_path':relative}]
        code = binding.pop('runtime_module')
        module = f'material-{index}'
        requires_gpu = requires_game_runtime(binding.get('state',{}))
        if not requires_gpu:
            # PBR is already baked into this exact GLB; no shader program is needed.
            replace_text(folder / f'{module}.ts', '// PBR material is stored in the versioned GLB.\nexport {};\n')
            binding.pop('state', None)
            continue
        replace_text(folder / f'{module}.ts', code)
        imports.append(f"import {{applySceneopsLookdev as apply{index}, assignSceneopsPrimitiveIds as ids{index}}} from './{module}'")
        binding.pop('state',None)
        cases.append(f"{{requiresGpu:{str(requires_gpu).lower()},assetId:{json.dumps(binding['asset_id'])},version:{binding['asset_version']},instanceId:{json.dumps(binding.get('scene_instance_id'))},apply:apply{index},ids:ids{index}}}")
    if not cases:
        replace_text(folder / 'index.ts', "import type {GLTF} from 'three/examples/jsm/loaders/GLTFLoader.js';\nimport type {Object3D} from 'three';\nexport async function applyProjectLookdev(_gltf:GLTF,_assetId:string,_version:number,_instanceId:string|undefined,_validate:((root:Object3D)=>Promise<void>)|undefined) {}\n")
        return
    registry = '\n'.join(imports)+"\nimport type {Object3D} from 'three';\n"
    registry += 'const bindings = ['+','.join(cases)+'];\n'
    registry += '''import {WebGPURenderer,Scene,PerspectiveCamera,Box3,Vector3} from 'three/webgpu';
async function validateMaterial(root:Object3D) {
  const renderer=new WebGPURenderer({antialias:false});
  renderer.setSize(64,64);
  const scene=new Scene(),camera=new PerspectiveCamera(45,1,.01,10000);
  const parent=root.parent;
  scene.add(root);
  const bounds=new Box3().setFromObject(root),center=bounds.getCenter(new Vector3());
  const radius=Math.max(bounds.getSize(new Vector3()).length(),.1);
  camera.position.copy(center).add(new Vector3(radius,radius,radius));camera.lookAt(center);
  try {
    await renderer.init();
    const device=(renderer.backend as unknown as {device:GPUDevice}).device;
    if(!device)throw new Error('此材质需要真实 WebGPU 设备。');
    device.pushErrorScope('validation');
    try {await renderer.compileAsync(scene,camera);await renderer.renderAsync(scene,camera);}
    finally {const error=await device.popErrorScope();if(error)throw new Error(error.message);}
  }
  finally {scene.remove(root);if(parent)parent.add(root);renderer.dispose();}
}
export async function applyProjectLookdev(gltf: Parameters<(typeof bindings)[number]['ids']>[0] & {scene:Object3D}, assetId:string, version:number, instanceId:string|undefined, validate:((root:Object3D)=>Promise<void>)|undefined) {
  // Each application creates a new catalog version; that version carries this appearance.
  const binding=bindings.find(item=>item.assetId===assetId && item.version===version && (!instanceId || !item.instanceId || item.instanceId===instanceId));
  if(!binding) return;
  if(!binding.requiresGpu) return;
  if(!navigator.gpu) throw new Error('此材质需要支持 WebGPU 的浏览器。');
  binding.ids(gltf);
  return binding.apply(gltf.scene, validate ?? validateMaterial);
}
'''
    replace_text(folder / 'index.ts', registry)
