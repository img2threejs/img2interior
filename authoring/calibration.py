"""Evidence-only runtime fixture for EXR row orientation, rotated UV1 and PI transport.

The Cycles reference evaluates the known Lambertian outgoing radiance albedo*field.
The runtime GLB instead contains only a zero-specular PBR material; the actual
viewer must reconstruct that radiance from its EXR lightmap at intensity PI.
No browser comparison or realism approval is asserted by generating this fixture.
"""
import hashlib
import json
import math
from pathlib import Path


def runtime_fixture(context, args):
    import bpy
    import numpy as np
    from mathutils import Vector
    from authoring import Context, bound_module

    child = context.evidence / 'calibration-viewer'
    assets = child / 'public/assets/interior'
    assets.mkdir(parents=True, exist_ok=False)
    local = Context(child, context.spec, assets, child)
    pipeline = bound_module('pipeline', local)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    h = local.helpers
    width = max(64, args.width)
    height = max(1, round(width * 3 / 4))
    aspect = width / height
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = False
    scene.cycles.seed = 17
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.view_settings.view_transform = 'Khronos PBR Neutral'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene.render.film_transparent = False
    world = bpy.data.worlds.new('Calibration.BlackWorld')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0,0,0,1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0
    scene.world = world

    # Bottom-up Blender image rows; asymmetric continuous field plus a distinct
    # upper-left region means row flips, rotations and PI errors cannot cancel.
    nx, ny = 32, 16
    field = np.empty((ny,nx,4), dtype=np.float32)
    for y in range(ny):
        for x in range(nx):
            u, v = x/(nx-1), y/(ny-1)
            field[y,x] = (.12 + .9*u, .08 + .7*v,
                          .15 + (.8 if x < 9 and y > 10 else .15*u*v), 1)
    atlas = pipeline.create_target('RuntimeCalibrationField', nx)
    atlas.scale(nx, ny)
    atlas.pixels.foreach_set(field.ravel())
    exr = assets / 'lightmap-calibration.exr'
    pipeline.save_linear_exr(atlas, exr)
    decoded = bpy.data.images.load(str(exr), check_existing=False)
    actual = np.asarray(decoded.pixels[:], dtype=np.float32).reshape(ny,nx,4)
    exr_error = float(np.max(np.abs(actual-field)))
    if exr_error > 1e-6:
        raise RuntimeError(f'Lossless EXR field changed decoded linear pixels: {exr_error}')
    bpy.data.images.remove(atlas)
    atlas = decoded
    atlas.colorspace_settings.name = 'Linear Rec.709'
    black = bpy.data.images.new('BlackProbe', width=32, height=16, alpha=True, float_buffer=True)
    black.colorspace_settings.name = 'Linear Rec.709'
    black.pixels[:] = [0,0,0,1] * (32*16)
    pipeline.save_linear_exr(black, assets / 'room-environment.exr')

    albedo = (.63,.42,.27)
    material = h.material('Calibration.PBR', albedo, roughness=1.0)
    shader = next(n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    shader.inputs['Specular IOR Level'].default_value = 0
    shader.inputs['Metallic'].default_value = 0
    shader.inputs['Sheen Weight'].default_value = 0
    obj = h.mesh('calibration.rotated-uv1', [(-1.2,0,.3),(1.2,0,.3),(1.2,0,2.1),(-1.2,0,2.1)],
                 [(0,1,2,3)], material, 'calibration')
    obj['lightmap'] = 'calibration'
    uv0 = [(0,0),(1,0),(1,1),(0,1)]
    uv1 = [(v,1-u) for u,v in uv0]
    for corner, value in zip(obj.data.uv_layers['UV0'].data, uv0):
        corner.uv = value
    layer = obj.data.uv_layers.new(name='Lightmap')
    for corner, value in zip(layer.data, uv1):
        corner.uv = value
    obj.data.uv_layers[0].active_render = True
    obj.data.uv_layers.active_index = 0
    data = bpy.data.cameras.new('Calibration.PerspectiveCamera')
    data.type = 'PERSP'
    data.lens, data.sensor_width = 35, 36
    data.sensor_fit = 'HORIZONTAL'
    data.clip_start, data.clip_end = .03, 100
    camera = bpy.data.objects.new('Calibration.PerspectiveCamera', data)
    scene.collection.objects.link(camera)
    camera.location = (0,-3,1.2)
    target = Vector((0,0,1.2))
    camera.rotation_euler = (target-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.camera = camera
    bpy.context.view_layer.update()
    pipeline.export_gltf(assets / 'room-runtime.glb', tangents=True)

    # Cycles expected radiance, independent of the runtime's lightMap machinery.
    expected_material = bpy.data.materials.new('Calibration.ExpectedLambertianRadiance')
    expected_material.use_nodes = True
    tree = expected_material.node_tree
    tree.nodes.clear()
    output = tree.nodes.new('ShaderNodeOutputMaterial')
    emission = tree.nodes.new('ShaderNodeEmission')
    multiply = tree.nodes.new('ShaderNodeMixRGB')
    multiply.blend_type = 'MULTIPLY'
    multiply.inputs[0].default_value = 1
    multiply.inputs[2].default_value = (*albedo,1)
    texture = tree.nodes.new('ShaderNodeTexImage')
    texture.image = atlas
    texture.interpolation = 'Linear'
    texture.extension = 'EXTEND'
    uv = tree.nodes.new('ShaderNodeUVMap')
    uv.uv_map = 'Lightmap'
    tree.links.new(uv.outputs['UV'], texture.inputs['Vector'])
    tree.links.new(texture.outputs['Color'], multiply.inputs[1])
    tree.links.new(multiply.outputs['Color'], emission.inputs['Color'])
    tree.links.new(emission.outputs[0], output.inputs['Surface'])
    obj.data.materials[0] = expected_material
    expected = context.evidence / 'calibration-runtime-expected.png'
    scene.render.filepath = str(expected)
    bpy.ops.render.render(write_still=True)
    # The child source is the actual rendered calibration image, never a substitute
    # reference photograph. Main may register it with interior_project start.
    (child / 'public/assets/reference.png').write_bytes(expected.read_bytes())
    pipeline.save_master()

    # Genuine portable static appearance, with Neutral applied once to its pixels.
    portable_pixels = field.copy()
    portable_pixels[...,:3] *= np.asarray(albedo, dtype=np.float32)
    portable_image = bpy.data.images.new('Calibration.Portable', width=nx, height=ny, alpha=True, float_buffer=True)
    portable_image.colorspace_settings.name = 'Linear Rec.709'
    portable_image.pixels.foreach_set(portable_pixels.ravel())
    portable_path = assets / 'portable-calibration.png'
    portable_image.save_render(str(portable_path), scene=scene)
    bpy.data.images.remove(portable_image)
    portable_image = bpy.data.images.load(str(portable_path), check_existing=False)
    portable_image.colorspace_settings.name = 'sRGB'
    portable_material = bpy.data.materials.new('Calibration.PortableUnlit')
    portable_material.use_nodes = True
    tree = portable_material.node_tree
    tree.nodes.clear()
    output = tree.nodes.new('ShaderNodeOutputMaterial')
    background = tree.nodes.new('ShaderNodeBackground')
    texture = tree.nodes.new('ShaderNodeTexImage')
    texture.image = portable_image
    uv = tree.nodes.new('ShaderNodeUVMap')
    uv.uv_map = 'Lightmap'
    tree.links.new(uv.outputs['UV'], texture.inputs['Vector'])
    tree.links.new(texture.outputs['Color'], background.inputs['Color'])
    tree.links.new(background.outputs[0], output.inputs['Surface'])
    try:
        obj.data.materials[0] = portable_material
        pipeline.export_gltf(assets / 'room-portable.glb')
    finally:
        obj.data.materials[0] = expected_material

    fov = math.degrees(2*math.atan(data.sensor_width/(2*data.lens*aspect)))
    manifest = {
        'schemaVersion':2, 'title':'EXR UV1 / PI transport calibration', 'sourceKind':'render',
        'sourceImage':'/assets/reference.png', 'sourceImageSize':[width,height], 'sourceAspect':aspect,
        'model':'/assets/interior/room-runtime.glb', 'portableModel':'/assets/interior/room-portable.glb',
        'blender':'/assets/interior/room-master.blend', 'environment':'/assets/interior/room-environment.exr',
        'background':'/assets/interior/room-environment.exr', 'backgroundIntensity':1,
        'camera':{'position':pipeline.three_point(camera.location), 'target':pipeline.three_point(target), 'fov':fov},
        'roomBounds':{'min':[-3,0,-2], 'max':[3,3,4]}, 'views':{},
        'lighting':{'model':'ambient-bake+shadowed-sun-v1', 'sun':None},
        'lightmaps':[{'id':'calibration', 'url':'/assets/interior/lightmap-calibration.exr', 'intensity':math.pi}],
        'variants':[], 'toneMapping':'neutral', 'exposure':1,
        'stats':{'meshes':1, 'triangles':2, 'components':1, 'lightmapAtlases':1},
        'sourceLimit':'Analytic transport fixture, not an image reconstruction or realism grade.',
        'portability':'Runtime PBR uses the EXR sidecar; portable embeds static Neutral diffuse. Native reference evaluates analytic Lambertian radiance.'
    }
    (assets / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    return {'viewerWorkspace':str(child), 'manifest':str(assets/'manifest.json'),
            'expectedRender':str(expected), 'renderSize':[width,height],
            'uv0':uv0, 'uv1':uv1, 'linearAlbedo':albedo, 'lightmapIntensity':math.pi,
            'decodedExrMaxError':exr_error, 'exrSha256':hashlib.sha256(exr.read_bytes()).hexdigest(),
            'camera':manifest['camera'], 'probe':'Actual all-black float EXR; no IBL contribution',
            'browserComparison':'Not performed by native stage; compare actual viewer canvas against expectedRender at identical dimensions and source camera',
            'expectedRadiance':'linearAlbedo * bilinear(EXR field, rotated UV1); runtime Lambertian PI cancels 1/PI'}
