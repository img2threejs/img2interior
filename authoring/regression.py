# SPDX-License-Identifier: Apache-2.0
"""Real Blender export regressions. These measurements are not visual-quality scores."""
from pathlib import Path
from types import SimpleNamespace
import json
import tempfile


def png(path, color):
    import bpy
    image = bpy.data.images.new('RegressionPixels', 2, 2, alpha=True)
    image.colorspace_settings.name = 'Non-Color'
    image.pixels[:] = color * 4
    image.filepath_raw = str(path)
    image.file_format = 'PNG'
    image.save()
    bpy.data.images.remove(image)


def material_regression(context, args):
    import bpy
    from authoring import Context, bound_module
    with tempfile.TemporaryDirectory(prefix='material-', dir=context.evidence) as temporary:
        root = Path(temporary)
        assets = root / 'public/assets/interior'
        assets.mkdir(parents=True)
        local = Context(root, context.spec, assets, root)
        pipeline = bound_module('pipeline', local)
        inspection = bound_module('inspection', local)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        path = root / 'color.png'
        png(path, [.25, .20, .18, 1])
        material = local.helpers.material('PackedCloth', (1,1,1), maps={'color':'color.png'})
        obj = local.helpers.box('cloth', (0,0,0), (1,0.2,1), material, 'curtains')
        shader = next(n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        shader.inputs['Sheen Weight'].default_value = .12
        shader.inputs['Sheen Tint'].default_value = (.8,.5,.25,1)
        original_tint = tuple(shader.inputs['Sheen Tint'].default_value)
        before_uv = [list(v.uv) for v in obj.data.uv_layers['UV0'].data]
        pipeline.save_master()
        png(path, [.75,.65,.5,1])
        fresh = bpy.data.images.load(str(path), check_existing=False)
        expected = list(fresh.pixels[:])
        bpy.data.images.remove(fresh)
        pipeline.stage_refresh_material(SimpleNamespace(image=['color.png']))
        path.unlink()
        bpy.ops.wm.open_mainfile(filepath=str(pipeline.MASTER))
        obj = bpy.context.scene.objects['cloth']
        shader = next(n for n in obj.active_material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        image = shader.inputs['Base Color'].links[0].from_node.image
        error = max(abs(a-b) for a,b in zip(image.pixels[:], expected))
        if not image.packed_file or error > 1e-6:
            raise RuntimeError(f'Packed pixels stale after external map removal: {error}')
        if before_uv != [list(v.uv) for v in obj.data.uv_layers['UV0'].data]:
            raise RuntimeError('Refresh changed UV0')
        path = context.evidence / 'weighted-sheen.glb'
        pipeline.export_gltf(path, tangents=True)
        document = inspection.glb_json(path)
        actual = document['materials'][0]['extensions']['KHR_materials_sheen']['sheenColorFactor']
        expected_sheen = [v*.12 for v in original_tint[:3]]
        if max(abs(a-b) for a,b in zip(actual, expected_sheen)) > 1e-6:
            raise RuntimeError(f'Weighted sheen not exported: {actual}')
        if tuple(shader.inputs['Sheen Tint'].default_value) != original_tint:
            raise RuntimeError('Successful export mutated native sheen')
        # Exercise failure restoration too, without replacing exporter or mocking bpy.
        blocked = root / 'not-a-directory'
        blocked.write_text('block actual filesystem export')
        try:
            pipeline.export_gltf(blocked / 'failure.glb', tangents=True)
        except Exception:
            pass
        else:
            raise RuntimeError('Expected actual export failure beneath a regular file')
        if tuple(shader.inputs['Sheen Tint'].default_value) != original_tint:
            raise RuntimeError('Failed export mutated native sheen')
        # Material policies address exported identities. Repeating a bake must
        # preserve those identities and artist edits, not grow suffixes/copies.
        pipeline.unwrap_atlas([obj], 64)
        identities = []
        for generation in ('first', 'repeat'):
            target = pipeline.create_target('RepeatBakeTarget', 64)
            pipeline.assign_bake_materials([obj], 'textiles', target)
            current_shader = next(n for n in obj.active_material.node_tree.nodes
                                  if n.type == 'BSDF_PRINCIPLED')
            if generation == 'first':
                current_shader.inputs['Roughness'].default_value = .72
            exported = context.evidence / f'rebake-{generation}.glb'
            pipeline.export_gltf(exported, tangents=True)
            emitted = inspection.glb_json(exported)['materials']
            identities.append([entry['name'] for entry in emitted])
            roughness = emitted[0]['pbrMetallicRoughness']['roughnessFactor']
            if abs(roughness - .72) > 1e-6:
                raise RuntimeError(f'Repeated bake lost edited roughness: {roughness}')
        if identities[0] != identities[1]:
            raise RuntimeError(f'Repeated bake changed exported material identity: {identities}')
        if before_uv != [list(v.uv) for v in obj.data.uv_layers['UV0'].data]:
            raise RuntimeError('Repeated bake preparation changed UV0')
        result = {'packedAlbedoPixelError':error, 'externalMapRemovedBeforeReopen':True,
                  'uv0Preserved':True, 'expectedGltfSheen':expected_sheen, 'actualGltfSheen':actual,
                  'nativeSheenRestoredAfterSuccessAndFailure':True,
                  'rebake': {'firstMaterialNames':identities[0], 'repeatMaterialNames':identities[1],
                             'editedRoughnessFactor':roughness}}
        (context.evidence / 'material-regression.json').write_text(json.dumps(result, indent=2))
        return result


def calibrate(context, args):
    """Render an asymmetric UV1 chart before/after actual GLB transport.

    UV0 is deliberately reversed. A texCoord=0 regression therefore produces a
    different image. Non-square offset geometry catches coordinate/root mistakes.
    All calibration assets are evidence-only; the production master is untouched.
    """
    import bpy
    import numpy as np
    from mathutils import Vector
    from authoring import bound_module
    pipeline = bound_module('pipeline', context)
    inspection = bound_module('inspection', context)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    h = context.helpers
    material = h.material('Calibration.UV1', (1,1,1))
    tree = material.node_tree
    tree.nodes.clear()
    output = tree.nodes.new('ShaderNodeOutputMaterial')
    emission = tree.nodes.new('ShaderNodeBackground')
    texture = tree.nodes.new('ShaderNodeTexImage')
    texture.interpolation = 'Closest'
    image = bpy.data.images.new('AsymmetricUV1Chart', width=4, height=3, alpha=True)
    image.colorspace_settings.name = 'Non-Color'
    colors = [(1,0,0),(0,1,0),(0,0,1),(1,1,0), (.1,.3,.6),(.8,.2,.1),(.2,.7,.5),(.7,.1,.8),
              (0,1,1),(1,0,1),(.25,.5,.75),(.9,.6,.2)]
    image.pixels[:] = [channel for color in colors for channel in (*color,1)]
    image.filepath_raw = str(context.evidence / 'uv1-chart.png')
    image.file_format = 'PNG'
    image.save()
    bpy.data.images.remove(image)
    image = bpy.data.images.load(str(context.evidence / 'uv1-chart.png'), check_existing=False)
    image.colorspace_settings.name = 'sRGB'
    texture.image = image
    uv = tree.nodes.new('ShaderNodeUVMap')
    uv.uv_map = 'Lightmap'
    tree.links.new(uv.outputs['UV'], texture.inputs['Vector'])
    tree.links.new(texture.outputs['Color'], emission.inputs['Color'])
    tree.links.new(emission.outputs[0], output.inputs['Surface'])
    obj = h.mesh('calibration.chart', [(-.7,.3,.2),(1.3,.3,.2),(1.3,.3,1.7),(-.7,.3,1.7)],
                 [(0,1,2,3)], material, 'calibration')
    layer = obj.data.uv_layers.new(name='Lightmap')
    values = [(0,0),(1,0),(1,1),(0,1)]
    for corner, value in zip(layer.data, values):
        corner.uv = value
    for corner, value in zip(obj.data.uv_layers['UV0'].data, values):
        corner.uv = (1-value[0], 1-value[1])
    obj.data.uv_layers[0].active_render = True
    obj.data.uv_layers.active_index = 0
    bpy.context.view_layer.update()
    before_bounds = h.bounds([obj])
    data = bpy.data.cameras.new('CalibrationCamera')
    camera = bpy.data.objects.new('CalibrationCamera', data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = (.3,-3,.95)
    camera.rotation_euler = (Vector((.3,.3,.95))-camera.location).to_track_quat('-Z','Y').to_euler()
    data.type = 'ORTHO'
    data.ortho_scale = 2.4
    bpy.context.scene.camera = camera

    def render(label):
        scene = bpy.context.scene
        scene.render.engine = 'CYCLES'
        scene.cycles.samples = args.samples
        scene.cycles.use_denoising = False
        scene.render.resolution_x = args.width
        scene.render.resolution_y = max(1, round(args.width * .75))
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = 'PNG'
        scene.render.image_settings.color_mode = 'RGBA'
        scene.view_settings.view_transform = 'Standard'
        scene.view_settings.look = 'None'
        scene.view_settings.exposure = 0
        scene.view_settings.gamma = 1
        path = context.evidence / f'calibration-{label}.png'
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        loaded = bpy.data.images.load(str(path), check_existing=False)
        pixels = np.array(loaded.pixels[:], dtype=np.float32)
        bpy.data.images.remove(loaded)
        return pixels

    before = render('native')
    glb = context.evidence / 'calibration.glb'
    pipeline.export_gltf(glb)
    document = inspection.glb_json(glb)
    coordinate = document['materials'][0]['pbrMetallicRoughness']['baseColorTexture'].get('texCoord',0)
    if coordinate != 1:
        raise RuntimeError(f'Calibration exported UV{coordinate}, expected UV1')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    scene = bpy.context.scene
    scene.camera = next(o for o in scene.objects if o.type == 'CAMERA')
    objects = [o for o in scene.objects if o.type == 'MESH']
    bpy.context.view_layer.update()
    after_bounds = h.bounds(objects)
    coordinate_error = float(np.max(np.abs(np.array(before_bounds)-np.array(after_bounds))))
    after = render('reimport')
    difference = np.abs(before-after)
    # Antialiasing at transported primitive edges may vary by a pixel; compare mean
    # and record max, never erase/rewrite a mismatch to manufacture a passing image.
    mean_error = float(difference.mean())
    if coordinate_error > 1e-5 or mean_error > .01:
        raise RuntimeError(f'Calibration transport mismatch: bounds={coordinate_error}, mean pixels={mean_error}')
    result = {'texCoord':coordinate, 'nativeBounds':before_bounds, 'reimportBounds':after_bounds,
              'gltfYUpBounds': {'min':[-.7,.2,-.3], 'max':[1.3,1.7,-.3]},
              'coordinateRoundTripMaxError':coordinate_error,
              'decodedPixelMeanError':mean_error, 'decodedPixelMaxError':float(difference.max()),
              'limit':'UV/color/coordinate transport regression only, not visual realism or reference fidelity'}
    result['probeAxes'] = probe_axes(context, args)
    from authoring.calibration import runtime_fixture
    result['runtimeLightmap'] = runtime_fixture(context, args)
    (context.evidence / 'calibration.json').write_text(json.dumps(result, indent=2))
    return result


def probe_axes(context, args):
    """Measure actual equirectangular export against Three's cardinal UV convention."""
    import math
    import bpy
    import numpy as np
    bpy.ops.wm.read_factory_settings(use_empty=True)
    h = context.helpers
    fixtures = [
        ('positiveX', (2,0,0), (.05,4,4), (1,0,0), .5),
        ('positiveZ', (0,-2,0), (4,.05,4), (0,1,0), .75),
        ('negativeX', (-2,0,0), (.05,4,4), (0,0,1), 0.0),
        ('negativeZ', (0,2,0), (4,.05,4), (1,1,0), .25),
    ]
    for name, position, size, color, u in fixtures:
        material = h.material('Axis.'+name, color)
        tree = material.node_tree
        tree.nodes.clear()
        emission = tree.nodes.new('ShaderNodeEmission')
        emission.inputs['Color'].default_value = (*color,1)
        output = tree.nodes.new('ShaderNodeOutputMaterial')
        tree.links.new(emission.outputs[0], output.inputs['Surface'])
        h.box(name, position, size, material, 'calibration')
    data = bpy.data.cameras.new('AxisProbe')
    data.type = 'PANO'
    data.panorama_type = 'EQUIRECTANGULAR'
    camera = bpy.data.objects.new('AxisProbe', data)
    scene = bpy.context.scene
    scene.collection.objects.link(camera)
    camera.rotation_euler = (math.pi/2, 0, -math.pi/2)
    scene.camera = camera
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = False
    scene.render.resolution_x, scene.render.resolution_y = 256, 128
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'OPEN_EXR'
    scene.render.image_settings.color_depth = '32'
    scene.render.image_settings.color_mode = 'RGBA'
    path = context.evidence / 'calibration-probe.exr'
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    image = bpy.data.images.load(str(path), check_existing=False)
    pixels = np.array(image.pixels[:], dtype=np.float32).reshape(128,256,4)
    readings = {}
    for name, position, size, color, u in fixtures:
        actual = pixels[64, int(u*256), :3]
        error = float(np.max(np.abs(actual-np.array(color))))
        if error > .001:
            raise RuntimeError(f'Probe coordinate mismatch at {name}, u={u}: {actual.tolist()}')
        readings[name] = {'u':u, 'rgb':actual.tolist(), 'maxError':error}
    bpy.data.images.remove(image)
    return readings
