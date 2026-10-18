"""Reopen the authored master or import the portable GLB and render it as a consumer.

Run with the project's bpy Python. Portable colors already contain the Neutral
view transform, so its independent render uses Standard rather than applying
Neutral twice. A neutral world is authored for the portable inspection; glTF
has no embedded environment-light/background contract.
"""
from argparse import ArgumentParser
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import time

import bpy
import bmesh
import numpy as np



def glb_json(path):
    with path.open('rb') as stream:
        magic, version, size = struct.unpack('<4sII', stream.read(12))
        if magic != b'glTF' or version != 2 or size != path.stat().st_size:
            raise RuntimeError(f'Invalid GLB header: {path.name}')
        length, kind = struct.unpack('<I4s', stream.read(8))
        if kind != b'JSON':
            raise RuntimeError(f'Missing GLB JSON chunk: {path.name}')
        return json.loads(stream.read(length))


def component_of(obj):
    while obj is not None:
        if obj.get('component'):
            return obj['component']
        obj = obj.parent
    return None


def audit(scene):
    rows = []
    for obj in scene.objects:
        if obj.type != 'MESH':
            continue
        component = component_of(obj)
        if not component or not obj.data.uv_layers:
            raise RuntimeError(f'Missing component or UVs: {obj.name}')
        if obj.get('lightmap') and len(obj.data.uv_layers) != 2:
            raise RuntimeError(f'Baked surface does not have exactly UV0 and UV1: {obj.name}')
        coordinates = np.empty(len(obj.data.vertices)*3, dtype=np.float32)
        obj.data.vertices.foreach_get('co', coordinates)
        if not np.isfinite(coordinates).all():
            raise RuntimeError(f'Non-finite positions: {obj.name}')
        for layer in obj.data.uv_layers:
            uv = np.empty(len(layer.data)*2, dtype=np.float32)
            layer.data.foreach_get('uv', uv)
            if not np.isfinite(uv).all():
                raise RuntimeError(f'Non-finite UV coordinates: {obj.name}:{layer.name}')
        obj.data.calc_loop_triangles()
        row = {'name': obj.name, 'component': component, 'vertices': len(obj.data.vertices),
               'triangles': len(obj.data.loop_triangles), 'uvLayers': [layer.name for layer in obj.data.uv_layers]}
        if component == 'sofa':
            # Weld UV/normal export seams on an audit-only copy; never mutate the asset.
            mesh = bmesh.new()
            mesh.from_mesh(obj.data)
            bmesh.ops.remove_doubles(mesh, verts=list(mesh.verts), dist=1e-6)
            row['boundaryEdgesAfterWelding'] = sum(edge.is_boundary for edge in mesh.edges)
            row['nonManifoldEdgesAfterWelding'] = sum(not edge.is_manifold for edge in mesh.edges)
            mesh.free()
            if row['nonManifoldEdgesAfterWelding']:
                raise RuntimeError(f'Open or non-manifold authored sofa component: {obj.name}')
        rows.append(row)
    if not rows:
        raise RuntimeError('No imported scene geometry')
    return rows


def run(args):
    started = time.perf_counter()
    asset = ASSETS / ('room-master.blend' if args.asset == 'master' else 'room-portable.glb')
    extension_summary = None
    if args.asset == 'master':
        bpy.ops.wm.open_mainfile(filepath=str(asset))
        missing = [image.name for image in bpy.data.images
                   if image.source in {'FILE', 'TILED'} and not image.packed_file and not image.packed_files]
        if missing:
            raise RuntimeError(f'Unpacked master images: {missing}')
    else:
        document = glb_json(asset)
        extension_summary = {'used': document.get('extensionsUsed', []),
                             'unlitMaterials': sum('KHR_materials_unlit' in material.get('extensions', {})
                                                   for material in document.get('materials', [])),
                             'materials': len(document.get('materials', [])),
                             'embeddedImages': len(document.get('images', []))}
        if not extension_summary['unlitMaterials'] or any('uri' in image for image in document.get('images', [])):
            raise RuntimeError('Portable GLB lacks embedded static unlit appearance')
        if any('uri' in buffer for buffer in document.get('buffers', [])):
            raise RuntimeError('Portable GLB has external buffers')
        unlit_coordinates = {
            material.get('pbrMetallicRoughness', {}).get('baseColorTexture', {}).get('texCoord', 0)
            for material in document.get('materials', [])
            if 'KHR_materials_unlit' in material.get('extensions', {})
        }
        if unlit_coordinates != {1}:
            raise RuntimeError(f'Portable appearance does not sample the baked UV1 atlas: {unlit_coordinates}')
        extension_summary['unlitTextureCoordinates'] = sorted(unlit_coordinates)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(asset))
        world = bpy.data.worlds.new('PortableInspection.NeutralWorld')
        world.use_nodes = True
        world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.35, 0.35, 0.35, 1)
        world.node_tree.nodes['Background'].inputs['Strength'].default_value = 1
        bpy.context.scene.world = world
    scene = bpy.context.scene
    cameras = [obj for obj in scene.objects if obj.type == 'CAMERA']
    if not cameras:
        raise RuntimeError('Export lost its authored camera')
    scene.camera = scene.camera or cameras[0]
    rows = audit(scene)
    scene.render.engine = 'CYCLES'
    from mathutils import Vector
    pose = (CONTRACT['authoring']['cameraEstimate'] if args.view == 'source'
            else CONTRACT['authoring']['inspectionViews'][args.view])
    scene.camera.rotation_mode = 'XYZ'
    scene.camera.location = pose['position']
    scene.camera.rotation_euler = (Vector(pose['target']) - scene.camera.location).to_track_quat('-Z', 'Y').to_euler()
    scene.cycles.device = 'CPU'
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.cycles.seed = 17
    scene.render.resolution_x = args.width
    w, h = CONTRACT['authoring']['sourceImageSize']
    scene.render.resolution_y = max(1, round(args.width * h / w))
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.view_settings.view_transform = 'Khronos PBR Neutral' if args.asset == 'master' else 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    output = EVIDENCE / f'reimport-{args.asset}-{args.view}.png'
    scene.render.filepath = str(output)
    bpy.ops.render.render(write_still=True)
    with asset.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    receipt = {'asset': str(asset.relative_to(ROOT)), 'sha256': digest,
               'bytes': asset.stat().st_size, 'blenderVersion': bpy.app.version_string,
               'objects': len(rows), 'triangles': sum(row['triangles'] for row in rows),
               'components': dict(Counter(row['component'] for row in rows)),
               'extensionSummary': extension_summary, 'meshes': rows,
               'materials': [{'name': m.name, 'nodes': [n.type for n in m.node_tree.nodes] if m.use_nodes else []}
                             for m in bpy.data.materials],
               'images': [{'name': i.name, 'packed': bool(i.packed_file or i.packed_files),
                           'size': list(i.size)} for i in bpy.data.images if i.type != 'RENDER_RESULT'],
               'viewTransform': scene.view_settings.view_transform, 'samples': args.samples,
               'portableWorld': 'Independent neutral world; source HDRI/background not embedded' if args.asset == 'portable' else None,
               'render': str(output.relative_to(ROOT)), 'elapsedSeconds': round(time.perf_counter()-started, 3)}
    (EVIDENCE / f'reimport-{args.asset}-{args.view}.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({key: value for key, value in receipt.items() if key != 'meshes'}), flush=True)


