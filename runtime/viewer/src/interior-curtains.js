import * as THREE from 'three';
import { validateRoomBounds, vector3 } from './interior-manifest.js';

const COLS = 50;
const ROWS = 16;
const STRIDE = COLS + 1;
const COUNT = STRIDE * (ROWS + 1);
const STEP = 1 / 60;
const clamp = THREE.MathUtils.clamp;

// All simulation positions are world-space. UVs, including the glTF V flip,
// identify material points independently of split vertices and panel direction.
export function createCurtainInteraction({ root, camera, canvas, controls, roomBounds, onChange = () => {}, isInteractive = () => true }) {
  validateRoomBounds(roomBounds);
  const room = new THREE.Box3(new THREE.Vector3().fromArray(roomBounds.min), new THREE.Vector3().fromArray(roomBounds.max));
  const doc = canvas.ownerDocument;
  const win = doc.defaultView;
  const motion = win.matchMedia('(prefers-reduced-motion: reduce)');
  let reduced = motion.matches;
  let windRequested = true;
  let wind = windRequested && !reduced;
  let enabled = true;
  let disposed = false;
  let inView = true;
  let paused = true;
  let accumulator = 0;
  let time = 0;
  let active = true;
  let quiet = 0;
  let grip = null;
  const originalCursor = canvas.style.cursor;
  const panels = [];
  const panelById = new Map();
  const fabricBindings = new Map();
  const fabricMeshes = [];
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  const hits = [];
  const point = new THREE.Vector3();
  const sample = new THREE.Vector3();
  const contactPoint = new THREE.Vector3();
  const identity = new THREE.Matrix4();
  const delta = new THREE.Vector3();
  const normal = new THREE.Vector3();
  const inverse = new THREE.Matrix4();
  const blocked = new Set();
  const cornerIds = new Int32Array(4);
  const cornerWeights = new Float64Array(4);

  function metadata(mesh) {
    const result = {};
    for (let node = mesh; node; node = node.parent) {
      for (const key of Object.keys(node.userData)) {
        if (key.startsWith('curtain_') && result[key] === undefined) result[key] = node.userData[key];
      }
      if (node === root) break;
    }
    return result;
  }

  function weights(u, v, ids = cornerIds, values = cornerWeights) {
    const x = clamp(u, 0, 1) * COLS;
    const y = clamp(v, 0, 1) * ROWS;
    const i = Math.min(COLS - 1, Math.floor(x));
    const j = Math.min(ROWS - 1, Math.floor(y));
    const a = x - i;
    const b = y - j;
    ids[0] = j * STRIDE + i; ids[1] = ids[0] + 1;
    ids[2] = ids[0] + STRIDE; ids[3] = ids[2] + 1;
    values[0] = (1 - a) * (1 - b); values[1] = a * (1 - b);
    values[2] = (1 - a) * b; values[3] = a * b;
  }

  function interpolate(array, ids, values, out) {
    out.set(0, 0, 0);
    for (let k = 0; k < 4; k++) {
      const i = ids[k] * 3;
      out.x += array[i] * values[k];
      out.y += array[i + 1] * values[k];
      out.z += array[i + 2] * values[k];
    }
    return out;
  }

  root.updateWorldMatrix(true, true);
  const geometryUsers = new Map();
  root.traverse(node => {
    if (node.isMesh) geometryUsers.set(node.geometry, (geometryUsers.get(node.geometry) ?? 0) + 1);
  });
  const meshes = [];
  root.traverse(node => {
    if (!node.isMesh) return;
    const meta = metadata(node);
    if (meta.curtain_id === undefined && meta.curtain_part === undefined) return;
    if (typeof meta.curtain_id !== 'string' || !meta.curtain_id) throw new Error(`Curtain mesh ${node.name} requires a nonempty curtain_id.`);
    if (!['cloth', 'hem', 'hook', 'rail'].includes(meta.curtain_part)) throw new Error(`Curtain ${meta.curtain_id} has an unsupported curtain_part.`);
    meshes.push({ mesh: node, meta });
    if (['cloth', 'hem', 'hook'].includes(meta.curtain_part)) {
      if (!root.matrixWorld.elements.every((value, i) => Math.abs(value - identity.elements[i]) < 1e-8)) {
        throw new Error('Interactive curtains require an identity scene root. Apply root transforms in the authoring scene and re-export metadata in Y-up scene coordinates.');
      }
      if (geometryUsers.get(node.geometry) !== 1) throw new Error(`Curtain ${meta.curtain_id} shares geometry with another mesh; make deforming geometry single-user before export.`);
      const p = node.geometry.getAttribute('position');
      const uv = node.geometry.getAttribute('uv');
      if (!p || p.itemSize !== 3 || !uv || uv.itemSize !== 2 || uv.count !== p.count) throw new Error(`Curtain ${meta.curtain_id} requires complete position and material UV0 attributes.`);
      for (let i = 0; i < p.count; i++) {
        if (![p.getX(i), p.getY(i), p.getZ(i), uv.getX(i), uv.getY(i)].every(Number.isFinite)) throw new Error(`Curtain ${meta.curtain_id} has non-finite geometry or UV0.`);
      }
      if (meta.curtain_part === 'hook' && (!Number.isFinite(meta.curtain_u) || meta.curtain_u < 0 || meta.curtain_u > 1)) throw new Error(`Curtain ${meta.curtain_id} hook needs curtain_u in [0, 1].`);
      if (meta.curtain_part === 'hem' && (!Number.isFinite(meta.curtain_v) || meta.curtain_v < 0 || meta.curtain_v > 1)) throw new Error(`Curtain ${meta.curtain_id} hem needs curtain_v in [0, 1].`);
    }
    if (meta.curtain_part !== 'cloth') return;
    for (const key of ['curtain_tile', 'curtain_fabric_width', 'curtain_height', 'curtain_open_width', 'curtain_closed_width']) {
      if (!Number.isFinite(meta[key]) || meta[key] <= 0) throw new Error(`Curtain ${meta.curtain_id} requires positive ${key}.`);
    }
    if (meta.curtain_closed_width <= meta.curtain_open_width) throw new Error(`Curtain ${meta.curtain_id} closed width must exceed open width.`);
    for (const key of ['curtain_rail_axis', 'curtain_depth_axis', 'curtain_plane_origin']) {
      if (!vector3(meta[key])) throw new Error(`Curtain ${meta.curtain_id} requires explicit Y-up ${key}; re-export using the current curtain helper.`);
    }
    const rail = new THREE.Vector3().fromArray(meta.curtain_rail_axis);
    const depthAxis = new THREE.Vector3().fromArray(meta.curtain_depth_axis);
    const planeOrigin = new THREE.Vector3().fromArray(meta.curtain_plane_origin);
    if (Math.abs(rail.lengthSq()-1) > 1e-5 || Math.abs(depthAxis.lengthSq()-1) > 1e-5
        || Math.abs(rail.dot(depthAxis)) > 1e-5 || Math.abs(rail.y) > 1e-5 || Math.abs(depthAxis.y) > 1e-5) {
      throw new Error(`Curtain ${meta.curtain_id} rail/depth axes must be horizontal orthogonal unit vectors in Y-up scene space.`);
    }
    const existing = panelById.get(meta.curtain_id);
    if (existing) {
      const keys = ['curtain_tile', 'curtain_fabric_width', 'curtain_height', 'curtain_open_width', 'curtain_closed_width', 'curtain_rail_axis', 'curtain_depth_axis', 'curtain_plane_origin'];
      if (keys.some(key => JSON.stringify(existing.meta[key]) !== JSON.stringify(meta[key]))) throw new Error(`Curtain ${meta.curtain_id} primitives disagree on panel metadata.`);
      return;
    }
    const panel = {
      id: meta.curtain_id, meta, rail, closure: 0, targetClosure: 0,
      depthAxis, planeOrigin, pleatDepth: new Float64Array(COUNT),
      rest: new Float64Array(COUNT * 3), goal: new Float64Array(COUNT * 3),
      position: new Float64Array(COUNT * 3), previous: new Float64Array(COUNT * 3),
      counts: new Uint16Array(COUNT), bindings: [], edges: [], speed: 0, displacement: 0,
    };
    panels.push(panel);
    panelById.set(panel.id, panel);
  });
  for (const { meta } of meshes) {
    if (meta.curtain_part !== 'rail' && !panelById.has(meta.curtain_id)) throw new Error(`Curtain ${meta.curtain_id} ${meta.curtain_part} has no cloth panel.`);
  }

  // Average front/back copies at each authored grid point, retaining the shell
  // offset separately when mapping the solver back onto the imported geometry.
  for (const { mesh, meta } of meshes) {
    if (meta.curtain_part !== 'cloth') continue;
    const panel = panelById.get(meta.curtain_id);
    const uv = mesh.geometry.getAttribute('uv');
    const positions = mesh.geometry.getAttribute('position');
    if (!uv) throw new Error(`Curtain ${panel.id} requires material UV0`);
    for (let i = 0; i < positions.count; i++) {
      const u = clamp(uv.getX(i) * meta.curtain_tile / meta.curtain_fabric_width, 0, 1);
      const v = clamp((1 - uv.getY(i)) * meta.curtain_tile / meta.curtain_height, 0, 1);
      const gridU = u*COLS, gridV = v*ROWS;
      const col = Math.round(gridU), row = Math.round(gridV);
      // The solver samples exact intersections of the denser authored mesh.
      // Averaging neighbouring material points would move rail pins and folds.
      if (Math.abs(gridU-col) > 1e-4 || Math.abs(gridV-row) > 1e-4) continue;
      const index = row*STRIDE + col;
      point.fromBufferAttribute(positions, i).applyMatrix4(mesh.matrixWorld);
      panel.rest[index * 3] += point.x;
      panel.rest[index * 3 + 1] += point.y;
      panel.rest[index * 3 + 2] += point.z;
      panel.counts[index]++;
    }
  }
  for (const panel of panels) {
    for (let i = 0; i < COUNT; i++) {
      if (!panel.counts[i]) throw new Error(`Curtain ${panel.id} is missing material grid point ${i}`);
      for (let a = 0; a < 3; a++) panel.rest[i * 3 + a] /= panel.counts[i];
      point.fromArray(panel.rest, i * 3);
      panel.pleatDepth[i] = delta.copy(point).sub(panel.planeOrigin).dot(panel.depthAxis);
      if (i >= ROWS * STRIDE) {
        const travel = (i % STRIDE) / COLS * (panel.meta.curtain_closed_width-panel.meta.curtain_open_width);
        if (!room.containsPoint(point) || !room.containsPoint(point.addScaledVector(panel.rail, travel))) {
          throw new Error(`Curtain ${panel.id} pinned header leaves roomBounds at open or closed coverage; repair the rail metadata or authored bounds.`);
        }
      }
    }
    panel.goal.set(panel.rest);
    panel.position.set(panel.rest);
    panel.previous.set(panel.rest);
    const edges = [];
    const add = (a, b, stiffness) => edges.push(a, b, stiffness);
    for (let j = 0; j <= ROWS; j++) {
      for (let i = 0; i <= COLS; i++) {
        const a = j * STRIDE + i;
        if (i < COLS) add(a, a + 1, 0.85);
        if (j < ROWS) add(a, a + STRIDE, 0.95);
        if (i < COLS && j < ROWS) {
          add(a, a + STRIDE + 1, 0.55);
          add(a + 1, a + STRIDE, 0.55);
        }
        if (i + 2 <= COLS) add(a, a + 2, 0.18);
        if (j + 2 <= ROWS) add(a, a + 2 * STRIDE, 0.18);
      }
    }
    panel.edges = new Float64Array(edges);
    panel.lengths = new Float64Array(edges.length / 3);
    updateGoal(panel);
  }

  for (const { mesh, meta } of meshes) {
    const panel = panelById.get(meta.curtain_id);
    if (!panel || !['cloth', 'hem', 'hook'].includes(meta.curtain_part)) continue;
    const geometry = mesh.geometry;
    const positions = geometry.getAttribute('position');
    const uv = geometry.getAttribute('uv');
    const binding = {
      panel, mesh, part: meta.curtain_part, ids: new Int32Array(positions.count * 4),
      weights: new Float64Array(positions.count * 4), offsets: new Float64Array(positions.count * 3),
      original: positions.array.slice(), originalUsage: positions.usage,
      originalNormal: geometry.getAttribute('normal')?.array.slice() ?? null,
      originalTangent: geometry.getAttribute('tangent')?.array.slice() ?? null,
      tangent1: null, tangent2: null,
    };
    positions.setUsage(THREE.DynamicDrawUsage);
    if (!geometry.getAttribute('normal')) geometry.setAttribute('normal', new THREE.BufferAttribute(new Float32Array(positions.count * 3), 3));
    if (geometry.getAttribute('tangent')) {
      binding.tangent1 = new Float64Array(positions.count * 3);
      binding.tangent2 = new Float64Array(positions.count * 3);
    }
    for (let i = 0; i < positions.count; i++) {
      point.fromBufferAttribute(positions, i).applyMatrix4(mesh.matrixWorld);
      let u;
      let v;
      if (meta.curtain_part === 'cloth') {
        u = uv.getX(i) * panel.meta.curtain_tile / panel.meta.curtain_fabric_width;
        v = (1 - uv.getY(i)) * panel.meta.curtain_tile / panel.meta.curtain_height;
      } else if (meta.curtain_part === 'hook') {
        u = meta.curtain_u; v = 1;
      } else {
        // Project onto the authored rail rather than raw local mesh axes.
        delta.copy(point).sub(sample.fromArray(panel.rest, ROWS * STRIDE * 3));
        u = delta.dot(panel.rail) / (panel.rail.lengthSq() * panel.meta.curtain_open_width);
        v = meta.curtain_v;
      }
      weights(u, v);
      interpolate(panel.rest, cornerIds, cornerWeights, sample);
      for (let k = 0; k < 4; k++) {
        binding.ids[i * 4 + k] = cornerIds[k];
        binding.weights[i * 4 + k] = cornerWeights[k];
      }
      binding.offsets[i * 3] = point.x - sample.x;
      binding.offsets[i * 3 + 1] = point.y - sample.y;
      binding.offsets[i * 3 + 2] = point.z - sample.z;
    }
    panel.bindings.push(binding);
    if (binding.part === 'cloth' || binding.part === 'hem') {
      fabricBindings.set(mesh, binding);
      fabricMeshes.push(mesh);
    }
  }

  function updateGoal(panel) {
    const expansion = panel.closure * (panel.meta.curtain_closed_width - panel.meta.curtain_open_width);
    for (let i = 0; i < COUNT; i++) {
      const shift = (i % STRIDE) / COLS * expansion;
      // Unfold the gathered depth as the rail expands, leaving modest closed
      // pleats. The short pinned header retains its authored depth so hooks
      // and their cloth attachments translate only along the rail.
      const v = Math.floor(i / STRIDE) / ROWS;
      const headerBlend = clamp((1 - v) * 8, 0, 1);
      const unfold = -panel.pleatDepth[i] * 0.72 * panel.closure
        * headerBlend * headerBlend * (3 - 2 * headerBlend);
      panel.goal[i * 3] = panel.rest[i * 3] + panel.rail.x * shift + panel.depthAxis.x * unfold;
      panel.goal[i * 3 + 1] = panel.rest[i * 3 + 1] + panel.rail.y * shift + panel.depthAxis.y * unfold;
      panel.goal[i * 3 + 2] = panel.rest[i * 3 + 2] + panel.rail.z * shift + panel.depthAxis.z * unfold;
    }
    for (let e = 0; e < panel.edges.length; e += 3) {
      const a = panel.edges[e] * 3;
      const b = panel.edges[e + 1] * 3;
      panel.lengths[e / 3] = Math.hypot(panel.goal[b] - panel.goal[a], panel.goal[b + 1] - panel.goal[a + 1], panel.goal[b + 2] - panel.goal[a + 2]);
    }
  }

  function constrainGrip(panel) {
    if (!grip || grip.panel !== panel) return;
    interpolate(panel.position, grip.ids, grip.weights, sample);
    delta.copy(grip.target).sub(grip.offset).sub(sample);
    let denominator = 0;
    let largestWeight = 0;
    for (let k = 0; k < 4; k++) {
      if (grip.ids[k] < ROWS * STRIDE) {
        denominator += grip.weights[k] ** 2;
        largestWeight = Math.max(largestWeight, grip.weights[k]);
      }
    }
    if (denominator < 0.0001) return; // A point exactly on the rail remains pinned.
    delta.clampLength(0, Math.min(0.10, 0.04 * denominator / largestWeight));
    for (let k = 0; k < 4; k++) {
      if (grip.ids[k] >= ROWS * STRIDE) continue;
      const i = grip.ids[k] * 3;
      const w = grip.weights[k] / denominator * 0.9;
      panel.position[i] += delta.x * w;
      panel.position[i + 1] += delta.y * w;
      panel.position[i + 2] += delta.z * w;
    }
  }

  function clampToRoom(vector) {
    return room.clampPoint(vector, vector);
  }

  function boundsAndPins(panel) {
    for (let i = 0; i < COUNT; i++) {
      const a = i * 3;
      if (i >= ROWS * STRIDE) {
        for (let k = 0; k < 3; k++) panel.position[a + k] = panel.goal[a + k];
      } else {
        contactPoint.fromArray(panel.position, a);
        clampToRoom(contactPoint);
        panel.position[a] = contactPoint.x;
        panel.position[a + 1] = contactPoint.y;
        panel.position[a + 2] = contactPoint.z;
      }
    }
  }

  function stepPanel(panel) {
    const difference = panel.targetClosure - panel.closure;
    if (Math.abs(difference) > 0.00001) {
      panel.closure += difference * (1 - Math.exp(-STEP * 9));
      if (Math.abs(panel.targetClosure - panel.closure) < 0.0001) panel.closure = panel.targetClosure;
      updateGoal(panel);
    }
    const p = panel.position;
    const prev = panel.previous;
    const goal = panel.goal;
    const damping = reduced ? 0.75 : 0.94;
    for (let i = 0; i < ROWS * STRIDE; i++) {
      const a = i * 3;
      const v = Math.floor(i / STRIDE) / ROWS;
      const breeze = wind ? 0.19 * Math.sin(time * 1.15 + i % STRIDE * 0.075 + v * 2.4) * (1 - v) : 0;
      for (let k = 0; k < 3; k++) {
        const value = p[a + k];
        const velocity = clamp((value - prev[a + k]) * damping, -0.035, 0.035);
        const force = (goal[a + k] - value) * 14 + (k === 1 ? -1.5 : 0) + breeze * panel.depthAxis.getComponent(k);
        p[a + k] = value + velocity + force * STEP * STEP;
        prev[a + k] = value;
      }
    }
    for (let iteration = 0; iteration < 7; iteration++) {
      for (let e = 0; e < panel.edges.length; e += 3) {
        const ai = panel.edges[e];
        const bi = panel.edges[e + 1];
        const a = ai * 3;
        const b = bi * 3;
        const dx = p[b] - p[a]; const dy = p[b + 1] - p[a + 1]; const dz = p[b + 2] - p[a + 2];
        const distance = Math.sqrt(dx*dx + dy*dy + dz*dz);
        const wa = ai < ROWS * STRIDE ? 1 : 0;
        const wb = bi < ROWS * STRIDE ? 1 : 0;
        if (!distance || !wa && !wb) continue;
        const correction = (distance - panel.lengths[e / 3]) / distance * panel.edges[e + 2] / (wa + wb);
        p[a] += dx * correction * wa; p[a + 1] += dy * correction * wa; p[a + 2] += dz * correction * wa;
        p[b] -= dx * correction * wb; p[b + 1] -= dy * correction * wb; p[b + 2] -= dz * correction * wb;
      }
      constrainGrip(panel);
      boundsAndPins(panel);
    }
    panel.speed = 0;
    panel.displacement = 0;
    for (let i = 0; i < COUNT; i++) {
      const a = i * 3;
      const vx = p[a]-prev[a], vy = p[a+1]-prev[a+1], vz = p[a+2]-prev[a+2];
      const dx = p[a]-goal[a], dy = p[a+1]-goal[a+1], dz = p[a+2]-goal[a+2];
      panel.speed = Math.max(panel.speed, vx*vx + vy*vy + vz*vz);
      panel.displacement = Math.max(panel.displacement, dx*dx + dy*dy + dz*dz);
      if (i >= ROWS * STRIDE) for (let k = 0; k < 3; k++) prev[a + k] = p[a + k];
    }
    panel.speed = Math.sqrt(panel.speed)/STEP;
    panel.displacement = Math.sqrt(panel.displacement);
  }

  // Reuse normal/tangent accumulators: computeTangents creates scratch arrays on
  // each call. UV0/UV1 and the imported shell topology remain untouched.
  function updateSurface(binding) {
    const geometry = binding.mesh.geometry;
    const p = geometry.getAttribute('position');
    const n = geometry.getAttribute('normal');
    const uv = geometry.getAttribute('uv');
    const tangent = geometry.getAttribute('tangent');
    const index = geometry.index;
    n.array.fill(0);
    binding.tangent1?.fill(0);
    binding.tangent2?.fill(0);
    const count = index ? index.count : p.count;
    for (let t = 0; t + 2 < count; t += 3) {
      const a = index ? index.getX(t) : t;
      const b = index ? index.getX(t + 1) : t + 1;
      const c = index ? index.getX(t + 2) : t + 2;
      const x1 = p.getX(b) - p.getX(a); const y1 = p.getY(b) - p.getY(a); const z1 = p.getZ(b) - p.getZ(a);
      const x2 = p.getX(c) - p.getX(a); const y2 = p.getY(c) - p.getY(a); const z2 = p.getZ(c) - p.getZ(a);
      const nx = y1 * z2 - z1 * y2; const ny = z1 * x2 - x1 * z2; const nz = x1 * y2 - y1 * x2;
      let sx = 0; let sy = 0; let sz = 0; let tx = 0; let ty = 0; let tz = 0;
      if (tangent && uv) {
        const s1 = uv.getX(b) - uv.getX(a); const s2 = uv.getX(c) - uv.getX(a);
        const t1 = uv.getY(b) - uv.getY(a); const t2 = uv.getY(c) - uv.getY(a);
        const determinant = s1 * t2 - s2 * t1;
        if (Math.abs(determinant) > 1e-12) {
          const r = 1 / determinant;
          sx = (t2 * x1 - t1 * x2) * r; sy = (t2 * y1 - t1 * y2) * r; sz = (t2 * z1 - t1 * z2) * r;
          tx = (s1 * x2 - s2 * x1) * r; ty = (s1 * y2 - s2 * y1) * r; tz = (s1 * z2 - s2 * z1) * r;
        }
      }
      for (let corner = 0; corner < 3; corner++) {
        const i = corner === 0 ? a : corner === 1 ? b : c;
        n.setXYZ(i, n.getX(i) + nx, n.getY(i) + ny, n.getZ(i) + nz);
        if (tangent) {
          binding.tangent1[i * 3] += sx; binding.tangent1[i * 3 + 1] += sy; binding.tangent1[i * 3 + 2] += sz;
          binding.tangent2[i * 3] += tx; binding.tangent2[i * 3 + 1] += ty; binding.tangent2[i * 3 + 2] += tz;
        }
      }
    }
    for (let i = 0; i < p.count; i++) {
      normal.fromBufferAttribute(n, i).normalize();
      n.setXYZ(i, normal.x, normal.y, normal.z);
      if (tangent) {
        point.fromArray(binding.tangent1, i * 3);
        point.addScaledVector(normal, -normal.dot(point)).normalize();
        delta.crossVectors(normal, point);
        sample.fromArray(binding.tangent2, i * 3);
        tangent.setXYZW(i, point.x, point.y, point.z, delta.dot(sample) < 0 ? -1 : 1);
      }
    }
    n.needsUpdate = true;
    if (tangent) tangent.needsUpdate = true;
  }

  function renderGeometry() {
    root.updateWorldMatrix(true, true);
    for (const panel of panels) for (const binding of panel.bindings) {
      inverse.copy(binding.mesh.matrixWorld).invert();
      const positions = binding.mesh.geometry.getAttribute('position');
      for (let i = 0; i < positions.count; i++) {
        point.fromArray(binding.offsets, i * 3);
        for (let k = 0; k < 4; k++) {
          const a = binding.ids[i * 4 + k] * 3;
          const w = binding.weights[i * 4 + k];
          point.x += panel.position[a] * w;
          point.y += panel.position[a + 1] * w;
          point.z += panel.position[a + 2] * w;
        }
        point.applyMatrix4(inverse);
        positions.setXYZ(i, point.x, point.y, point.z);
      }
      positions.needsUpdate = true;
      updateSurface(binding);
      binding.mesh.geometry.computeBoundingBox();
      binding.mesh.geometry.computeBoundingSphere();
    }
  }

  function available() {
    return !disposed && enabled && !doc.hidden && inView && isInteractive();
  }

  function wake() {
    active = true;
    quiet = 0;
    if (!disposed) onChange();
  }

  function setRay(event) {
    const rect = canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return false;
    pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, 1 - (event.clientY - rect.top) / rect.height * 2);
    camera.updateWorldMatrix(true, false);
    raycaster.setFromCamera(pointer, camera);
    return true;
  }

  function visibleHit(hit) {
    if (!hit.object.isMesh || !camera.layers.test(hit.object.layers)) return false;
    for (let node = hit.object; node; node = node.parent) if (!node.visible) return false;
    const materials = hit.object.material;
    const material = Array.isArray(materials) ? materials[hit.face?.materialIndex ?? 0] : materials;
    return !!material?.visible && !(material.transparent && material.opacity === 0);
  }

  function pick(event) {
    if (!setRay(event)) return null;
    root.updateWorldMatrix(true, true);
    hits.length = 0;
    raycaster.intersectObjects(fabricMeshes, false, hits);
    let candidate = null;
    for (const hit of hits) {
      if (hit.uv && visibleHit(hit)) { candidate = hit; break; }
    }
    if (!candidate) return null;
    // Only pay for scene occlusion when the pointer actually reaches fabric.
    // Limit the second query to the candidate; geometry behind it is irrelevant.
    const previousFar = raycaster.far;
    raycaster.far = Math.min(previousFar, candidate.distance + 0.0001);
    hits.length = 0;
    try {
      raycaster.intersectObject(root, true, hits);
    } finally {
      raycaster.far = previousFar;
    }
    for (const hit of hits) {
      if (!visibleHit(hit)) continue;
      return fabricBindings.has(hit.object) && hit.uv ? hit : null;
    }
    return null;
  }

  function cancelGrip() {
    if (!grip) return;
    const old = grip;
    grip = null;
    win.removeEventListener('wheel', suppress, true);
    controls.enabled = old.controlsEnabled && enabled && isInteractive();
    canvas.style.cursor = originalCursor;
    if (canvas.hasPointerCapture(old.pointerId)) canvas.releasePointerCapture(old.pointerId);
    wake();
  }

  function suppress(event) {
    event.preventDefault();
    event.stopImmediatePropagation();
  }

  function pointerDown(event) {
    if (grip && event.pointerId !== grip.pointerId) {
      blocked.add(event.pointerId);
      blocked.add(grip.pointerId);
      cancelGrip();
      suppress(event);
      return;
    }
    if (event.target !== canvas || !available() || blocked.size || event.button !== 0 || event.isPrimary === false) return;
    const hit = pick(event);
    if (!hit) return;
    const binding = fabricBindings.get(hit.object);
    const panel = binding.panel;
    let u, v;
    if (binding.part === 'cloth') {
      u = hit.uv.x * panel.meta.curtain_tile / panel.meta.curtain_fabric_width;
      v = (1-hit.uv.y) * panel.meta.curtain_tile / panel.meta.curtain_height;
    } else {
      // Hem texture UVs describe the tube, not the parent fabric. Recover the
      // grabbed material point from the same vertex bindings used to deform it.
      u = v = 0;
      for (let corner = 0; corner < 3; corner++) {
        const vertex = corner === 0 ? hit.face.a : corner === 1 ? hit.face.b : hit.face.c;
        const barycentric = corner === 0 ? hit.barycoord.x : corner === 1 ? hit.barycoord.y : hit.barycoord.z;
        for (let k = 0; k < 4; k++) {
          const slot = vertex*4+k;
          const id = binding.ids[slot];
          const weight = barycentric*binding.weights[slot];
          u += id%STRIDE/COLS*weight;
          v += Math.floor(id/STRIDE)/ROWS*weight;
        }
      }
    }
    u = clamp(u, 0, 1); v = clamp(v, 0, 1);
    const ids = new Int32Array(4);
    const values = new Float64Array(4);
    weights(u, v, ids, values);
    interpolate(panel.position, ids, values, sample);
    camera.getWorldDirection(normal);
    grip = {
      panel, part: binding.part, pointerId: event.pointerId, ids, weights: values, uv: [u, v],
      offset: hit.point.clone().sub(sample), start: hit.point.clone(), target: hit.point.clone(),
      plane: new THREE.Plane().setFromNormalAndCoplanarPoint(normal, hit.point),
      startClosure: panel.closure, controlsEnabled: controls.enabled,
    };
    controls.enabled = false;
    suppress(event);
    try { canvas.setPointerCapture(event.pointerId); } catch { cancelGrip(); return; }
    win.addEventListener('wheel', suppress, eventOptions);
    canvas.style.cursor = 'grabbing';
    wake();
  }

  function pointerMove(event) {
    if (blocked.has(event.pointerId)) { suppress(event); return; }
    if (!grip) {
      if (event.target === canvas && event.pointerType !== 'touch') canvas.style.cursor = available() && pick(event) ? 'grab' : originalCursor;
      return;
    }
    if (event.pointerId !== grip.pointerId) return;
    suppress(event);
    if (!available()) { cancelGrip(); return; }
    if (!setRay(event) || !raycaster.ray.intersectPlane(grip.plane, point)) return;
    const panel = grip.panel;
    // Rail displacement is retained independently from elastic displacement.
    delta.copy(point).sub(grip.start);
    const travel = panel.meta.curtain_closed_width - panel.meta.curtain_open_width;
    const alongRail = delta.dot(panel.rail) / panel.rail.lengthSq();
    panel.targetClosure = clamp(grip.startClosure + alongRail / (Math.max(0.18, grip.uv[0]) * travel), 0, 1);
    sample.copy(panel.rail).multiplyScalar((panel.targetClosure - grip.startClosure) * travel * grip.uv[0]).add(grip.start);
    delta.copy(point).sub(sample).clampLength(0, 0.85);
    grip.target.copy(sample).add(delta);
    clampToRoom(grip.target);
    wake();
  }

  function pointerEnd(event) {
    if (blocked.delete(event.pointerId)) { suppress(event); return; }
    if (grip?.pointerId !== event.pointerId) return;
    suppress(event);
    cancelGrip();
  }

  function interrupt() {
    cancelGrip();
    blocked.clear();
    accumulator = 0;
    paused = true;
    for (const panel of panels) panel.previous.set(panel.position);
    canvas.style.cursor = originalCursor;
  }

  function visibilityChanged() {
    interrupt();
    if (available()) wake();
  }

  function preferenceChanged() {
    reduced = motion.matches;
    wind = windRequested && !reduced;
    wake();
  }

  function pointerLeave() { if (!grip) canvas.style.cursor = originalCursor; }
  function lostCapture(event) { if (grip?.pointerId === event.pointerId) cancelGrip(); }
  const eventOptions = { capture: true, passive: false };
  win.addEventListener('pointerdown', pointerDown, eventOptions);
  win.addEventListener('pointermove', pointerMove, eventOptions);
  win.addEventListener('pointerup', pointerEnd, eventOptions);
  win.addEventListener('pointercancel', pointerEnd, eventOptions);
  win.addEventListener('blur', interrupt);
  doc.addEventListener('visibilitychange', visibilityChanged);
  canvas.addEventListener('lostpointercapture', lostCapture);
  canvas.addEventListener('pointerleave', pointerLeave);
  motion.addEventListener('change', preferenceChanged);
  const observer = win.IntersectionObserver ? new win.IntersectionObserver(entries => {
    inView = entries[0].isIntersecting;
    visibilityChanged();
  }) : null;
  observer?.observe(canvas);

  function probe(panel, u, v, rect) {
    weights(u, v);
    interpolate(panel.position, cornerIds, cornerWeights, point);
    const world = point.toArray();
    point.project(camera);
    return { uv: [u, v], world, canvas: [(point.x + 1) * rect.width / 2, (1 - point.y) * rect.height / 2], inFrustum: Math.abs(point.x) <= 1 && Math.abs(point.y) <= 1 && Math.abs(point.z) <= 1 };
  }

  return {
    get count() { return panels.length; },
    get closure() {
      let sum = 0;
      for (const panel of panels) sum += panel.closure;
      return panels.length ? sum / panels.length : 0;
    },
    get targetClosure() {
      let sum = 0;
      for (const panel of panels) sum += panel.targetClosure;
      return panels.length ? sum / panels.length : 0;
    },
    get wind() { return wind; },
    get reducedMotion() { return reduced; },
    get grabbing() { return !!grip; },
    update(deltaSeconds, elapsedSeconds) {
      // Native lostpointercapture can wait for the next pointer event.
      if (grip && !canvas.hasPointerCapture(grip.pointerId)) cancelGrip();
      if (!available()) { if (!paused || grip) interrupt(); return false; }
      if (!panels.length) return false;
      if (paused) { paused = false; accumulator = 0; deltaSeconds = 0; }
      if (!active && !wind && !grip) return false;
      // Use simulation time, not wall-clock elapsedSeconds, so tab resumes never
      // jump the wind phase or integrate an accumulated background interval.
      accumulator += clamp(Number.isFinite(deltaSeconds) ? deltaSeconds : 0, 0, STEP * 4);
      let changed = false;
      while (accumulator >= STEP) {
        accumulator -= STEP;
        time += STEP;
        for (const panel of panels) stepPanel(panel);
        changed = true;
        const settling = panels.some(panel => panel.speed > 0.012 || Math.abs(panel.targetClosure - panel.closure) > 0.0001);
        quiet = settling || grip || wind ? 0 : quiet + STEP;
        if (quiet > (reduced ? 0.12 : 0.4)) {
          active = false;
          for (const panel of panels) { panel.previous.set(panel.position); panel.speed = 0; }
          break;
        }
      }
      if (changed) renderGeometry();
      return active || wind || !!grip;
    },
    setClosure(value) {
      if (disposed || !Number.isFinite(value)) return;
      cancelGrip();
      for (const panel of panels) panel.targetClosure = clamp(value, 0, 1);
      wake();
    },
    setWind(value) {
      if (!disposed) { windRequested = !!value; wind = windRequested && !reduced; wake(); }
      return wind;
    },
    setEnabled(value) {
      if (disposed || enabled === !!value) return;
      enabled = !!value;
      if (!enabled) interrupt(); else wake();
    },
    reset() {
      if (disposed) return;
      interrupt();
      windRequested = true;
      wind = !reduced;
      time = 0;
      for (const panel of panels) {
        panel.closure = panel.targetClosure = 0;
        panel.position.set(panel.rest);
        panel.previous.set(panel.rest);
        panel.speed = panel.displacement = 0;
        updateGoal(panel);
      }
      renderGeometry();
      wake();
    },
    snapshot() {
      const rect = canvas.getBoundingClientRect();
      camera.updateWorldMatrix(true, false);
      const result = {
        closure: panels.length ? panels.reduce((sum, panel) => sum + panel.closure, 0) / panels.length : 0,
        wind, grabbing: !!grip, enabled, reducedMotion: reduced,
        panels: panels.map(panel => {
          let topAnchorError = 0;
          for (let i = ROWS * STRIDE * 3; i < COUNT * 3; i += 3) topAnchorError = Math.max(topAnchorError, Math.hypot(panel.position[i] - panel.goal[i], panel.position[i + 1] - panel.goal[i + 1], panel.position[i + 2] - panel.goal[i + 2]));
          return { id: panel.id, closure: panel.closure, targetClosure: panel.targetClosure,
            maxDisplacement: panel.displacement, maxSpeed: panel.speed, topAnchorError,
            probes: [probe(panel, 0.55, 0.25, rect), probe(panel, 0.7, 0.5, rect), probe(panel, 0.8, 0.8, rect), probe(panel, 0.9, 1, rect), probe(panel, 0.55, 0, rect)] };
        }),
        grip: null,
      };
      if (grip) {
        interpolate(grip.panel.position, grip.ids, grip.weights, point).add(grip.offset);
        result.grip = { panel: grip.panel.id, part: grip.part, uv: [...grip.uv], point: point.toArray(), target: grip.target.toArray(), error: point.distanceTo(grip.target) };
      }
      return result;
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      interrupt();
      observer?.disconnect();
      win.removeEventListener('pointerdown', pointerDown, true);
      win.removeEventListener('pointermove', pointerMove, true);
      win.removeEventListener('pointerup', pointerEnd, true);
      win.removeEventListener('pointercancel', pointerEnd, true);
      win.removeEventListener('blur', interrupt);
      doc.removeEventListener('visibilitychange', visibilityChanged);
      canvas.removeEventListener('lostpointercapture', lostCapture);
      canvas.removeEventListener('pointerleave', pointerLeave);
      motion.removeEventListener('change', preferenceChanged);
      // Geometry belongs to the caller: restore it, never dispose shared assets.
      for (const panel of panels) for (const binding of panel.bindings) {
        const geometry = binding.mesh.geometry;
        const positions = geometry.getAttribute('position');
        positions.array.set(binding.original);
        positions.setUsage(binding.originalUsage);
        positions.needsUpdate = true;
        if (binding.originalNormal) {
          geometry.getAttribute('normal').array.set(binding.originalNormal);
          geometry.getAttribute('normal').needsUpdate = true;
        } else geometry.deleteAttribute('normal');
        if (binding.originalTangent) {
          geometry.getAttribute('tangent').array.set(binding.originalTangent);
          geometry.getAttribute('tangent').needsUpdate = true;
        }
        binding.mesh.geometry.computeBoundingBox();
        binding.mesh.geometry.computeBoundingSphere();
      }
      fabricBindings.clear();
      blocked.clear();
    },
  };
}
