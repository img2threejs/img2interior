import test from 'node:test';
import assert from 'node:assert/strict';
import { THREE, runtime, curtainFixture } from './helpers.mjs';
const { createCurtainInteraction } = await runtime('interior-curtains.js');

function tick(interaction, frames = 90) {
  interaction.update(0, 0);
  for (let i = 1; i <= frames; i++) interaction.update(1/60, i/60);
}

test('explicit rail frames move a translated panel, pin headers and preserve geometry/UV identities', () => {
  const f = curtainFixture();
  const geometry = f.cloth.geometry;
  const position = geometry.getAttribute('position');
  const uv = geometry.getAttribute('uv');
  const uv1 = geometry.getAttribute('uv1');
  const index = geometry.index;
  const original = position.array.slice();
  const normals = geometry.getAttribute('normal').array.slice();
  const originalUV = uv.array.slice();
  const usage = position.usage;
  const interaction = createCurtainInteraction(f);
  assert.equal(interaction.count, 1);
  interaction.setWind(false);
  interaction.setClosure(1);
  tick(interaction);
  const result = interaction.snapshot();
  assert.ok(result.closure > 0.99);
  assert.ok(result.panels[0].topAnchorError < 1e-10);
  // Signed rail is +X, not the legacy Oak -Z; translated room has x=9..15.
  assert.ok(result.panels[0].probes[3].world[0] > 11.79);
  assert.ok(Math.abs(result.panels[0].probes[3].world[2]-20) < 1e-6);
  for (const { world } of result.panels[0].probes) {
    world.forEach((value, axis) => assert.ok(value >= f.roomBounds.min[axis] && value <= f.roomBounds.max[axis]));
  }
  assert.equal(f.cloth.geometry, geometry);
  assert.equal(geometry.getAttribute('position'), position);
  assert.equal(geometry.getAttribute('uv'), uv);
  assert.equal(geometry.getAttribute('uv1'), uv1);
  assert.equal(geometry.index, index);
  assert.deepEqual(uv.array, originalUV);
  assert.notDeepEqual(position.array, original);
  interaction.reset();
  assert.deepEqual(position.array, original);
  interaction.setClosure(1);
  tick(interaction, 4);
  interaction.dispose();
  interaction.dispose();
  assert.deepEqual(position.array, original);
  assert.deepEqual(geometry.getAttribute('normal').array, normals);
  assert.equal(position.usage, usage);
  assert.equal(f.win.listenerCount()+f.doc.listenerCount()+f.canvas.listenerCount()+f.motion.listenerCount(), 0);
  assert.equal(interaction.update(1, 1), false);
});

test('material-point grips exclusively own wheel and release on capture, visibility and multitouch interruption', () => {
  const f = curtainFixture();
  const interaction = createCurtainInteraction(f);
  interaction.setWind(false);
  const down = () => f.win.emit('pointerdown', f.pointerAt([10.5, 1.4, 20]));
  assert.equal(down().prevented, true);
  assert.equal(interaction.grabbing, true);
  assert.equal(f.controls.enabled, false);
  assert.equal(f.win.emit('wheel').prevented, true);
  assert.equal(f.win.listenerCount('wheel'), 1);
  f.canvas.releasePointerCapture(1);
  assert.equal(interaction.grabbing, false);
  assert.equal(f.controls.enabled, true);
  assert.equal(f.win.listenerCount('wheel'), 0);
  down();
  f.doc.hidden = true;
  f.doc.emit('visibilitychange');
  assert.equal(interaction.grabbing, false);
  assert.equal(f.canvas.hasPointerCapture(1), false);
  assert.equal(interaction.update(60, 60), false);
  f.doc.hidden = false;
  f.doc.emit('visibilitychange');
  down();
  f.win.emit('pointerdown', f.pointerAt([10.6, 1.4, 20], 2, { isPrimary: false, pointerType: 'touch' }));
  assert.equal(interaction.grabbing, false);
  assert.equal(down().prevented, undefined); // still blocked until both contacts end
  f.win.emit('pointerup', { pointerId: 1 });
  f.win.emit('pointerup', { pointerId: 2 });
  down();
  assert.equal(interaction.grabbing, true);
  interaction.dispose();
  assert.equal(f.controls.enabled, true);
  assert.equal(f.canvas.hasPointerCapture(1), false);
  assert.equal(f.win.listenerCount('wheel'), 0);
});

test('hem picking binds barycentric material points, not its decorative texture UV', () => {
  const f = curtainFixture({ hem: true });
  const interaction = createCurtainInteraction(f);
  interaction.setWind(false);
  f.win.emit('pointerdown', f.pointerAt([10.75, 0.4, 20.02]));
  const grip = interaction.snapshot().grip;
  assert.ok(grip);
  assert.equal(grip.part, 'hem');
  assert.ok(Math.abs(grip.uv[0]-0.75) < 1e-4);
  assert.ok(Math.abs(grip.uv[1]) < 1e-6);
  f.win.emit('pointermove', f.pointerAt([11.15, 0.4, 20.02]));
  assert.ok(interaction.targetClosure > 0);
  tick(interaction, 8);
  assert.ok(interaction.snapshot().panels[0].topAnchorError < 1e-10);
  interaction.setEnabled(false);
  assert.equal(interaction.grabbing, false);
  assert.equal(f.win.listenerCount('wheel'), 0);
  interaction.dispose();
});

test('reduced-motion stops wind; settled and zero-cloth scenes stop requesting frames', () => {
  const f = curtainFixture();
  const interaction = createCurtainInteraction(f);
  f.motion.matches = true;
  f.motion.emit('change');
  assert.equal(interaction.wind, false);
  assert.equal(interaction.setWind(true), false);
  tick(interaction, 180);
  assert.equal(interaction.update(1/60, 4), false);
  interaction.dispose();
  const empty = curtainFixture();
  empty.root.clear();
  const noCloth = createCurtainInteraction(empty);
  assert.equal(noCloth.count, 0);
  assert.equal(noCloth.update(1/60, 1), false);
  assert.equal(empty.controls.enabled, true);
  noCloth.dispose();
  assert.equal(empty.win.listenerCount(), 0);
});

test('invalid frames, duplicate geometry and missing grid points fail before acquiring input', () => {
  for (const [mutate, message] of [
    [f => { delete f.cloth.userData.curtain_rail_axis; }, /explicit Y-up curtain_rail_axis/],
    [f => { f.cloth.userData.curtain_depth_axis = [1, 0, 0]; }, /orthogonal unit/],
    [f => { f.root.rotation.y = 0.2; }, /identity scene root/],
    [f => { f.root.add(new THREE.Mesh(f.cloth.geometry, f.cloth.material)); }, /shares geometry/],
    [f => { f.cloth.geometry.getAttribute('uv').setXY(0, 0.01, 0.99); }, /missing material grid point/],
    [f => { f.cloth.userData.curtain_closed_width = 100; }, /header leaves roomBounds/],
  ]) {
    const f = curtainFixture();
    const original = f.cloth.geometry.getAttribute('position').array.slice();
    mutate(f);
    assert.throws(() => createCurtainInteraction(f), message);
    assert.deepEqual(f.cloth.geometry.getAttribute('position').array, original);
    assert.equal(f.win.listenerCount()+f.doc.listenerCount()+f.canvas.listenerCount()+f.motion.listenerCount(), 0);
  }
});
