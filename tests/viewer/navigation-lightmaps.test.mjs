import test from 'node:test';
import assert from 'node:assert/strict';
import { THREE, runtime } from './helpers.mjs';
const { createInteriorNavigation } = await runtime('interior-navigation.js');
const { prepareLightmaps } = await runtime('interior-lightmaps.js');

function controlsFor(camera, emitChange) {
  const controls = new THREE.EventDispatcher();
  controls.target = new THREE.Vector3(12, 2, 22);
  controls.minDistance = 0;
  controls.maxDistance = Infinity;
  controls.minPolarAngle = 0;
  controls.maxPolarAngle = Math.PI;
  controls.update = function(delta) {
    camera.position.x = 14.8 + 1e-9;
    this.target.y = 4 + 1e-9;
    if (emitChange) this.dispatchEvent({ type: 'change' });
    return emitChange;
  };
  return controls;
}

for (const emitsChange of [true, false]) test(`navigation clamps every update, including sub-EPS change=${emitsChange}`, () => {
  const camera = new THREE.PerspectiveCamera();
  camera.position.set(12, 2, 23);
  const controls = controlsFor(camera, emitsChange);
  const originalUpdate = controls.update;
  const bounds = { min: [10, 0, 20], max: [15, 4, 25] };
  const nav = createInteriorNavigation(camera, controls, bounds);
  assert.equal(controls.update(0.01), true);
  const snapshot = nav.snapshot();
  assert.equal(snapshot.safety.cameraInBounds, true);
  assert.equal(snapshot.safety.targetInBounds, true);
  assert.equal(snapshot.safety.atBoundary, true);
  assert.equal(camera.position.x, 14.8);
  assert.equal(controls.target.y, 3.85);
  // The wrapper copies caller-owned bounds, it does not mutate the manifest.
  assert.deepEqual(bounds, { min: [10, 0, 20], max: [15, 4, 25] });
  nav.dispose();
  nav.dispose();
  assert.equal(controls.update, originalUpdate);
  assert.equal(controls.minDistance, 0);
  assert.equal(controls.maxDistance, Infinity);
  camera.position.set(100, 100, 100);
  controls.dispatchEvent({ type: 'change' });
  assert.equal(camera.position.x, 100);
});

test('tiny valid rooms keep a nonzero view direction without escaping bounds', () => {
  const camera = new THREE.PerspectiveCamera();
  camera.position.set(0.255, 0.255, 0.255);
  const controls = controlsFor(camera, false);
  controls.target.copy(camera.position);
  const nav = createInteriorNavigation(camera, controls, { min: [0, 0, 0], max: [0.51, 0.51, 0.51] });
  const snapshot = nav.snapshot();
  assert.equal(snapshot.safety.cameraInBounds, true);
  assert.equal(snapshot.safety.targetInBounds, true);
  assert.ok(snapshot.safety.distance > 0.05);
  nav.dispose();
});

test('invalid room bounds do not replace controls update', () => {
  const camera = new THREE.PerspectiveCamera();
  const controls = controlsFor(camera, false);
  const update = controls.update;
  assert.throws(() => createInteriorNavigation(camera, controls, { min: [0, 0, 0], max: [0.1, 3, 3] }), /roomBounds/);
  assert.equal(controls.update, update);
});

test('lightmap orientation swaps decoded rows once, including wrappers sharing pixels', () => {
  const data = new Float32Array([
    1, 2, 3, 4, 5, 6, 7, 8,
    11, 12, 13, 14, 15, 16, 17, 18,
    21, 22, 23, 24, 25, 26, 27, 28,
  ]);
  const texture = new THREE.DataTexture(data, 2, 3, THREE.RGBAFormat, THREE.FloatType);
  const clone = texture.clone();
  const original = data.slice();
  const atlas = { texture, intensity: Math.PI };
  prepareLightmaps([atlas, { texture: clone, intensity: Math.PI }]);
  assert.deepEqual(data, new Float32Array([...original.slice(16), ...original.slice(8, 16), ...original.slice(0, 8)]));
  const oriented = data.slice();
  prepareLightmaps([atlas]);
  assert.deepEqual(data, oriented);
  assert.equal(texture.channel, 1);
  assert.equal(clone.channel, 1);
  assert.equal(texture.flipY, false);
  assert.equal(texture.colorSpace, THREE.NoColorSpace);
  const otherSession = new THREE.DataTexture(original.slice(), 2, 3, THREE.RGBAFormat, THREE.FloatType);
  prepareLightmaps([{ texture: otherSession }]);
  assert.deepEqual(otherSession.image.data, oriented);
});

test('malformed atlas cannot be silently bound as RGBA', () => {
  const texture = new THREE.DataTexture(new Float32Array(3), 1, 1);
  assert.throws(() => prepareLightmaps([{ texture }]), /RGBA/);
});
