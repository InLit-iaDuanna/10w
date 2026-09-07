"""Create the first real Three.js project without overwriting existing game code."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .git_projects import GitProjects
from .test_adapter_files import test_adapter_files


class GameProjectError(ValueError):
    pass


THREE_VERSION = "0.183.2"
MINIPLEX_VERSION = "2.0.0"
ARCHITECTURE_VERSION = 1


def _shared_files(*, ecs: bool) -> dict[str, str]:
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
        **test_adapter_files(),
        "README.md": """# SceneOps game project

This is the playable game project created from the technical plan selected in Design Room.

```bash
pnpm install
pnpm check
pnpm dev
```

Open the URL printed by Vite, then move with WASD or the arrow keys to collect the yellow items.
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
  <body><div id="hud">移动：WASD / 方向键　得分：<strong id="score">0</strong></div><div id="app"></div><script type="module" src="/src/main.ts"></script></body>
</html>
""",
        "src/style.css": """html,body,#app{width:100%;height:100%;margin:0;overflow:hidden;background:#111827}body{font-family:system-ui,sans-serif;color:white}canvas{display:block}#hud{position:fixed;z-index:2;top:16px;left:16px;padding:10px 14px;border:1px solid #ffffff2e;border-radius:10px;background:#111827d9}
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
new Game(host).start()
""",
        "src/game/components/InputController.ts": """export class InputController {
  private readonly pressed = new Set<string>()
  constructor() {
    window.addEventListener('keydown', event => this.pressed.add(event.key.toLowerCase()))
    window.addEventListener('keyup', event => this.pressed.delete(event.key.toLowerCase()))
  }
  direction() {
    const x = Number(this.pressed.has('d') || this.pressed.has('arrowright')) - Number(this.pressed.has('a') || this.pressed.has('arrowleft'))
    const z = Number(this.pressed.has('s') || this.pressed.has('arrowdown')) - Number(this.pressed.has('w') || this.pressed.has('arrowup'))
    const length = Math.hypot(x, z) || 1
    return { x: x / length, z: z / length }
  }
  reset() { this.pressed.clear() }
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

export class Player {
  readonly mesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshStandardMaterial({ color: 0x60a5fa }))
  constructor(private readonly input: InputController) { this.mesh.position.y = 0.5 }
  update(deltaSeconds: number) {
    const direction = this.input.direction()
    this.mesh.position.x = THREE.MathUtils.clamp(this.mesh.position.x + direction.x * 5 * deltaSeconds, -8, 8)
    this.mesh.position.z = THREE.MathUtils.clamp(this.mesh.position.z + direction.z * 5 * deltaSeconds, -5, 5)
  }
}
""",
        "src/game/objects/Collectible.ts": """import * as THREE from 'three'

export class Collectible {
  readonly mesh = new THREE.Mesh(new THREE.SphereGeometry(0.35, 18, 12), new THREE.MeshStandardMaterial({ color: 0xfbbf24 }))
  collected = false
  constructor(x: number, z: number) { this.mesh.position.set(x, 0.45, z) }
  tryCollect(player: THREE.Vector3) {
    if (this.collected || this.mesh.position.distanceTo(player) >= 0.9) return false
    this.collected = true
    this.mesh.visible = false
    return true
  }
}
""",
        "src/game/Game.ts": """import * as THREE from 'three'
import { InputController } from './components/InputController'
import { ScoreCounter } from './components/ScoreCounter'
import { Collectible } from './objects/Collectible'
import { Player } from './objects/Player'
import { createTestAdapter } from './sceneops-test'

export class Game {
  private readonly renderer = new THREE.WebGLRenderer({ antialias: true })
  private readonly scene = new THREE.Scene()
  private readonly camera = new THREE.PerspectiveCamera(55, 1, 0.1, 100)
  private readonly input = new InputController()
  private readonly player = new Player(this.input)
  private readonly collectibles = [[-4,-2],[0,2],[4,-1]].map(([x,z]) => new Collectible(x, z))
  private readonly score = new ScoreCounter(document.querySelector<HTMLElement>('#score')!)
  private last = performance.now()
  private test?: ReturnType<typeof createTestAdapter>

  constructor(private readonly host: HTMLElement) {
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); this.host.append(this.renderer.domElement)
    this.scene.background = new THREE.Color(0x111827)
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x334155, 2.2), this.player.mesh)
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
        this.last = performance.now()
        this.host.dataset.playerX = spawn.x.toFixed(3); this.host.dataset.playerZ = spawn.z.toFixed(3)
      }, () => ({
        player: { x: this.player.mesh.position.x, y: this.player.mesh.position.y, z: this.player.mesh.position.z },
        score: this.score.current(),
        collectibles: this.collectibles.map((item, index) => ({
          id: `collectible-${index + 1}`, x: item.mesh.position.x, y: item.mesh.position.y, z: item.mesh.position.z,
          collected: item.collected, visible: item.mesh.visible,
        })),
      }))
      window.__sceneopsTest = this.test.protocol
    }
  }
  start() { requestAnimationFrame(time => this.update(time)) }
  private update(time: number) {
    const delta = Math.min((time - this.last) / 1000, 0.05); this.last = time
    if (!this.test?.paused) {
      this.player.update(delta)
      this.collectibles.forEach(item => { if (item.tryCollect(this.player.mesh.position)) this.score.collect() })
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

const host = document.querySelector<HTMLDivElement>('#app')
const score = document.querySelector<HTMLElement>('#score')
if (!host || !score) throw new Error('Missing game host')
const gameHost: HTMLDivElement = host
const scoreOutput: HTMLElement = score
const renderer = new THREE.WebGLRenderer({ antialias: true }); gameHost.append(renderer.domElement)
const scene = new THREE.Scene(); scene.background = new THREE.Color(0x111827)
const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 100); camera.position.set(0, 10, 11); camera.lookAt(0, 0, 0)
scene.add(new THREE.HemisphereLight(0xffffff, 0x334155, 2.2))
const floor = new THREE.Mesh(new THREE.PlaneGeometry(18, 12), new THREE.MeshStandardMaterial({ color: 0x334155 })); floor.rotation.x = -Math.PI / 2; scene.add(floor)
const game = createGameWorld(scene)
const keys = new Set<string>(); addEventListener('keydown', e => keys.add(e.key.toLowerCase())); addEventListener('keyup', e => keys.delete(e.key.toLowerCase()))
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
    keys.clear(); player.position.copy(spawn); player.velocity.set(0, 0, 0); resetScore(scoreOutput)
    items.forEach((item, index) => {
      item.position.copy(spawns[index]); item.mesh.visible = true
      if (!game.world.has(item)) game.world.add(item)
      scene.add(item.mesh)
    })
    last = performance.now()
    gameHost.dataset.playerX = spawn.x.toFixed(3); gameHost.dataset.playerZ = spawn.z.toFixed(3)
  }, () => ({
    player: { x: player.position.x, y: player.position.y, z: player.position.z }, score: currentScore(),
    collectibles: items.map((item, index) => ({
      id: `collectible-${index + 1}`, x: item.position.x, y: item.position.y, z: item.position.z,
      collected: !game.world.has(item), visible: item.mesh.parent === scene && item.mesh.visible,
    })),
  }))
  window.__sceneopsTest = test.protocol
}
function frame(time: number) {
  const delta = Math.min((time-last)/1000, 0.05); last=time
  if (!test?.paused) {
    inputSystem(game.world, keys); movementSystem(game.world, delta); collectionSystem(game.world, scoreOutput)
    test?.recordFrame(delta)
  }
  const [player] = game.world.with('player','position'); if (player) { gameHost.dataset.playerX=player.position.x.toFixed(3); gameHost.dataset.playerZ=player.position.z.toFixed(3) }
  renderer.render(scene, camera); requestAnimationFrame(frame)
}
requestAnimationFrame(frame)
""",
        "src/game/world.ts": """import { World } from 'miniplex'
import * as THREE from 'three'

export type Entity = {
  position?: THREE.Vector3
  velocity?: THREE.Vector3
  mesh?: THREE.Mesh
  player?: true
  collectible?: true
}
export function createGameWorld(scene: THREE.Scene) {
  const world = new World<Entity>()
  const playerMesh = new THREE.Mesh(new THREE.BoxGeometry(1,1,1), new THREE.MeshStandardMaterial({color:0x60a5fa})); playerMesh.position.y=.5; scene.add(playerMesh)
  world.add({player:true,position:playerMesh.position,velocity:new THREE.Vector3(),mesh:playerMesh})
  for (const [x,z] of [[-4,-2],[0,2],[4,-1]]) {
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(.35,18,12), new THREE.MeshStandardMaterial({color:0xfbbf24})); mesh.position.set(x,.45,z); scene.add(mesh)
    world.add({collectible:true,position:mesh.position,mesh})
  }
  return { world }
}
""",
        "src/game/systems/inputSystem.ts": """import type { World } from 'miniplex'
import type { Entity } from '../world'

export function inputSystem(world: World<Entity>, keys: Set<string>) {
  const x = Number(keys.has('d')||keys.has('arrowright'))-Number(keys.has('a')||keys.has('arrowleft'))
  const z = Number(keys.has('s')||keys.has('arrowdown'))-Number(keys.has('w')||keys.has('arrowup'))
  const length = Math.hypot(x,z)||1
  for (const entity of world.with('player','velocity')) entity.velocity.set(x/length*5,0,z/length*5)
}
""",
        "src/game/systems/movementSystem.ts": """import type { World } from 'miniplex'
import type { Entity } from '../world'

export function movementSystem(world: World<Entity>, delta: number) {
  for (const entity of world.with('position','velocity')) {
    entity.position.addScaledVector(entity.velocity, delta)
    entity.position.x = Math.max(-8, Math.min(8, entity.position.x)); entity.position.z = Math.max(-5, Math.min(5, entity.position.z))
  }
}
""",
        "src/game/systems/collectionSystem.ts": """import type { World } from 'miniplex'
import type { Entity } from '../world'

let points = 0
export function resetScore(output: HTMLElement) { points = 0; output.textContent = '0' }
export function currentScore() { return points }
export function collectionSystem(world: World<Entity>, output: HTMLElement) {
  const [player] = world.with('player','position')
  if (!player) return
  for (const item of world.with('collectible','position','mesh')) {
    if (item.position.distanceTo(player.position) < .9) { world.remove(item); item.mesh.removeFromParent(); output.textContent=String(++points) }
  }
}
""",
    }


def template_files(architecture: str) -> dict[str, str]:
    if architecture == "object-component":
        return object_component_files()
    if architecture == "ecs":
        return ecs_files()
    raise GameProjectError("未知游戏代码架构。")


class GameProjects:
    def __init__(self, repository):
        self.repository = repository

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
            self._materialize_files(root, template_files(selection["code_architecture"]))
            baseline = self._commit_baseline(project_id, current, recorded_version)
            return {**scaffold, "baseline_commit": baseline}

        files = template_files(selection["code_architecture"])
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
        record = {**selection, "project_kind": scaffold["project_kind"],
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
