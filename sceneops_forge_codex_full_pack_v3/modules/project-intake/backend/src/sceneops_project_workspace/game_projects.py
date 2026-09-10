"""Create the first real Three.js project without overwriting existing game code."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .git_projects import GitProjects
from .demo_assets import demo_asset_files
from .demo_content import EMPTY_DEMO_CONTENT, demo_content_source
from .test_adapter_files import test_adapter_files


class GameProjectError(ValueError):
    pass


THREE_VERSION = "0.183.2"
MINIPLEX_VERSION = "2.0.0"
ARCHITECTURE_VERSION = 1


def _shared_files(*, ecs: bool, include_demo: bool = True) -> dict[str, str]:
    dependencies = {"three": THREE_VERSION}
    if ecs:
        dependencies["miniplex"] = MINIPLEX_VERSION
    package = {
        "name": "sceneops-game",
        "private": True,
        "version": "0.1.0",
        "type": "module",
        "packageManager": "pnpm@11.13.0",
        "scripts": {
            "dev": "vite --host 127.0.0.1",
            "check": "tsc --noEmit",
            "build": "tsc --noEmit && vite build",
            "preview": "vite preview --host 127.0.0.1",
        },
        "dependencies": dependencies,
        "devDependencies": {"@types/three": "0.183.1", "typescript": "6.0.3", "vite": "8.0.0"},
    }
    return {
        **(demo_asset_files() if include_demo else {}),
        "src/game/sceneops-demo-content.ts": demo_content_source(EMPTY_DEMO_CONTENT),
        **(test_adapter_files() if include_demo else {}),
        "README.md": """# SceneOps game project

This is the playable game project created from the technical plan selected in Design Room.

```bash
pnpm install
pnpm check
pnpm dev
```

打开 Vite 显示的本地地址，用 WASD 或方向键移动，收集黄色宝石。

内置演示资产位于 `src/game/sceneops-demo-assets.ts`，无需用户上传素材或联网下载。蓝色玩家、红色敌人、黄色 NPC、绿色队友使用相同人物轮廓；小屋、树、木箱和岩石组成示例村落。示例敌人和 NPC 目前是场景展示物，不代表已经实现战斗或对话。素材均为可编辑的 Three.js 基础几何，单位米、Y 轴向上。
Read `ARCHITECTURE.md` before adding gameplay code so new work continues within the selected architecture.
""",
        "package.json": json.dumps(package, ensure_ascii=False, indent=2) + "\n",
        "tsconfig.json": json.dumps({
            "compilerOptions": {
                "target": "ES2022", "useDefineForClassFields": True,
                "module": "ESNext", "moduleResolution": "Bundler", "strict": True,
                "noEmit": True, "skipLibCheck": True,
                "lib": ["ES2022", "DOM", "DOM.Iterable"],
            },
            "include": ["src"],
        }, indent=2) + "\n",
        "index.html": """<!doctype html>
<html lang="zh-CN">
  <head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><link rel="icon" href="data:,"/><title>SceneOps Game</title></head>
  <body><div id="hud">移动：WASD / 方向键　互动：空格 / Enter　道具：<strong id="score">0</strong><span id="prompt"></span></div><div id="app"></div><script type="module" src="/src/main.ts"></script></body>
</html>
""",
        "src/style.css": """html,body,#app{width:100%;height:100%;margin:0;overflow:hidden;background:#111827}body{font-family:system-ui,sans-serif;color:white}canvas{display:block}#hud{position:fixed;z-index:2;top:16px;left:16px;padding:10px 14px;border:1px solid #ffffff2e;border-radius:10px;background:#111827d9}#prompt{display:block;margin-top:6px;color:#f6d37a}
""",
        "src/vite-env.d.ts": "/// <reference types=\"vite/client\" />\n",
        ".gitignore": "node_modules/\ndist/\n.DS_Store\n",
    }


def object_component_files() -> dict[str, str]:
    return {
        **_shared_files(ecs=False),
        "ARCHITECTURE.md": """# Object / component architecture

Gameplay behavior belongs to long-lived game objects such as `Player` and `Collectible`. Reusable services such as input and score live under `components`. `Game` owns these objects and calls their update behavior from the main loop.

When adding a feature, read the existing objects first, extend the object that owns the behavior, and extract a component only when behavior is shared. Keep the current `Game` loop and do not replace the project with an ECS implementation.
""",
        "src/main.ts": """import './style.css'
import { Game } from './game/Game'

const host = document.querySelector<HTMLDivElement>('#app')
if (!host) throw new Error('Missing #app host')
Game.create(host).then(game => game.start()).catch(error => { document.querySelector<HTMLElement>('#prompt')!.textContent = `模型加载失败：${String(error)}` })
""",
        "src/game/components/InputController.ts": """export class InputController {
  private readonly pressed = new Set<string>()
  private interactRequested = false
  constructor() {
    window.addEventListener('keydown', event => { this.pressed.add(event.key.toLowerCase()); if (event.key === ' ' || event.key === 'Enter') this.interactRequested = true })
    window.addEventListener('keyup', event => this.pressed.delete(event.key.toLowerCase()))
  }
  direction() {
    const x = Number(this.pressed.has('d') || this.pressed.has('arrowright')) - Number(this.pressed.has('a') || this.pressed.has('arrowleft'))
    const z = Number(this.pressed.has('s') || this.pressed.has('arrowdown')) - Number(this.pressed.has('w') || this.pressed.has('arrowup'))
    const length = Math.hypot(x, z) || 1
    return { x: x / length, z: z / length }
  }
  consumeInteract() { const requested = this.interactRequested; this.interactRequested = false; return requested }
  reset() { this.pressed.clear(); this.interactRequested = false }
}
""",
        "src/game/components/ScoreCounter.ts": """export class ScoreCounter {
  private value = 0
  constructor(private readonly output: HTMLElement) { this.render() }
  collect() { this.value += 1; this.render() }
  reset() { this.value = 0; this.render() }
  current() { return this.value }
  private render() { this.output.textContent = String(this.value) }
}
""",
        "src/game/objects/Player.ts": """import * as THREE from 'three'
import type { InputController } from '../components/InputController'
import { createCharacter } from '../sceneops-demo-assets'

export class Player {
  readonly mesh = createCharacter('player')
  constructor(private readonly input: InputController) {}
  update(deltaSeconds: number) {
    const direction = this.input.direction()
    this.mesh.position.x = THREE.MathUtils.clamp(this.mesh.position.x + direction.x * 5 * deltaSeconds, -8, 8)
    this.mesh.position.z = THREE.MathUtils.clamp(this.mesh.position.z + direction.z * 5 * deltaSeconds, -5, 5)
  }
}
""",
        "src/game/objects/Collectible.ts": """import * as THREE from 'three'
import { createCollectible } from '../sceneops-demo-assets'

export class Collectible {
  readonly mesh = createCollectible()
  collected = false
  constructor(x: number, z: number) { this.mesh.position.set(x, 0, z) }
  tryCollect(player: THREE.Vector3) {
    if (this.collected || this.mesh.position.distanceTo(player) >= 0.9) return false
    this.collected = true
    this.mesh.visible = false
    return true
  }
}
""",
        "src/game/objects/KeyDoor.ts": """import * as THREE from 'three'
import { createDemoAsset, setDemoDoorOpen, keyDoorCanOpen, type DemoAsset, type DemoObject } from '../sceneops-demo-content'

export class KeyDoor {
  readonly mesh: THREE.Object3D
  opened = false
  static async create(source: DemoObject, asset: DemoAsset) { return new KeyDoor(source, await createDemoAsset(asset, {instanceId:source.id})) }
  constructor(readonly source: DemoObject, mesh: THREE.Object3D) {
    this.mesh = mesh
    const {position_m,rotation_y_deg,scale} = source.transform
    this.mesh.position.set(...position_m); this.mesh.scale.setScalar(scale)
    this.mesh.rotation.y = THREE.MathUtils.degToRad(rotation_y_deg)
    this.mesh.name = source.id; this.mesh.userData.sceneops_id = source.id
  }
  distanceTo(player: THREE.Vector3) { const at=this.mesh.position.clone(); at.y=player.y; return at.distanceTo(player) }
  tryOpen(player: THREE.Vector3, inventory: ReadonlySet<string>) {
    const behavior = this.source.behavior
    if (!behavior || this.opened || !keyDoorCanOpen(player, this.mesh, inventory, behavior)) return false
    this.opened = true; setDemoDoorOpen(this.mesh, THREE.MathUtils.degToRad(behavior.open_angle_deg))
    return true
  }
  reset() { this.opened = false; setDemoDoorOpen(this.mesh, 0) }
}
""",
        "src/game/Game.ts": """import * as THREE from 'three'
import { InputController } from './components/InputController'
import { ScoreCounter } from './components/ScoreCounter'
import { Collectible } from './objects/Collectible'
import { Player } from './objects/Player'
import { KeyDoor } from './objects/KeyDoor'
import { createTestAdapter } from './sceneops-test'
import { createDemoScenery } from './sceneops-demo-assets'
import { demoContent, demoAssetBlocksPlayer } from './sceneops-demo-content'

export class Game {
  private readonly renderer = new THREE.WebGLRenderer({ antialias: true })
  private readonly scene = new THREE.Scene()
  private readonly camera = new THREE.PerspectiveCamera(55, 1, 0.1, 100)
  private readonly input = new InputController()
  private readonly player = new Player(this.input)
  private readonly collectibles = [[-4,-2],[0,2],[4,-1]].map(([x,z]) => new Collectible(x, z))
  private readonly score = new ScoreCounter(document.querySelector<HTMLElement>('#score')!)
  private readonly prompt = document.querySelector<HTMLElement>('#prompt')!
  static async create(host: HTMLElement) {
    const doors = await Promise.all(demoContent.objects.map(source => {
      const asset = demoContent.assets.find(item => item.asset_id === source.asset_id && item.asset_version === source.asset_version)
      if (!asset) throw new Error(`资产版本缺失：${source.asset_id}`)
      return KeyDoor.create(source, asset)
    }))
    return new Game(host, doors)
  }
  private last = performance.now()
  private test?: ReturnType<typeof createTestAdapter>

  constructor(private readonly host: HTMLElement, private readonly doors: KeyDoor[]) {
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); this.host.append(this.renderer.domElement)
    this.scene.background = new THREE.Color(0x111827)
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x334155, 2.2), this.player.mesh, createDemoScenery(), ...this.doors.map(item => item.mesh))
    this.collectibles.forEach(item => this.scene.add(item.mesh))
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(18, 12), new THREE.MeshStandardMaterial({ color: 0x334155 }))
    floor.rotation.x = -Math.PI / 2; this.scene.add(floor); this.camera.position.set(0, 10, 11); this.camera.lookAt(0, 0, 0)
    window.addEventListener('resize', () => this.resize()); this.resize()
    if (import.meta.env.MODE === 'sceneops-test') {
      const spawn = this.player.mesh.position.clone()
      const spawns = this.collectibles.map(item => item.mesh.position.clone())
      this.test = createTestAdapter(() => {
        this.input.reset(); this.player.mesh.position.copy(spawn); this.score.reset()
        this.collectibles.forEach((item, index) => {
          item.mesh.position.copy(spawns[index]); item.collected = false; item.mesh.visible = true
        })
        this.doors.forEach(item => item.reset()); this.prompt.textContent = ''
        this.last = performance.now()
        this.host.dataset.playerX = spawn.x.toFixed(3); this.host.dataset.playerZ = spawn.z.toFixed(3)
      }, () => ({
        player: { x: this.player.mesh.position.x, y: this.player.mesh.position.y, z: this.player.mesh.position.z },
        score: this.score.current(),
        collectibles: this.collectibles.map((item, index) => ({
          id: `collectible-${index + 1}`, x: item.mesh.position.x, y: item.mesh.position.y, z: item.mesh.position.z,
          collected: item.collected, visible: item.mesh.visible,
        })),
        doors: this.doors.map(item => ({ id:item.source.id, open:item.opened, distance:item.distanceTo(this.player.mesh.position),
          interactionDistance:item.source.behavior?.interaction_distance_m, colliderDimensions:item.mesh.userData.colliderDimensionsM })),
      }))
      window.__sceneopsTest = this.test.protocol
    }
  }
  start() { requestAnimationFrame(time => this.update(time)) }
  private update(time: number) {
    const delta = Math.min((time - this.last) / 1000, 0.05); this.last = time
    if (!this.test?.paused) {
      const previous = this.player.mesh.position.clone()
      this.player.update(delta)
      if (this.doors.some(door => demoAssetBlocksPlayer(door.mesh, this.player.mesh.position))) this.player.mesh.position.copy(previous)
      this.collectibles.forEach(item => { if (item.tryCollect(this.player.mesh.position)) this.score.collect() })
      const keyItem = this.doors.find(item => item.source.behavior)?.source.behavior?.required_key_asset_id
      const inventory = new Set(this.score.current() > 0 && keyItem ? [keyItem] : [])
      if (this.input.consumeInteract()) this.doors.forEach(item => item.tryOpen(this.player.mesh.position, inventory))
      const nearby = this.doors.find(item => !item.opened && item.source.behavior && item.distanceTo(this.player.mesh.position) <= item.source.behavior.interaction_distance_m)
      this.prompt.textContent = nearby ? (inventory.has(nearby.source.behavior!.required_key_asset_id) ? '按空格或 Enter 开门' : '需要钥匙') : ''
      this.test?.recordFrame(delta)
    }
    this.host.dataset.playerX = this.player.mesh.position.x.toFixed(3)
    this.host.dataset.playerZ = this.player.mesh.position.z.toFixed(3)
    this.renderer.render(this.scene, this.camera); requestAnimationFrame(next => this.update(next))
  }
  private resize() {
    const width = this.host.clientWidth, height = this.host.clientHeight
    this.renderer.setSize(width, height, false); this.camera.aspect = width / Math.max(height, 1); this.camera.updateProjectionMatrix()
  }
}
""",
    }


def ecs_files() -> dict[str, str]:
    return {
        **_shared_files(ecs=True),
        "ARCHITECTURE.md": """# ECS architecture

This project uses Miniplex as its only ECS library. Entities are component data stored in the world; systems query matching entities and update them each frame. Rendering objects are components referenced by entities.

When adding a feature, define the needed component data in `world.ts`, create or extend a focused system under `systems`, and run it from the existing frame pipeline. Keep behavior out of entity classes and do not replace Miniplex with another ECS library.
""",
        "src/main.ts": """import './style.css'
import * as THREE from 'three'
import { createGameWorld } from './game/world'
import { inputSystem } from './game/systems/inputSystem'
import { movementSystem } from './game/systems/movementSystem'
import { collectionSystem, resetScore, currentScore } from './game/systems/collectionSystem'
import { createTestAdapter } from './game/sceneops-test'
import { createDemoScenery } from './game/sceneops-demo-assets'
import { doorSystem } from './game/systems/doorSystem'
import { setDemoDoorOpen } from './game/sceneops-demo-content'

async function start() {

const host = document.querySelector<HTMLDivElement>('#app')
const score = document.querySelector<HTMLElement>('#score')
if (!host || !score) throw new Error('Missing game host')
const gameHost: HTMLDivElement = host
const scoreOutput: HTMLElement = score
const renderer = new THREE.WebGLRenderer({ antialias: true }); gameHost.append(renderer.domElement)
const scene = new THREE.Scene(); scene.background = new THREE.Color(0x111827)
const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 100); camera.position.set(0, 10, 11); camera.lookAt(0, 0, 0)
scene.add(new THREE.HemisphereLight(0xffffff, 0x334155, 2.2), createDemoScenery())
const floor = new THREE.Mesh(new THREE.PlaneGeometry(18, 12), new THREE.MeshStandardMaterial({ color: 0x334155 })); floor.rotation.x = -Math.PI / 2; scene.add(floor)
const game = await createGameWorld(scene)
const input = { keys: new Set<string>(), interactRequested: false }
addEventListener('keydown', e => {
  input.keys.add(e.key.toLowerCase())
  if (e.key === ' ' || e.key === 'Enter') input.interactRequested = true
})
addEventListener('keyup', e => input.keys.delete(e.key.toLowerCase()))
const resize = () => { const width=gameHost.clientWidth,height=gameHost.clientHeight; renderer.setSize(width,height,false); camera.aspect=width/Math.max(height,1); camera.updateProjectionMatrix() }
addEventListener('resize', resize); resize()
let last = performance.now()
let test: ReturnType<typeof createTestAdapter> | undefined
if (import.meta.env.MODE === 'sceneops-test') {
  const [player] = game.world.with('player', 'position', 'velocity')
  const spawn = player.position.clone()
  const items = [...game.world.with('collectible', 'position', 'mesh')]
  const spawns = items.map(item => item.position.clone())
  test = createTestAdapter(() => {
    input.keys.clear(); input.interactRequested = false; player.position.copy(spawn); player.velocity.set(0, 0, 0); player.inventory?.clear(); resetScore(scoreOutput)
    items.forEach((item, index) => {
      item.position.copy(spawns[index]); item.mesh.visible = true
      if (!game.world.has(item)) game.world.add(item)
      scene.add(item.mesh)
    })
    for (const door of game.world.with('keyDoor','mesh')) { door.keyDoor.open=false; setDemoDoorOpen(door.mesh, 0) }
    document.querySelector<HTMLElement>('#prompt')!.textContent=''
    last = performance.now()
    gameHost.dataset.playerX = spawn.x.toFixed(3); gameHost.dataset.playerZ = spawn.z.toFixed(3)
  }, () => ({
    player: { x: player.position.x, y: player.position.y, z: player.position.z }, score: currentScore(),
    collectibles: items.map((item, index) => ({
      id: `collectible-${index + 1}`, x: item.position.x, y: item.position.y, z: item.position.z,
      collected: !game.world.has(item), visible: item.mesh.parent === scene && item.mesh.visible,
    })),
    doors: [...game.world.with('keyDoor','mesh')].map(item => ({ id:item.sceneObjectId, open:item.keyDoor.open,
      distance:item.mesh.position.distanceTo(player.position), interactionDistance:item.keyDoor.behavior.interaction_distance_m,
      colliderDimensions:item.mesh.userData.colliderDimensionsM })),
  }))
  window.__sceneopsTest = test.protocol
}
function frame(time: number) {
  const delta = Math.min((time-last)/1000, 0.05); last=time
  if (!test?.paused) {
    const interact = inputSystem(game.world, input); movementSystem(game.world, delta); collectionSystem(game.world, scoreOutput)
    doorSystem(game.world, interact, document.querySelector<HTMLElement>('#prompt')!)
    test?.recordFrame(delta)
  }
  const [player] = game.world.with('player','position'); if (player) { gameHost.dataset.playerX=player.position.x.toFixed(3); gameHost.dataset.playerZ=player.position.z.toFixed(3) }
  renderer.render(scene, camera); requestAnimationFrame(frame)
}
requestAnimationFrame(frame)
}
start().catch(error => { document.querySelector<HTMLElement>('#prompt')!.textContent = `模型加载失败：${String(error)}` })
""",
        "src/game/world.ts": """import { World } from 'miniplex'
import * as THREE from 'three'
import { createCharacter, createCollectible } from './sceneops-demo-assets'
import { createDemoAsset, demoContent, type KeyDoorBehavior } from './sceneops-demo-content'

export type Entity = {
  position?: THREE.Vector3
  velocity?: THREE.Vector3
  mesh?: THREE.Object3D
  player?: true
  collectible?: true
  itemId?: string
  inventory?: Set<string>
  sceneObjectId?: string
  keyDoor?: { behavior: KeyDoorBehavior; closedRotation: number; open: boolean }
}
export async function createGameWorld(scene: THREE.Scene) {
  const world = new World<Entity>()
  const playerMesh = createCharacter('player'); scene.add(playerMesh)
  world.add({player:true,position:playerMesh.position,velocity:new THREE.Vector3(),mesh:playerMesh,inventory:new Set<string>()})
  for (const [x,z] of [[-4,-2],[0,2],[4,-1]]) {
    const mesh = createCollectible(); mesh.position.set(x,0,z); scene.add(mesh)
    world.add({collectible:true,position:mesh.position,mesh,itemId:demoContent.objects.find(item => item.behavior)?.behavior?.required_key_asset_id ?? 'key-item'})
  }
  for (const source of demoContent.objects) {
    const asset = demoContent.assets.find(item => item.asset_id === source.asset_id && item.asset_version === source.asset_version)
    if (!asset) throw new Error(`资产版本缺失：${source.asset_id}`)
    const mesh = await createDemoAsset(asset, {instanceId:source.id}), {position_m,rotation_y_deg,scale} = source.transform
    mesh.position.set(...position_m); mesh.scale.setScalar(scale); mesh.rotation.y=THREE.MathUtils.degToRad(rotation_y_deg)
    mesh.name=source.id; mesh.userData.sceneops_id=source.id; scene.add(mesh)
    world.add({sceneObjectId:source.id,position:mesh.position,mesh,
      ...(source.behavior ? {keyDoor:{behavior:source.behavior,closedRotation:mesh.rotation.y,open:false}} : {})})
  }
  return { world }
}
""",
        "src/game/systems/inputSystem.ts": """import type { World } from 'miniplex'
import type { Entity } from '../world'

export type InputState = { keys: Set<string>; interactRequested: boolean }

export function inputSystem(world: World<Entity>, input: InputState) {
  const keys = input.keys
  const x = Number(keys.has('d')||keys.has('arrowright'))-Number(keys.has('a')||keys.has('arrowleft'))
  const z = Number(keys.has('s')||keys.has('arrowdown'))-Number(keys.has('w')||keys.has('arrowup'))
  const length = Math.hypot(x,z)||1
  for (const entity of world.with('player','velocity')) entity.velocity.set(x/length*5,0,z/length*5)
  const interact = input.interactRequested
  input.interactRequested = false
  return interact
}
""",
        "src/game/systems/movementSystem.ts": """import { demoAssetBlocksPlayer } from '../sceneops-demo-content'
import type { World } from 'miniplex'
import type { Entity } from '../world'

export function movementSystem(world: World<Entity>, delta: number) {
  for (const entity of world.with('position','velocity')) {
    const previous = entity.position.clone()
    entity.position.addScaledVector(entity.velocity, delta)
    entity.position.x = Math.max(-8, Math.min(8, entity.position.x)); entity.position.z = Math.max(-5, Math.min(5, entity.position.z))
    if ([...world.with('sceneObjectId','mesh')].some(door => demoAssetBlocksPlayer(door.mesh, entity.position))) entity.position.copy(previous)
  }
}
""",
        "src/game/systems/collectionSystem.ts": """import type { World } from 'miniplex'
import type { Entity } from '../world'

let points = 0
export function resetScore(output: HTMLElement) { points = 0; output.textContent = '0' }
export function currentScore() { return points }
export function collectionSystem(world: World<Entity>, output: HTMLElement) {
  const [player] = world.with('player','position','inventory')
  if (!player) return
  for (const item of world.with('collectible','position','mesh')) {
    if (item.position.distanceTo(player.position) < .9) { if (item.itemId) player.inventory.add(item.itemId); world.remove(item); item.mesh.removeFromParent(); output.textContent=String(++points) }
  }
}
""",
        "src/game/systems/doorSystem.ts": """import * as THREE from 'three'
import type { World } from 'miniplex'
import type { Entity } from '../world'
import { keyDoorCanOpen, setDemoDoorOpen } from '../sceneops-demo-content'

export function doorSystem(world: World<Entity>, interact: boolean, prompt: HTMLElement) {
  const [player] = world.with('player','position','inventory')
  if (!player) return
  let message = ''
  for (const entity of world.with('keyDoor','mesh')) {
    const door = entity.keyDoor
    const distance = entity.mesh.position.distanceTo(player.position)
    if (!door.open && distance <= door.behavior.interaction_distance_m) {
      message = player.inventory.has(door.behavior.required_key_asset_id) ? '按空格或 Enter 开门' : '需要钥匙'
    }
    if (interact && !door.open && keyDoorCanOpen(player.position, entity.mesh, player.inventory, door.behavior)) {
      door.open = true; setDemoDoorOpen(entity.mesh, THREE.MathUtils.degToRad(door.behavior.open_angle_deg))
    }
  }
  prompt.textContent = message
}
""",
    }


def template_files(architecture: str) -> dict[str, str]:
    if architecture == "object-component":
        return object_component_files()
    if architecture == "ecs":
        return ecs_files()
    raise GameProjectError("未知游戏代码架构。")



def native_template_files(architecture: str) -> dict[str, str]:
    """Neutral new-project seed; legacy templates remain migration inputs only."""
    if architecture not in ('object-component', 'ecs'):
        raise GameProjectError('未知游戏代码架构。')
    files = {
        **_shared_files(ecs=architecture == 'ecs', include_demo=False),
        'AGENTS.md': '你正在制作游戏，不是在开发 SceneOps 平台。读取 ARCHITECTURE.md 和 .sceneops/creation-brief.md。保留已选架构、已有源码和真实资产来源；普通源码原生编辑，托管资产和实例使用 SceneOps 领域工具。用户已确认目标优先，不自动购买、提交或发布。\n',
        'README.md': """# 游戏工程

运行 `pnpm install`、`pnpm check`、`pnpm dev` 打开本地场景。
这是空白制作起点，不预设人物、收集、战斗或关卡目标。先读取 `ARCHITECTURE.md`，再按已确认简报增量制作。
工作台资产与实例由 `src/game/sceneops-demo-content.ts` 物化，运行入口实际读取其版本和变换。
坐标使用米、Y 轴向上。现有文件归用户所有，重新初始化不会替换用户源码。
""",
        'index.html': """<!doctype html>
<html lang="zh-CN">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><link rel="icon" href="data:,"/><title>新场景</title></head>
<body><div id="app"></div><p id="status" role="status"></p><script type="module" src="/src/main.ts"></script></body>
</html>
""",
        'src/style.css': """html,body,#app{width:100%;height:100%;margin:0;overflow:hidden;background:#20242a}body{font-family:system-ui,sans-serif;color:#fff}canvas{display:block}#status{position:fixed;bottom:16px;left:16px;right:16px;margin:0}#status:empty{display:none}
""",
        'src/game/SceneView.ts': """import * as THREE from 'three'

export class SceneView {
  readonly scene = new THREE.Scene()
  private readonly renderer = new THREE.WebGLRenderer({ antialias: true })
  private readonly camera = new THREE.PerspectiveCamera(50, 1, 0.1, 200)
  constructor(private readonly host: HTMLElement) {
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
    host.append(this.renderer.domElement)
    this.scene.background = new THREE.Color(0x20242a)
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x52565c, 2))
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(20, 20), new THREE.MeshStandardMaterial({ color: 0x63676c }))
    floor.rotation.x = -Math.PI / 2
    this.scene.add(floor)
    this.camera.position.set(8, 8, 10)
    this.camera.lookAt(0, 0, 0)
    window.addEventListener('resize', () => this.resize())
    this.resize()
  }
  private resize() {
    const width = this.host.clientWidth, height = Math.max(this.host.clientHeight, 1)
    this.renderer.setSize(width, height, false)
    this.camera.aspect = width / height
    this.camera.updateProjectionMatrix()
  }
  start(update: () => void) {
    this.renderer.setAnimationLoop(() => { update(); this.renderer.render(this.scene, this.camera) })
  }
}
""",
    }
    if architecture == 'object-component':
        files.update({
            'ARCHITECTURE.md': """# 对象／组件架构

`Game` 组织对象和帧循环，`SceneView` 负责显示，`SceneObject` 持有单个已登记场景实例。
新增行为放入所属对象，可复用能力提取为组件；保留该架构，不引入 ECS。
当前场景没有预置玩法。依据制作简报建立对象与行为，并继续读取托管内容的稳定 ID、资产版本和变换。
""",
            'src/main.ts': """import './style.css'
import { Game } from './game/Game'

const host = document.querySelector<HTMLElement>('#app')!
Game.create(host).then(game => game.start()).catch(error => {
  document.querySelector<HTMLElement>('#status')!.textContent = `场景加载失败：${String(error)}`
})
""",
            'src/game/objects/SceneObject.ts': """import * as THREE from 'three'
import { createDemoAsset, type DemoAsset, type DemoObject } from '../sceneops-demo-content'

export class SceneObject {
  static async create(source: DemoObject, asset: DemoAsset) {
    const mesh = await createDemoAsset(asset, {instanceId:source.id})
    return new SceneObject(source, mesh)
  }
  constructor(readonly source: DemoObject, readonly mesh: THREE.Object3D) {
    const transform = source.transform
    mesh.position.set(...transform.position_m)
    mesh.rotation.y = THREE.MathUtils.degToRad(transform.rotation_y_deg)
    mesh.scale.setScalar(transform.scale)
    mesh.name = source.id
    mesh.userData.sceneops_id = source.id
  }
}
""",
            'src/game/Game.ts': """import { SceneView } from './SceneView'
import { SceneObject } from './objects/SceneObject'
import { demoContent } from './sceneops-demo-content'

export class Game {
  private constructor(private readonly view: SceneView, readonly objects: SceneObject[]) {
    for (const object of objects) view.scene.add(object.mesh)
  }
  static async create(host: HTMLElement) {
    const objects = await Promise.all(demoContent.objects.map(source => {
      const asset = demoContent.assets.find(asset => asset.asset_id === source.asset_id && asset.asset_version === source.asset_version)
      if (!asset) throw new Error(`资产版本缺失：${source.asset_id}`)
      return SceneObject.create(source, asset)
    }))
    return new Game(new SceneView(host), objects)
  }
  start() { this.view.start(() => this.update()) }
  private update() {
    // Add object behavior here when the confirmed brief defines it.
  }
}
""",
        })
    else:
        files.update({
            'ARCHITECTURE.md': """# ECS 架构

Miniplex 是唯一 ECS 库。`world.ts` 定义实体组件数据，`systems` 中的系统查询实体，入口组织帧流水线。
`SceneView` 只负责 Three.js 显示。新增玩法定义组件和系统，不在实体类中存放行为，不替换 Miniplex。
当前世界没有预置玩法；托管场景的稳定 ID、资产版本、位置、旋转和缩放已接入实际渲染。
""",
            'src/main.ts': """import './style.css'
import { SceneView } from './game/SceneView'
import { createGameWorld } from './game/world'
import { renderSystem } from './game/systems/renderSystem'

async function start() {
  const view = new SceneView(document.querySelector<HTMLElement>('#app')!)
  const world = await createGameWorld(view.scene)
  view.start(() => renderSystem(world))
}
start().catch(error => {
  document.querySelector<HTMLElement>('#status')!.textContent = `场景加载失败：${String(error)}`
})
""",
            'src/game/world.ts': """import { World } from 'miniplex'
import * as THREE from 'three'
import { createDemoAsset, demoContent } from './sceneops-demo-content'

export type Entity = {
  sceneObjectId?: string
  position?: THREE.Vector3
  mesh?: THREE.Object3D
}
export async function createGameWorld(scene: THREE.Scene) {
  const world = new World<Entity>()
  for (const source of demoContent.objects) {
    const asset = demoContent.assets.find(asset => asset.asset_id === source.asset_id && asset.asset_version === source.asset_version)
    if (!asset) throw new Error(`资产版本缺失：${source.asset_id}`)
    const mesh = await createDemoAsset(asset, {instanceId:source.id})
    mesh.position.set(...source.transform.position_m)
    mesh.rotation.y = THREE.MathUtils.degToRad(source.transform.rotation_y_deg)
    mesh.scale.setScalar(source.transform.scale)
    mesh.name = source.id
    mesh.userData.sceneops_id = source.id
    scene.add(mesh)
    world.add({ sceneObjectId: source.id, position: mesh.position.clone(), mesh })
  }
  return world
}
""",
            'src/game/systems/renderSystem.ts': """import type { World } from 'miniplex'
import type { Entity } from '../world'

export function renderSystem(world: World<Entity>) {
  for (const entity of world.with('position', 'mesh')) entity.mesh.position.copy(entity.position)
}
""",
        })
    return files


class GameProjects:
    def __init__(self, repository):
        self.repository = repository

    def install_demo_assets(self, project_id: str, card_id: str) -> dict:
        """Install fixed pack files into an authorized, registered card worktree."""
        worktree = GitProjects(self.repository).get_card(project_id, card_id)
        root = self.repository._safe_existing_directory(Path(worktree['worktree_path']))
        installed, preserved = [], []
        for relative, content in demo_asset_files().items():
            target = root / relative
            parent = root
            for component in Path(relative).parts[:-1]:
                parent = self.repository._real_directory(parent / component, create=True)
            if target.is_symlink() or (target.exists() and not target.is_file()):
                raise GameProjectError(f'演示资产路径 {relative} 不是普通文件，未写入。')
            if target.exists():
                preserved.append(relative)
                continue
            self._write_text(target, content)
            installed.append(relative)
        return {'pack_id': 'sceneops-demo-pack', 'version': 1,
                'workspace_root': str(root), 'installed_files': installed,
                'preserved_files': preserved, 'module_path': 'src/game/sceneops-demo-assets.ts',
                'exports': ['createCharacter', 'createHouse', 'createTree', 'createCrate',
                            'createRock', 'createCollectible', 'createDemoScenery'],
                'integration_note': '先读取模块；从当前入口相对导入所需工厂，将返回的 Group 加入场景。'
                    'createCharacter 接受 player/enemy/npc/ally。安装不修改入口；已有文件保持原样。'}

    def materialize_demo_content(self, project_id: str, workspace_id: str, manifest: dict) -> dict:
        """Write derived runtime inputs only after validating the registered project workspace."""
        workspace = self.repository.get_project_demo_workspace(project_id, workspace_id)
        root = self.repository._safe_existing_directory(Path(workspace["workspace_root"]))
        if manifest.get("project_id") != project_id or manifest.get("workspace_id") != workspace_id:
            raise GameProjectError("Demo 内容版本不属于当前项目工作区。")
        scene_refs = {(item['asset_id'], item['asset_version']) for item in manifest.get('objects', [])}
        if any(asset.get("source_kind") in {"blender", "file"} and (asset['asset_id'], asset['asset_version']) in scene_refs for asset in manifest.get("assets", [])):
            consumers = [root / "src/game/objects/KeyDoor.ts", root / "src/game/objects/SceneObject.ts",
                         root / "src/game/world.ts"]
            existing = [path for path in consumers if path.exists()]
            if not existing or any(path.is_symlink() or not path.is_file()
                    or "createDemoAsset" not in path.read_text(encoding="utf-8") for path in existing):
                raise GameProjectError("LEGACY_RUNTIME_REQUIRES_EDIT：当前游戏尚未接入 GLB 加载；请修改现有运行代码后重新更新 Demo，用户行为源码保持不变。")
        source = root / "src" / "game" / "sceneops-demo-content.ts"
        metadata = self.repository._real_directory(root / ".sceneops", create=True)
        record = metadata / "demo-content.json"
        if not source.parent.is_dir() or source.parent.is_symlink():
            raise GameProjectError("游戏工程缺少可写入的 src/game 目录。")
        from .lookdev_content import write_lookdev_content
        write_lookdev_content(root, manifest, self._replace_text)
        self._replace_text(source, demo_content_source(manifest))
        self._replace_text(record, json.dumps(manifest, ensure_ascii=False, allow_nan=False, indent=2) + "\n")
        return {
            "workspace_id": workspace_id,
            "workspace_root": str(root),
            "source_path": "src/game/sceneops-demo-content.ts",
            "manifest_path": ".sceneops/demo-content.json",
            "scene_id": manifest.get("scene_id"),
            "scene_version": manifest.get("scene_version"),
        }

    @staticmethod
    def _replace_text(path: Path, content: str) -> None:
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise GameProjectError(f"派生内容路径 {path.name} 不是普通文件。")
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(content)
            os.replace(temporary, path)
        finally:
            if temporary.exists() and not temporary.is_symlink():
                temporary.unlink()

    def _root(self, project_id: str) -> Path:
        return self.repository._safe_existing_directory(Path(self.repository.get_folder_project(project_id).root_path))

    @staticmethod
    def _read_json(path: Path):
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
            raise GameProjectError("游戏架构记录不可安全读取。")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise GameProjectError("游戏架构记录不可读取。") from error

    @staticmethod
    def _write_text(path: Path, content: str):
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content.encode("utf-8"))

    def initialize(self, project_id: str, selection: dict, design_version: int,
                   *, commit_baseline: bool = True) -> dict:
        root = self._root(project_id)
        project = self.repository.get_folder_project(project_id)
        metadata = self.repository._real_directory(root / ".sceneops", create=True)
        marker = metadata / "game-architecture.json"
        if marker.exists() or marker.is_symlink():
            current = self._read_json(marker)
            if current.get("code_architecture") != selection["code_architecture"]:
                raise GameProjectError("游戏工程已有代码架构；更换架构需要建立明确迁移任务。")
            scaffold = current["scaffold"]
            if scaffold.get("initialization_status") != "generated":
                return scaffold
            recorded_version = current.get("design_version")
            if recorded_version is None or project.project_kind != "sceneops_created":
                # Old projects stay readable, but are not silently adopted into a new baseline.
                return scaffold
            if recorded_version != design_version:
                raise GameProjectError("游戏工程基线绑定了其他策划版本，请先建立明确迁移任务。")
            if not commit_baseline:
                return scaffold
            with self.repository.connect() as connection:
                baseline_exists = connection.execute(
                    'SELECT 1 FROM workspace_game_baselines WHERE project_id=?', (project_id,)).fetchone()
            # Once committed, project sources belong to the user, including older templates.
            if not baseline_exists:
                self._materialize_files(root, (native_template_files if current.get("template_kind") == "native-light"
                                              else template_files)(selection["code_architecture"]))
            baseline = self._commit_baseline(project_id, current, recorded_version)
            return {**scaffold, "baseline_commit": baseline}

        files = native_template_files(selection["code_architecture"])
        code_candidates = [root / "package.json", root / "index.html", root / "src"]
        existing_code = any(path.exists() or path.is_symlink() for path in code_candidates)
        if existing_code:
            self.repository.set_project_kind(project_id, "existing_unadopted")
            scaffold = {
                "root_path": str(root), "initialization_status": "existing",
                "project_kind": "existing_unadopted", "architecture_version": ARCHITECTURE_VERSION,
                "design_version": design_version, "baseline_commit": None,
                "package_manager": None, "entry_file": None, "generated_files": [],
                "check_command": None, "build_command": None, "preview_command": None,
            }
        else:
            scaffold = {
                "root_path": str(root), "initialization_status": "generated",
                "project_kind": "sceneops_created", "architecture_version": ARCHITECTURE_VERSION,
                "design_version": design_version, "baseline_commit": None,
                "package_manager": "pnpm", "entry_file": "src/main.ts",
                "generated_files": sorted(files), "check_command": "pnpm check",
                "build_command": "pnpm build", "preview_command": "pnpm dev",
            }
        record = {**selection, "project_kind": scaffold["project_kind"], "template_kind": "native-light",
                  "architecture_version": ARCHITECTURE_VERSION, "design_version": design_version,
                  "selected_at": datetime.now(timezone.utc).isoformat(), "scaffold": scaffold}
        self.repository._write_json_exclusive(marker, record)
        if scaffold["initialization_status"] != "generated":
            return scaffold
        self._materialize_files(root, files)
        if not commit_baseline:
            return scaffold
        baseline = self._commit_baseline(project_id, record, design_version)
        return {**scaffold, "baseline_commit": baseline}

    def _materialize_files(self, root: Path, files: dict[str, str]):
        for relative, content in files.items():
            target = root / relative
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if target.exists() or target.is_symlink():
                if (target.is_symlink() or not target.is_file()
                        or target.read_text(encoding="utf-8") != content):
                    raise GameProjectError(f"工程文件 {relative} 已存在，未覆盖。")
                continue
            self._write_text(target, content)

    def _commit_baseline(self, project_id: str, record: dict, design_version: int) -> str:
        scaffold = record["scaffold"]
        paths = [".sceneops/project.json", ".sceneops/game-architecture.json",
                 *scaffold["generated_files"]]
        return GitProjects(self.repository).commit_game_baseline(
            project_id, paths, f"Initialize game project: {record['architecture_label']}",
            design_version, ARCHITECTURE_VERSION)
