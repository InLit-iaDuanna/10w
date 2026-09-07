import assert from 'node:assert/strict'

let score = 2, resetCalls = 0
const adapter = createTestAdapter(() => { score = 0; resetCalls += 1 }, () => ({
  player: { x: 0, y: .5, z: 0 }, score,
  collectibles: [{ id: 'collectible-1', x: -4, y: .45, z: -2, collected: false, visible: true }],
}))
assert.equal(adapter.protocol.version, 1)
assert.deepEqual(adapter.protocol.states().map(state => state.id), ['start'])
assert.equal(adapter.protocol.diagnostics().player.y, .5)
adapter.recordFrame(.016)
adapter.protocol.pause()
assert.equal(adapter.paused, true)
assert.deepEqual(adapter.protocol.diagnostics().simulation, { paused: true, steps: 1, elapsed_seconds: .016 })
assert.throws(() => adapter.protocol.setState('missing'), /Unknown SceneOps test state/)
assert.equal(resetCalls, 0)
assert.equal(adapter.paused, true)
assert.equal(adapter.protocol.diagnostics().score, 2)
adapter.protocol.resume()
assert.equal(adapter.paused, false)
const reset = adapter.protocol.setState('start')
assert.equal(resetCalls, 1)
assert.equal(reset.score, 0)
assert.deepEqual(reset.simulation, { paused: false, steps: 0, elapsed_seconds: 0 })
assert.deepEqual(reset.randomness, { kind: 'none', description: 'fixed positions; no random source' })
assert.equal('step' in adapter.protocol, false)
assert.equal('advance' in adapter.protocol, false)
