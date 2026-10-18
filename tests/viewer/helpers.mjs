import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { resolve } from 'node:path';

// Run against the installed workspace when VIEWER_ROOT is set; otherwise the
// template must have its pinned dependencies installed. No DOM/WebGL shim is
// used for geometry or physics: these tests exercise the real Three classes.
export const viewerRoot = process.env.VIEWER_ROOT
  ? resolve(process.env.VIEWER_ROOT)
  : fileURLToPath(new URL('../../runtime/viewer/', import.meta.url));
export const THREE = createRequire(pathToFileURL(resolve(viewerRoot, 'package.json')))('three');
export const runtime = name => import(pathToFileURL(resolve(viewerRoot, 'src', name)));

export class Events {
  listeners = new Map();
  addEventListener(type, listener) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type).add(listener);
  }
  removeEventListener(type, listener) { this.listeners.get(type)?.delete(listener); }
  emit(type, properties = {}) {
    const event = { type, target: this, preventDefault() { this.prevented = true; },
      stopImmediatePropagation() { this.stopped = true; }, ...properties };
    for (const listener of [...(this.listeners.get(type) ?? [])]) {
      listener(event);
      if (event.stopped) break;
    }
    return event;
  }
  listenerCount(type) {
    return type ? this.listeners.get(type)?.size ?? 0
      : [...this.listeners.values()].reduce((sum, set) => sum + set.size, 0);
  }
}

export function curtainFixture({ hem = false } = {}) {
  const win = new Events();
  const doc = new Events();
  const motion = new Events();
  motion.matches = false;
  win.matchMedia = () => motion;
  doc.defaultView = win;
  doc.hidden = false;
  const canvas = new Events();
  canvas.ownerDocument = doc;
  canvas.style = { cursor: 'grab' };
  canvas.getBoundingClientRect = () => ({ left: 0, top: 0, width: 800, height: 600 });
  const captures = new Set();
  canvas.setPointerCapture = id => captures.add(id);
  canvas.hasPointerCapture = id => captures.has(id);
  canvas.releasePointerCapture = id => {
    captures.delete(id);
    canvas.emit('lostpointercapture', { pointerId: id });
  };
  const controls = { enabled: true };
  const root = new THREE.Group();
  const positions = [], uvs = [], indices = [];
  for (let row = 0; row <= 16; row++) for (let col = 0; col <= 50; col++) {
    const u = col/50, v = row/16;
    positions.push(10+u, 0.4+v*2, 20);
    uvs.push(u, 1-v*2);
    if (row < 16 && col < 50) {
      const a = row*51+col;
      indices.push(a, a+1, a+51, a+1, a+52, a+51);
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
  geometry.setAttribute('uv1', new THREE.Float32BufferAttribute(uvs, 2));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  const material = new THREE.MeshStandardMaterial({ side: THREE.DoubleSide });
  const cloth = new THREE.Mesh(geometry, material);
  cloth.userData = { curtain_id: 'test-panel', curtain_part: 'cloth',
    curtain_tile: 1, curtain_fabric_width: 1, curtain_height: 2,
    curtain_open_width: 1, curtain_closed_width: 2,
    curtain_rail_axis: [1, 0, 0], curtain_depth_axis: [0, 0, 1], curtain_plane_origin: [10, 0, 20] };
  root.add(cloth);
  let hemMesh;
  if (hem) {
    const hemGeometry = new THREE.PlaneGeometry(1, 0.06, 4, 1).translate(10.5, 0.4, 20.02);
    hemMesh = new THREE.Mesh(hemGeometry, material);
    hemMesh.userData = { curtain_id: 'test-panel', curtain_part: 'hem', curtain_v: 0 };
    root.add(hemMesh);
  }
  const camera = new THREE.PerspectiveCamera(60, 800/600, 0.01, 100);
  camera.position.set(10.5, 1.4, 21.5);
  camera.lookAt(10.5, 1.4, 20);
  camera.updateWorldMatrix(true, false);
  const roomBounds = { min: [9, 0, 19], max: [15, 3, 22] };
  function pointerAt(world, pointerId = 1, extra = {}) {
    const p = new THREE.Vector3().fromArray(world).project(camera);
    return { target: canvas, clientX: (p.x+1)*400, clientY: (1-p.y)*300,
      pointerId, button: 0, isPrimary: true, pointerType: 'mouse', ...extra };
  }
  return { root, camera, canvas, controls, roomBounds, win, doc, motion, cloth, hemMesh, pointerAt };
}
