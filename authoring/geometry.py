#!/usr/bin/env python3
"""Reusable metric geometry/PBR/UV helpers, bound explicitly by Context.helpers.

Coordinates are native Blender Z-up metres. Importing does not author a scene.
"""
from __future__ import annotations

import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

# This implementation is loaded into a private namespace by Context.helpers.
# ROOT and CONTEXT are bound only on that instance, never on this imported module.


def _activate(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _tag(obj, name, component, finish=None):
    obj.name = name
    obj['component'] = component
    obj['physical_id'] = name
    if finish:
        obj['finish'] = finish
    return obj


def _image(path, color=True):
    path = Path(path)
    path = CONTEXT.resolve(path.relative_to(ROOT) if path.is_absolute() else path)
    image = bpy.data.images.load(str(path), check_existing=True)
    image.colorspace_settings.name = 'sRGB' if color else 'Non-Color'
    return image


def _material(name, color, roughness=0.6, metallic=0.0, maps=None,
              color_path=None, normal_strength=0.3):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*color, 1)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    output = nodes.new('ShaderNodeOutputMaterial')
    output.is_active_output = True
    shader = nodes.new('ShaderNodeBsdfPrincipled')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Metallic'].default_value = metallic
    links.new(shader.outputs['BSDF'], output.inputs['Surface'])
    if color_path is None and maps and maps.get('color'):
        color_path = CONTEXT.resolve(maps['color'])
    if color_path:
        texture = nodes.new('ShaderNodeTexImage')
        texture.image = _image(color_path)
        texture.label = 'UV0 albedo, sRGB'
        links.new(texture.outputs['Color'], shader.inputs['Base Color'])
    if maps and maps.get('roughness'):
        texture = nodes.new('ShaderNodeTexImage')
        texture.image = _image(CONTEXT.resolve(maps['roughness']), False)
        links.new(texture.outputs['Color'], shader.inputs['Roughness'])
    if maps and maps.get('normal'):
        texture = nodes.new('ShaderNodeTexImage')
        texture.image = _image(CONTEXT.resolve(maps['normal']), False)
        normal = nodes.new('ShaderNodeNormalMap')
        normal.uv_map = 'UV0'
        normal.inputs['Strength'].default_value = normal_strength
        links.new(texture.outputs['Color'], normal.inputs['Color'])
        links.new(normal.outputs['Normal'], shader.inputs['Normal'])
    return mat




def _project_uv(obj, metres=1.0):
    """Local metric box projection, independent of object placement/rotation."""
    mesh = obj.data
    mesh.update()
    # Authored primitives often arrive with a default UVMap. Replace it rather
    # than appending UV0: the baker must reserve index 1 for its lightmap.
    # Imported native glTF UVs bypass this projection when already present.
    for layer in list(mesh.uv_layers):
        mesh.uv_layers.remove(layer)
    uv = mesh.uv_layers.new(name='UV0')
    mesh.uv_layers.active = uv
    uv.active_render = True
    for face in mesh.polygons:
        axis = max(range(3), key=lambda k: abs(face.normal[k]))
        a, b = ((1, 2), (0, 2), (0, 1))[axis]
        sign = -1 if face.normal[axis] < 0 else 1
        for index in face.loop_indices:
            point = mesh.vertices[mesh.loops[index].vertex_index].co
            uv.data[index].uv = (sign * point[a] / metres, point[b] / metres)
    obj['uv_tile_metres'] = metres


def _mesh(name, vertices, faces, mat, component, finish=None, tile=1.0):
    data = bpy.data.meshes.new(name + '.geometry')
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    _tag(obj, name, component, finish)
    obj.data.materials.append(mat)
    _project_uv(obj, tile)
    return obj


def _box(name, location, size, mat, component, bevel=0.0, tile=1.0,
         finish=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = _tag(bpy.context.object, name, component, finish)
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if bevel:
        modifier = obj.modifiers.new('Physical softened edges', 'BEVEL')
        modifier.width = bevel
        modifier.segments = 4
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    _project_uv(obj, tile)
    return obj


def _tube(name, points, radius, mat, component, cyclic=False, finish=None):
    curve = bpy.data.curves.new(name + '.path', 'CURVE')
    curve.dimensions = '3D'
    curve.resolution_u = 1
    curve.bevel_depth = radius
    curve.bevel_resolution = 2
    curve.use_fill_caps = True
    spline = curve.splines.new('POLY')
    spline.points.add(len(points) - 1)
    for p, co in zip(spline.points, points):
        p.co = (*co, 1)
    spline.use_cyclic_u = cyclic
    obj = bpy.data.objects.new(name, curve)
    bpy.context.scene.collection.objects.link(obj)
    _activate(obj)
    bpy.ops.object.convert(target='MESH')
    obj = _tag(bpy.context.object, name, component, finish)
    obj['bake_detail'] = True
    obj.data.materials.append(mat)
    _project_uv(obj, 1.1 if finish == 'sofa' else 0.25)
    for face in obj.data.polygons:
        face.use_smooth = True
    return obj


def _lathe(name, profile, mat, component, location=(0, 0, 0), segments=64):
    # Closed meridian profile makes a shell with actual inner and outer faces.
    vertices, rings, faces = [], [], []
    for r, z in profile:
        ring = []
        for i in range(1 if r == 0 else segments):
            ring.append(len(vertices))
            vertices.append((r * math.cos(i * math.tau / segments),
                             r * math.sin(i * math.tau / segments), z))
        rings.append(ring)
    for j, ring in enumerate(rings):
        following = rings[(j + 1) % len(rings)]
        if len(ring) == len(following) == 1:
            continue
        for i in range(segments):
            n = (i + 1) % segments
            if len(ring) == 1:
                faces.append((ring[0], following[n], following[i]))
            elif len(following) == 1:
                faces.append((ring[i], ring[n], following[0]))
            else:
                faces.append((ring[i], ring[n], following[n], following[i]))
    obj = _mesh(name, vertices, faces, mat, component, tile=0.5)
    obj.location = location
    for face in obj.data.polygons:
        face.use_smooth = True
    return obj




def _cushion(name, location, size, mat, rotation=(0, 0, 0), phase=0.0,
             exponent=5.0, seams=True, loose=False, component='sofa',
             finish='sofa', tile=0.75, seam_levels=None, seam_radius=0.0011, outline=None, resolution=28):
    """Closed dense cloth volume, with localized perimeter gathers and optional sewn outline.

    Each face starts as a resolution-by-resolution grid. Deformation happens on actual vertices,
    including underside; piping is seated on the actual tessellated cloth mesh.
    """
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2)
    bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=resolution-1, use_grid_fill=True)
    # Irregular, localized cloth gathers, not a periodic corrugated panel.
    folds = tuple((center+0.025*math.sin(phase+i), width, depth, zc, span)
                  for i, (center, width, depth, zc, span) in enumerate((
                      (-0.83,0.045,0.0070,-0.20,0.65), (-0.57,0.060,-0.0035,0.35,0.45),
                      (-0.17,0.040,0.0022,-0.30,0.55), (0.36,0.050,-0.0026,0.20,0.60),
                      (0.68,0.040,0.0050,-0.15,0.70), (0.86,0.045,-0.0065,0.10,0.55)
                  ))) if seams and not loose else ()
    fold_bend = 0.025*math.sin(phase)

    def shape(p):
        denominator = sum(abs(v) ** exponent for v in p) ** (1 / exponent)
        x, y, z = (v / denominator for v in p)
        if loose:
            # A sewn square pillow has thin pointed corners, not a rounded balloon.
            x, y = p[0], p[1]
            puff = 0.16 + 0.84 * math.sqrt(max((1 - x*x) * (1 - y*y), 0))
            z = p[2] * puff
            x *= 1 - 0.035 * (1 - y*y)
            y *= 1 - 0.035 * (1 - p[0]*p[0])
        # Local seam gathers and front-panel folds, not global displacement noise.
        edge = math.exp(-((abs(y) - 0.86) / 0.16) ** 2)
        edge2 = math.exp(-((abs(x) - 0.86) / 0.15) ** 2)
        wrinkle = (math.sin(39 * x + phase + 3 * y) * edge
                   + 0.65 * math.sin(43 * y - phase) * edge2)
        top = abs(p[2]) ** 3 if loose else abs(z) ** 3
        crease = 0.003 * math.exp(-((abs(y) - 0.93) / 0.045) ** 2)
        # A shallow off-centre compression, not high-frequency surface noise.
        sag = (0.009 * max(z, 0) ** 2
               * math.exp(-((x - 0.16 * math.sin(phase)) / 0.60) ** 2
                          - ((y + 0.08) / 0.65) ** 2)) if seams else 0.0
        front_fold = 0.0
        for center, width, depth, zc, span in folds:
            q = (x-center-fold_bend*z*z)/width
            front_fold += depth*q*math.exp(-0.5*q*q-((z-zc)/span)**2)
        front_fold *= max(-y, 0)**6
        if loose:
            corner_fold = (
                math.exp(-((x - 0.63 + 0.26*y) / 0.055) ** 2 - ((y - 0.65) / 0.35) ** 2)
                + 0.75 * math.exp(-((x + 0.62 - 0.20*y) / 0.065) ** 2 - ((y + 0.58) / 0.38) ** 2))
            crease += 0.018 * corner_fold
        px, py = x * size[0] / 2, y * size[1] / 2
        if outline is not None:
            # A source-guided, deformed seam is lofted into a closed bag, not a photo plane.
            u, v = (x+1)/2, (y+1)/2
            px = ((1-u)*outline[0][0]+u*outline[1][0])*v + ((1-u)*outline[3][0]+u*outline[2][0])*(1-v)
            py = ((1-u)*outline[0][1]+u*outline[1][1])*v + ((1-u)*outline[3][1]+u*outline[2][1])*(1-v)
        return (px, py + front_fold,
                z * size[2] / 2 + (1 if z >= 0 else -1) * top * ((0 if loose else 0.0014) * wrinkle - crease) - sag)

    for vertex in bm.verts:
        vertex.co = shape(vertex.co)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    data = bpy.data.meshes.new(name + '.geometry')
    bm.to_mesh(data)
    bm.free()
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    _tag(obj, name, component, finish)
    obj.data.materials.append(mat)
    _project_uv(obj, tile)
    obj.location = location
    obj.rotation_euler = rotation
    for face in data.polygons:
        face.use_smooth = True
    if seams:
        surface = BVHTree.FromPolygons(
            [vertex.co for vertex in data.vertices], [face.vertices[:] for face in data.polygons])
        levels = seam_levels if seam_levels is not None else ((0.0,) if loose else (-0.65,))
        for index, z in enumerate(levels):
            points = []
            radial = (1 - abs(z) ** exponent) ** (1 / exponent)
            for i in range(160):
                angle = math.tau * i / 160
                c, s = math.cos(angle), math.sin(angle)
                if loose:
                    scale = max(abs(c), abs(s))
                    p = (c / scale, s / scale, z)
                else:
                    p = (math.copysign(abs(c) ** (2 / exponent), c) * radial,
                         math.copysign(abs(s) ** (2 / exponent), s) * radial, z)
                # The analytic cloth differs from its tessellated surface by millimetres.
                # Seat the welt on the actual mesh, not partly inside those facets.
                point, normal, _, _ = surface.find_nearest(Vector(shape(p)))
                points.append(point + normal * (seam_radius * 0.8))
            seam = _tube(name + f'.welt.{index}',
                         points, seam_radius, mat, component, True, finish)
            seam.location = location
            seam.rotation_euler = rotation
    return obj








def _bounds(objects):
    points = [obj.matrix_world @ Vector(corner)
              for obj in objects for corner in obj.bound_box]
    return ([min(p[i] for p in points) for i in range(3)],
            [max(p[i] for p in points) for i in range(3)])


def _import_model(path, component, center, height=None, width=None, yaw=0.0):
    path = Path(path)
    path = CONTEXT.resolve(path.relative_to(ROOT) if path.is_absolute() else path)
    if (height is None) == (width is None):
        raise ValueError('Specify exactly one positive import height or width')
    if (height if height is not None else width) <= 0:
        raise ValueError('Import dimension must be positive')
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    created = sorted(set(bpy.data.objects) - before, key=lambda o: o.name)
    meshes = [o for o in created if o.type == 'MESH']
    bpy.context.view_layer.update()
    low, high = _bounds(meshes)
    scale = height / (high[2] - low[2]) if height else width / (high[0] - low[0])
    origin = Vector(((low[0] + high[0]) / 2, (low[1] + high[1]) / 2, low[2]))
    placement = (Matrix.Translation(Vector(center)) @ Matrix.Rotation(yaw, 4, 'Z')
                 @ Matrix.Scale(scale, 4) @ Matrix.Translation(-origin))
    # Flatten imported hierarchy but preserve each child's complete world matrix.
    matrices = {obj: obj.matrix_world.copy() for obj in meshes}
    for index, obj in enumerate(meshes):
        obj.parent = None
        obj.matrix_world = placement @ matrices[obj]
        _tag(obj, f'{component}.{index:02d}.{obj.name}', component)
        obj['source_asset'] = str(path.relative_to(ROOT))
        if obj.data.uv_layers:
            old_uv_name = obj.data.uv_layers[0].name
            obj.data.uv_layers[0].name = 'UV0'
            obj.data.uv_layers.active_index = 0
            obj.data.uv_layers[0].active_render = True
            for material in obj.data.materials:
                if material and material.use_nodes:
                    for node in material.node_tree.nodes:
                        if node.type in {'NORMAL_MAP', 'UVMAP'} and node.uv_map == old_uv_name:
                            node.uv_map = 'UV0'
        else:
            _project_uv(obj)
    for obj in created:
        if obj.type != 'MESH':
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.context.view_layer.update()
    return meshes




def _light(name, kind, position, target, energy, color):
    data = bpy.data.lights.new(name, kind)
    data.energy, data.color = energy, color
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = position
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()
    return obj




def curtain_panel(name, origin, rail, depth, width, closed_width, height, material,
                  panel_id='panel', floor=0.02, folds=5, fabric_width=None, tile=0.65):
    """Create cloth, hems and hooks in an explicit native Z-up horizontal frame.

    origin is the horizontal start of the rail at z=0; rail and depth are
    orthogonal horizontal unit vectors. All generated geometry is world-space.
    Metadata vectors alone are converted to glTF Y-up for the runtime solver.
    """
    rail, depth, origin = Vector(rail), Vector(depth), Vector(origin)
    if (abs(rail.length-1) > 1e-6 or abs(depth.length-1) > 1e-6
            or abs(rail.dot(depth)) > 1e-6 or abs(rail.z)+abs(depth.z)+abs(origin.z) > 1e-6):
        raise ValueError('Curtain requires horizontal orthonormal rail/depth and origin.z=0')
    if min(width, closed_width, height, tile) <= 0 or folds < 1:
        raise ValueError('Curtain dimensions and folds must be positive')
    fabric_width = fabric_width or closed_width * 1.2
    convert = lambda p: [p[0], p[2], -p[1]]
    metadata = {'curtain_id': panel_id, 'curtain_direction': 1,
                'curtain_anchor': 0.0, 'curtain_open_width': width,
                'curtain_closed_width': closed_width, 'curtain_height': height,
                'curtain_floor': floor, 'curtain_folds': folds,
                'curtain_fabric_width': fabric_width, 'curtain_tile': tile,
                'curtain_rail_axis': convert(rail), 'curtain_depth_axis': convert(depth),
                'curtain_plane_origin': convert(origin)}

    def attach(obj, part):
        for key, value in metadata.items():
            obj[key] = value
        obj['curtain_part'] = part
        return obj

    nx, nz = 100, 32
    vertices, faces = [], []
    for j in range(nz+1):
        v = j/nz
        for i in range(nx+1):
            u = i/nx
            p = origin + rail * (width*u) + depth * (0.06 * math.sin(u*math.tau*folds))
            p.z = floor + height*v
            vertices.append(tuple(p))
    for j in range(nz):
        for i in range(nx):
            a = j*(nx+1)+i
            faces.append((a, a+1, a+nx+2, a+nx+1))
    obj = attach(_mesh(name, vertices, faces, material, 'curtains'), 'cloth')
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
        for loop in polygon.loop_indices:
            j, i = divmod(obj.data.loops[loop].vertex_index, nx+1)
            obj.data.uv_layers['UV0'].data[loop].uv = (i/nx*fabric_width/tile, j/nz*height/tile)
    for j, v, label in ((0, 0, 'bottom'), (nz, 1, 'top')):
        hem = attach(_tube(name+'.'+label, vertices[j*(nx+1):(j+1)*(nx+1)],
                           0.003, material, 'curtains'), 'hem')
        hem['curtain_v'] = v
    for i in range(folds+1):
        p = origin + rail*(width*i/folds)
        p.z = floor+height
        hook = attach(_tube(name+f'.hook.{i}', [p, p+Vector((0,0,0.035))],
                            0.003, material, 'curtains'), 'hook')
        hook['curtain_u'] = i/folds
    return obj
