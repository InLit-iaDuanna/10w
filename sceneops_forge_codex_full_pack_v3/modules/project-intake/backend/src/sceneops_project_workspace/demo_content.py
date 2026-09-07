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

export type DoorRecipe = {{ kind: 'door-v1'; seed: 0; width_m: number; height_m: number; thickness_m: number; material: {{ color_hex: string; roughness: number; metalness: number }} }}
export type KeyDoorBehavior = {{ behavior_instance_id: string; kind: 'KeyDoor'; definition_id: 'KeyDoor@1'; required_key_asset_id: string; interaction_distance_m: number; open_angle_deg: number }}
export type DemoAsset = {{ asset_id: string; asset_version: number; asset_version_id: string | null; source_kind: 'file'|'procedural'; dimensions_m: [number,number,number]; recipe: DoorRecipe | null; runtime_artifacts: Array<{{ artifact_id: string; artifact_type: 'render'|'collision'|'module'; project_relative_path: string; export_name?: string }}> }}
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

export function distanceToDoor(player: THREE.Vector3, door: THREE.Object3D) {{
  const at = new THREE.Vector3(); door.getWorldPosition(at); at.y = player.y
  return at.distanceTo(player)
}}

export function keyDoorCanOpen(player: THREE.Vector3, door: THREE.Object3D, inventory: ReadonlySet<string>, behavior: KeyDoorBehavior) {{
  return inventory.has(behavior.required_key_asset_id) && distanceToDoor(player, door) <= behavior.interaction_distance_m
}}
"""
