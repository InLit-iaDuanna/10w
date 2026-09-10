/** Execute the procedural asset source against the installed Three.js primitives. */
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { createRequire } = require('node:module')
const ts = require('typescript')
const viewerRequire = createRequire(path.resolve('packages/scene-viewer/package.json'))
const THREE = viewerRequire('three')
const source = fs.readFileSync(process.argv[2], 'utf8')
const compiled = ts.transpileModule(source, { compilerOptions: {
  target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS,
}})
const exportsObject = {}
new Function('require', 'exports', compiled.outputText)(() => THREE, exportsObject)
const { createCharacter, createHouse, createTree, createCrate, createRock,
  createCollectible, createDemoScenery, ROLE_COLORS } = exportsObject
const roles = ['player', 'enemy', 'npc', 'ally']
const characters = roles.map(role => createCharacter(role))
const shape = group => group.children.map(mesh => ({ name: mesh.name,
  positions: Array.from(mesh.geometry.attributes.position.array),
  position: mesh.position.toArray(), rotation: mesh.rotation.toArray(), scale: mesh.scale.toArray(),
}))
for (const [index, character] of characters.entries()) {
  assert.deepEqual(shape(character), shape(characters[0]))
  assert.equal(character.getObjectByName('body').material.color.getHex(), ROLE_COLORS[roles[index]])
  assert.ok(Math.abs(new THREE.Box3().setFromObject(character).min.y) < 1e-6)
}
assert.equal(new Set(Object.values(ROLE_COLORS)).size, 4)
for (const factory of [createHouse, createTree, createCrate, createRock, createCollectible]) {
  const object = factory()
  assert.ok(object.children.length > 0)
  assert.ok(!new THREE.Box3().setFromObject(object).isEmpty())
  object.traverse(part => { if (part.isMesh) assert.ok(part.geometry.attributes.position.count > 0) })
}
const village = createDemoScenery()
assert.equal(village.children.filter(child => child.userData.kind === 'house').length, 2)
assert.deepEqual(village.children.filter(child => child.userData.kind === 'character')
  .map(child => child.userData.role).sort(), ['ally','enemy','npc'])
const player = createCharacter('player'), gem = createCollectible()
gem.position.set(4,0,-1)
assert.ok(player.position.distanceTo(gem.position) > .9)
player.position.set(4,0,-1)
assert.ok(player.position.distanceTo(gem.position) < .9)
console.log('Demo geometry smoke passed: role silhouettes, colors, scenery and collection coordinates.')
