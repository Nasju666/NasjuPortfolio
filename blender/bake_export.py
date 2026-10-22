"""Bakes the room's lighting into textures and exports a web-ready GLB.

    python blender/bake_export.py            # full quality (2048px props, 1024px room, 24 samples + denoise)
    BAKE_SIZE=512 BAKE_SAMPLES=8 python blender/bake_export.py   # quick test

Steps:
 1. Apply modifiers/transforms, sort meshes into: room (walls/floor/curtains), props,
    and clickable groups (hit_*). Screens (screen_*) and glowing parts (glow_*) are not baked.
 2. Give every baked mesh a second UV map packed into one of two texture atlases.
 3. Bake Cycles "Combined" (all lighting, shadows, bounce light), denoise, save as PNG
    with the scene's AgX look applied, so the browser can show it as-is without lights.
 4. Swap materials for the baked textures, join meshes per group, export blender/export/room-raw.glb
    and the camera settings to public/models/room-camera.json.
Then run `npm run room:compress` to make the final, small files in public/models/.
"""
import json
import math
import os
import time

import bpy  # must come before bmesh/mathutils when running as a Python module
import bmesh
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, 'export')
MODELS = os.path.join(ROOT, 'public', 'models')
# Props get the big atlas (that's where detail is); walls/floor are large and smooth.
SIZE = int(os.environ.get('BAKE_SIZE', 2048))
ROOM_SIZE = int(os.environ.get('BAKE_ROOM_SIZE', SIZE // 2))
SAMPLES = int(os.environ.get('BAKE_SAMPLES', 24))
os.makedirs(OUT, exist_ok=True)
os.makedirs(MODELS, exist_ok=True)

ROOM_ROOTS = {'room_shell', 'curtains', 'window'}


def log(*a):
    print('[bake]', *a, flush=True)


bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, 'room.blend'))
scene = bpy.context.scene
view_layer = bpy.context.view_layer


def select(objs, active=None):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    view_layer.objects.active = active or objs[0]


# ---------------------------------------------------------------------------
# 1. Classify, then flatten the hierarchy
# ---------------------------------------------------------------------------
def ancestor(o, test):
    p = o
    while p is not None:
        if test(p):
            return p
        p = p.parent
    return None


info = {}
for o in scene.objects:
    if o.type != 'MESH':
        continue
    hit = ancestor(o, lambda p: p.name.startswith('hit_'))
    if o.name.startswith('screen_'):
        kind = 'screen'
    elif o.name == 'window_view':
        kind = 'image'
    elif o.name.startswith('glow_'):
        kind = 'glow'
    else:
        kind = 'bake'
    info[o.name] = {
        'kind': kind,
        'hit': hit.name if hit else None,
        'room': ancestor(o, lambda p: p.name in ROOM_ROOTS) is not None,
    }

meshes = [bpy.data.objects[n] for n in info]
select(meshes)
bpy.ops.object.make_single_user(object=True, obdata=True, material=False)
bpy.ops.object.convert(target='MESH')  # applies bevel/solidify modifiers
bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
for o in list(scene.objects):
    if o.type == 'EMPTY':
        bpy.data.objects.remove(o)

objs = {n: bpy.data.objects[n] for n in info}
room = [objs[n] for n, i in info.items() if i['kind'] == 'bake' and i['room']]
props = [objs[n] for n, i in info.items() if i['kind'] == 'bake' and not i['room']]
log(f'{len(room)} room meshes, {len(props)} prop meshes, size {SIZE}, samples {SAMPLES}')


# ---------------------------------------------------------------------------
# 2. Lightmap UVs
# ---------------------------------------------------------------------------
# Less texture space for things that matter less (multiplies UV island size).
OBJECT_WEIGHT = {
    'desk_ped_l': 0.5, 'desk_ped_r': 0.5, 'desk_back': 0.3,
    'desk_apron': 0.5, 'curtain_l': 0.8, 'curtain_r': 0.6, 'curtain_rod': 0.5,
}
CAM_POS = scene.camera.matrix_world.translation.copy()


def front_facing(f, tol=0.0):
    return f.normal.dot((CAM_POS - f.calc_center_median()).normalized()) > tol


def mark_front_faces(o):
    """Select faces that point toward the camera. The website camera never moves from this
    position (it only turns), so faces pointing away can never be seen."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    for f in bm.faces:
        f.select_set(front_facing(f))
    bm.to_mesh(o.data)
    bm.free()


def scale_uvs(o):
    """Shrink islands by their per-face weight; hidden faces get zero area (no texture space)."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    uv = bm.loops.layers.uv['bake']
    wl = bm.faces.layers.float.get('uvw')
    for f in bm.faces:
        w = f[wl] if wl is not None else 1.0
        for l in f.loops:
            l[uv].uv = l[uv].uv * w if f.select else Vector((0.0, 0.0))
    bm.to_mesh(o.data)
    bm.free()


def unwrap(group):
    for o in group:
        uv = o.data.uv_layers.new(name='bake')
        o.data.uv_layers.active = uv
        mark_front_faces(o)
    select(group)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.0, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    for o in group:
        scale_uvs(o)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(rotate=True, scale=True, margin_method='FRACTION', margin=0.003,
                            shape_method='CONCAVE', udim_source='CLOSEST_UDIM')
    bpy.ops.object.mode_set(mode='OBJECT')


def delete_back_faces(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if not front_facing(f)], context='FACES')
    bm.to_mesh(o.data)
    bm.free()


def join(group, name):
    select(group)
    if len(group) > 1:
        bpy.ops.object.join()
    o = view_layer.objects.active
    o.name = name
    o.data.name = name
    return o


for o in room + props:
    w = OBJECT_WEIGHT.get(o.name, 1.0)
    if o.name.startswith('chair_') and any(k in o.name for k in ('leg', 'wheel', 'gas', 'seat_base')):
        w *= 0.5
    a = o.data.attributes.new('uvw', 'FLOAT', 'FACE')
    a.data.foreach_set('value', [w] * len(o.data.polygons))

# Image textures (e.g. the framed print) must keep reading their original UV map once the
# lightmap UV map is added and objects are joined.
for m in bpy.data.materials:
    if not m.node_tree:
        continue
    for n in list(m.node_tree.nodes):
        if n.type == 'TEX_IMAGE' and not n.inputs['Vector'].is_linked:
            uvn = m.node_tree.nodes.new('ShaderNodeUVMap')
            uvn.uv_map = 'UVMap'
            m.node_tree.links.new(uvn.outputs['UV'], n.inputs['Vector'])

hits = sorted({i['hit'] for i in info.values() if i['hit']})
hit_members = {h: [o for o in props if info[o.name]['hit'] == h] for h in hits}
static_props = [o for o in props if not info[o.name]['hit']]
room = [join(room, 'room_shell')]
hit_bodies = {h: join(m, 'mesh_' + h[4:]) for h, m in hit_members.items()}
props = [join(static_props, 'props_static')] + list(hit_bodies.values())
log(f'joined into {len(room) + len(props)} meshes')

unwrap(room)
unwrap(props)
if os.environ.get('UV_ONLY'):
    raise SystemExit


# ---------------------------------------------------------------------------
# 3. Bake + denoise
# ---------------------------------------------------------------------------
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = SAMPLES
scene.render.bake.margin = 16
scene.render.bake.margin_type = 'EXTEND'
scene.render.bake.use_clear = True


def bake(group, name, size, glossy):
    # Reflections depend on where you look from; baked from the wrong angle they show up as
    # bright patches (e.g. the ceiling light on the floor). Metals need them though, or they bake black.
    bk = scene.render.bake
    bk.use_pass_direct = bk.use_pass_indirect = True
    bk.use_pass_diffuse = bk.use_pass_transmission = bk.use_pass_emit = True
    bk.use_pass_glossy = glossy
    img = bpy.data.images.new(name, size, size, float_buffer=True, alpha=False)
    mats = {s.material for o in group for s in o.material_slots if s.material}
    for m in mats:
        nt = m.node_tree
        n = nt.nodes.get('BAKE_TARGET') or nt.nodes.new('ShaderNodeTexImage')
        n.name = 'BAKE_TARGET'
        n.image = img
        nt.nodes.active = n
    select(group)
    t = time.time()
    bpy.ops.object.bake(type='COMBINED')
    log(f'baked {name} in {time.time() - t:.0f}s')
    return img


def denoise_and_save(img, path):
    """Run Blender's denoiser over the baked image and save it with the AgX look applied."""
    sc = bpy.data.scenes.new('denoise_' + img.name)
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = 1
    sc.render.resolution_x = img.size[0]
    sc.render.resolution_y = img.size[1]
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = scene.view_settings.view_transform
    sc.view_settings.look = scene.view_settings.look
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGB'
    ng = bpy.data.node_groups.new('denoise', 'CompositorNodeTree')
    ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    a = ng.nodes.new('CompositorNodeImage')
    a.image = img
    d = ng.nodes.new('CompositorNodeDenoise')
    out = ng.nodes.new('NodeGroupOutput')
    ng.links.new(a.outputs['Image'], d.inputs['Image'])
    ng.links.new(d.outputs['Image'], out.inputs[0])
    sc.compositing_node_group = ng
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=sc.name)
    bpy.data.scenes.remove(sc)
    log('saved', path)


atlases = {}
for group, name, size, glossy in ((room, 'atlas_room', ROOM_SIZE, False), (props, 'atlas_props', SIZE, True)):
    img = bake(group, name, size, glossy)
    path = os.path.join(OUT, name + '.png')
    denoise_and_save(img, path)
    atlases[name] = path


# ---------------------------------------------------------------------------
# 4. Export materials, join, export
# ---------------------------------------------------------------------------
def flat_material(name, image_path=None, color=(1, 1, 1)):
    m = bpy.data.materials.new(name)
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Roughness'].default_value = 1.0
    b.inputs['Base Color'].default_value = (*color, 1)
    if image_path:
        t = m.node_tree.nodes.new('ShaderNodeTexImage')
        t.image = bpy.data.images.load(image_path, check_existing=True)
        m.node_tree.links.new(t.outputs['Color'], b.inputs['Base Color'])
    return m


def keep_only_uv(o, name):
    layers = o.data.uv_layers
    for l in [l for l in layers if l.name != name]:
        layers.remove(l)
    if len(layers):
        layers[0].name = 'UVMap'


def emission_color(o):
    for s in o.material_slots:
        b = s.material.node_tree.nodes.get('Principled BSDF') if s.material else None
        if b:
            c = b.inputs['Emission Color'].default_value
            return (c[0], c[1], c[2])
    return (1, 1, 1)


def source_image(o):
    for s in o.material_slots:
        if not s.material:
            continue
        for n in s.material.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.name != 'BAKE_TARGET' and n.image:
                return n.image
    return None


for o in room + props:
    delete_back_faces(o)

baked = {
    'atlas_room': flat_material('baked_room', atlases['atlas_room']),
    'atlas_props': flat_material('baked_props', atlases['atlas_props']),
}
for group, key in ((room, 'atlas_room'), (props, 'atlas_props')):
    for o in group:
        keep_only_uv(o, 'bake')
        o.data.materials.clear()
        o.data.materials.append(baked[key])

for n, i in info.items():
    o = objs[n]
    if i['kind'] in ('screen', 'image'):
        img = source_image(o)
        keep_only_uv(o, 'UVMap')
        m = flat_material('mat_' + n, bpy.path.abspath(img.filepath) if img else None)
        o.data.materials.clear()
        o.data.materials.append(m)
    elif i['kind'] == 'glow':
        c = emission_color(o)
        k = 1.0 / max(c)
        m = flat_material('mat_' + n, color=tuple(min(1.0, x * k) for x in c))
        o.data.materials.clear()
        o.data.materials.append(m)
        for l in list(o.data.uv_layers):
            o.data.uv_layers.remove(l)


for o in room + props:
    o.data.attributes.remove(o.data.attributes['uvw'])

join([room[0], props[0]] + [objs[n] for n, i in info.items() if i['kind'] == 'image'], 'room_static')
for h, body in hit_bodies.items():
    extras = [objs[n] for n, i in info.items() if i['hit'] == h and i['kind'] != 'bake']
    e = bpy.data.objects.new(h, None)
    scene.collection.objects.link(e)
    for o in [body] + extras:
        o.parent = e

for o in list(scene.objects):
    if o.type in ('LIGHT',):
        bpy.data.objects.remove(o)

# Camera settings for the website (converted to Y-up like the GLB)
cam = scene.camera
q = cam.matrix_world.to_quaternion()
fwd = q @ Vector((0, 0, -1))
up = q @ Vector((0, 1, 0))
yup = lambda v: [round(v.x, 5), round(v.z, 5), round(-v.y, 5)]
cam_json = {
    'position': yup(cam.matrix_world.translation),
    'forward': yup(fwd),
    'up': yup(up),
    'lens': cam.data.lens,
    'sensorWidth': cam.data.sensor_width,
    'shiftX': cam.data.shift_x,
    'shiftY': cam.data.shift_y,
    'aspect': scene.render.resolution_x / scene.render.resolution_y,
}
with open(os.path.join(MODELS, 'room-camera.json'), 'w') as f:
    json.dump(cam_json, f, indent=2)
bpy.data.objects.remove(cam)

tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in scene.objects if o.type == 'MESH')
log(f'{len(scene.objects)} objects, {tris} triangles')

raw = os.path.join(OUT, 'room-raw.glb')
bpy.ops.export_scene.gltf(
    filepath=raw,
    export_format='GLB',
    export_yup=True,
    export_apply=True,
    export_normals=False,
    export_texcoords=True,
    export_materials='EXPORT',
    export_cameras=False,
    export_lights=False,
    export_image_format='AUTO',
)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'room-baked.blend'))
log('exported', raw)
