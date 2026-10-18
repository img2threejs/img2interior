"""Explicit hash-guarded Oak/Linen recipe, not a generic image interpreter."""

import json
import math

import bpy
import bmesh
from mathutils import Matrix, Vector

def _curtain_material(context, linen_maps):
    _material = context.helpers.material
    ROOT = context.workspace
    material = _material('Interior.CurtainLinen', (0.85, 0.81, 0.71), 0.94,
                         maps={'normal': linen_maps['normal'], 'roughness': 'public/assets/interior/curtain-roughness.png'},
                         color_path=ROOT / 'public/assets/interior/curtain-basecolor.png', normal_strength=0.70)
    tree = material.node_tree
    shader = next(node for node in tree.nodes if node.type == 'BSDF_PRINCIPLED')
    shader.inputs['Specular IOR Level'].default_value = 0.25
    shader.inputs['Sheen Weight'].default_value = 0.12
    shader.inputs['Sheen Roughness'].default_value = 0.90
    uv = tree.nodes.new('ShaderNodeUVMap')
    uv.uv_map = 'UV0'
    for texture in tree.nodes:
        if texture.type == 'TEX_IMAGE':
            tree.links.new(uv.outputs['UV'], texture.inputs['Vector'])
    return material


def _table_vase(helpers, mat, location):
    """Smooth cubic meridian, 6 mm shell, open neck and closed ceramic foot."""
    _lathe = helpers.lathe
    profile = [(0.0, 0.0), (0.052, 0.0)]

    def arc(control_a, control_b, end, steps=20):
        start = profile[-1]
        for i in range(1, steps + 1):
            t = i / steps
            s = 1 - t
            profile.append(tuple(s**3 * start[k] + 3*s*s*t * control_a[k]
                                 + 3*s*t*t * control_b[k] + t**3 * end[k]
                                 for k in range(2)))

    arc((0.054, 0.0), (0.052, 0.025), (0.052, 0.040), 12)
    arc((0.052, 0.065), (0.120, 0.075), (0.120, 0.130))
    arc((0.120, 0.195), (0.035, 0.205), (0.035, 0.235), 28)
    arc((0.035, 0.250), (0.035, 0.280), (0.035, 0.296), 12)
    arc((0.035, 0.3013), (0.029, 0.3013), (0.029, 0.296), 12)
    arc((0.029, 0.280), (0.029, 0.250), (0.029, 0.235), 12)
    arc((0.029, 0.199), (0.114, 0.189), (0.114, 0.130), 28)
    arc((0.114, 0.081), (0.046, 0.071), (0.046, 0.045))
    arc((0.046, 0.020), (0.020, 0.012), (0.0, 0.012), 16)
    return _lathe('table-vase.body', profile, mat, 'table-vase', location, segments=96)


def _book(helpers, name, center, size, cover, paper):
    _box = helpers.box
    x, y, z = center
    w, d, h = size
    _box(name + '.pages', (x, y, z+h/2), (w-0.009, d-0.009, h-0.006), paper, 'books', 0.001)
    for side in (0, 1):
        _box(name + f'.cover.{side}', (x, y, z+0.0015+side*(h-0.003)), (w, d, 0.003), cover, 'books', 0.001)
    _box(name + '.spine', (x-w/2+0.002, y, z+h/2), (0.004, d, h), cover, 'books', 0.001)


def _source_table(helpers, center, stone, metal):
    """Source's thin disk and three radial U-shaped hairpin legs."""
    _lathe, _project_uv, _tube = helpers.lathe, helpers.project_uv, helpers.tube
    x, y, floor = center
    top = 0.435 + floor
    disk = _lathe('coffee-table.marble-top',
           [(0, top-0.029), (0.696, top-0.029), (0.708, top-0.022),
            (0.712, top-0.009), (0.704, top), (0, top)],
           stone, 'coffee-table', (x, y, 0), segments=128)
    _project_uv(disk, 1.5)
    for uv in disk.data.uv_layers.active.data:
        uv.uv += Vector((0.5, 0.5))
    # Two convex-hull-bounded Bezier bends share a horizontal floor tangent.
    # The shared apex is one tube radius above the rug; both ends stay in the stone.
    controls = (
        ((0.29,top-0.030),(0.39,floor+0.120),(0.44,floor+0.012),(0.49,floor+0.012)),
        ((0.49,floor+0.012),(0.54,floor+0.012),(0.60,floor+0.120),(0.63,top-0.030)))
    profile = []
    for a, b, c, d in controls:
        for step in range(24):
            t, u = step/24, 1-step/24
            profile.append((u**3*a[0]+3*u*u*t*b[0]+3*u*t*t*c[0]+t**3*d[0],
                            u**3*a[1]+3*u*u*t*b[1]+3*u*t*t*c[1]+t**3*d[1]))
    profile.append(controls[-1][-1])
    for index, angle in enumerate((math.pi/2, math.pi*7/6, math.pi*11/6)):
        cosine, sine = math.cos(angle), math.sin(angle)
        points = [(x+r*cosine, y+r*sine, z) for r, z in profile]
        _tube(f'coffee-table.hairpin.{index}', points, 0.012, metal, 'coffee-table')
    return top


def _source_chair(helpers, center, yaw, wood, leather, rug):
    """Low lounge chair with canted tapered legs, flowing arms and separate leather pads."""
    _cushion, _mesh, _tube = helpers.cushion, helpers.mesh, helpers.tube
    before = set(bpy.data.objects)
    transform = (Matrix.Translation(Vector(center)) @ Matrix.Rotation(yaw, 4, 'Z')
                 @ Matrix.Diagonal((0.825, 0.99, 1.0, 1.0)))
    _cushion('armchair.seat-pad', (0, -0.10, 0.435), (0.86, 0.84, 0.17),
             leather, exponent=4.0, component='armchair', finish=None, tile=0.50,
             seam_levels=(-0.6,), seam_radius=0.0012, resolution=42)
    _cushion('armchair.back-pad', (0, 0.275, 0.66), (0.82, 0.55, 0.18),
             leather, (math.radians(72), 0, 0), phase=2.6, exponent=3.2,
             component='armchair', finish=None, tile=0.50,
             seam_levels=(0.65,), seam_radius=0.0012, resolution=42)
    for side in (-1, 1):
        for label, bottom, upper in (
                ('front', (side*0.475, -0.48, 0), (side*0.405, -0.335, 0.65)),
                ('rear', (side*0.475, 0.49, 0), (side*0.385, 0.34, 0.87))):
            contact = transform @ Vector(bottom)
            support = rug[4] if rug[0] <= contact.x <= rug[1] and rug[2] <= contact.y <= rug[3] else 0
            vertices = [(p[0]+r*math.cos(i*math.tau/24), p[1]+r*math.sin(i*math.tau/24), p[2]+dz)
                        for p, r, dz in ((bottom, 0.019, support), (upper, 0.033, 0))
                        for i in range(24)]
            faces = [(i, (i+1)%24, (i+1)%24+24, i+24) for i in range(24)]
            faces.extend([tuple(reversed(range(24))), tuple(range(24, 48))])
            obj = _mesh(f'armchair.{label}-leg.{side}', vertices, faces, wood, 'armchair', tile=1.4)
            for face in obj.data.polygons:
                face.use_smooth = len(face.vertices) == 4
        _tube(f'armchair.side-apron.{side}', [(side*0.41, -0.35, 0.345), (side*0.405, 0.35, 0.36)],
              0.024, wood, 'armchair')
        rail = []
        for i in range(41):
            t = i/40
            rail.append((side*(0.455-0.055*t), -0.52+0.92*t,
                         0.635-0.025*math.sin(math.pi*t)+0.235*t*t))
        _tube(f'armchair.curved-arm.{side}', rail, 0.022, wood, 'armchair')
    for y, z in ((-0.335, 0.345), (0.34, 0.365), (0.34, 0.85)):
        _tube(f'armchair.crossrail.{z}', [(-0.405, y, z), (0.405, y, z)], 0.021, wood, 'armchair')
    for obj in set(bpy.data.objects)-before:
        # Bake the complete affine placement into vertices; no TRS shear loss on pads.
        placement = transform @ obj.matrix_world
        for vertex in obj.data.vertices:
            vertex.co = placement @ vertex.co
        obj.matrix_world = Matrix.Identity(4)


def _curtain(helpers, name, anchor, width, mat, *, panel_id, direction, closed_width=3.10):
    """Rail-mounted linen; UV0 also preserves material coordinates for runtime cloth."""
    _mesh, _tube = helpers.mesh, helpers.tube
    vertices, faces = [], []
    nx, nz = 100, 32
    folds = 7 if panel_id == 'front' else 9
    settings = {
        'curtain_id': panel_id, 'curtain_anchor': anchor, 'curtain_direction': direction,
        'curtain_open_width': width, 'curtain_closed_width': closed_width,
        'curtain_height': 3.086, 'curtain_floor': 0.014, 'curtain_folds': folds,
        'curtain_fabric_width': 3.65, 'curtain_tile': 0.65, 'curtain_plane_x': -2.98,
        'curtain_rail_axis': [0, 0, -direction],
        'curtain_depth_axis': [1, 0, 0],
        'curtain_plane_origin': [-2.98, 0, -anchor],
    }

    def attach(obj, part):
        for key, value in settings.items():
            obj[key] = value
        obj['curtain_part'] = part
        return obj

    for j in range(nz + 1):
        v = j / nz
        for i in range(nx + 1):
            u = i / nx
            y = anchor + direction * (width*u + 0.008*math.sin(v*math.pi)*math.sin(u*19))
            x = -2.98 + (0.085+0.015*(1-v))*math.sin(u*math.tau*folds)
            x += 0.010*math.sin(u*math.tau*folds*2+0.4*v)
            vertices.append((x, y, 0.014+3.086*v+0.007*(1-v)*math.sin(u*49)))
    for j in range(nz):
        for i in range(nx):
            a = j*(nx+1)+i
            faces.append((a, a+1, a+nx+2, a+nx+1))
    obj = attach(_mesh(name, vertices, faces, mat, 'curtains', tile=0.65), 'cloth')
    uv = obj.data.uv_layers['UV0']
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
        for loop_index in polygon.loop_indices:
            vertex = obj.data.loops[loop_index].vertex_index
            j, i = divmod(vertex, nx+1)
            uv.data[loop_index].uv = (i/nx*3.65/0.65, j/nz*3.086/0.65)
    solid = obj.modifiers.new('Hemmed cloth thickness', 'SOLIDIFY')
    solid.thickness = 0.0015
    for end, j, v in (('bottom', 0, 0), ('top', nz, 1)):
        hem = attach(_tube(name+'.'+end+'-hem', vertices[j*(nx+1):(j+1)*(nx+1)],
                           0.003, mat, 'curtains'), 'hem')
        hem['curtain_v'] = v
    for i in range(folds+1):
        u = i/folds
        y = anchor+direction*width*u
        hook = attach(_tube(name+f'.hook.{i:02}', [(-2.98, y, 3.10), (-2.98, y, 3.14)],
                            0.003, mat, 'curtains'), 'hook')
        hook['curtain_u'] = u
    return obj


def build_scene(context) -> dict:
    """Build the complete editable PBR scene and return JSON-serializable metadata."""
    import hashlib
    CONTEXT, ROOT = context, context.workspace
    helpers = context.helpers
    _material, _box, _mesh = helpers.material, helpers.box, helpers.mesh
    _cushion, _lathe, _tube = helpers.cushion, helpers.lathe, helpers.tube
    _image, _import_model, _bounds = helpers.image, helpers.import_model, helpers.bounds
    _activate, _tag, _project_uv = helpers.activate, helpers.tag, helpers.project_uv
    _light = helpers.light
    contract = CONTEXT.spec
    expected = '95eb31d840165964deac849813dc77ad18bad71f1df90770bff1f7b4a5fb666b'
    if hashlib.sha256(CONTEXT.resolve(contract['source']).read_bytes()).hexdigest() != expected:
        raise ValueError('Oak/Linen requires its exact authorized reference image; author a new builder for a different room')
    resources = json.loads(CONTEXT.resolve(contract['authoring']['resourceManifest']).read_text())
    for category in ('models', 'hdris'):
        for path in resources[category].values():
            CONTEXT.resolve(path)
    for maps in resources['textures'].values():
        for path in maps.values():
            CONTEXT.resolve(path)
    artwork = ROOT / 'public/assets/interior/artwork.png'
    linen = ROOT / 'public/assets/interior/linen-neutral.png'
    walnut_color = ROOT / 'public/assets/interior/walnut-color.png'
    surfaces = {name: ROOT / f'public/assets/interior/{name}.png' for name in (
        'floor-oak-color', 'plaster-color', 'rug-basecolor', 'rug-normal', 'rug-roughness',
        'curtain-basecolor', 'curtain-roughness', 'chair-oak-color', 'leather-basecolor',
        'leather-roughness', 'marble-basecolor', 'marble-normal')}
    required = [artwork, linen, walnut_color, *surfaces.values()]
    required += [ROOT / p for p in resources['models'].values()]
    required += [ROOT / p for maps in resources['textures'].values() for p in maps.values()]
    required += [ROOT / p for p in resources['hdris'].values()]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        raise FileNotFoundError('Required interior resources missing: ' + ', '.join(missing))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    tex = resources['textures']
    plaster = _material('Interior.WarmPlaster', (0.72, 0.67, 0.57), maps=tex['painted_plaster_wall'], color_path=surfaces['plaster-color'], normal_strength=0.20)
    ceiling = _material('Interior.CeilingIvory', (0.83, 0.81, 0.75), 0.85)
    oak = _material('Interior.OakFloor', (0.49, 0.39, 0.26), maps=tex['oak_wood_planks'], color_path=surfaces['floor-oak-color'], normal_strength=0.35)
    walnut = _material('Interior.WalnutCabinet', (0.18, 0.075, 0.032), maps=tex['oak_veneer_03'], color_path=walnut_color, normal_strength=0.20)
    chair_wood = _material('Interior.ChairNaturalOak', (0.32, 0.215, 0.12), 0.38, maps={'normal': tex['oak_veneer_03']['normal']}, color_path=surfaces['chair-oak-color'], normal_strength=0.15)
    leather = _material('Interior.ChairBlackLeather', (0.022, 0.022, 0.018), 0.43, maps={'normal': tex['brown_leather']['normal'], 'roughness': str(surfaces['leather-roughness'].relative_to(ROOT))}, color_path=surfaces['leather-basecolor'], normal_strength=0.35)
    marble = _material('Interior.TableIvoryMarble', (0.78, 0.75, 0.67), 0.27, maps={'normal': str(surfaces['marble-normal'].relative_to(ROOT))}, color_path=surfaces['marble-basecolor'], normal_strength=0.10)
    bronze = _material('Interior.BrushedBronze', (0.13, 0.11, 0.085), 0.30, 0.8)
    dark = _material('Interior.DarkJoinery', (0.025, 0.019, 0.012), 0.45)
    upholstery = _material('Interior.SofaCreamLinen', (0.84, 0.78, 0.67), maps=tex['rough_linen'], color_path=linen, normal_strength=0.45)
    linen_relief = {key: tex['rough_linen'][key] for key in ('normal', 'roughness')}
    tan = _material('Interior.SofaTanLinen', (0.39, 0.27, 0.16), maps=linen_relief, normal_strength=0.45)
    rug_mat = _material('Interior.WovenIvoryRug', (0.64, 0.60, 0.50),
                        maps={'normal': str(surfaces['rug-normal'].relative_to(ROOT)), 'roughness': str(surfaces['rug-roughness'].relative_to(ROOT))},
                        color_path=surfaces['rug-basecolor'], normal_strength=0.65)
    curtain_mat = _curtain_material(context, tex['rough_linen'])
    shade_mat = _material('Interior.LinenShade', (0.80, 0.69, 0.49), maps=linen_relief, normal_strength=0.15)
    ceramic = _material('Interior.GlazedCreamCeramic', (0.74, 0.70, 0.61), 0.32)
    pages = _material('Interior.BookPaper', (0.79, 0.75, 0.64), 0.82)
    book_white = _material('Interior.BookCoverIvory', (0.65, 0.62, 0.54), 0.55)
    book_brown = _material('Interior.BookCoverUmber', (0.13, 0.08, 0.045), 0.57)
    ground = _material('Exterior.GardenSoil', (0.065, 0.047, 0.026), 0.95)
    stone = _material('Exterior.TerraceStone', (0.42, 0.40, 0.34), 0.83)
    glass = _material('Interior.WindowGlass', (0.98, 0.99, 1), 0.035)
    glass_shader = next(n for n in glass.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    glass_shader.inputs['Transmission Weight'].default_value = 1
    glass_shader.inputs['IOR'].default_value = 1.45
    # Parallel 6 mm clear panes have negligible net angular deviation. Cycles
    # shadow rays use straight-through interface transmission; camera/glossy
    # rays retain the refractive Principled surface. Geometry still casts shadows.
    tree = glass.node_tree
    path = tree.nodes.new('ShaderNodeLightPath')
    transmitted = tree.nodes.new('ShaderNodeBsdfTransparent')
    transmitted.inputs['Color'].default_value = (0.96, 0.96, 0.96, 1)
    shadow_mix = tree.nodes.new('ShaderNodeMixShader')
    tree.links.new(path.outputs['Is Shadow Ray'], shadow_mix.inputs[0])
    tree.links.new(glass_shader.outputs['BSDF'], shadow_mix.inputs[1])
    tree.links.new(transmitted.outputs[0], shadow_mix.inputs[2])
    output = next(node for node in tree.nodes if node.type == 'OUTPUT_MATERIAL')
    tree.links.new(shadow_mix.outputs[0], output.inputs['Surface'])
    glass['thin_pane_shadow_transmittance'] = 0.96

    room = contract['authoring']['room']
    xmin, xmax = room['x']
    ymin, ymax = room['y']
    ymin = min(ymin, -6.4)  # Authored unseen shell extension, behind source camera.
    height = room['height']
    midx, midy = (xmin + xmax) / 2, (ymin + ymax) / 2
    _box('architecture.floor', (midx, midy, -0.09), (xmax-xmin+0.3, ymax-ymin+0.3, 0.18), oak, 'floor', 0.006, tile=1.8)
    _box('architecture.back-wall', (midx, ymax+0.1, height/2), (xmax-xmin+0.4, 0.2, height), plaster, 'walls', 0.008, tile=2.0)
    _box('architecture.right-wall', (xmax+0.1, midy, height/2), (0.2, ymax-ymin, height), plaster, 'walls', 0.008, tile=2.0)
    _box('architecture.ceiling', (midx, midy, height+0.10), (xmax-xmin+0.4, ymax-ymin+0.4, 0.2), ceiling, 'ceiling')
    _box('architecture.front-wall', (midx, ymin-0.1, height/2), (xmax-xmin+0.4, 0.2, height), plaster, 'walls', 0.008, tile=2.0)
    window_min, window_end = -4.0, 2.2
    window_mid = (window_min+window_end)/2
    _box('architecture.left-extension', (xmin-0.1, (ymin+window_min)/2, height/2), (0.2, window_min-ymin, height), plaster, 'walls', 0.008, tile=2.0)
    _box('architecture.left-rear-return', (xmin-0.1, (window_end+ymax)/2, height/2), (0.2, ymax-window_end, height), plaster, 'walls', 0.008, tile=2.0)
    _box('architecture.skirt.back', (midx, ymax-0.012, 0.045), (xmax-xmin, 0.025, 0.09), plaster, 'walls', 0.004)
    _box('architecture.skirt.right', (xmax-0.012, midy, 0.045), (0.025, ymax-ymin, 0.09), plaster, 'walls', 0.004)
    for z in (0.035, height-0.035):
        _box(f'window.horizontal.{z:.3f}', (xmin, window_mid, z), (0.09, window_end-window_min, 0.07), bronze, 'windows', 0.006)
    divisions = 5
    for i in range(divisions + 1):
        y = window_min + (window_end-window_min) * i / divisions
        _box(f'window.mullion.{i:02}', (xmin, y, height/2), (0.065, 0.035, height), bronze, 'windows', 0.004)
        if i < divisions:
            spacing = (window_end-window_min)/divisions
            _box(f'window.glass.{i:02}', (xmin-0.014, y+spacing/2, height/2), (0.006, spacing-0.035, height-0.07), glass, 'windows')
    _tube('window.door-handle', [(xmin+0.07, -0.03, 0.93), (xmin+0.12, -0.03, 0.93), (xmin+0.12, -0.03, 1.14), (xmin+0.07, -0.03, 1.14)], 0.009, bronze, 'windows')
    _box('curtains.track', (-2.98, window_mid, 3.14), (0.045, window_end-window_min, 0.035), ceiling, 'curtains', 0.006)
    _curtain(helpers, 'curtains.rear-panel', window_end, 0.88, curtain_mat, panel_id='rear', direction=-1)
    _curtain(helpers, 'curtains.front-panel', window_min, 0.68, curtain_mat, panel_id='front', direction=1)

    # Three tall soft seat fronts over an almost hidden plinth, not stacked mattresses.
    sx, sy = -0.65, 1.93
    for i, x in enumerate((sx-1.58, sx+1.58)):
        for j, y in enumerate((1.43, 2.30)):
            _box(f'sofa.foot.{i}.{j}', (x, y, 0.035+(0.007 if j == 0 else 0)),
                 (0.10, 0.10, 0.07), walnut, 'sofa', 0.012)
    _box('sofa.lower-frame', (sx, 1.99, 0.105), (3.66, 0.85, 0.09), upholstery, 'sofa', 0.04, 0.75, 'sofa')
    _box('sofa.back-shell', (sx, 2.365, 0.435), (3.66, 0.25, 0.78), upholstery, 'sofa', 0.115, 0.75, 'sofa')
    for side in (-1, 1):
        _cushion('sofa.arm.' + ('left' if side < 0 else 'right'), (sx+side*1.71, 1.92, 0.35),
                 (0.30, 1.14, 0.66), upholstery, exponent=8, seams=False)
    for i, x in enumerate((sx-1.095, sx, sx+1.095)):
        _cushion(f'sofa.seat.{i}', (x, 1.83, 0.24), (1.075, 1.0, 0.44), upholstery, phase=i*1.9, exponent=6, resolution=72)
        _cushion(f'sofa.back-cushion.{i}', (x, 2.27, 0.5925), (1.10, 0.435, 0.21), upholstery,
                 (math.radians(83), 0, 0), phase=i*2.3, exponent=6, resolution=42)
    for profile in contract['authoring']['pillowProfiles']:
        _cushion('sofa.throw.' + profile['id'], profile['position'], profile['size'],
                 tan if profile['id'] == 'right-back' else upholstery,
                 tuple(math.radians(v) for v in profile['rotationDegrees']), profile['phase'],
                 exponent=6, loose=True, seam_radius=0.0009, outline=profile['outline'], resolution=56)

    rug_center = (-0.645, 0.36)
    rug_width, rug_depth, rug_thickness = 4.21, 2.68, 0.007
    rug_left, rug_right = (rug_center[0]-rug_width/2, rug_center[0]+rug_width/2)
    rug_front, rug_back = (rug_center[1]-rug_depth/2, rug_center[1]+rug_depth/2)
    _box('rug.woven-body', (*rug_center, rug_thickness/2), (rug_width, rug_depth, rug_thickness), rug_mat, 'rug', 0.003, tile=0.36)
    for side in (-1, 1):
        y = rug_center[1] + side * (rug_depth/2-0.008)
        _tube(f'rug.bound-edge.{side}', [(rug_left+0.02, y, rug_thickness-0.001), (rug_right-0.02, y, rug_thickness-0.001)], 0.002, rug_mat, 'rug')
    # Short twisted yarn loops, rather than an alpha fringe strip.
    vertices, faces = [], []
    for side in (-1, 1):
        x = rug_center[0] + side * (rug_width/2-0.01)
        yarn_count = round((rug_depth-0.04)/0.0152) + 1
        for i in range(yarn_count):
            y = rug_front + 0.02 + i*(rug_back-rug_front-0.04)/(yarn_count-1)
            start = len(vertices)
            for j in range(5):
                t = j / 4
                for k in range(4):
                    a = k * math.tau/4
                    vertices.append((x + side*(0.035*t), y+0.0010*math.cos(a)+0.002*math.sin(t*math.tau), 0.003+0.0010*math.sin(a)+0.002*math.sin(t*math.pi)))
            for j in range(4):
                for k in range(4):
                    faces.append((start+j*4+k, start+j*4+(k+1)%4, start+(j+1)*4+(k+1)%4, start+(j+1)*4+k))
            faces.extend([(start+3, start+2, start+1, start), tuple(start+16+k for k in range(4))])
    _mesh('rug.fringe-yarns', vertices, faces, rug_mat, 'rug', tile=0.36)

    models = resources['models']
    table_top = _source_table(helpers, (-0.65, 0.05, rug_thickness), marble, bronze)
    _source_chair(helpers, (0.98, -0.65, 0), math.radians(-105), chair_wood, leather,
                  (rug_left, rug_right, rug_front, rug_back, rug_thickness))
    _table_vase(helpers, ceramic, (-0.65, 0.18, table_top+0.002))
    _lathe('table-bowl', [(0.025, 0), (0.042, 0), (0.046, 0.025), (0.105, 0.069), (0.114, 0.095), (0.107, 0.098), (0.099, 0.075), (0.038, 0.035), (0.025, 0.034)], ceramic, 'table-bowl', (-0.90, -0.20, table_top+0.002))
    for i, (x, y, w, d, h, cover) in enumerate(((-0.26, -0.09, 0.34, 0.24, 0.034, book_white), (-0.28, -0.075, 0.31, 0.225, 0.027, book_white))):
        _book(helpers, f'books.table.{i}', (x, y, table_top+0.002+(0.038 if i else 0)), (w, d, h), cover, pages)

    # Complete cabinet carcass with reveals; slats attach to individual doors.
    cx, cy, cw, cd = 2.95, 2.30, 1.72, 0.55
    for i, x in enumerate((cx-cw/2+0.10, cx+cw/2-0.10)):
        for j, y in enumerate((cy-cd/2+0.08, cy+cd/2-0.08)):
            _box(f'console.foot.{i}.{j}', (x, y, 0.08), (0.065, 0.065, 0.16), dark, 'console', 0.012)
    for label, z in (('bottom', 0.17), ('top', 0.95)):
        _box('console.' + label, (cx, cy, z), (cw, cd, 0.045), walnut, 'console', 0.008, tile=0.8)
    _box('console.back', (cx, cy+cd/2-0.015, 0.56), (cw-0.06, 0.03, 0.74), walnut, 'console', tile=0.8)
    for index, x in enumerate((cx-cw/2+0.02, cx, cx+cw/2-0.02)):
        _box(f'console.partition.{index}', (x, cy, 0.56), (0.035, cd-0.04, 0.74), walnut, 'console', tile=0.8)
    for door in range(2):
        x = cx + (door-0.5)*cw/2
        _box(f'console.door.{door}', (x, cy-cd/2-0.006, 0.56), (cw/2-0.009, 0.025, 0.735), walnut, 'console', 0.003, tile=0.8)
        for i in range(23):
            px = x-cw/4+0.024+i*(cw/2-0.048)/22
            _box(f'console.door.{door}.flute.{i:02}', (px, cy-cd/2-0.025, 0.56), (0.024, 0.025, 0.724), walnut, 'console', 0.011, tile=0.8)
        handle_x = x + (1 if door == 0 else -1)*(cw/4-0.08)
        _tube(f'console.handle.{door}', [(handle_x, cy-cd/2-0.044, 0.46), (handle_x, cy-cd/2-0.070, 0.46), (handle_x, cy-cd/2-0.070, 0.67), (handle_x, cy-cd/2-0.044, 0.67)], 0.006, bronze, 'console')
    console_z_scale = 0.88
    console_prop_base = 0.974 * console_z_scale
    _lathe('console.jug', [(0, 0), (0.045, 0), (0.065, 0.02), (0.060, 0.18),
                         (0.048, 0.23), (0.043, 0.23), (0.055, 0.18), (0.059, 0.025), (0, 0.010)],
           ceramic, 'console-vase', (cx-0.08, cy-0.03, console_prop_base))
    _tube('console.jug-handle', [(cx-0.025, cy-0.03, console_prop_base+0.18),
                               (cx+0.035, cy-0.03, console_prop_base+0.17),
                               (cx+0.050, cy-0.03, console_prop_base+0.10),
                               (cx-0.025, cy-0.03, console_prop_base+0.07)],
          0.008, ceramic, 'console-vase')
    for i in range(2):
        _lathe(f'console.small-bowl.{i}', [(0.02, 0), (0.045, 0), (0.08, 0.045), (0.085, 0.075), (0.078, 0.076), (0.071, 0.048), (0.025, 0.012)],
               ceramic, 'console-bowl', (cx-0.42, cy-0.05, console_prop_base+i*0.022))
    for i in range(2):
        _book(helpers, f'books.console.{i}', (cx+0.50, cy-0.04, console_prop_base+i*0.035),
              (0.30, 0.22, 0.032), book_white if i else book_brown, pages)

    lx, ly = 1.32, 1.43
    _lathe('lamp.base', [(0.002, 0), (0.15, 0), (0.16, 0.006), (0.15, 0.012), (0.002, 0.012)], bronze, 'floor-lamp', (lx, ly, 0))
    _tube('lamp.stem', [(lx, ly, 0.010), (lx, ly, 1.65)], 0.009, bronze, 'floor-lamp')
    _lathe('lamp.open-shade', [(0.24, 1.35), (0.17, 1.69), (0.167, 1.69), (0.237, 1.35)], shade_mat, 'floor-lamp', (lx, ly, 0))
    for z, radius in ((1.35, 0.239), (1.69, 0.169)):
        _tube(f'lamp.shade-rim.{z}', [(lx+radius*math.cos(i*math.tau/96), ly+radius*math.sin(i*math.tau/96), z) for i in range(96)], 0.0035, shade_mat, 'floor-lamp', True)
    for i in range(3):
        a = i*math.tau/3
        _tube(f'lamp.spider.{i}', [(lx, ly, 1.53), (lx+0.18*math.cos(a), ly+0.18*math.sin(a), 1.51)], 0.0025, bronze, 'floor-lamp')
    bulb_mat = _material('Interior.LampBulb', (1, 0.78, 0.46), 0.22)
    bulb_shader = next(n for n in bulb_mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bulb_shader.inputs['Emission Color'].default_value = (1, 0.64, 0.27, 1)
    bulb_shader.inputs['Emission Strength'].default_value = 2.5
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, radius=0.035, location=(lx, ly, 1.53))
    bulb = _tag(bpy.context.object, 'lamp.bulb', 'floor-lamp')
    bulb.data.materials.append(bulb_mat)
    _project_uv(bulb)
    _light('lighting.lamp-bulb', 'POINT', (lx, ly, 1.53), (lx, ly, 0), 6, (1, 0.72, 0.40)).data.shadow_soft_size = 0.035

    art_mat = _material('Interior.ArtworkCanvas', (1, 1, 1), 0.88, color_path=artwork)
    ax, az, aw, ah = -0.65, 1.76, 1.67, 1.24
    _box('artwork.canvas-body', (ax, 2.651, az), (aw, 0.025, ah), ceiling, 'artwork', 0.001)
    art = _mesh('artwork.print', [(ax-aw/2, 2.637, az-ah/2), (ax+aw/2, 2.637, az-ah/2), (ax+aw/2, 2.637, az+ah/2), (ax-aw/2, 2.637, az+ah/2)], [(0, 1, 2, 3)], art_mat, 'artwork')
    for loop, uv in zip(art.data.uv_layers.active.data, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop.uv = uv
    for side in (-1, 1):
        _box(f'artwork.frame.vertical.{side}', (ax+side*(aw/2+0.009), 2.64, az), (0.018, 0.043, ah+0.036), walnut, 'artwork', 0.003)
        _box(f'artwork.frame.horizontal.{side}', (ax, 2.64, az+side*(ah/2+0.009)), (aw, 0.043, 0.018), walnut, 'artwork', 0.003)

    _box('garden.terrain', (-13.2, -0.8, -0.16), (20.0, 28.0, 0.20), ground, 'garden', 0.03, tile=2.0)
    _box('garden.terrace', (-3.80, -0.50, -0.045), (1.10, 10.0, 0.09), stone, 'garden', 0.008)
    _box('garden.window-threshold', (-3.28, window_mid, -0.035), (0.20, window_end-window_min, 0.07), stone, 'garden', 0.006)
    _box('garden.planted-border', (-4.43, window_mid, 0.045), (0.16, 10.0, 0.21), stone, 'garden', 0.012)
    _lathe('garden.white-planter', [(0,0), (0.215,0), (0.236,0.03), (0.275,0.62),
                                  (0.279,0.69), (0.270,0.69), (0.267,0.635),
                                  (0.225,0.035), (0,0.035)],
           ceramic, 'garden', (-4.1,2.3,0))
    _lathe('garden.planter-soil', [(0,0.035), (0.225,0.035), (0.267,0.64), (0,0.64)],
           ground, 'garden', (-4.1,2.3,0), segments=64)
    plant = _import_model(ROOT / models['potted_plant_02'], 'garden.plant.00', (-5.75, 1.75, -0.06), height=2.3)
    foliage = []
    for obj in plant:
        if any(slot.material.name.startswith('potted_plant_02_leaves') for slot in obj.material_slots):
            foliage.append(obj)
        else:
            bpy.data.objects.remove(obj, do_unlink=True)
    plant = foliage
    bpy.context.view_layer.update()
    ground_offset = -0.06 - _bounds(plant)[0][2]
    for obj in plant:
        obj.location.z += ground_offset
    # Linked real geometry instances, not photographs; no point-cloud cards.
    bpy.context.view_layer.update()
    source_origin = Vector((-5.75, 1.75, -0.06))
    for index, (position, scale, yaw) in enumerate((
            ((-6.0, -0.7, -0.06), 1.2, 0.8), ((-5.8, -3.3, -0.06), 0.85, 2.1),
            ((-7.0, 3.5, -0.06), 1.8, 1.1), ((-7.2, 0.2, -0.06), 1.9, 2.9),
            ((-6.9, -3.4, -0.06), 1.6, 4.1), ((-8.5, 1.6, -0.06), 2.0, 1.4),
            ((-4.1, 2.3, 0.64), 0.45, 0.4)), start=1):
        transform = (Matrix.Translation(Vector(position)) @ Matrix.Rotation(yaw, 4, 'Z')
                     @ Matrix.Scale(scale, 4) @ Matrix.Translation(-source_origin))
        for part, source in enumerate(plant):
            obj = source.copy()
            obj.data = source.data
            bpy.context.scene.collection.objects.link(obj)
            obj.matrix_world = transform @ source.matrix_world
            _tag(obj, f'garden.plant.{index:02}.{part:02}', 'garden')
    for obj in plant:
        obj['component'] = 'garden'

    world = bpy.data.worlds.new('Interior.GardenDaylight')
    scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    nodes.clear()
    environment = nodes.new('ShaderNodeTexEnvironment')
    environment.image = _image(ROOT / resources['hdris']['meadow'], False)
    background = nodes.new('ShaderNodeBackground')
    background.inputs['Strength'].default_value = 0.22
    camera_background = nodes.new('ShaderNodeBackground')
    camera_background.inputs['Strength'].default_value = 1.20
    paths = nodes.new('ShaderNodeLightPath')
    visible = nodes.new('ShaderNodeMath')
    visible.operation = 'MAXIMUM'
    mix = nodes.new('ShaderNodeMixShader')
    output = nodes.new('ShaderNodeOutputWorld')
    links = world.node_tree.links
    links.new(environment.outputs['Color'], background.inputs['Color'])
    links.new(environment.outputs['Color'], camera_background.inputs['Color'])
    links.new(paths.outputs['Is Camera Ray'], visible.inputs[0])
    links.new(paths.outputs['Is Transmission Ray'], visible.inputs[1])
    links.new(visible.outputs[0], mix.inputs[0])
    links.new(background.outputs['Background'], mix.inputs[1])
    links.new(camera_background.outputs['Background'], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs['Surface'])
    daylight = _light('lighting.window-softbox', 'AREA', (-3.65, -0.3, 2.15), (0.1, 1.1, 0.9), 300, (1.0, 1.0, 1.0))
    daylight.visible_camera = False
    daylight.visible_transmission = False
    daylight.data.shape = 'RECTANGLE'
    daylight.data.size = 4.4
    daylight.data.size_y = 2.6
    sun = _light('lighting.soft-afternoon-sun', 'SUN', (-8, 1.2, 7), (0.5, -0.8, 0), 2.0, (1.0, 0.97, 0.90))
    sun.data.angle = math.radians(0.55)

    bpy.context.view_layer.update()
    component_z_scales = {'console': console_z_scale}
    for obj in scene.objects:
        if obj.type == 'MESH' and obj.get('component') in component_z_scales:
            _activate(obj)
            # Bake existing cushion rotations first: otherwise assigning a
            # nonuniform world scale to a rotated object loses shear in TRS.
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
            compression = Matrix.Diagonal((1.0, 1.0, component_z_scales[obj['component']], 1.0))
            obj.matrix_world = compression @ obj.matrix_world
    bpy.context.view_layer.update()

    # Final evaluated geometry is what the baker sees; leave no modifier stacks.
    for obj in sorted(bpy.data.objects, key=lambda item: item.name):
        if obj.type != 'MESH':
            continue
        _activate(obj)
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        for modifier in list(obj.modifiers):
            bpy.ops.object.modifier_apply(modifier=modifier.name)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()
        if any(not math.isfinite(value) for vertex in obj.data.vertices for value in vertex.co):
            raise ValueError(f'Nonfinite geometry: {obj.name}')
        if len(obj.data.uv_layers) != 1 or obj.data.uv_layers[0].name != 'UV0':
            raise ValueError(
                f'{obj.name}: expected exactly one material UV layer named UV0 '
                f'at index 0 before baking, found {[uv.name for uv in obj.data.uv_layers]}')
        obj.data.uv_layers.active_index = 0
        obj.data.uv_layers[0].active_render = True
        for material in obj.data.materials:
            if material and material.use_nodes:
                for node in material.node_tree.nodes:
                    if (node.type in {'NORMAL_MAP', 'UVMAP'} and node.uv_map
                            and node.uv_map not in obj.data.uv_layers):
                        raise ValueError(
                            f'{obj.name}: material {material.name}, node {node.name} '
                            f'references missing UV layer {node.uv_map!r}')

    camera_spec = contract['authoring']['cameraEstimate']
    camera_data = bpy.data.cameras.new('Interior.SourceCamera')
    camera = bpy.data.objects.new('Interior.SourceCamera', camera_data)
    scene.collection.objects.link(camera)
    camera.location = camera_spec['position']
    camera.rotation_euler = (Vector(camera_spec['target'])-camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera_data.lens = camera_spec['lensMm']
    camera_data.sensor_width = camera_spec['sensorWidthMm']
    camera_data.sensor_fit = 'HORIZONTAL'
    camera_data.clip_start, camera_data.clip_end = 0.03, 100
    scene.camera = camera
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 96
    scene.cycles.use_denoising = True
    scene.cycles.seed = 47
    scene.cycles.use_animated_seed = False
    scene.cycles.max_bounces = 12
    scene.cycles.diffuse_bounces = 6
    scene.cycles.transmission_bounces = 8
    scene.render.resolution_x, scene.render.resolution_y = contract['authoring']['sourceImageSize']
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.view_settings.view_transform = 'Khronos PBR Neutral'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene.render.film_transparent = False
    # Only this freshly authored scene: discard unused importer/curve data before packing.
    bpy.data.orphans_purge(do_recursive=True)
    bpy.context.view_layer.update()
    meshes = [obj for obj in scene.objects if obj.type == 'MESH']
    triangles = 0
    for obj in meshes:
        obj.data.calc_loop_triangles()
        triangles += len(obj.data.loop_triangles)
    components = {}
    for obj in sorted(meshes, key=lambda item: item.name):
        components.setdefault(obj['component'], []).append(obj.name)
    materials = sorted({mat.name for obj in meshes for mat in obj.data.materials if mat})
    bounds = _bounds(meshes)
    info = {
        'schemaVersion': 1,
        'coordinates': 'Blender Z-up metres; convert (x,y,z) to (x,z,-y) for glTF',
        'sourceKind': contract['sourceKind'],
        'camera': {'name': camera.name, 'position': list(camera.location),
                   'target': camera_spec['target'], 'lensMm': camera_data.lens,
                   'sensorWidthMm': camera_data.sensor_width,
                   'horizontalFovDegrees': math.degrees(camera_data.angle_x)},
        'views': contract['authoring']['inspectionViews'],
        'components': components,
        'stats': {'meshes': len(meshes), 'materials': len(materials), 'triangles': triangles},
        'materialNames': materials,
        'bounds': {'min': bounds[0], 'max': bounds[1]},
        'roomBounds': {'min': [xmin, ymin, 0], 'max': [xmax, ymax, height]},
        'extras': ['component', 'physical_id', 'finish (upholstery only)', 'source_asset (imports)', 'uv_tile_metres (authored surfaces)'],
        'assumptions': ['Authored hidden geometry and dimensions from a single synthetic view.',
                        'Unseen front shell extends to y=-6.4 or farther; glazing y=-4..2.2 ends at an authored rear wall return behind the curtain.',
                        'Chair and hairpin table silhouettes are authored against the source; no source furniture image planes.',
                        'Skewed sewn throw pillows, tall seat fronts and a low plinth replace the previous rounded pillows and stacked seat bands.',
                        'UV0 material regions and authored dye are not measured source-image BRDFs.',
                        'World uses authored 0.22 baseline and 1.20 camera/transmission exposure branches; this is not a measured, energy-preserving GI/background separation.'],
    }
    scene['interior_metadata'] = json.dumps(info)
    scene['source_image'] = contract['source']
    scene['coordinate_convention'] = info['coordinates']
    _activate(camera)
    return info
