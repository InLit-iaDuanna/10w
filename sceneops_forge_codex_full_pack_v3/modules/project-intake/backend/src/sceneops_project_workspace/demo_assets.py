"""Bundled editable geometry; no downloads, binary assets, or user-file replacements."""

DEMO_ASSET_PATH = 'src/game/sceneops-demo-assets.ts'
DEMO_ASSET_SOURCE = """import * as THREE from 'three'

/** SceneOps demo pack v1. Units: meters; Y up; character forward: +Z.
 * Original procedural primitives, editable without any external asset files.
 * Character roles share exactly the same geometry and differ only in color.
 */
export type CharacterRole = 'player' | 'enemy' | 'npc' | 'ally'
export const ROLE_COLORS: Record<CharacterRole, number> = {
  player: 0x4b9eff, enemy: 0xf06464, npc: 0xf3c969, ally: 0x65cc9b,
}

function material(color: number) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.85, flatShading: true })
}
function part(group: THREE.Group, name: string, geometry: THREE.BufferGeometry,
              surface: THREE.Material, x: number, y: number, z: number) {
  const mesh = new THREE.Mesh(geometry, surface)
  mesh.name = name; mesh.position.set(x, y, z)
  mesh.castShadow = true; mesh.receiveShadow = true; group.add(mesh)
  return mesh
}
function asset(kind: string) {
  const group = new THREE.Group()
  group.name = `demo-${kind}`
  group.userData = { source: 'sceneops-demo-pack', version: 1, kind, unit: 'meter' }
  return group
}

export function createCharacter(role: CharacterRole = 'player'): THREE.Group {
  const group = asset('character'); group.userData.role = role
  const suit = material(ROLE_COLORS[role]), dark = material(0x27354a), face = material(0xf5ddbe)
  part(group, 'body', new THREE.BoxGeometry(.58,.64,.36), suit, 0,.83,0)
  part(group, 'head', new THREE.BoxGeometry(.46,.42,.42), face, 0,1.38,0)
  part(group, 'cap', new THREE.BoxGeometry(.49,.14,.45), suit, 0,1.61,0)
  for (const side of [-1, 1]) {
    part(group, `arm-${side}`, new THREE.BoxGeometry(.17,.56,.23), suit, side*.4,.82,0)
    part(group, `leg-${side}`, new THREE.BoxGeometry(.2,.44,.25), dark, side*.16,.28,0)
    part(group, `boot-${side}`, new THREE.BoxGeometry(.23,.13,.34), dark, side*.16,.065,.045)
    part(group, `eye-${side}`, new THREE.BoxGeometry(.05,.05,.025), dark, side*.1,1.4,.222)
  }
  return group
}

export function createHouse(): THREE.Group {
  const group = asset('house'), wall = material(0xe6d2af), timber = material(0x69513f)
  part(group, 'walls', new THREE.BoxGeometry(2.4,1.8,1.8), wall, 0,.9,0)
  const roof = part(group, 'roof', new THREE.ConeGeometry(1.9,1.1,4), material(0xae6551), 0,2.25,0)
  roof.rotation.y = Math.PI/4; roof.scale.z = .82
  part(group, 'door', new THREE.BoxGeometry(.48,.95,.06), timber, 0,.475,.93)
  for (const x of [-.77,.77]) {
    part(group, `window-${x}`, new THREE.BoxGeometry(.48,.48,.06), material(0x9ed9e8), x,1.08,.93)
  }
  part(group, 'chimney', new THREE.BoxGeometry(.3,.85,.3), timber, .7,2.35,-.25)
  return group
}

export function createTree(): THREE.Group {
  const group = asset('tree')
  part(group, 'trunk', new THREE.CylinderGeometry(.16,.22,1.2,6), material(0x806144), 0,.6,0)
  const leaves = material(0x68a77a)
  part(group, 'lower-crown', new THREE.ConeGeometry(.85,1.4,7), leaves, 0,1.4,0)
  part(group, 'upper-crown', new THREE.ConeGeometry(.63,1.25,7), leaves, 0,2.1,0)
  return group
}

export function createCrate(): THREE.Group {
  const group = asset('crate'), wood = material(0xb48b58), trim = material(0x785938)
  part(group, 'box', new THREE.BoxGeometry(.75,.75,.75), wood, 0,.375,0)
  for (const x of [-.29,.29]) part(group, `strap-${x}`, new THREE.BoxGeometry(.08,.79,.79), trim, x,.395,0)
  return group
}

export function createRock(): THREE.Group {
  const group = asset('rock')
  const rock = part(group, 'stone', new THREE.DodecahedronGeometry(.48,0), material(0x8e9a9b), 0,.3,0)
  rock.scale.set(1.3,.75,1); rock.rotation.set(.2,.35,.1)
  return group
}

export function createCollectible(): THREE.Group {
  const group = asset('collectible')
  part(group, 'gem', new THREE.OctahedronGeometry(.33), material(0xffd76a), 0,.45,0)
  return group
}

/** A small village surrounding the playable collection area. NPC roles are display props. */
export function createDemoScenery(): THREE.Group {
  const village = asset('village')
  const place = (item: THREE.Group, x: number, z: number, turn = 0) => {
    item.position.set(x,0,z); item.rotation.y = turn; village.add(item)
  }
  place(createHouse(), -5.6,-3.8); place(createHouse(), 5.6,-3.8)
  for (const [x,z] of [[-8,-1],[-7,3],[8,1],[7,4],[0,-5]]) place(createTree(),x,z)
  place(createCrate(),-4.2,-3.2); place(createCrate(),-3.3,-3.2)
  place(createRock(),6.8,2.5); place(createRock(),-6,4.7)
  place(createCharacter('npc'),-5.6,-2.1)
  place(createCharacter('ally'),5.6,-2.1)
  place(createCharacter('enemy'),6,3.8,Math.PI)
  return village
}
"""


def demo_asset_files() -> dict[str, str]:
    return {DEMO_ASSET_PATH: DEMO_ASSET_SOURCE}
