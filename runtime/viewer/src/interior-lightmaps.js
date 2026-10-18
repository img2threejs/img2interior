import * as THREE from 'three';

// Track decoded storage, not the texture wrapper: clones can share EXR pixels.
const oriented = new WeakSet();
export function prepareLightmaps(atlases) {
  let rowScratch;
  for (const { texture } of atlases) {
    const { data, width, height } = texture.image;
    const stride = data?.length / height;
    if (!ArrayBuffer.isView(data) || !Number.isInteger(width) || width <= 0
        || !Number.isInteger(height) || height <= 0 || stride !== width * 4) {
      throw new Error('EXR atlas does not contain valid RGBA data.');
    }
    // r180 EXRLoader decodes bottom-row-first; glTF UV1 uses a top origin.
    // Only the lightmap crosses this boundary, never the environment probe.
    if (!oriented.has(data)) {
      if (!rowScratch || rowScratch.constructor !== data.constructor || rowScratch.length < stride) rowScratch = new data.constructor(stride);
      for (let y = 0; y < Math.floor(height / 2); y++) {
        const top = y * stride;
        const bottom = (height - 1 - y) * stride;
        rowScratch.set(data.subarray(top, top + stride));
        data.copyWithin(top, bottom, bottom + stride);
        data.set(rowScratch.subarray(0, stride), bottom);
      }
      oriented.add(data);
    }
    texture.channel = 1;
    texture.colorSpace = THREE.NoColorSpace;
    texture.flipY = false;
    texture.needsUpdate = true;
  }
}
