// Bounded keyboard/readback protocol. No caller-authored JS or assertion language.
export async function installClock(page) {
  await page.clock.install({ time: new Date('2026-01-01T00:00:00Z') });
  await page.clock.pauseAt(new Date('2026-01-01T00:00:01Z'));
}

const fail = (code, message) => { throw Object.assign(new Error(message), { code }); };
const positionEqual = (a, b) => a && b && ['x', 'y', 'z'].every(key => Math.abs(a[key] - b[key]) < 1e-6);

export async function interact(page, request, result, heldKeys) {
  result.input_trace = [];
  result.assertions = [];
  result.check_scope = request.check;
  result.time_control = { kind: 'playwright-clock', clock_installed_before_navigation: true,
    requested_ms: request.steps.reduce((sum, step) => sum + step.duration_ms, 0), real_fps_measured: false };
  const assert = (id, passed) => result.assertions.push({ id, passed: !!passed });
  const release = async () => {
    for (const key of heldKeys) await page.keyboard.up(key);
    heldKeys.clear();
  };
  const hooked = request.check !== 'current-input';
  const setState = async () => {
    // Reset on the original RAF boundary, so the first movement frame receives a
    // full simulation delta rather than a machine-dependent partial frame.
    const acknowledgment = page.evaluate(id => new Promise((resolve, reject) => {
      requestAnimationFrame(() => {
        try { resolve(window.__sceneopsTest.setState(id)); } catch (error) { reject(error); }
      });
    }), request.state_id);
    await page.clock.runFor(16);
    return await acknowledgment;
  };
  const read = async () => {
    const data = await page.evaluate(useHooks => useHooks
      ? window.__sceneopsTest.diagnostics()
      : { player: { x: Number(document.querySelector('#app')?.dataset.playerX), y: 0,
          z: Number(document.querySelector('#app')?.dataset.playerZ) },
          score: Number(document.querySelector('#score')?.textContent) }, hooked);
    if (JSON.stringify(data).length > 32768) fail('BROWSER_DIAGNOSTICS_TOO_LARGE', 'Game diagnostics exceed 32 KiB.');
    return data;
  };
  const version = await page.evaluate(() => window.__sceneopsTest?.version ?? null);
  if (hooked) {
    if (version !== 1) fail('BROWSER_TEST_HOOKS_UNAVAILABLE', 'This build does not provide version 1 test hooks.');
    const states = await page.evaluate(() => window.__sceneopsTest.states());
    if (!Array.isArray(states) || states.length > 32 || JSON.stringify(states).length > 8192)
      fail('BROWSER_TEST_PROTOCOL_INVALID', 'Invalid state catalogue.');
    result.available_states = states;
    if (!states.some(state => state.id === request.state_id)) fail('BROWSER_TEST_STATE_UNKNOWN', 'Requested test state is not supported.');
    await release();
    // Deliberately leave a listener key down across reset, then verify that the
    // adapter cleared it. This is a setup check, separate from gameplay checks.
    await page.keyboard.down('ArrowDown'); heldKeys.add('ArrowDown');
    await page.clock.runFor(400);
    result.before_reset = await read();
    const acknowledgment = await setState();
    const actual = await read();
    result.state_setup = { requested: request.state_id, acknowledgment, actual };
    await page.clock.runFor(160);
    const resetIdle = await read();
    assert('reset-clears-residual-input', positionEqual(actual.player, resetIdle.player));
    assert('state-readback', actual.state_id === request.state_id);
    if (request.check === 'movement-collection') assert('reset-game-state', result.before_reset.score > 0
      && result.before_reset.simulation?.steps > 0 && actual.score === 0
      && actual.collectibles?.every(item => !item.collected && item.visible)
      && actual.simulation?.steps === 0 && actual.simulation?.elapsed_seconds === 0);
    await release();
    await setState();
    // Pause and resume use the real game loop; only clock time is controlled.
    await page.evaluate(() => window.__sceneopsTest.pause());
    const paused = await read();
    await page.clock.runFor(1600);
    const afterPause = await read();
    assert('pause-does-not-simulate', positionEqual(paused.player, afterPause.player)
      && paused.simulation.steps === afterPause.simulation.steps);
    await page.evaluate(() => window.__sceneopsTest.resume());
    await page.clock.runFor(16);
    const resumed = await read();
    assert('resume-no-time-jump', resumed.simulation.elapsed_seconds - afterPause.simulation.elapsed_seconds <= .017);
    // Use the requested state for the input run, never a synthesized position.
    await setState();
  } else {
    assert('delivery-has-no-state-hooks', version === null);
    if (version !== null) fail('BROWSER_DELIVERY_HOOKS_EXPOSED', 'Delivery build exposes test state controls.');
    await page.clock.runFor(16);
  }
  const initial = await read();
  result.initial_state = initial;
  try {
    for (const step of request.steps) {
      await release();
      for (const key of step.keys) { await page.keyboard.down(key); heldKeys.add(key); }
      await page.clock.runFor(step.duration_ms);
      result.input_trace.push({ keys: step.keys, duration_ms: step.duration_ms, actual: await read() });
    }
  } finally { await release(); }
  result.final_state = await read();
  const [moved, stopped] = result.input_trace.map(step => step.actual);
  assert('keyboard-moves-player', initial.player && moved.player
    && Number.isFinite(moved.player.x) && Number.isFinite(moved.player.z)
    && !positionEqual(initial.player, moved.player));
  if (request.steps[1]?.keys.length === 0) assert('key-release-stops-player', positionEqual(moved.player, stopped.player));
  if (request.check === 'movement-collection') {
    const away = result.input_trace[2].actual;
    assert('leave-and-revisit', !positionEqual(away.player, moved.player)
      && positionEqual(result.final_state.player, moved.player));
    const collected = moved.collectibles?.filter(item => item.collected) ?? [];
    assert('input-collects-and-scores', collected.length > 0 && moved.score - initial.score === collected.length
      && collected.every(item => !item.visible));
    assert('same-items-not-scored-twice', result.final_state.score === moved.score
      && collected.every(item => result.final_state.collectibles.some(last => last.id === item.id && last.collected && !last.visible)));
  }
  if (hooked) await page.evaluate(() => window.__sceneopsTest.pause());
  result.behavior_checks_verified = result.assertions.every(assertion => assertion.passed);
  result.gameplay_verified = false;
  result.visual_reviewed = false;
  // Allow browser paint for screenshot; paused hooks keep the simulated game still.
  await page.clock.resume();
}
