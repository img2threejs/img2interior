import './interior.css';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { EXRLoader } from 'three/addons/loaders/EXRLoader.js';
import { HDRLoader } from 'three/addons/loaders/HDRLoader.js';
import { createCurtainInteraction } from './interior-curtains.js';
import { createInteriorNavigation } from './interior-navigation.js';
import { validateManifest, sourceLabel, usesPolyHavenAPI } from './interior-manifest.js';
import { prepareLightmaps } from './interior-lightmaps.js';

const ui = Object.fromEntries([
  'viewport', 'canvas-host', 'source-panel', 'source-view', 'source-thumbnail', 'source-link',
  'mode-3d', 'mode-source', 'view-label', 'viewer-message', 'message-title', 'message-detail',
  'load-status', 'load-progress', 'retry-load', 'finish-swatches', 'finish-label', 'wireframe',
  'reset', 'download-glb', 'download-blend',
  'curtain-amount', 'curtain-percent', 'curtain-open', 'curtain-close', 'curtain-wind',
  'scene-title', 'camera-actions', 'finish-controls', 'curtain-controls', 'resource-credit',
  'source-caption', 'thumbnail-caption', 'interaction-hint', 'representation-title', 'representation-detail',
].map(id => [id, document.getElementById(id)]));
let viewButtons = [];
const state = { status: 'loading', error: null, mode: '3d', view: 'source', finish: null, wireframe: false, frames: 0 };
const offset = new THREE.Vector3();
const orbit = new THREE.Spherical();
const number = new Intl.NumberFormat('en-US');
const iblDiffuseLine = 'iblIrradiance += getIBLIrradiance( geometryNormal );';
const lightsInclude = '#include <lights_fragment_maps>';
let session = null;
let loading = false;
let renderRequest = 0;
let applyingPose = false;
let stopped = false;

function cameraSnapshot() {
  if (!session?.camera) return null;
  const { camera, controls } = session;
  return { position: camera.position.toArray(), quaternion: camera.quaternion.toArray(),
    target: controls.target.toArray(), fov: camera.fov, aspect: camera.aspect,
    near: camera.near, far: camera.far, view: state.view };
}

function textureSnapshot(texture) {
  if (!texture) return null;
  return { uuid: texture.uuid, channel: texture.channel, colorSpace: texture.colorSpace,
    flipY: texture.flipY, width: texture.image?.width, height: texture.image?.height };
}

function materialSnapshot(material) {
  const textures = {};
  for (const [name, value] of Object.entries(material)) {
    if (value?.isTexture) textures[name] = textureSnapshot(value);
  }
  return { uuid: material.uuid, name: material.name, type: material.type,
    color: material.color?.toArray(), roughness: material.roughness, metalness: material.metalness,
    transparent: material.transparent, opacity: material.opacity, alphaTest: material.alphaTest,
    transmission: material.transmission ?? 0, emissive: material.emissive?.toArray(),
    emissiveIntensity: material.emissiveIntensity,
    side: material.side, depthWrite: material.depthWrite, lightMapIntensity: material.lightMapIntensity,
    textures };
}

function inventorySnapshot() {
  return session?.entries.map(({ mesh, pbr, diagnostic }) => ({
    component: mesh.userData.component, uuid: mesh.uuid, name: mesh.name,
    geometryUuid: mesh.geometry.uuid, finish: mesh.userData.finish ?? null,
    currentFinish: session.manifest.finishTarget && mesh.userData.finish === session.manifest.finishTarget ? state.finish : null,
    curtain: mesh.userData.curtain_id ?? null, curtainPart: mesh.userData.curtain_part ?? null,
    lightmap: mesh.userData.lightmap ?? null,
    attributes: Object.fromEntries(Object.entries(mesh.geometry.attributes).map(([name, attribute]) =>
      [name, { count: attribute.count, itemSize: attribute.itemSize, version: attribute.version }])),
    indexCount: mesh.geometry.index?.count ?? null,
    materials: (Array.isArray(pbr) ? pbr : [pbr]).map(materialSnapshot),
    activeMaterialUuids: (Array.isArray(mesh.material) ? mesh.material : [mesh.material]).map(material => material.uuid),
    diagnosticMaterialUuids: (Array.isArray(diagnostic) ? diagnostic : [diagnostic]).map(material => material.uuid),
  })) ?? [];
}

Object.defineProperty(window, 'interiorStudy', {
  value: Object.freeze({
    get status() { return state.status; },
    get error() { return state.error; },
    get camera() { return cameraSnapshot(); },
    get frames() { return state.frames; },
    get stats() { return session?.stats ? structuredClone(session.stats) : null; },
    get inventory() { return inventorySnapshot(); },
    get mode() { return state.mode; },
    get finish() { return state.finish; },
    get wireframe() { return state.wireframe; },
    get curtains() { return session?.curtains?.snapshot() ?? null; },
    get navigation() { return session?.navigation?.snapshot() ?? null; },
    get lighting() { return session?.renderer ? { model: session.manifest.lighting.model,
      exposure: session.renderer.toneMappingExposure, sunIntensity: session.sun?.intensity ?? null,
      shadowMapSize: session.sun?.shadow.mapSize.toArray() ?? null } : null; },
    setView, setFinish, setMode, setWireframe, setCurtainClosure, setCurtainWind, reset,
  }),
});

function syncCurtainControls() {
  const curtain = session?.curtains;
  const percent = Math.round((curtain?.targetClosure ?? 0) * 100);
  if (ui['curtain-amount'].value !== String(percent)) ui['curtain-amount'].value = percent;
  ui['curtain-percent'].textContent = `${percent}%`;
  ui['curtain-amount'].setAttribute('aria-valuetext', `${ui['curtain-amount'].value}% coverage`);
  ui['curtain-wind'].setAttribute('aria-pressed', String(curtain?.wind ?? false));
  ui['curtain-wind'].disabled = !curtain?.count || state.status !== 'ready' || state.mode !== '3d' || !!curtain?.reducedMotion;
  ui['curtain-wind'].title = curtain?.reducedMotion ? 'Wind disabled by your reduced-motion setting.' : 'Toggle the gentle breeze that animates the fabric.';
}

function syncControls() {
  const ready = state.status === 'ready';
  const interactive = ready && state.mode === '3d';
  for (const mode of ['3d', 'source']) {
    ui[`mode-${mode}`].disabled = !ready;
    ui[`mode-${mode}`].setAttribute('aria-pressed', String(state.mode === mode));
  }
  for (const button of viewButtons) {
    button.disabled = !interactive;
    button.setAttribute('aria-pressed', String(state.view === button.dataset.view));
  }
  for (const button of ui['finish-swatches'].children) {
    button.disabled = !interactive;
    button.setAttribute('aria-pressed', String(state.finish === button.dataset.finish));
  }
  ui.wireframe.disabled = !interactive;
  ui.wireframe.setAttribute('aria-pressed', String(state.wireframe));
  ui.reset.disabled = !ready;
  for (const id of ['curtain-amount', 'curtain-open', 'curtain-close', 'curtain-wind']) ui[id].disabled = !interactive || !session?.curtains?.count;
  ui['curtain-controls'].hidden = !session?.curtains?.count;
  ui['finish-controls'].hidden = !session?.manifest.variants.length || !session?.finishes.size;
  syncCurtainControls();
  ui['canvas-host'].hidden = state.mode !== '3d';
  ui['source-panel'].hidden = state.mode !== 'source';
  ui['viewer-message'].hidden = ready;
  ui['load-progress'].hidden = state.status !== 'loading';
  ui['retry-load'].hidden = state.status !== 'error';
  ui.viewport.setAttribute('aria-busy', String(state.status === 'loading'));
  ui['retry-load'].disabled = loading;
  ui['load-status'].dataset.state = state.status;
  ui['view-label'].textContent = state.mode === 'source' ? sourceLabel(session.manifest)
    : state.wireframe ? '3D · geometry wireframe'
      : session?.curtains?.count ? '3D · interactive curtains' : '3D · authored interior';
  for (const [id, field] of [['download-glb', 'portableModel'], ['download-blend', 'blender']]) {
    const link = ui[id];
    link.setAttribute('aria-disabled', String(!ready));
    link.tabIndex = ready ? 0 : -1;
    if (ready) link.href = session.manifest[field];
    else link.removeAttribute('href');
  }
  if (session?.controls) {
    session.curtains?.setEnabled(interactive);
    session.controls.enabled = interactive && !session.curtains?.grabbing;
    session.renderer.domElement.tabIndex = interactive ? 0 : -1;
    session.renderer.domElement.setAttribute('aria-disabled', String(!interactive));
  }
}

function fail(error) {
  state.status = 'error';
  state.error = error instanceof Error ? error.message : String(error);
  session?.curtains?.setEnabled(false);
  cancelAnimationFrame(renderRequest);
  renderRequest = 0;
  ui['message-title'].textContent = 'Could not open the room';
  ui['message-detail'].textContent = state.error;
  ui['load-status'].textContent = 'Scene load did not finish. Check your connection, then choose “Retry load”.';
  syncControls();
}

function requestRender() {
  if (renderRequest || state.status !== 'ready' || state.mode !== '3d' || document.hidden) return;
  renderRequest = requestAnimationFrame(time => {
    renderRequest = 0;
    if (!session || state.status !== 'ready' || state.mode !== '3d' || document.hidden) return;
    try {
      const previous = session.lastRenderTime;
      session.lastRenderTime = time;
      const moving = session.curtains?.update(previous === null ? 0 : (time-previous)/1000, time/1000);
      syncCurtainControls();
      session.renderer.render(session.scene, session.camera);
      if (session.shaderError) throw session.shaderError;
      state.frames++;
      if (moving) requestRender();
      else session.lastRenderTime = null;
    } catch (error) { fail(error); }
  });
}

function resize() {
  if (!session?.camera) return;
  const width = ui.viewport.clientWidth;
  const height = ui.viewport.clientHeight;
  if (!width || !height) return;
  session.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  session.renderer.setSize(width, height, false);
  session.camera.aspect = width / height;
  session.camera.updateProjectionMatrix();
  requestRender();
}

function applyView(name) {
  const { manifest, camera, controls } = session;
  const pose = name === 'source' ? manifest.camera : manifest.views[name];
  applyingPose = true;
  camera.position.fromArray(pose.position);
  camera.fov = pose.fov ?? manifest.camera.fov;
  camera.updateProjectionMatrix();
  controls.target.fromArray(pose.target);
  camera.lookAt(controls.target);
  controls.update();
  applyingPose = false;
  state.view = name;
}

function setView(name) {
  if (state.status !== 'ready' || state.mode !== '3d') return false;
  if (name !== 'source' && !Object.hasOwn(session.manifest.views, name)) throw new Error(`Unknown view: ${name}`);
  if (session.curtains?.grabbing) session.curtains.setEnabled(false);
  applyView(name);
  syncControls();
  requestRender();
  return true;
}

function setFinish(id) {
  if (state.status !== 'ready' || state.mode !== '3d') return false;
  const variant = session.manifest.variants.find(item => item.id === id);
  if (!variant) throw new Error(`Unknown fabric finish: ${id}`);
  for (const [material, original] of session.finishes) {
    const base = id === session.manifest.variants[0].id;
    if (base) material.color.copy(original.color);
    else material.color.copy(original.color).multiply(session.finishTints.get(id));
    material.roughness = base ? original.roughness : variant.roughness ?? original.roughness;
  }
  state.finish = id;
  ui['finish-label'].textContent = variant.label;
  syncControls();
  requestRender();
  return true;
}

function setMode(mode) {
  if (!['3d', 'source'].includes(mode)) throw new Error(`Unknown mode: ${mode}`);
  if (state.status !== 'ready') return false;
  state.mode = mode;
  syncControls();
  if (mode === '3d') resize();
  return true;
}

function setWireframe(enabled) {
  if (typeof enabled !== 'boolean') throw new TypeError('Wireframe requires a boolean.');
  if (state.status !== 'ready' || state.mode !== '3d') return false;
  state.wireframe = enabled;
  for (const { mesh, pbr, diagnostic } of session.entries) mesh.material = enabled ? diagnostic : pbr;
  syncControls();
  requestRender();
  return true;
}

function setCurtainClosure(value) {
  if (state.status !== 'ready' || state.mode !== '3d' || !session.curtains?.count) return false;
  if (!Number.isFinite(value) || value < 0 || value > 1) throw new RangeError('Curtain coverage must be between 0 and 1.');
  session.curtains.setClosure(value);
  requestRender();
  return true;
}

function setCurtainWind(enabled) {
  if (state.status !== 'ready' || state.mode !== '3d' || !session.curtains?.count) return false;
  if (typeof enabled !== 'boolean') throw new TypeError('Gentle breeze requires a boolean.');
  const actual = session.curtains.setWind(enabled);
  syncCurtainControls();
  requestRender();
  return actual === enabled;
}

function reset() {
  if (state.status !== 'ready') return false;
  setMode('3d');
  session.curtains?.reset();
  setWireframe(false);
  if (session.manifest.variants.length) setFinish(session.manifest.variants[0].id);
  setView('source');
  return true;
}

function cameraKeys(event) {
  if (!session?.controls.enabled || !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', '+', '=', '-', '_', 'Home'].includes(event.key)) return;
  event.preventDefault();
  if (event.key === 'Home') { setView('source'); return; }
  const { camera, controls } = session;
  orbit.setFromVector3(offset.copy(camera.position).sub(controls.target));
  if (event.key === 'ArrowLeft') orbit.theta -= 0.045;
  if (event.key === 'ArrowRight') orbit.theta += 0.045;
  if (event.key === 'ArrowUp') orbit.phi -= 0.035;
  if (event.key === 'ArrowDown') orbit.phi += 0.035;
  if (event.key === '+' || event.key === '=') orbit.radius *= 0.9;
  if (event.key === '-' || event.key === '_') orbit.radius *= 1.1;
  orbit.phi = THREE.MathUtils.clamp(orbit.phi, controls.minPolarAngle, controls.maxPolarAngle);
  orbit.radius = THREE.MathUtils.clamp(orbit.radius, controls.minDistance, controls.maxDistance);
  camera.position.copy(controls.target).add(offset.setFromSpherical(orbit));
  controls.update();
}


function configureSceneContent(manifest) {
  document.title = `${manifest.title} — Interior study`;
  ui['scene-title'].textContent = manifest.title;
  ui.viewport.style.setProperty('--source-aspect', `${manifest.sourceImageSize[0]} / ${manifest.sourceImageSize[1]}`);
  for (const id of ['source-view', 'source-thumbnail']) {
    ui[id].width = manifest.sourceImageSize[0];
    ui[id].height = manifest.sourceImageSize[1];
    ui[id].alt = `${sourceLabel(manifest)} for ${manifest.title}`;
  }
  ui['source-caption'].textContent = `${sourceLabel(manifest)} · not a viewer render`;
  ui['thumbnail-caption'].textContent = `${sourceLabel(manifest)}. Open the image to compare details.`;
  ui['resource-credit'].hidden = !usesPolyHavenAPI(manifest);
  viewButtons = [['source', { label: 'Source view' }], ...Object.entries(manifest.views)].map(([name, pose]) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.view = name;
    button.textContent = pose.label || name;
    button.disabled = true;
    button.setAttribute('aria-pressed', String(name === 'source'));
    button.addEventListener('click', () => setView(name));
    return button;
  });
  ui['camera-actions'].replaceChildren(...viewButtons);
  state.finish = manifest.variants[0]?.id ?? null;
  createSwatches(manifest);
}

function configureInteractionContent(current) {
  const cloth = current.curtains.count > 0;
  const cameraHint = 'Scroll or pinch to zoom, right-drag to pan inside the room. Keyboard: Tab into the 3D frame, arrow keys to rotate, + / − to zoom, Home returns to the source view.';
  ui['interaction-hint'].textContent = cloth
    ? `Drag the fabric to open or close the curtains; drag elsewhere to orbit the camera. ${cameraHint} Adjust the curtains with the Coverage slider and buttons; turn off Gentle breeze to settle the cloth.`
    : `Drag to orbit the camera. ${cameraHint}`;
  current.renderer.domElement.setAttribute('aria-label', `${current.manifest.title}. Interactive 3D interior. ${ui['interaction-hint'].textContent}`);
  ui['representation-title'].textContent = cloth && current.sun ? 'Sunlight follows the curtain' : 'Baked light, editable geometry';
  ui['representation-detail'].textContent = !current.sun
    ? 'Lighting and reflections use the authored static bake and reflection probe. This scene has no runtime sun or dynamic GI; changing materials or cloth does not rebake lighting. The camera stays inside the declared room bounds.'
    : cloth
      ? 'Direct sunlight and cast shadows update with the curtain shape. Indirect bounce and reflections retain the authored open-curtain bake; this is not dynamic GI. The camera stays inside the declared room bounds.'
      : 'Direct sunlight and shadows are rendered in real time. Indirect bounce and reflections use the authored static bake; material changes do not rebake them. The camera stays inside the declared room bounds.';
}

function createSwatches(manifest) {
  ui['finish-swatches'].replaceChildren();
  for (const variant of manifest.variants) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'finish-swatch';
    button.dataset.finish = variant.id;
    button.disabled = true;
    button.setAttribute('aria-pressed', String(variant.id === state.finish));
    const chip = document.createElement('span');
    chip.className = 'swatch-chip';
    chip.style.setProperty('--swatch-color', variant.color);
    chip.setAttribute('aria-hidden', 'true');
    button.append(chip, document.createTextNode(variant.label));
    button.addEventListener('click', () => setFinish(variant.id));
    ui['finish-swatches'].append(button);
  }
  ui['finish-label'].textContent = manifest.variants[0]?.label ?? '';
}

function collectResources(root, current) {
  root.traverse(object => {
    if (!object.isMesh) return;
    current.geometries.add(object.geometry);
    for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
      current.materials.add(material);
      for (const value of Object.values(material)) if (value?.isTexture) current.textures.add(value);
    }
  });
}

function bindMaterials(root, current) {
  const chunk = THREE.ShaderChunk.lights_fragment_maps;
  if (typeof chunk !== 'string' || chunk.split(iblDiffuseLine).length !== 2) throw new Error('Three.js shader does not match the bake version: missing the IBL diffuse line.');
  const bakedChunk = chunk.replace(iblDiffuseLine, '// Diffuse is supplied by the Blender lightmap only.');
  const cache = new Map();
  const wireCache = new Map();
  const clothTextures = new Map();
  const clothAnisotropy = Math.max(1, Math.min(8, current.renderer.capabilities.getMaxAnisotropy()));
  let triangles = 0;
  root.traverse(mesh => {
    if (mesh.isLight) throw new Error('Runtime GLB must not contain lights outside the manifest sun configuration.');
    if (!mesh.isMesh) return;
    // glTF node extras live on a Group when an object has multiple material primitives.
    // Carry those authored semantics to the rendered primitive, never infer a missing atlas.
    for (const key of ['component', 'lightmap', 'finish', 'curtain_id', 'curtain_part']) {
      if (mesh.userData[key] !== undefined) continue;
      let owner = mesh.parent;
      while (owner && owner !== root && owner.userData[key] === undefined) owner = owner.parent;
      if (owner?.userData[key] !== undefined) mesh.userData[key] = owner.userData[key];
    }
    const component = mesh.userData.component;
    const atlasId = mesh.userData.lightmap;
    const atlas = current.atlases.get(atlasId);
    if (!component) throw new Error(`Mesh ${mesh.name || mesh.uuid} is missing a component.`);
    if (atlasId !== undefined && !atlas) throw new Error(`Mesh ${component} has an invalid lightmap.`);
    const { position, uv, uv1 } = mesh.geometry.attributes;
    if (!position || !uv || uv.count !== position.count || uv.itemSize !== 2) throw new Error(`Mesh ${component} is missing a full UV0 channel.`);
    if (atlas && (!uv1 || uv1.count !== position.count || uv1.itemSize !== 2)) throw new Error(`Mesh ${component} is missing a full UV1 channel for the atlas.`);
    const configurable = current.manifest.variants.length > 0 && current.manifest.finishTarget && mesh.userData.finish === current.manifest.finishTarget;
    const dynamic = mesh.userData.curtain_id !== undefined;
    function bind(source) {
      if (!source.isMeshStandardMaterial) throw new Error(`Material ${source.name} of ${component} is not a standard PBR material.`);
      if (dynamic) {
        const key = `${source.uuid}:cloth:${configurable}`;
        if (cache.has(key)) return cache.get(key);
        const material = source.clone();
        material.lightMap = null;
        material.side = material.shadowSide = THREE.DoubleSide;
        // Keep the scan's yarn detail at grazing angles without changing sofa samplers.
        for (const key of ['map', 'normalMap', 'roughnessMap', 'metalnessMap']) {
          const sourceTexture = material[key];
          if (!sourceTexture) continue;
          if (!clothTextures.has(sourceTexture)) {
            const texture = sourceTexture.clone();
            texture.anisotropy = clothAnisotropy;
            texture.needsUpdate = true;
            current.textures.add(texture);
            clothTextures.set(sourceTexture, texture);
          }
          material[key] = clothTextures.get(sourceTexture);
        }
        current.materials.add(material);
        if (configurable) current.finishes.set(material, { color: material.color.clone(), roughness: material.roughness });
        cache.set(key, material);
        return material;
      }
      // Glass and the emissive bulb intentionally have no baked atlas.
      // Leave their native physical/emissive material and environment response intact.
      if (!atlas && !configurable) {
        cache.set(`${source.uuid}:unbaked`, source);
        return source;
      }
      // Partition material identity by finish ownership as well as atlas.
      const key = `${source.uuid}:${atlas?.id ?? 'unbaked'}:${configurable}`;
      if (cache.has(key)) return cache.get(key);
      const material = source.clone();
      current.materials.add(material);
      if (atlas) {
        material.lightMap = atlas.texture;
        // Exporter records PI irradiance compensation in atlas.intensity.
        material.lightMapIntensity = atlas.intensity;
        material.onBeforeCompile = shader => {
          if (!shader.fragmentShader.includes(lightsInclude)) throw new Error('PBR shader is missing lights_fragment_maps for the diffuse bake.');
          shader.fragmentShader = shader.fragmentShader.replace(lightsInclude, bakedChunk);
        };
        material.customProgramCacheKey = () => 'interior-baked-diffuse-r180';
      }
      // Cloning retains authored alpha blending, alpha test, side and depth settings (including foliage).
      cache.set(key, material);
      if (configurable) current.finishes.set(material, { color: material.color.clone(), roughness: material.roughness });
      return material;
    }
    function diagnostic(material) {
      if (!wireCache.has(material.uuid)) {
        const wire = new THREE.MeshBasicMaterial({ color: '#d8d2c6', wireframe: true, side: material.side });
        current.materials.add(wire);
        wireCache.set(material.uuid, wire);
      }
      return wireCache.get(material.uuid);
    }
    const pbr = Array.isArray(mesh.material) ? mesh.material.map(bind) : bind(mesh.material);
    const wire = Array.isArray(pbr) ? pbr.map(diagnostic) : diagnostic(pbr);
    mesh.material = pbr;
    const materials = Array.isArray(pbr) ? pbr : [pbr];
    mesh.castShadow = !materials.some(material => (material.transmission ?? 0) > 0.5);
    mesh.receiveShadow = true;
    current.entries.push({ mesh, pbr, diagnostic: wire });
    triangles += (mesh.geometry.index?.count ?? position.count) / 3;
  });
  if (!current.entries.length) throw new Error('Scene has no meshes.');
  if (current.manifest.variants.length && !current.finishes.size) throw new Error(`Finish variants require an explicit finishTarget matching actual mesh finish tags: ${current.manifest.finishTarget ?? '(missing)'}`);
  current.stats = { meshes: current.entries.length, components: new Set(current.entries.map(entry => entry.mesh.userData.component)).size,
    triangles, geometries: current.geometries.size, pbrMaterials: cache.size, lightmaps: current.atlases.size,
    environmentTextureUuid: current.environmentTarget.texture.uuid, manifest: current.manifest.stats ?? {} };
}

function disposeSession() {
  cancelAnimationFrame(renderRequest);
  renderRequest = 0;
  if (!session) return;
  session.curtains?.dispose();
  session.navigation?.dispose();
  session.sun?.dispose();
  session.controls?.dispose();
  session.environmentTarget?.dispose();
  for (const geometry of session.geometries) geometry.dispose();
  for (const material of session.materials) material.dispose();
  const closedImages = new Set();
  for (const texture of session.textures) {
    texture.dispose();
    if (texture.image?.close && !closedImages.has(texture.image)) {
      texture.image.close();
      closedImages.add(texture.image);
    }
  }
  session.renderer?.dispose();
  session.renderer?.domElement.remove();
  session = null;
}

async function start() {
  if (loading || stopped) return;
  loading = true;
  disposeSession();
  Object.assign(state, { status: 'loading', error: null, mode: '3d', view: 'source', finish: null, wireframe: false, frames: 0 });
  ui['message-title'].textContent = 'Opening room';
  ui['message-detail'].textContent = 'Reading model, materials and lightmap atlases.';
  ui['load-status'].textContent = 'Reading scene manifest…';
  ui['load-progress'].removeAttribute('value');
  syncControls();
  try {
    const response = await fetch('/assets/interior/manifest.json', { cache: 'no-cache' });
    if (!response.ok) throw new Error(`Could not load manifest (${response.status}).`);
    const manifest = await response.json();
    if (stopped) return;
    validateManifest(manifest);
    configureSceneContent(manifest);
    const current = { manifest, geometries: new Set(), materials: new Set(), textures: new Set(),
      atlases: new Map(), finishes: new Map(), finishTints: new Map(), entries: [], shaderError: null, lastRenderTime: null };
    session = current;
    // The first variant describes the authored base, not an extra tint.
    const base = new THREE.Color(manifest.variants[0]?.color ?? '#ffffff');
    for (const variant of manifest.variants.slice(1)) {
      const tint = new THREE.Color(variant.color);
      tint.setRGB(tint.r / base.r, tint.g / base.g, tint.b / base.b);
      current.finishTints.set(variant.id, tint);
    }
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    current.renderer = renderer;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.NeutralToneMapping;
    renderer.toneMappingExposure = manifest.exposure;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.setClearColor('#282722');
    renderer.debug.onShaderError = () => { current.shaderError = new Error('Could not compile the PBR/lightmap shader on this device.'); };
    const canvas = renderer.domElement;
    canvas.tabIndex = -1;
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('aria-label', `${manifest.title}. Interactive 3D interior.`);
    canvas.setAttribute('aria-describedby', 'interaction-hint');
    canvas.addEventListener('keydown', cameraKeys);
    canvas.addEventListener('webglcontextlost', event => { event.preventDefault(); fail(new Error('Lost the WebGL context. Choose Retry load to rebuild the viewer.')); });
    ui['canvas-host'].append(canvas);
    const scene = new THREE.Scene();
    current.scene = scene;
    const roomSize = new THREE.Vector3().fromArray(manifest.roomBounds.max).sub(new THREE.Vector3().fromArray(manifest.roomBounds.min)).length();
    current.camera = new THREE.PerspectiveCamera(manifest.camera.fov, manifest.sourceImageSize[0] / manifest.sourceImageSize[1], 0.03, Math.max(250, roomSize * 4));
    const controls = new OrbitControls(current.camera, canvas);
    current.controls = controls;
    controls.enabled = false;
    controls.enableDamping = false;
    controls.enablePan = true;
    controls.rotateSpeed = 0.55;
    controls.zoomSpeed = 0.7;
    current.navigation = createInteriorNavigation(current.camera, controls, manifest.roomBounds);
    controls.addEventListener('change', () => {
      if (!applyingPose && state.status === 'ready') { state.view = null; syncControls(); }
      requestRender();
    });
    applyView('source');
    resize();
    let completed = 0;
    const total = manifest.lightmaps.length + 3 + (manifest.background != null ? 1 : 0);
    ui['load-progress'].max = total;
    ui['load-progress'].value = 0;
    const tracked = async (promise, label) => {
      try {
        const value = await promise;
        completed++;
        if (state.status === 'loading') {
          ui['load-progress'].value = completed;
          ui['load-status'].textContent = `Loaded ${completed}/${total} asset groups · ${label}`;
        }
        return value;
      } catch (error) { throw new Error(`Could not load ${label}: ${error.message}`); }
    };
    for (const id of ['source-view', 'source-thumbnail']) ui[id].src = manifest.sourceImage;
    ui['source-link'].href = manifest.sourceImage;
    const exrLoader = new EXRLoader();
    const tasks = [
      tracked(new GLTFLoader().loadAsync(manifest.model).then(async gltf => {
        current.root = gltf.scene;
        collectResources(gltf.scene, current);
        // GLTFLoader deliberately resolves failed texture loads as null. Never call that ready.
        const textures = await gltf.parser.getDependencies('texture');
        for (const texture of textures) if (texture) current.textures.add(texture);
        if (textures.some(texture => !texture)) throw new Error('One or more textures inside the GLB are missing.');
      }), 'model and PBR textures'),
      tracked(exrLoader.loadAsync(manifest.environment).then(texture => {
        texture.colorSpace = THREE.NoColorSpace;
        texture.mapping = THREE.EquirectangularReflectionMapping;
        current.probe = texture;
        current.textures.add(texture);
      }), 'room reflection probe'),
      tracked(Promise.all([ui['source-view'].decode(), ui['source-thumbnail'].decode()]).then(() => {
        const image = ui['source-view'];
        if (image.naturalWidth !== manifest.sourceImageSize[0] || image.naturalHeight !== manifest.sourceImageSize[1]) {
          throw new Error('sourceImageSize does not match the decoded source image; correct the scene specification and re-export.');
        }
      }), 'source reference image'),
      ...manifest.lightmaps.map(atlas => tracked(exrLoader.loadAsync(atlas.url).then(texture => {
        current.textures.add(texture);
        current.atlases.set(atlas.id, { ...atlas, texture });
      }), `atlas ${atlas.id}`)),
    ];
    if (manifest.background != null) {
      const backgroundLoader = /\.exr$/i.test(manifest.background) ? exrLoader : new HDRLoader();
      tasks.push(tracked(backgroundLoader.loadAsync(manifest.background).then(texture => {
        texture.mapping = THREE.EquirectangularReflectionMapping;
        texture.colorSpace = THREE.NoColorSpace;
        current.background = texture;
        current.textures.add(texture);
        scene.background = texture;
        scene.backgroundIntensity = manifest.backgroundIntensity;
      }), 'scene background'));
    }
    // Settle every load before disposal/retry; a late texture must not leak into another session.
    const results = await Promise.allSettled(tasks);
    if (stopped) throw new Error('Viewer was disposed while assets were loading.');
    const rejected = results.find(result => result.status === 'rejected');
    if (rejected) throw rejected.reason;
    if (state.error) throw new Error(state.error);
    prepareLightmaps(current.atlases.values());
    ui['load-status'].textContent = 'Preparing reflection probe and compiling materials…';
    const pmrem = new THREE.PMREMGenerator(renderer);
    try { current.environmentTarget = pmrem.fromEquirectangular(current.probe); }
    finally { pmrem.dispose(); current.probe.dispose(); current.textures.delete(current.probe); }
    scene.environment = current.environmentTarget.texture;
    bindMaterials(current.root, current);
    scene.add(current.root);
    const sunSpec = manifest.lighting.sun;
    if (sunSpec) {
      const sun = new THREE.DirectionalLight();
      sun.color.setRGB(...sunSpec.color);
      sun.intensity = sunSpec.intensity;
      // Fit the shadow volume to the authored room, not Oak/Linen coordinates.
      const roomCenter = new THREE.Vector3().fromArray(manifest.roomBounds.min).add(new THREE.Vector3().fromArray(manifest.roomBounds.max)).multiplyScalar(0.5);
      const shadowExtent = roomSize * 0.6;
      sun.target.position.copy(roomCenter);
      sun.position.fromArray(sunSpec.position).sub(new THREE.Vector3().fromArray(sunSpec.target)).normalize().multiplyScalar(roomSize * 1.5).add(roomCenter);
      sun.castShadow = true;
      sun.shadow.mapSize.setScalar(sunSpec.shadowMapSize);
      sun.shadow.camera.near = 0.1;
      sun.shadow.camera.far = roomSize * 3;
      sun.shadow.camera.left = sun.shadow.camera.bottom = -shadowExtent;
      sun.shadow.camera.right = sun.shadow.camera.top = shadowExtent;
      sun.shadow.bias = -0.00008;
      sun.shadow.normalBias = 0.015;
      sun.shadow.camera.updateProjectionMatrix();
      current.sun = sun;
      scene.add(sun, sun.target);
    }
    current.curtains = createCurtainInteraction({ root: current.root, camera: current.camera, roomBounds: manifest.roomBounds,
      canvas, controls, onChange: requestRender, isInteractive: () => state.status === 'ready' && state.mode === '3d' });
    configureInteractionContent(current);
    await renderer.compileAsync(scene, current.camera);
    if (stopped) throw new Error('Viewer was disposed while shaders were compiling.');
    if (state.error) throw new Error(state.error);
    if (current.shaderError) throw current.shaderError;
    renderer.render(scene, current.camera);
    if (current.shaderError) throw current.shaderError;
    state.frames++;
    state.status = 'ready';
    ui['load-status'].textContent = `${number.format(current.stats.meshes)} meshes · ${number.format(current.stats.triangles)} triangles · all textures and atlases loaded.`;
    syncControls();
    requestRender();
  } catch (error) {
    disposeSession();
    if (!stopped) fail(error);
  } finally {
    loading = false;
    if (stopped) disposeSession();
    else syncControls();
  }
}

ui['mode-3d'].addEventListener('click', () => setMode('3d'));
ui['mode-source'].addEventListener('click', () => setMode('source'));
ui.wireframe.addEventListener('click', () => setWireframe(!state.wireframe));
ui.reset.addEventListener('click', reset);
ui['retry-load'].addEventListener('click', start);
ui['curtain-amount'].addEventListener('input', () => setCurtainClosure(Number(ui['curtain-amount'].value)/100));
ui['curtain-open'].addEventListener('click', () => setCurtainClosure(0));
ui['curtain-close'].addEventListener('click', () => setCurtainClosure(1));
ui['curtain-wind'].addEventListener('click', () => setCurtainWind(!session.curtains.wind));
const resizeObserver = new ResizeObserver(resize);
resizeObserver.observe(ui.viewport);
window.addEventListener('resize', resize);
document.addEventListener('visibilitychange', requestRender);
window.addEventListener('pagehide', event => {
  if (!event.persisted) {
    stopped = true;
    cancelAnimationFrame(renderRequest);
    resizeObserver.disconnect();
    session?.curtains?.setEnabled(false);
    // In-flight loaders retain ownership until all settle, then finally disposes.
    if (!loading) disposeSession();
  }
});
start();
