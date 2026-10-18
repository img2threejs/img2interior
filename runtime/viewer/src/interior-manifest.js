export function vector3(value) {
  return Array.isArray(value) && value.length === 3 && value.every(Number.isFinite);
}

export function validateRoomBounds(bounds) {
  if (!vector3(bounds?.min) || !vector3(bounds?.max)
      || bounds.min.some((value, i) => value + 0.5 >= bounds.max[i])) {
    throw new Error('roomBounds must contain Y-up min/max vectors with more than 0.5 m on every axis.');
  }
}

function assetPath(value, field) {
  if (typeof value !== 'string' || !value.startsWith('/assets/') || /[\\?#\s]/.test(value)) {
    throw new Error(`Missing local /assets/ URL: ${field}`);
  }
  let decoded;
  try { decoded = decodeURIComponent(value); } catch { throw new Error(`Invalid asset URL: ${field}`); }
  if (decoded.split('/').some(part => part === '.' || part === '..') || /[\\?#]/.test(decoded)) {
    throw new Error(`Asset URL must stay inside /assets/: ${field}`);
  }
}

export function validateManifest(manifest) {
  if (manifest?.schemaVersion !== 2 || manifest.lighting?.model !== 'ambient-bake+shadowed-sun-v1') {
    throw new Error('Scene requires schema 2 SUN-free ambient atlases and ambient-bake+shadowed-sun-v1 lighting; full-sun bakes cannot be combined with a runtime sun.');
  }
  if (typeof manifest.title !== 'string' || !manifest.title.trim()) throw new Error('Scene title is required.');
  if (!Array.isArray(manifest.sourceImageSize) || manifest.sourceImageSize.length !== 2
      || !manifest.sourceImageSize.every(value => Number.isInteger(value) && value > 0)) {
    throw new Error('sourceImageSize must contain the source image width and height in pixels.');
  }
  for (const field of ['sourceImage', 'model', 'portableModel', 'blender', 'environment']) assetPath(manifest[field], field);
  if (manifest.background != null) {
    assetPath(manifest.background, 'background');
    if (!Number.isFinite(manifest.backgroundIntensity) || manifest.backgroundIntensity < 0) throw new Error('Background intensity is invalid.');
    if (!/\.(hdr|exr)$/i.test(manifest.background)) throw new Error('Background must be an HDR or EXR image.');
  }
  if (!manifest.views || typeof manifest.views !== 'object' || Array.isArray(manifest.views)) throw new Error('views must be an object of named camera poses (it may be empty).');
  if (Object.hasOwn(manifest.views, 'source')) throw new Error('The source view is implicit in camera; do not duplicate it in views.');
  for (const [name, pose] of [['source', manifest.camera], ...Object.entries(manifest.views)]) {
    if (!name.trim() || !vector3(pose?.position) || !vector3(pose?.target)) throw new Error(`View ${name} needs Y-up position and target vectors.`);
    if (pose.position.every((value, i) => value === pose.target[i])) throw new Error(`View ${name} has position equal to its target.`);
    const fov = pose.fov ?? manifest.camera?.fov;
    if (!Number.isFinite(fov) || fov <= 0 || fov >= 180) throw new Error(`Invalid FOV: ${name}`);
    if (pose.label !== undefined && typeof pose.label !== 'string') throw new Error(`Invalid view label: ${name}`);
  }
  validateRoomBounds(manifest.roomBounds);
  const sun = manifest.lighting.sun;
  if (sun !== null) {
    for (const key of ['position', 'target', 'color']) if (!vector3(sun?.[key])) throw new Error(`Sun config is missing ${key}; use lighting.sun: null when there is no authored sun.`);
    if (sun.position.every((value, i) => value === sun.target[i]) || sun.color.some(value => value < 0)
        || !Number.isFinite(sun.intensity) || sun.intensity < 0
        || !Number.isInteger(sun.shadowMapSize) || sun.shadowMapSize < 512 || sun.shadowMapSize > 4096) {
      throw new Error('Sun direction, color, intensity or shadow map size is invalid.');
    }
  }
  if (manifest.toneMapping !== 'neutral' || !Number.isFinite(manifest.exposure) || manifest.exposure <= 0) throw new Error('Need Neutral tone mapping and a valid exposure.');
  if (!Array.isArray(manifest.lightmaps) || !manifest.lightmaps.length) throw new Error('Manifest has no lightmap atlas.');
  const atlasIds = new Set();
  for (const atlas of manifest.lightmaps) {
    if (!atlas || typeof atlas.id !== 'string' || !atlas.id || atlasIds.has(atlas.id)
        || !Number.isFinite(atlas.intensity) || atlas.intensity <= 0) throw new Error('Lightmap atlas is invalid or has a duplicate id.');
    assetPath(atlas.url, `atlas ${atlas.id}`);
    atlasIds.add(atlas.id);
  }
  if (!Array.isArray(manifest.variants)) throw new Error('variants must be an array (it may be empty).');
  const variantIds = new Set();
  for (const variant of manifest.variants) {
    if (!variant || typeof variant.id !== 'string' || !variant.id || variantIds.has(variant.id)
        || typeof variant.label !== 'string' || !variant.label || !/^#[\da-f]{6}$/i.test(variant.color)
        || (variant.roughness !== undefined && (!Number.isFinite(variant.roughness) || variant.roughness < 0 || variant.roughness > 1))) {
      throw new Error('Finish variants require unique ids, labels, hex colors and optional roughness in [0, 1].');
    }
    variantIds.add(variant.id);
  }
  // Relative linear tints cannot reconstruct a channel absent from the authored base.
  if (manifest.variants.length > 1 && manifest.variants[0].color.slice(1).match(/../g).includes('00')) {
    throw new Error('The first (authored base) finish must have nonzero RGB channels for relative recoloring.');
  }
  if (manifest.finishTarget !== undefined && (typeof manifest.finishTarget !== 'string' || !manifest.finishTarget)) throw new Error('finishTarget must name a nonempty mesh finish tag.');
  return manifest;
}

export function sourceLabel(manifest) {
  return ['synthetic', 'synthetic-design', 'synthetic-design-reference'].includes(manifest.sourceKind)
    ? 'Synthetic design reference' : 'Source reference image';
}

export function usesPolyHavenAPI(manifest) {
  return manifest.resourceCredit?.provider === 'Poly Haven' && manifest.resourceCredit?.apiDerived === true;
}
