"""Small authored studio: actual desk, stool, shelf, window and optional moving linen.

Install this file and scene-spec.json in W. Supply an authorized source image at
spec.source. This fixture exercises transport/export, not source-image likeness.
"""
import json
import math
import bpy
from mathutils import Vector


def build_scene(context):
    h = context.helpers
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    # Deterministic physical material map, intentionally asymmetric for repair checks.
    path = context.assets / 'studio-textile.png'
    if not path.exists():
        image = bpy.data.images.new('StudioWovenMap', width=32, height=32, alpha=True)
        image.colorspace_settings.name = 'Non-Color'
        pixels = []
        for y in range(32):
            for x in range(32):
                thread = 0.86 if (x+y) % 2 else 1.0
                color = (0.65, 0.38, 0.19) if x < 11 and y > 18 else (0.62, 0.68, 0.72)
                pixels.extend([c*thread for c in color] + [1])
        image.pixels[:] = pixels
        image.filepath_raw = str(path)
        image.file_format = 'PNG'
        image.save()
        bpy.data.images.remove(image)
    plaster = h.material('Studio.Plaster', (0.7, 0.66, 0.56), 0.85)
    floor = h.material('Studio.Oak', (0.26, 0.16, 0.08), 0.48)
    blue = h.material('Studio.BlueJoinery', (0.045, 0.13, 0.19), 0.46)
    steel = h.material('Studio.Steel', (0.1, 0.11, 0.12), 0.3, metallic=0.8)
    cloth = h.material('Studio.Textile', (1, 1, 1), 0.9,
                       maps={'color': str(path.relative_to(context.workspace))})
    shader = next(n for n in cloth.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    shader.inputs['Sheen Weight'].default_value = 0.12
    shader.inputs['Sheen Tint'].default_value = (0.8, 0.5, 0.25, 1)
    h.box('room.floor', (0, 0, -0.06), (4.2, 4.6, 0.12), floor, 'floor')
    h.box('room.back', (0, 2.3, 1.4), (4.2, 0.12, 2.8), plaster, 'walls')
    h.box('room.right', (2.1, 0, 1.4), (0.12, 4.6, 2.8), plaster, 'walls')
    h.box('room.front', (0, -2.3, 1.4), (4.2, 0.12, 2.8), plaster, 'walls')
    h.box('room.ceiling', (0, 0, 2.85), (4.2, 4.6, 0.1), plaster, 'ceiling')
    # Left wall has a real large opening, asymmetric upper and lower returns.
    h.box('window.sill-wall', (-2.1, 0, 0.22), (0.12, 4.6, 0.44), plaster, 'walls')
    h.box('window.header', (-2.1, 0, 2.68), (0.12, 4.6, 0.24), plaster, 'walls')
    for y in (-2.25, 0.55, 2.25):
        h.box('window.mullion.'+str(y), (-2.1, y, 1.5), (0.08, 0.045, 2.2), steel, 'windows')
    h.box('desk.top', (0.55, 1.45, 0.77), (1.65, 0.72, 0.065), floor, 'desk', 0.015)
    for x in (-0.15, 1.25):
        for y in (1.17, 1.73):
            h.box(f'desk.leg.{x}.{y}', (x, y, 0.37), (0.045, 0.045, 0.74), steel, 'desk')
    h.box('stool.seat', (0.25, 0.55, 0.47), (0.55, 0.48, 0.12), cloth, 'stool', 0.025, finish='seat')
    for x in (0.04, 0.46):
        for y in (0.38, 0.72):
            h.box(f'stool.leg.{x}.{y}', (x, y, 0.22), (0.045, 0.045, 0.44), blue, 'stool')
    h.box('shelf.left-panel', (-1.25, 1.95, 0.66), (0.05, 0.45, 1.32), blue, 'shelf')
    h.box('shelf.right-panel', (-0.65, 1.95, 0.66), (0.05, 0.45, 1.32), blue, 'shelf')
    for z in (0.1, 0.65, 1.3):
        h.box('shelf.board.'+str(z), (-0.95, 1.95, z), (0.65, 0.45, 0.045), blue, 'shelf')
    h.lathe('desk.cup', [(0,0),(0.055,0),(0.06,0.12),(0.052,0.12),(0.047,0.01),(0,0.01)],
            plaster, 'cup', (0.95,1.5,0.804), segments=24)
    if context.spec['authoring'].get('includeCurtain', True):
        h.curtain('curtain.studio', (-1.93, 1.95, 0), (0,-1,0), (1,0,0),
                  0.48, 2.1, 2.42, cloth, panel_id='studio', floor=0.08, folds=4)
    world = bpy.data.worlds.new('Studio.SolidDaylight')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.65, 0.75, 1.0, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.35
    scene.world = world
    sun = h.light('Studio.Sun', 'SUN', (-5,-3,6), (0,1,0), 1.8, (1,0.94,0.84))
    sun.data.angle = math.radians(1)
    area = h.light('Studio.WindowFill', 'AREA', (-2.5,0.1,1.8), (0,0.7,0.7), 150, (0.9,0.95,1))
    area.data.shape = 'RECTANGLE'
    area.data.size, area.data.size_y = 2.5, 1.9
    pose = context.spec['authoring']['cameraEstimate']
    data = bpy.data.cameras.new('Studio.SourceCamera')
    camera = bpy.data.objects.new('Studio.SourceCamera', data)
    scene.collection.objects.link(camera)
    camera.location = pose['position']
    camera.rotation_euler = (Vector(pose['target'])-camera.location).to_track_quat('-Z','Y').to_euler()
    data.lens, data.sensor_width = pose['lensMm'], pose['sensorWidthMm']
    data.sensor_fit = 'HORIZONTAL'
    scene.camera = camera
    bpy.context.view_layer.update()
    components = {}
    for obj in scene.objects:
        if obj.type == 'MESH':
            components.setdefault(obj['component'], []).append(obj.name)
    summary = {'schemaVersion':1, 'roomBounds':{'min':[-2.04,-2.24,0], 'max':[2.04,2.24,2.8]},
               'camera':pose, 'views':context.spec['authoring']['inspectionViews'],
               'components':components, 'assumptions':context.spec['assumptions']}
    scene['interior_metadata'] = json.dumps(summary)
    return summary
