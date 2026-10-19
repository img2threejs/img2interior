# SPDX-License-Identifier: Apache-2.0
"""Workspace-bound native production using actual Blender/Cycles.

Loaded privately by authoring.bound_module; no paths or scene data are accessed
at import. Numeric regression results never certify reference likeness.
"""
from collections import defaultdict
from pathlib import Path
import hashlib
import json
import math
import time
import uuid

import bpy
import numpy as np
from mathutils import Vector

BAKE_MARGIN = 2


def log(event, **data):
    print(json.dumps({'event': event, **data}), flush=True)


def select_objects(objects):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]


def meshes():
    return [obj for obj in bpy.context.scene.objects if obj.type == 'MESH' and not obj.hide_render]


def set_render(width, samples, format='PNG'):
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.seed = 17
    scene.render.resolution_x = width
    width_px, height_px = CONTRACT['authoring']['sourceImageSize']
    scene.render.resolution_y = max(1, round(width * height_px / width_px))
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = format
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '16' if format == 'OPEN_EXR' else '8'
    scene.render.film_transparent = False
    scene.view_settings.view_transform = 'Khronos PBR Neutral'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    return scene


def look_at(camera, target):
    camera.rotation_mode = 'XYZ'
    camera.rotation_euler = (Vector(target) - camera.location).to_track_quat('-Z', 'Y').to_euler()


def save_master():
    bpy.ops.file.pack_all()
    settings = bpy.context.preferences.filepaths
    original = settings.save_version
    try:
        settings.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=str(MASTER), compress=True)
    finally:
        settings.save_version = original


def inventory():
    rows = []
    for obj in meshes():
        obj.data.calc_loop_triangles()
        coordinates = np.empty(len(obj.data.vertices) * 3, dtype=np.float32)
        obj.data.vertices.foreach_get('co', coordinates)
        if not np.isfinite(coordinates).all():
            raise RuntimeError(f'Non-finite geometry: {obj.name}')
        if not obj.get('component'):
            raise RuntimeError(f'Physical mesh missing component identity: {obj.name}')
        if not obj.data.uv_layers:
            raise RuntimeError(f'Physical mesh missing material UVs: {obj.name}')
        rows.append({'name': obj.name, 'component': obj['component'],
                     'finish': obj.get('finish'), 'lightmap': obj.get('lightmap'),
                     'vertices': len(obj.data.vertices), 'triangles': len(obj.data.loop_triangles),
                     'uvLayers': [layer.name for layer in obj.data.uv_layers],
                     'materials': [slot.material.name if slot.material else None for slot in obj.material_slots],
                     'bounds': [list(obj.matrix_world @ Vector(corner)) for corner in obj.bound_box]})
    return rows


def stage_draft(args):
    from authoring import private_module
    bpy.ops.wm.read_factory_settings(use_empty=True)
    builder = private_module(CONTEXT.resolve(CONTRACT['authoring']['sceneBuilder']))
    result = builder.build_scene(CONTEXT)
    json.dumps(result)
    scene = set_render(args.width, args.samples)
    if not scene.camera:
        raise RuntimeError('Scene builder did not provide a reference camera')
    for obj in meshes():
        select_objects([obj])
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        for modifier in list(obj.modifiers):
            bpy.ops.object.modifier_apply(modifier=modifier.name)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        if len(obj.data.uv_layers) != 1 or obj.data.uv_layers[0].name != 'UV0':
            raise ValueError(f'{obj.name}: builder must supply exactly one UV0 layer before baking')
    scene['dirty_atlases_json'] = json.dumps(sorted({atlas_group(o) for o in meshes() if atlas_group(o)}))
    scene['authoring_revision'] = uuid.uuid4().hex
    rows = inventory()
    scene['authoring_summary_json'] = json.dumps(result)
    scene['reference_camera'] = scene.camera.name
    save_master()
    scene.render.filepath = str(EVIDENCE / 'draft-source.png')
    bpy.ops.render.render(write_still=True)
    (EVIDENCE / 'authoring.json').write_text(json.dumps({'builder': result, 'meshes': rows}, indent=2) + '\n')
    log('draft-complete', output=str(EVIDENCE / 'draft-source.png'), meshes=len(rows),
        triangles=sum(row['triangles'] for row in rows))


def stage_refresh_material(args):
    """Reload named file maps from disk, removing stale packed bytes first."""
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    paths = {CONTEXT.resolve(path) for path in args.image}
    if not paths:
        raise ValueError('refresh-material requires one or more --image W-relative paths')
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    refreshed = []
    for image in bpy.data.images:
        path = Path(bpy.path.abspath(image.filepath)).resolve()
        if image.source == 'FILE' and path in paths:
            if image.packed_file:
                image.unpack(method='REMOVE')
            image.reload()
            image.pack()
            refreshed.append(str(path.relative_to(ROOT)))
    if set(refreshed) != {str(path.relative_to(ROOT)) for path in paths}:
        raise ValueError('Some requested maps are not used by the packed master')
    bpy.context.scene['dirty_atlases_json'] = json.dumps(sorted({atlas_group(o) for o in meshes() if atlas_group(o)}))
    bpy.context.scene['authoring_revision'] = uuid.uuid4().hex
    save_master()
    (EVIDENCE / 'material-refresh.json').write_text(json.dumps({
        'images': refreshed, 'nextStages': ['bake', 'probe', 'export'],
        'sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    }, indent=2))


def is_glass(obj):
    for slot in obj.material_slots:
        material = slot.material
        if not material or not material.use_nodes:
            continue
        for node in material.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                transmission = node.inputs.get('Transmission Weight')
                if transmission and not transmission.is_linked and transmission.default_value > 0.5:
                    return True
    return False


def atlas_group(obj):
    component = str(obj['component']).lower()
    if is_glass(obj) or 'bulb' in obj.name.lower():
        return None
    if obj.get('bake_detail'):
        return 'details'
    if 'exterior' in component or 'garden' in component:
        return 'garden'
    if any(part in component for part in ('sofa', 'pillow', 'curtain', 'rug')):
        return 'textiles'
    if any(part in component for part in ('floor', 'wall', 'ceiling', 'window', 'architecture', 'room')):
        return 'architecture'
    return 'furniture'


def unwrap_atlas(objects, size):
    for obj in objects:
        # Shared imported geometry needs independent lightmap coordinates per placement.
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        original = obj.data.uv_layers[0]
        original.active_render = True
        layer = obj.data.uv_layers.get('Lightmap') or obj.data.uv_layers.new(name='Lightmap')
        obj.data.uv_layers.active = layer
    select_objects(objects)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(70), margin_method='FRACTION',
                             island_margin=(2 * BAKE_MARGIN + 2) / size,
                             area_weight=0.4, correct_aspect=True, scale_to_bounds=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    for obj in objects:
        obj.data.uv_layers[0].active_render = True
        mesh = obj.data
        mesh.calc_loop_triangles()
        coordinates = np.array([corner.uv[:] for corner in mesh.uv_layers['Lightmap'].data])
        triangles = coordinates[np.array([triangle.loops[:] for triangle in mesh.loop_triangles])]
        edges = triangles[:, 1:] - triangles[:, :1]
        area = np.abs(edges[:, 0, 0] * edges[:, 1, 1] - edges[:, 0, 1] * edges[:, 1, 0]).sum() * 0.5
        if not np.isfinite(coordinates).all() or area * size * size < 1:
            raise RuntimeError(f'Collapsed or subpixel lightmap UVs: {obj.name}, area={area}')


def create_target(name, size):
    image = bpy.data.images.new(name, width=size, height=size, alpha=True, float_buffer=True)
    image.colorspace_settings.name = 'Linear Rec.709'
    return image


def assign_bake_materials(objects, atlas_id, target):
    copies = {}
    for obj in objects:
        obj['lightmap'] = atlas_id
        if not obj.material_slots:
            raise RuntimeError(f'No material on bake target: {obj.name}')
        for slot in obj.material_slots:
            original = slot.material
            if original is None:
                raise RuntimeError(f'Empty material slot: {obj.name}')
            key = original.as_pointer()
            if key not in copies:
                # The reserved target node already identifies our prepared
                # material. Reuse it across bakes instead of copying it again.
                prepared = original.node_tree.nodes.get('InteriorBakeTarget') is not None
                material = original if prepared else original.copy()
                if not prepared:
                    material.name = f'{original.name}__{atlas_id}'
                # The bake operator overrides the active UV with Lightmap. Source
                # sampling must remain explicitly UV0, independent of that target.
                tree = material.node_tree
                source_uv = next((node for node in tree.nodes
                                  if node.type == 'UVMAP' and node.uv_map == 'UV0'), None)
                if source_uv is None:
                    source_uv = tree.nodes.new('ShaderNodeUVMap')
                    source_uv.uv_map = 'UV0'
                for texture in tree.nodes:
                    if texture.type == 'TEX_IMAGE' and texture.name != 'InteriorBakeTarget' and not texture.inputs['Vector'].is_linked:
                        tree.links.new(source_uv.outputs['UV'], texture.inputs['Vector'])
                node = material.node_tree.nodes.get('InteriorBakeTarget')
                if node is None:
                    node = material.node_tree.nodes.new('ShaderNodeTexImage')
                node.name = 'InteriorBakeTarget'
                node.label = 'UV1 diffuse irradiance; runtime sidecar, not baked into source PBR'
                node.image = target
                material.node_tree.nodes.active = node
                copies[key] = material
            slot.material = copies[key]
    return list(copies.values())


def set_targets(materials, image):
    for material in materials:
        node = material.node_tree.nodes['InteriorBakeTarget']
        node.image = image
        material.node_tree.nodes.active = node


def bake_albedo(objects, materials, target, channel='Base Color'):
    restores = []
    for material in materials:
        tree = material.node_tree
        outputs = [node for node in tree.nodes if node.type == 'OUTPUT_MATERIAL' and node.is_active_output]
        principled = next((node for node in tree.nodes if node.type == 'BSDF_PRINCIPLED'), None)
        if not outputs or principled is None:
            raise RuntimeError(f'Expected exportable Principled material: {material.name}')
        output = outputs[0]
        surface = output.inputs['Surface']
        original = surface.links[0].from_socket if surface.is_linked else None
        emission = tree.nodes.new('ShaderNodeEmission')
        color = principled.inputs[channel]
        if color.is_linked:
            tree.links.new(color.links[0].from_socket, emission.inputs['Color'])
        else:
            value = color.default_value
            emission.inputs['Color'].default_value = (value, value, value, 1) if isinstance(value, float) else value
        tree.links.new(emission.outputs[0], surface)
        restores.append((tree, output, original, emission))
    set_targets(materials, target)
    select_objects(objects)
    original_samples = bpy.context.scene.cycles.samples
    bpy.context.scene.cycles.samples = 1
    try:
        bpy.ops.object.bake(type='EMIT', uv_layer='Lightmap', use_clear=True,
                            margin=BAKE_MARGIN, margin_type='EXTEND')
    finally:
        bpy.context.scene.cycles.samples = original_samples
        for tree, output, original, emission in restores:
            tree.nodes.remove(emission)
            if original is not None:
                tree.links.new(original, output.inputs['Surface'])


def save_linear_exr(image, path):
    image.filepath_raw = str(path)
    image.file_format = 'OPEN_EXR'
    # Image.save() otherwise writes uncompressed float atlases.
    scene = bpy.context.scene
    settings = scene.render.image_settings
    original = (settings.file_format, settings.color_depth, settings.color_mode, settings.exr_codec)
    try:
        settings.file_format = 'OPEN_EXR'
        settings.color_depth = '32'
        settings.color_mode = 'RGBA'
        settings.exr_codec = 'ZIP'
        image.save_render(str(path), scene=scene)
    finally:
        settings.file_format, settings.color_depth, settings.color_mode, settings.exr_codec = original


def denoise_irradiance(objects, materials, irradiance, group, size):
    """OIDN filters lighting only; UV0 albedo and normal detail remain separate."""
    normal = create_target(f'NormalGuide_{group}', size)
    set_targets(materials, normal)
    select_objects(objects)
    bpy.ops.object.bake(type='NORMAL', normal_space='OBJECT', uv_layer='Lightmap',
                        use_clear=True, margin=BAKE_MARGIN, margin_type='EXTEND')
    values = np.empty(size * size * 4, dtype=np.float32)
    normal.pixels.foreach_get(values)
    values.reshape(-1, 4)[:, :3] = values.reshape(-1, 4)[:, :3] * 2 - 1
    normal.pixels.foreach_set(values)
    compositor = bpy.data.scenes.new(f'Denoise_{group}')
    camera_data = bpy.data.cameras.new('DenoiseCamera')
    camera = bpy.data.objects.new('DenoiseCamera', camera_data)
    compositor.collection.objects.link(camera)
    compositor.camera = camera
    compositor.render.engine = 'BLENDER_EEVEE_NEXT'
    compositor.render.resolution_x = compositor.render.resolution_y = size
    compositor.render.resolution_percentage = 100
    compositor.use_nodes = True
    tree = compositor.node_tree
    tree.nodes.clear()
    source = tree.nodes.new('CompositorNodeImage')
    source.image = irradiance
    guide = tree.nodes.new('CompositorNodeImage')
    guide.image = normal
    denoise = tree.nodes.new('CompositorNodeDenoise')
    denoise.prefilter = 'ACCURATE'
    denoise.use_hdr = True
    tree.links.new(source.outputs['Image'], denoise.inputs['Image'])
    tree.links.new(guide.outputs['Image'], denoise.inputs['Normal'])
    output = tree.nodes.new('CompositorNodeComposite')
    tree.links.new(denoise.outputs['Image'], output.inputs['Image'])
    compositor.view_settings.view_transform = 'Standard'
    compositor.render.image_settings.file_format = 'OPEN_EXR'
    compositor.render.image_settings.color_depth = '32'
    path = WORK / f'denoised-{group}.exr'
    compositor.render.filepath = str(path)
    filtered = None
    try:
        bpy.ops.render.render(scene=compositor.name, write_still=True)
        filtered = bpy.data.images.load(str(path), check_existing=False)
        filtered.pixels.foreach_get(values)
        if not np.isfinite(values).all():
            raise RuntimeError(f'Non-finite denoised irradiance: {group}')
        np.maximum(values, 0, out=values)
        irradiance.pixels.foreach_set(values)
    finally:
        if filtered is not None:
            bpy.data.images.remove(filtered)
        bpy.data.scenes.remove(compositor)
        bpy.data.objects.remove(camera, do_unlink=True)
        bpy.data.cameras.remove(camera_data)
        bpy.data.images.remove(normal)
        set_targets(materials, irradiance)


def stage_bake(args):
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    scene = set_render(args.width, args.samples)
    scene.cycles.use_denoising = False  # Cycles texture baking does not use the render denoiser.
    groups = defaultdict(list)
    for obj in meshes():
        group = atlas_group(obj)
        if group:
            groups[group].append(obj)
    if args.atlas:
        if args.atlas not in groups:
            raise RuntimeError(f'No geometry for atlas: {args.atlas}')
        groups = {args.atlas: groups[args.atlas]}
        selected_names = {obj.name for objects in groups.values() for obj in objects}
        receipt = [row for row in json.loads(scene.get('bake_receipt_json', '[]')) if row['id'] != args.atlas]
        for row in receipt:
            row['objects'] = [name for name in row['objects'] if name not in selected_names]
    else:
        receipt = []
    for group, objects in groups.items():
        started = time.perf_counter()
        # Dense curved upholstery and repeated plant leaves need room for chart gutters.
        size = args.resolution * 2 if group in ('textiles', 'garden') else args.resolution
        unwrap_atlas(objects, size)
        irradiance = create_target(f'Lightmap_{group}', size)
        materials = assign_bake_materials(objects, group, irradiance)
        select_objects(objects)
        log('bake-start', atlas=group, size=size, objects=len(objects), samples=args.samples)
        bpy.ops.object.bake(type='DIFFUSE', pass_filter={'DIRECT', 'INDIRECT'},
                            uv_layer='Lightmap', use_clear=True, margin=BAKE_MARGIN, margin_type='EXTEND')
        save_linear_exr(irradiance, WORK / f'raw-lightmap-{group}.exr')
        denoise_irradiance(objects, materials, irradiance, group, size)
        # Preserve the full static appearance for portable glTF. Runtime direct
        # sunlight is evaluated with moving cloth shadows, never baked twice.
        save_linear_exr(irradiance, WORK / f'full-lightmap-{group}.exr')
        albedo = create_target(f'Albedo_{group}', size)
        bake_albedo(objects, materials, albedo)
        light_pixels = np.empty(size * size * 4, dtype=np.float32)
        color_pixels = np.empty_like(light_pixels)
        irradiance.pixels.foreach_get(light_pixels)
        albedo.pixels.foreach_get(color_pixels)
        light_pixels = light_pixels.reshape(size, size, 4)
        color_pixels = color_pixels.reshape(size, size, 4)
        if not np.isfinite(light_pixels).all() or not np.isfinite(color_pixels).all():
            raise RuntimeError(f'Non-finite bake pixels: {group}')
        if light_pixels[..., :3].max() <= 0:
            raise RuntimeError(f'Empty irradiance bake: {group}')
        combined = color_pixels.copy()
        combined[..., :3] *= light_pixels[..., :3]
        combined[..., 3] = 1
        has_alpha = any(node.inputs['Alpha'].is_linked or node.inputs['Alpha'].default_value < 1
                        for material in materials for node in material.node_tree.nodes
                        if node.type == 'BSDF_PRINCIPLED')
        if has_alpha:
            alpha = create_target(f'Alpha_{group}', size)
            bake_albedo(objects, materials, alpha, channel='Alpha')
            alpha_pixels = np.empty(size * size * 4, dtype=np.float32)
            alpha.pixels.foreach_get(alpha_pixels)
            combined[..., 3] = np.clip(alpha_pixels.reshape(size, size, 4)[..., 0], 0, 1)
            bpy.data.images.remove(alpha)
        portable = create_target(f'PortableDiffuse_{group}', size)
        portable.pixels.foreach_set(combined.ravel())
        portable_path = ASSETS / f'portable-{group}.png'
        scene.render.image_settings.color_mode = 'RGBA'
        portable.save_render(str(portable_path), scene=scene)
        bpy.data.images.remove(portable)
        full_max, full_mean = float(light_pixels[..., :3].max()), float(light_pixels[..., :3].mean())
        sun_strengths = [(obj.data, obj.data.energy) for obj in scene.objects
                         if obj.type == 'LIGHT' and obj.data.type == 'SUN']
        set_targets(materials, irradiance)
        select_objects(objects)
        try:
            for light, _ in sun_strengths:
                light.energy = 0
            log('ambient-bake-start', atlas=group, size=size, samples=args.samples)
            bpy.ops.object.bake(type='DIFFUSE', pass_filter={'DIRECT', 'INDIRECT'},
                                uv_layer='Lightmap', use_clear=True, margin=BAKE_MARGIN, margin_type='EXTEND')
        finally:
            for light, energy in sun_strengths:
                light.energy = energy
        save_linear_exr(irradiance, WORK / f'raw-ambient-{group}.exr')
        denoise_irradiance(objects, materials, irradiance, group, size)
        save_linear_exr(irradiance, ASSETS / f'lightmap-{group}.exr')
        irradiance.pixels.foreach_get(light_pixels.ravel())
        if not np.isfinite(light_pixels).all() or light_pixels[..., :3].max() <= 0:
            raise RuntimeError(f'Invalid ambient irradiance bake: {group}')
        set_targets(materials, irradiance)
        bpy.data.images.remove(albedo)
        receipt.append({'id': group, 'url': f'/assets/interior/lightmap-{group}.exr',
                        'intensity': math.pi, 'size': size, 'objects': [obj.name for obj in objects],
                        'portableImage': f'/assets/interior/portable-{group}.png', 'linearRgbMax': float(light_pixels[..., :3].max()),
                        'linearRgbMean': float(light_pixels[..., :3].mean()),
                        'samples': args.samples, 'denoised': True,
                        'lightingModel': 'ambient-bake+shadowed-sun-v1',
                        'portableFullLightingMax': full_max, 'portableFullLightingMean': full_mean,
                        'denoiser': 'OpenImageDenoise HDR, accurate object-normal guide in UV1 atlas space',
                        'elapsedSeconds': round(time.perf_counter() - started, 3)})
        log('bake-complete', **{key: value for key, value in receipt[-1].items() if key != 'objects'})
    scene['bake_receipt_json'] = json.dumps(receipt)
    dirty = set(json.loads(scene.get('dirty_atlases_json', '[]'))) - set(groups)
    scene['dirty_atlases_json'] = json.dumps(sorted(dirty))
    scene['bake_lighting_model'] = 'ambient-bake+shadowed-sun-v1'
    scene.cycles.use_denoising = True
    scene.cycles.samples = 128
    scene.render.resolution_x, scene.render.resolution_y = CONTRACT['authoring']['sourceImageSize']
    save_master()
    (EVIDENCE / 'bake.json').write_text(json.dumps({'atlases': receipt, 'meshes': inventory()}, indent=2) + '\n')


def probe_pose():
    position = CONTRACT['authoring'].get('probePosition')
    if position is None:
        raise ValueError('Declare authoring.probePosition inside the authored room')
    return {'position': list(position), 'rotationEuler': [math.pi / 2, 0, -math.pi / 2]}


def require_current_probe(scene):
    pointer = CONTEXT.resolve('.img2/artifacts/interior/current-probe.json')
    path = ASSETS / 'room-environment.exr'
    if not pointer.is_file() or not path.is_file():
        raise RuntimeError('Run probe before export: current probe receipt or EXR is missing')
    receipt = json.loads(pointer.read_text())
    if (not scene.get('authoring_revision')
            or receipt.get('authoringRevision') != scene['authoring_revision']
            or receipt.get('pose') != probe_pose()
            or receipt.get('sha256') != hashlib.sha256(path.read_bytes()).hexdigest()):
        raise RuntimeError('Stale reflection probe: rerun probe for the current authoring revision and pose')
    return receipt


def stage_probe(args):
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    scene = set_render(args.width, args.samples, 'OPEN_EXR')
    if not scene.get('authoring_revision'):
        raise RuntimeError('Master lacks authoring revision; rerun draft before probe')
    pose = probe_pose()
    source_camera = scene.camera
    scene.render.resolution_y = max(1, args.width // 2)
    camera_data = bpy.data.cameras.new('IndoorReflectionProbe')
    camera_data.type = 'PANO'
    camera_data.panorama_type = 'EQUIRECTANGULAR'
    camera = bpy.data.objects.new('IndoorReflectionProbe', camera_data)
    scene.collection.objects.link(camera)
    camera.location = pose['position']
    camera.rotation_euler = pose['rotationEuler']
    scene.camera = camera
    path = ASSETS / 'room-environment.exr'
    scene.render.filepath = str(path)
    try:
        bpy.ops.render.render(write_still=True)
        receipt = {'authoringRevision': scene['authoring_revision'], 'pose': pose,
                   'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                   'path': str(path.relative_to(ROOT)), 'width': args.width,
                   'samples': args.samples, 'run': str(EVIDENCE.relative_to(ROOT))}
        with (EVIDENCE / 'probe.json').open('x') as stream:
            json.dump(receipt, stream, indent=2)
        pointer = CONTEXT.resolve('.img2/artifacts/interior/current-probe.json')
        pointer.write_text(json.dumps(receipt, indent=2))
    finally:
        scene.camera = source_camera
        bpy.data.objects.remove(camera, do_unlink=True)
        bpy.data.cameras.remove(camera_data)
    log('probe-complete', **receipt)


def three_point(point):
    return [point[0], point[2], -point[1]]


def export_gltf(path, *, tangents=False):
    """Export-only thin-pane, tangent-cap and weighted sheen corrections."""
    restores, sheen_restores, triangulations = [], [], []
    try:
        for material in bpy.data.materials:
            if not material.use_nodes:
                continue
            tree = material.node_tree
            if material.get('thin_pane_shadow_transmittance'):
                output = next(n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output)
                shader = next(n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED')
                original = output.inputs['Surface'].links[0].from_socket
                restores.append((tree, output, original))
                tree.links.new(shader.outputs['BSDF'], output.inputs['Surface'])
            for shader in tree.nodes:
                if shader.type != 'BSDF_PRINCIPLED':
                    continue
                weight, tint = shader.inputs['Sheen Weight'], shader.inputs['Sheen Tint']
                if weight.is_linked or tint.is_linked or weight.default_value in (0, 1):
                    continue
                original = tuple(tint.default_value)
                sheen_restores.append((tint, original))
                tint.default_value = (*[v * weight.default_value for v in original[:3]], original[3])
        if tangents:
            for obj in meshes():
                if any(len(face.vertices) > 4 for face in obj.data.polygons):
                    modifier = obj.modifiers.new('ExportTangentCaps', 'TRIANGULATE')
                    modifier.min_vertices = 5
                    modifier.keep_custom_normals = True
                    triangulations.append((obj, modifier))
        bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB', export_texcoords=True,
                                  export_normals=True, export_tangents=tangents, export_cameras=True, export_lights=False,
                                  export_extras=True, export_yup=True, export_apply=True,
                                  export_image_format='AUTO', export_keep_originals=False)
    finally:
        for obj, modifier in triangulations:
            obj.modifiers.remove(modifier)
        for tree, output, original in restores:
            tree.links.new(original, output.inputs['Surface'])
        for tint, original in sheen_restores:
            tint.default_value = original


def stage_export(args):
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    scene = bpy.context.scene
    require_current_probe(scene)
    camera = scene.camera
    if not camera or camera.type != 'CAMERA':
        raise RuntimeError('Packed master has no active reference camera')
    rows = inventory()
    receipt = json.loads(scene['bake_receipt_json'])
    if (scene.get('bake_lighting_model') != 'ambient-bake+shadowed-sun-v1'
            or any(row.get('lightingModel') != 'ambient-bake+shadowed-sun-v1' for row in receipt)):
        raise RuntimeError('Rebake every atlas: runtime sunlight must not be present in static irradiance')
    if json.loads(scene.get('dirty_atlases_json', '[]')):
        raise RuntimeError('Rebake dirty atlases after draft/material refresh before export')
    expected = {obj.name for obj in meshes() if atlas_group(obj)}
    baked = {name for row in receipt for name in row['objects']}
    if expected != baked:
        raise RuntimeError(f'Incomplete bake inventory; missing={sorted(expected-baked)}, obsolete={sorted(baked-expected)}')
    # Use material UV0 as render UV, preserving Lightmap in TEXCOORD_1.
    for obj in meshes():
        obj.data.uv_layers[0].active_render = True
        obj.data.uv_layers.active_index = 0
    summary = json.loads(scene['authoring_summary_json'])
    summary['views'] = CONTRACT['authoring']['inspectionViews']
    scene['interior_metadata'] = scene['authoring_summary_json'] = json.dumps(summary)
    authoring_path = EVIDENCE / 'authoring.json'
    authoring = {'builder': summary, 'meshes': rows}
    authoring['builder'] = summary
    authoring_path.write_text(json.dumps(authoring, indent=2) + '\n')
    save_master()
    # Export the packed native world's actual HDRI, not a manually copied old sky.
    outdoor_nodes = ([node for node in scene.world.node_tree.nodes if node.type == 'TEX_ENVIRONMENT']
                     if scene.world and scene.world.use_nodes else [])
    if len(outdoor_nodes) > 1:
        raise RuntimeError('Only one world HDRI is supported for runtime background export')
    background_url = CONTRACT['runtime'].get('background')
    if background_url:
        if len(outdoor_nodes) != 1 or not outdoor_nodes[0].image or not outdoor_nodes[0].image.packed_file:
            raise RuntimeError('Configured background requires one actual packed world HDRI')
        background_path = CONTEXT.resolve('public/' + background_url.lstrip('/'))
        background_path.parent.mkdir(parents=True, exist_ok=True)
        background_path.write_bytes(outdoor_nodes[0].image.packed_file.data)
    runtime = ASSETS / 'room-runtime.glb'
    export_gltf(runtime, tangents=True)
    source_position = list(camera.location)
    forward = camera.matrix_world.to_quaternion() @ Vector((0, 0, -1))
    source_target = camera.location + forward * 6
    aspect = CONTRACT['authoring']['sourceImageSize'][0] / CONTRACT['authoring']['sourceImageSize'][1]
    vertical_fov = math.degrees(2 * math.atan(camera.data.sensor_width / (2 * camera.data.lens * aspect)))
    suns = [obj for obj in scene.objects if obj.type == 'LIGHT' and obj.data.type == 'SUN']
    if len(suns) > 1:
        raise RuntimeError('Runtime supports at most one SUN; consolidate authored sunlight')
    sunlight = suns[0] if suns else None
    sun_forward = sunlight.matrix_world.to_quaternion() @ Vector((0, 0, -1)) if sunlight else None
    transmission = CONTRACT['runtime'].get('glassTransmission', 1.0)
    room = summary['roomBounds']
    manifest = {
        'schemaVersion': 2, 'title': CONTRACT['title'],
        'sourceImage': '/' + str(Path(CONTRACT['source']).relative_to('public')),
        'sourceImageSize': CONTRACT['authoring']['sourceImageSize'],
        'sourceAspect': aspect, 'sourceKind': CONTRACT['sourceKind'],
        'model': '/assets/interior/room-runtime.glb',
        'portableModel': '/assets/interior/room-portable.glb',
        'blender': '/assets/interior/room-master.blend',
        'environment': '/assets/interior/room-environment.exr',
        'background': background_url,
        'backgroundIntensity': CONTRACT['runtime'].get('backgroundIntensity', 1),
        'camera': {'position': three_point(source_position), 'target': three_point(source_target), 'fov': vertical_fov},
        'roomBounds': {'min': [room['min'][0], room['min'][2], -room['max'][1]],
                       'max': [room['max'][0], room['max'][2], -room['min'][1]]},
        'lighting': {'model': 'ambient-bake+shadowed-sun-v1',
                     'sun': {'position': three_point(sunlight.location),
                             'target': three_point(sunlight.location+sun_forward*10),
                             'color': list(sunlight.data.color),
                             'intensity': sunlight.data.energy * transmission,
                             'glassTransmission': transmission,
                             'shadowMapSize': 2048} if sunlight else None},
        'views': {name: {'position': three_point(pose['position']), 'target': three_point(pose['target'])}
                  for name, pose in CONTRACT['authoring']['inspectionViews'].items()},
        'lightmaps': [{key: row[key] for key in ('id', 'url', 'intensity')} for row in receipt],
        'variants': CONTRACT['runtime'].get('variants', []),
        'toneMapping': 'neutral', 'exposure': 1,
        'stats': {'meshes': len(rows), 'triangles': sum(row['triangles'] for row in rows),
                  'components': len(set(row['component'] for row in rows)),
                  'lightmapAtlases': len(receipt)},
        'portability': CONTRACT['portability'],
        'sourceLimit': CONTRACT['sourceViewLimit'],
    }
    if CONTRACT['runtime'].get('finishTarget'):
        manifest['finishTarget'] = CONTRACT['runtime']['finishTarget']
    resource_path = CONTRACT['authoring'].get('resourceManifest')
    if resource_path:
        resources = json.loads(CONTEXT.resolve(resource_path).read_text())
        if resources.get('provider') == 'Poly Haven':
            manifest['resourceCredit'] = {'provider': 'Poly Haven', 'apiDerived': True, 'credit': 'Powered by Poly Haven'}
    # A separate explicitly static appearance export; do not pretend native glTF has a lightMap slot.
    portable_materials = {}
    portable_textures = {
        row['id']: bpy.data.images.load(str(ROOT / 'public' / row['portableImage'].lstrip('/')), check_existing=False)
        for row in receipt
    }
    for image in portable_textures.values():
        image.colorspace_settings.name = 'sRGB'
    original_slots = [(slot, slot.material) for obj in meshes() for slot in obj.material_slots]
    portable_path = ASSETS / 'room-portable.glb'
    try:
        for obj in meshes():
            group = obj.get('lightmap')
            if not group:
                continue
            for slot in obj.material_slots:
                key = (slot.material.as_pointer(), group)
                if key not in portable_materials:
                    material = bpy.data.materials.new(f'Baked_{slot.material.name}')
                    material.use_nodes = True
                    tree = material.node_tree
                    tree.nodes.clear()
                    output = tree.nodes.new('ShaderNodeOutputMaterial')
                    background = tree.nodes.new('ShaderNodeBackground')
                    texture = tree.nodes.new('ShaderNodeTexImage')
                    texture.image = portable_textures[group]
                    uv = tree.nodes.new('ShaderNodeUVMap')
                    uv.uv_map = 'Lightmap'
                    tree.links.new(uv.outputs['UV'], texture.inputs['Vector'])
                    tree.links.new(texture.outputs['Color'], background.inputs['Color'])
                    tree.links.new(background.outputs[0], output.inputs['Surface'])
                    principled = next((node for node in slot.material.node_tree.nodes if node.type == 'BSDF_PRINCIPLED'), None)
                    if principled and (principled.inputs['Alpha'].is_linked or principled.inputs['Alpha'].default_value < 1):
                        transparent = tree.nodes.new('ShaderNodeBsdfTransparent')
                        coverage = tree.nodes.new('ShaderNodeMixShader')
                        tree.links.new(texture.outputs['Alpha'], coverage.inputs[0])
                        tree.links.new(transparent.outputs[0], coverage.inputs[1])
                        tree.links.new(background.outputs[0], coverage.inputs[2])
                        tree.links.new(coverage.outputs[0], output.inputs['Surface'])
                        material.surface_render_method = slot.material.surface_render_method
                    portable_materials[key] = material
                slot.material = portable_materials[key]
        export_gltf(portable_path)
    finally:
        for slot, material in original_slots:
            slot.material = material
    (ASSETS / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    output = {'manifest': manifest, 'runtimeBytes': runtime.stat().st_size,
              'runtimeSha256': hashlib.sha256(runtime.read_bytes()).hexdigest(),
              'portableBytes': portable_path.stat().st_size,
              'portableSha256': hashlib.sha256(portable_path.read_bytes()).hexdigest(),
              'masterBytes': MASTER.stat().st_size}
    (EVIDENCE / 'exports.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    log('export-complete', runtimeBytes=output['runtimeBytes'], portableBytes=output['portableBytes'])


def stage_render(args):
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    scene = set_render(args.width, args.samples)
    if args.view != 'source':
        pose = CONTRACT['authoring']['inspectionViews'][args.view]
        scene.camera.location = pose['position']
        look_at(scene.camera, pose['target'])
    scene.render.filepath = str(EVIDENCE / f'blender-{args.view}.png')
    bpy.ops.render.render(write_still=True)
    log('render-complete', view=args.view, output=str(Path(scene.render.filepath).relative_to(ROOT)))


