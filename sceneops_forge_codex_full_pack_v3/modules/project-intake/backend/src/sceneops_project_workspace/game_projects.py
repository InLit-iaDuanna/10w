"""Create the first real Three.js project without overwriting existing game code."""
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path


class GameProjectError(ValueError):
    pass


THREE_VERSION = "0.183.2"
MINIPLEX_VERSION = "2.0.0"
EXCLUDED_PROJECT_DIRECTORIES = {
    '.git', '.sceneops', '.venv', 'node_modules', 'dist', 'build', 'coverage',
    'Library', 'Temp', 'Obj', 'Logs', 'Build', 'Builds',
}
MAX_EXISTING_PROJECT_FILES = 2048
MAX_EXISTING_PROJECT_BYTES = 256 * 1024 * 1024
MAX_EXISTING_FILE_BYTES = 64 * 1024 * 1024


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
}
""",
        "src/game/components/ScoreCounter.ts": """export class ScoreCounter {
  private value = 0
  constructor(private readonly output: HTMLElement) { this.render() }
  collect() { this.value += 1; this.render() }
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

export class Game {
  private readonly renderer = new THREE.WebGLRenderer({ antialias: true })
  private readonly scene = new THREE.Scene()
  private readonly camera = new THREE.PerspectiveCamera(55, 1, 0.1, 100)
  private readonly player = new Player(new InputController())
  private readonly collectibles = [[-4,-2],[0,2],[4,-1]].map(([x,z]) => new Collectible(x, z))
  private readonly score = new ScoreCounter(document.querySelector<HTMLElement>('#score')!)
  private last = performance.now()

  constructor(private readonly host: HTMLElement) {
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); this.host.append(this.renderer.domElement)
    this.scene.background = new THREE.Color(0x111827)
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x334155, 2.2), this.player.mesh)
    this.collectibles.forEach(item => this.scene.add(item.mesh))
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(18, 12), new THREE.MeshStandardMaterial({ color: 0x334155 }))
    floor.rotation.x = -Math.PI / 2; this.scene.add(floor); this.camera.position.set(0, 10, 11); this.camera.lookAt(0, 0, 0)
    window.addEventListener('resize', () => this.resize()); this.resize()
  }
  start() { requestAnimationFrame(time => this.update(time)) }
  private update(time: number) {
    const delta = Math.min((time - this.last) / 1000, 0.05); this.last = time
    this.player.update(delta)
    this.host.dataset.playerX = this.player.mesh.position.x.toFixed(3)
    this.host.dataset.playerZ = this.player.mesh.position.z.toFixed(3)
    this.collectibles.forEach(item => { if (item.tryCollect(this.player.mesh.position)) this.score.collect() })
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
import { collectionSystem } from './game/systems/collectionSystem'

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
function frame(time: number) {
  const delta = Math.min((time-last)/1000, 0.05); last=time
  inputSystem(game.world, keys); movementSystem(game.world, delta); collectionSystem(game.world, scoreOutput)
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

    @staticmethod
    def _copy_file(source: Path, destination: Path):
        source_descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            info = os.fstat(source_descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_EXISTING_FILE_BYTES:
                raise GameProjectError(f"工程文件 {source.name} 不是可复制的普通文件或体积过大。")
            mode = 0o755 if info.st_mode & stat.S_IXUSR else 0o644
            destination_descriptor = os.open(
                destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
            try:
                with os.fdopen(source_descriptor, 'rb', closefd=False) as source_stream, \
                        os.fdopen(destination_descriptor, 'wb') as destination_stream:
                    copied = 0
                    while chunk := source_stream.read(1024 * 1024):
                        copied += len(chunk)
                        if copied > MAX_EXISTING_FILE_BYTES:
                            raise GameProjectError(f"工程文件 {source.name} 在复制时超出体积限制。")
                        destination_stream.write(chunk)
            except Exception:
                destination.unlink(missing_ok=True)
                raise
        finally:
            os.close(source_descriptor)

    @staticmethod
    def _existing_project_files(root: Path) -> list[Path]:
        files, total = [], 0
        for parent, directories, names in os.walk(root, followlinks=False):
            directories[:] = sorted(name for name in directories
                if name not in EXCLUDED_PROJECT_DIRECTORIES and not name.startswith('.')
                and not (Path(parent) / name).is_symlink())
            for name in sorted(names):
                if name.startswith('.') and name != '.gitignore':
                    continue
                source = Path(parent) / name
                if source.is_symlink():
                    continue
                try:
                    info = source.stat()
                except OSError as error:
                    raise GameProjectError("读取已有工程文件时项目发生变化，请重试。") from error
                if not stat.S_ISREG(info.st_mode):
                    continue
                if info.st_nlink != 1:
                    raise GameProjectError(f"已有工程文件 {source.relative_to(root)} 存在多个硬链接，未复制到卡片工作区。")
                if info.st_size > MAX_EXISTING_FILE_BYTES:
                    raise GameProjectError(f"已有工程文件 {source.relative_to(root)} 体积过大，未复制到卡片工作区。")
                files.append(source)
                total += info.st_size
                if len(files) > MAX_EXISTING_PROJECT_FILES or total > MAX_EXISTING_PROJECT_BYTES:
                    raise GameProjectError("已有工程超出卡片工作区复制范围，请先将工程纳入 Git 后重试。")
        return files

    def initialize(self, project_id: str, selection: dict) -> dict:
        root = self._root(project_id)
        metadata = self.repository._real_directory(root / ".sceneops", create=True)
        marker = metadata / "game-architecture.json"
        if marker.exists() or marker.is_symlink():
            current = self._read_json(marker)
            if current.get("code_architecture") != selection["code_architecture"]:
                raise GameProjectError("游戏工程已有代码架构；更换架构需要建立明确迁移任务。")
            return current["scaffold"]

        files = template_files(selection["code_architecture"])
        code_candidates = [root / "package.json", root / "index.html", root / "src"]
        existing_code = any(path.exists() or path.is_symlink() for path in code_candidates)
        if existing_code:
            scaffold = {
                "root_path": str(root), "initialization_status": "existing",
                "package_manager": None, "entry_file": None, "generated_files": [],
                "check_command": None, "build_command": None, "preview_command": None,
            }
        else:
            for relative, content in files.items():
                target = root / relative
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                if target.exists() or target.is_symlink():
                    if target.is_symlink() or not target.is_file() or target.read_text(encoding="utf-8") != content:
                        raise GameProjectError(f"工程文件 {relative} 已存在，未覆盖。")
                    continue
                self._write_text(target, content)
            scaffold = {
                "root_path": str(root), "initialization_status": "generated",
                "package_manager": "pnpm", "entry_file": "src/main.ts",
                "generated_files": sorted(files), "check_command": "pnpm check",
                "build_command": "pnpm build", "preview_command": "pnpm dev",
            }
        record = {**selection, "selected_at": datetime.now(timezone.utc).isoformat(), "scaffold": scaffold}
        self.repository._write_json_exclusive(marker, record)
        return scaffold

    def materialize_card(self, project_id: str, target: Path, technical_plan: dict | None):
        if not technical_plan:
            return
        scaffold = technical_plan.get("scaffold") or {}
        status = scaffold.get("initialization_status")
        if status not in ("generated", "existing"):
            return
        root = self._root(project_id)
        sources = ([root / relative for relative in scaffold.get("generated_files", [])]
                   if status == "generated" else self._existing_project_files(root))
        for source in sources:
            relative = source.relative_to(root)
            destination = target / relative
            if source.is_symlink() or not source.is_file():
                raise GameProjectError(f"工程文件 {relative} 不可安全复制。")
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if destination.exists() or destination.is_symlink():
                continue
            self._copy_file(source, destination)
        marker = target / ".sceneops" / "game-architecture.json"
        if not marker.exists() and not marker.is_symlink():
            self.repository._write_json_exclusive(marker, technical_plan)
