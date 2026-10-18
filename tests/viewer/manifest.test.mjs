import test from 'node:test';
import assert from 'node:assert/strict';
import { runtime } from './helpers.mjs';
const { validateManifest, usesPolyHavenAPI } = await runtime('interior-manifest.js');

function manifest() {
  return { schemaVersion: 2, title: 'Asymmetric studio', sourceImageSize: [900, 1200], sourceKind: 'photograph',
    sourceImage: '/assets/reference.webp', model: '/assets/interior/room-runtime.glb',
    portableModel: '/assets/interior/room-portable.glb', blender: '/assets/interior/room-master.blend',
    environment: '/assets/interior/room-environment.exr', background: null,
    camera: { position: [1, 1.7, 3], target: [0, 1, 0], fov: 48 },
    views: { 'window-detail': { position: [-1, 2, 2], target: [0, 1, 0], label: 'Window detail' } },
    roomBounds: { min: [-3, 0, -4], max: [3, 3.2, 4] },
    toneMapping: 'neutral', exposure: 1,
    lighting: { model: 'ambient-bake+shadowed-sun-v1', sun: null },
    lightmaps: [{ id: 'room', url: '/assets/interior/lightmap-room.exr', intensity: Math.PI }],
    variants: [] };
}

test('API attribution is conditional on the actual manifest provenance, not scene identity', () => {
  const value = manifest();
  assert.equal(usesPolyHavenAPI(value), false);
  value.resourceCredit = { provider: 'Poly Haven', apiDerived: false };
  assert.equal(usesPolyHavenAPI(value), false);
  value.resourceCredit.apiDerived = true;
  assert.equal(usesPolyHavenAPI(value), true);
  value.resourceCredit.provider = 'Procedural';
  assert.equal(usesPolyHavenAPI(value), false);
});

test('ambiguous lighting, unsafe paths, invalid camera frames and duplicate identities fail actionably', () => {
  for (const [mutate, expected] of [
    [m => { m.lighting.model = 'full-sun-bake'; }, /full-sun bakes/],
    [m => { delete m.lighting.sun; }, /sun: null/],
    [m => { m.sourceImage = '/assets/../private.png'; }, /inside \/assets/],
    [m => { m.model = '/assets/%2e%2e/room.glb'; }, /inside \/assets/],
    [m => { m.model = 'https://example.org/model.glb'; }, /local \/assets/],
    [m => { m.sourceImageSize = [0, 100]; }, /sourceImageSize/],
    [m => { m.camera.target = [...m.camera.position]; }, /equal to its target/],
    [m => { m.views.source = structuredClone(m.camera); }, /source view is implicit/],
    [m => { m.roomBounds.max[0] = m.roomBounds.min[0]; }, /roomBounds/],
    [m => { m.lightmaps.push({ ...m.lightmaps[0] }); }, /duplicate id/],
    [m => { m.variants = [{ id: 'one', label: 'One', color: '#abcdef' }, { id: 'one', label: 'Again', color: '#123456' }]; }, /unique ids/],
    [m => { m.variants = [{ id: 'base', label: 'Base', color: '#000000' }, { id: 'white', label: 'White', color: '#ffffff' }]; }, /nonzero RGB/],
  ]) {
    const value = manifest();
    mutate(value);
    assert.throws(() => validateManifest(value), expected);
  }
});
