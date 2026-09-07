"""Materialize versioned SceneOps content as a derived Three.js module."""
from __future__ import annotations

import json


EMPTY_DEMO_CONTENT = {
    "schema_version": 1,
    "project_id": "unbound",
    "workspace_id": "unbound",
    "scene_id": "unbound",
    "scene_version": 0,
    "assets": [],
    "objects": [],
}


def demo_content_source(manifest: dict) -> str:
    payload = json.dumps(manifest, ensure_ascii=False, allow_nan=False, indent=2)
    return f"""// Generated from SceneOps asset and scene versions. Edit those sources, then update the Demo.
import * as THREE from 'three'
import {{ GLTFLoader }} from 'three/examples/jsm/loaders/GLTFLoader.js'

export type DoorRecipe = {{ kind: 'door-v1'; seed: 0; width_m: number; height_m: number; thickness_m: number; material: {{ color_hex: string; roughness: number; metalness: number }} }}
export type KeyDoorBehavior = {{ behavior_instance_id: string; kind: 'KeyDoor'; definition_id: 'KeyDoor@1'; required_key_asset_id: string; interaction_distance_m: number; open_angle_deg: number }}
export type DemoAsset = {{ asset_id: string; asset_version: number; asset_version_id: string | null; source_kind: 'file'|'procedural'|'blender'; dimensions_m: [number,number,number]; recipe: DoorRecipe | null; runtime_artifacts: Array<{{ artifact_id: string; artifact_type: 'render'|'collision'|'module'; project_relative_path: string; export_name?: string | null }}> }}
export type DemoObject = {{ id: string; asset_id: string; asset_version: number; asset_version_id: string | null; transform: {{ position_m: [number,number,number]; rotation_y_deg: number; scale: number }}; behavior: KeyDoorBehavior | null }}
export type DemoContent = {{ schema_version: 1; project_id: string; workspace_id: string; scene_id: string; scene_version: number; assets: DemoAsset[]; objects: DemoObject[] }}

export const demoContent = {payload} as DemoContent

export function createDoorMesh(recipe: DoorRecipe) {{
  const geometry = new THREE.BoxGeometry(recipe.width_m, recipe.height_m, recipe.thickness_m)
  const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({{ color: recipe.material.color_hex, roughness: recipe.material.roughness, metalness: recipe.material.metalness }}))
  mesh.position.y = recipe.height_m / 2
  mesh.castShadow = true; mesh.receiveShadow = true
  mesh.userData.recipe = recipe
  mesh.userData.colliderDimensionsM = [recipe.width_m, recipe.height_m, recipe.thickness_m]
  return mesh
}}

{GLB_RUNTIME}
export function distanceToDoor(player: THREE.Vector3, door: THREE.Object3D) {{
  const at = new THREE.Vector3(); door.getWorldPosition(at); at.y = player.y
  return at.distanceTo(player)
}}

export function keyDoorCanOpen(player: THREE.Vector3, door: THREE.Object3D, inventory: ReadonlySet<string>, behavior: KeyDoorBehavior) {{
  return inventory.has(behavior.required_key_asset_id) && distanceToDoor(player, door) <= behavior.interaction_distance_m
}}
"""


GLB_RUNTIME = r"""
export function prepareDemoAsset(root: THREE.Object3D) {
  const nodes: THREE.Object3D[] = []; const ids = new Set<string>()
  root.traverse(node => {
    if (node.userData.sceneops_role) {
      const id = node.userData.sceneops_id
      if (typeof id !== 'string' || !id || ids.has(id)) throw new Error('模型节点身份缺失或重复')
      ids.add(id); nodes.push(node)
    }
    if (node instanceof THREE.Mesh) { node.castShadow = true; node.receiveShadow = true }
  })
  const hinges = nodes.filter(node => node.userData.sceneops_role === 'hinge')
  const leaves = nodes.filter(node => node.userData.sceneops_role === 'leaf')
  const frames = nodes.filter(node => node.userData.sceneops_role === 'frame')
  if (hinges.length !== 1 || !leaves.length || !frames.length) throw new Error('门模型缺少门框、门扇或唯一铰链语义')
  const hinge = hinges[0]
  const belowHinge = (node: THREE.Object3D) => { for (let parent = node.parent; parent; parent = parent.parent) if (parent === hinge) return true; return false }
  if (leaves.some(node => !belowHinge(node)) || frames.some(belowHinge)) throw new Error('门模型铰链层级无效')
  const bounds = new THREE.Box3().setFromObject(root)
  if (bounds.isEmpty() || !bounds.min.toArray().concat(bounds.max.toArray()).every(Number.isFinite)) throw new Error('门模型几何尺寸无效')
  root.userData.doorHinge = hinge
  root.userData.closedHingeQuaternion = hinge.quaternion.clone()
  root.userData.colliderDimensionsM = bounds.getSize(new THREE.Vector3()).toArray()
  return root
}

export async function createDemoAsset(asset: DemoAsset): Promise<THREE.Object3D> {
  if (asset.source_kind === 'procedural' && asset.recipe) {
    const root = new THREE.Group(), hinge = new THREE.Group(), leaf = createDoorMesh(asset.recipe)
    hinge.position.x = -asset.recipe.width_m / 2; leaf.position.x = asset.recipe.width_m / 2
    hinge.add(leaf); root.add(hinge)
    root.userData.doorHinge = hinge; root.userData.closedHingeQuaternion = hinge.quaternion.clone()
    root.userData.colliderDimensionsM = leaf.userData.colliderDimensionsM
    return root
  }
  const artifact = asset.runtime_artifacts.find(item => item.artifact_type === 'render')
  const path = artifact?.project_relative_path
  if (!path || !path.startsWith('public/') || !path.endsWith('.glb') || path.split('/').some(part => part === '..' || !part) || path.includes('\\')) throw new Error('模型缺少有效 GLB 运行文件')
  const url = '/' + path.slice(7).split('/').map(encodeURIComponent).join('/')
  const gltf = await new GLTFLoader().loadAsync(url)
  const root = new THREE.Group(); root.add(gltf.scene)
  return prepareDemoAsset(root)
}

export function setDemoDoorOpen(root: THREE.Object3D, angleRadians: number) {
  const hinge = root.userData.doorHinge as THREE.Object3D | undefined
  const closed = root.userData.closedHingeQuaternion as THREE.Quaternion | undefined
  if (!hinge || !closed) throw new Error('模型未登记可操作铰链')
  root.updateWorldMatrix(true, true)
  const axis = new THREE.Vector3(0, 1, 0).applyQuaternion(root.getWorldQuaternion(new THREE.Quaternion()))
  if (hinge.parent) axis.applyQuaternion(hinge.parent.getWorldQuaternion(new THREE.Quaternion()).invert())
  hinge.quaternion.copy(closed).premultiply(new THREE.Quaternion().setFromAxisAngle(axis.normalize(), angleRadians))
  root.updateMatrixWorld(true)
}

export function demoAssetBlocksPlayer(root: THREE.Object3D, player: THREE.Vector3, radius = .3) {
  root.updateWorldMatrix(true, true)
  let blocked = false
  root.traverse(node => {
    if (!(node instanceof THREE.Mesh)) return
    if (!node.geometry.boundingBox) node.geometry.computeBoundingBox()
    const bounds = node.geometry.boundingBox!.clone().applyMatrix4(node.matrixWorld)
    const x = Math.max(bounds.min.x, Math.min(bounds.max.x, player.x))
    const z = Math.max(bounds.min.z, Math.min(bounds.max.z, player.z))
    if (bounds.max.y > player.y && bounds.min.y < player.y + 1.4 && Math.hypot(player.x - x, player.z - z) < radius) blocked = true
  })
  return blocked
}
"""
