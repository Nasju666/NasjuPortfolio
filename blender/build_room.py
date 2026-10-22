"""Builds the desk-corner room and saves it to blender/room.blend.

Run with Blender's Python module (no GPU needed):
    pip install bpy
    python blender/build_room.py
or with Blender itself:
    blender -b -P blender/build_room.py

Units are metres, Z is up. The back wall's inner face is at y = 0 and the room extends
toward -y. The right wall's inner face is at x = XR.

Clickable objects are grouped under empties named hit_<name>. The website looks those
names up (src/data/sections.ts). Screens that the website replaces with live content are
named screen_<name>; anything named glow_<name> gets a soft halo on the web.
"""
import math
import os

import bpy  # must come before bmesh when running as a Python module
import bmesh
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, 'textures')
OUT_BLEND = os.path.join(HERE, 'room.blend')

XR = 1.35          # right wall inner face
DESK_Z = 0.78      # desk top surface
RISER_Z = 0.92     # riser top surface
SHELF_Z = 1.64     # wall shelf top surface
D = math.radians


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def lin(hexstr):
    h = hexstr.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def rgba(hexstr):
    return (*lin(hexstr), 1.0)


def new_material(name):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    return m


def principled(name, color, rough=0.5, metal=0.0, emit=None, strength=0.0, coat=0.0, sheen=0.0):
    m = new_material(name)
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = rgba(color)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if coat:
        b.inputs['Coat Weight'].default_value = coat
    if sheen:
        b.inputs['Sheen Weight'].default_value = sheen
    if emit:
        b.inputs['Emission Color'].default_value = rgba(emit)
        b.inputs['Emission Strength'].default_value = strength
    return m


def node(nt, kind, loc=(0, 0)):
    n = nt.nodes.new(kind)
    n.location = loc
    return n


def wood(name, dark, light, rough=0.32, stretch=(0.6, 14, 14), coat=0.25):
    """Varnished wood: stretched noise gives streaky grain along local X."""
    m = principled(name, dark, rough, coat=coat)
    nt = m.node_tree
    L = nt.links
    b = nt.nodes['Principled BSDF']
    tc = node(nt, 'ShaderNodeTexCoord', (-1200, 0))
    mp = node(nt, 'ShaderNodeMapping', (-1000, 0))
    mp.inputs['Scale'].default_value = stretch
    L.new(tc.outputs['Object'], mp.inputs['Vector'])
    n1 = node(nt, 'ShaderNodeTexNoise', (-800, 100))
    n1.inputs['Scale'].default_value = 3.0
    n1.inputs['Detail'].default_value = 8
    n1.inputs['Distortion'].default_value = 1.5
    L.new(mp.outputs['Vector'], n1.inputs['Vector'])
    ramp = node(nt, 'ShaderNodeValToRGB', (-550, 100))
    e = ramp.color_ramp.elements
    e[0].position, e[0].color = 0.35, rgba(dark)
    e[1].position, e[1].color = 0.7, rgba(light)
    L.new(n1.outputs['Fac'], ramp.inputs['Fac'])
    L.new(ramp.outputs['Color'], b.inputs['Base Color'])
    bump = node(nt, 'ShaderNodeBump', (-300, -200))
    bump.inputs['Strength'].default_value = 0.04
    L.new(n1.outputs['Fac'], bump.inputs['Height'])
    L.new(bump.outputs['Normal'], b.inputs['Normal'])
    return m


def floor_planks(name):
    m = principled(name, '#4a2418', 0.38, coat=0.15)
    nt = m.node_tree
    L = nt.links
    b = nt.nodes['Principled BSDF']
    tc = node(nt, 'ShaderNodeTexCoord', (-1300, 0))
    brick = node(nt, 'ShaderNodeTexBrick', (-900, 150))
    brick.offset = 0.5
    brick.squash = 1.0
    brick.inputs['Color1'].default_value = rgba('#5a2c1c')
    brick.inputs['Color2'].default_value = rgba('#3f1d13')
    brick.inputs['Mortar'].default_value = rgba('#1e0d08')
    brick.inputs['Scale'].default_value = 1.0
    brick.inputs['Mortar Size'].default_value = 0.0025
    brick.inputs['Bias'].default_value = 0.0
    brick.inputs['Brick Width'].default_value = 1.3
    brick.inputs['Row Height'].default_value = 0.16
    L.new(tc.outputs['Object'], brick.inputs['Vector'])
    mp = node(nt, 'ShaderNodeMapping', (-1100, -150))
    mp.inputs['Scale'].default_value = (0.8, 18, 18)
    L.new(tc.outputs['Object'], mp.inputs['Vector'])
    grain = node(nt, 'ShaderNodeTexNoise', (-900, -150))
    grain.inputs['Scale'].default_value = 4
    grain.inputs['Detail'].default_value = 8
    L.new(mp.outputs['Vector'], grain.inputs['Vector'])
    mix = node(nt, 'ShaderNodeMix', (-500, 100))
    mix.data_type = 'RGBA'
    mix.blend_type = 'OVERLAY'
    mix.inputs['Factor'].default_value = 0.45
    L.new(brick.outputs['Color'], mix.inputs['A'])
    L.new(grain.outputs['Color'], mix.inputs['B'])
    L.new(mix.outputs['Result'], b.inputs['Base Color'])
    bump = node(nt, 'ShaderNodeBump', (-300, -250))
    bump.inputs['Strength'].default_value = 0.25
    L.new(brick.outputs['Fac'], bump.inputs['Height'])
    L.new(bump.outputs['Normal'], b.inputs['Normal'])
    return m


def plaster(name, color):
    m = principled(name, color, 0.92)
    nt = m.node_tree
    L = nt.links
    b = nt.nodes['Principled BSDF']
    n = node(nt, 'ShaderNodeTexNoise', (-700, -200))
    n.inputs['Scale'].default_value = 180
    n.inputs['Detail'].default_value = 6
    bump = node(nt, 'ShaderNodeBump', (-400, -200))
    bump.inputs['Strength'].default_value = 0.18
    L.new(n.outputs['Fac'], bump.inputs['Height'])
    L.new(bump.outputs['Normal'], b.inputs['Normal'])
    big = node(nt, 'ShaderNodeTexNoise', (-900, 150))
    big.inputs['Scale'].default_value = 2.5
    ramp = node(nt, 'ShaderNodeValToRGB', (-600, 150))
    ramp.color_ramp.elements[0].color = rgba(color)
    ramp.color_ramp.elements[1].color = tuple(min(1, c * 1.12) for c in lin(color)) + (1,)
    L.new(big.outputs['Fac'], ramp.inputs['Fac'])
    L.new(ramp.outputs['Color'], b.inputs['Base Color'])
    return m


def image_material(name, filename, emissive=True, strength=1.0, rough=0.4):
    m = new_material(name)
    nt = m.node_tree
    L = nt.links
    img = node(nt, 'ShaderNodeTexImage', (-500, 0))
    img.image = bpy.data.images.load(os.path.join(TEX, filename))
    b = nt.nodes['Principled BSDF']
    b.inputs['Roughness'].default_value = rough
    if emissive:
        b.inputs['Base Color'].default_value = (0, 0, 0, 1)
        b.inputs['Roughness'].default_value = 0.15
        b.inputs['Emission Strength'].default_value = strength
        L.new(img.outputs['Color'], b.inputs['Emission Color'])
    else:
        L.new(img.outputs['Color'], b.inputs['Base Color'])
    return m


def link(o, parent=None):
    bpy.context.scene.collection.objects.link(o)
    if parent is not None:
        o.parent = parent
    return o


def hide_from_bake(o):
    """Photo quads are drawn by the website; keep them out of the lighting so the paper bakes clean."""
    for a in ('visible_camera', 'visible_diffuse', 'visible_glossy', 'visible_transmission',
              'visible_volume_scatter', 'visible_shadow'):
        setattr(o, a, False)
    return o


def empty(name, parent=None):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.1
    return link(e, parent)


def from_bmesh(name, bm, mats, parent=None, loc=(0, 0, 0), rot=(0, 0, 0), smooth=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in (mats if isinstance(mats, (list, tuple)) else [mats]):
        me.materials.append(m)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    o.location = loc
    o.rotation_euler = rot
    return link(o, parent)


def add_bevel(o, width, segments=3):
    mod = o.modifiers.new('Bevel', 'BEVEL')
    mod.width = width
    mod.segments = segments
    mod.limit_method = 'ANGLE'
    mod.angle_limit = D(40)
    mod.harden_normals = True
    return o


def box(name, size, loc, mat, parent=None, bev=0.006, rot=(0, 0, 0), segs=3):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= size[0]
        v.co.y *= size[1]
        v.co.z *= size[2]
    o = from_bmesh(name, bm, mat, parent, loc, rot)
    if bev:
        add_bevel(o, min(bev, min(size) * 0.45), segs)
    return o


def cyl(name, r, h, loc, mat, parent=None, segs=40, r2=None, rot=(0, 0, 0), bev=0.003):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs, radius1=r,
                          radius2=r if r2 is None else r2, depth=h)
    o = from_bmesh(name, bm, mat, parent, loc, rot)
    if bev:
        add_bevel(o, min(bev, h * 0.45), 2)
    return o


def sphere(name, r, loc, mat, parent=None, scale=(1, 1, 1), rot=(0, 0, 0), segs=24):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=segs // 2 + 2, radius=r)
    for v in bm.verts:
        v.co.x *= scale[0]
        v.co.y *= scale[1]
        v.co.z *= scale[2]
    return from_bmesh(name, bm, mat, parent, loc, rot)


def torus(name, R, r, loc, mat, parent=None, arc=2 * math.pi, segu=48, segv=14, rot=(0, 0, 0)):
    """Torus in the XZ plane... actually XY plane, around Z. `arc` < 2pi makes an open arch."""
    bm = bmesh.new()
    closed = arc >= 2 * math.pi - 1e-6
    nu = segu if closed else segu + 1
    rings = []
    for i in range(nu):
        a = arc * i / segu
        c = Vector((math.cos(a), math.sin(a), 0))
        ring = []
        for j in range(segv):
            b = 2 * math.pi * j / segv
            p = c * (R + r * math.cos(b)) + Vector((0, 0, r * math.sin(b)))
            ring.append(bm.verts.new(p))
        rings.append(ring)
    for i in range(segu):
        a, b_ = rings[i], rings[(i + 1) % nu]
        for j in range(segv):
            bm.faces.new((a[j], b_[j], b_[(j + 1) % segv], a[(j + 1) % segv]))
    if not closed:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return from_bmesh(name, bm, mat, parent, loc, rot)


def quad(name, w, h, loc, mat, parent=None, rot=(0, 0, 0)):
    """Flat rectangle with a 0..1 UV map, facing -Y (toward the camera side)."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')
    vs = [bm.verts.new((x * w / 2, 0, z * h / 2)) for x, z in [(-1, -1), (1, -1), (1, 1), (-1, 1)]]
    f = bm.faces.new(vs)
    for loop, (u, v) in zip(f.loops, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        loop[uv].uv = (u, v)
    f.normal_update()
    if f.normal.y > 0:
        f.normal_flip()
    return from_bmesh(name, bm, mat, parent, loc, rot, smooth=False)


def plane(name, corners, mat, parent=None, cuts=8):
    """Flat polygon from 4 corners (counter-clockwise as seen from the visible side), subdivided
    a little so baked lighting has vertices to sit on."""
    bm = bmesh.new()
    vs = [bm.verts.new(c) for c in corners]
    f = bm.faces.new(vs)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    return from_bmesh(name, bm, mat, parent, smooth=False)


def foam_panel(name, w, h, loc, mat, parent=None, cell=0.075, depth=0.045):
    """Acoustic foam: a back board covered in little pyramids, facing -Y."""
    bm = bmesh.new()
    nx, nz = int(w / cell), int(h / cell)
    w, h = nx * cell, nz * cell
    for i in range(nx):
        for j in range(nz):
            x0, z0 = -w / 2 + i * cell, -h / 2 + j * cell
            a = bm.verts.new((x0, 0, z0))
            b = bm.verts.new((x0 + cell, 0, z0))
            c = bm.verts.new((x0 + cell, 0, z0 + cell))
            d = bm.verts.new((x0, 0, z0 + cell))
            # alternate pyramid apex height a little so it doesn't look stamped
            tip = bm.verts.new((x0 + cell / 2, -depth * (0.85 + 0.15 * ((i + j) % 2)), z0 + cell / 2))
            for e1, e2 in [(a, b), (b, c), (c, d), (d, a)]:
                bm.faces.new((e1, e2, tip))
    back = [bm.verts.new((x, 0.012, z)) for x, z in [(-w / 2, -h / 2), (-w / 2, h / 2), (w / 2, h / 2), (w / 2, -h / 2)]]
    bm.faces.new(back)
    # Winding above already points every face outward (toward -Y). Don't recalc normals here:
    # on this open mesh it flips some pyramid faces, and the web export deletes "back" faces.
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    return from_bmesh(name, bm, mat, parent, loc, smooth=False)


def curtain(name, w, h, loc, mat, parent=None, folds=7, amp=0.045):
    """Hanging curtain on the right wall: a wavy sheet in the YZ plane, facing -X."""
    bm = bmesh.new()
    nu, nv = 120, 6
    grid = []
    for i in range(nu + 1):
        t = i / nu
        y = -t * w
        x = -amp * (0.5 + 0.5 * math.sin(t * folds * 2 * math.pi))
        col = []
        for j in range(nv + 1):
            z = h * j / nv
            # folds flare out a little toward the floor
            col.append(bm.verts.new((x * (1.25 - 0.35 * j / nv), y, z)))
        grid.append(col)
    for i in range(nu):
        for j in range(nv):
            bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = from_bmesh(name, bm, mat, parent, loc)
    sol = o.modifiers.new('Thickness', 'SOLIDIFY')
    sol.thickness = 0.01
    return o


# ----------------------------------------------------------------------------
# Scene
# ----------------------------------------------------------------------------
def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    M = {
        'wall': plaster('wall', '#c79f84'),
        'floor': floor_planks('floor'),
        'trim': wood('trim', '#2e150d', '#4a2416', 0.4, coat=0.1),
        'desk_wood': wood('desk_wood', '#3a190c', '#6b3519', 0.3),
        'shelf_wood': wood('shelf_wood', '#43200e', '#74401f', 0.32),
        'black': principled('black_matte', '#16171c', 0.55),
        'black_gloss': principled('black_gloss', '#0d0e12', 0.18, coat=0.5),
        'foam': principled('foam', '#18181b', 0.95),
        'speaker': principled('speaker', '#3e3b5e', 0.45),
        'speaker_cone': principled('speaker_cone', '#1d1c2a', 0.6),
        'silver': principled('silver', '#c8ccd6', 0.28, metal=1.0),
        'white_plastic': principled('white_plastic', '#eceef4', 0.35),
        'keycap_purple': principled('keycap_purple', '#6e62c9', 0.4),
        'deskmat': principled('deskmat', '#1d1f26', 0.85),
        'phone': principled('phone_body', '#5aa9e6', 0.3),
        'ceramic': principled('ceramic', '#f5f3f0', 0.2, coat=0.3),
        'coffee': principled('coffee', '#2b160b', 0.08),
        'curtain': principled('curtain', '#284457', 0.85, sheen=0.5),
        'gold': principled('gold', '#e8b445', 0.22, metal=1.0),
        'silver_trophy': principled('silver_trophy', '#d7dbe3', 0.2, metal=1.0),
        'pot': principled('pot', '#f2f0ec', 0.45),
        'leaf': principled('leaf', '#3f8c4a', 0.5),
        'leaf_dark': principled('leaf_dark', '#2e6e3a', 0.5),
        'soil': principled('soil', '#2a1b12', 0.9),
        'chair_frame': principled('chair_frame', '#8f939c', 0.45),
        'chair_mesh': principled('chair_mesh', '#7d818a', 0.7, sheen=0.3),
        'chair_seat': principled('chair_seat', '#7f838c', 0.75, sheen=0.4),
        'chair_dark': principled('chair_dark', '#3a3c42', 0.5),
        'cork': principled('cork', '#b98a5c', 0.9),
        'paper': principled('paper', '#f6f4ef', 0.8),
        'led_blue': principled('led_blue', '#000000', 0.5, emit='#4f86ff', strength=18),
        'fan_ring': principled('fan_ring', '#000000', 0.5, emit='#5aa0ff', strength=10),
        'glass_dark': principled('glass_dark', '#0b0e16', 0.06, coat=1.0),
        'book_a': principled('book_a', '#3b47b5', 0.6),
        'book_b': principled('book_b', '#c9483e', 0.6),
        'book_c': principled('book_c', '#e8b445', 0.6),
        'book_d': principled('book_d', '#2f8f6e', 0.6),
        'book_e': principled('book_e', '#ece7dd', 0.6),
        'red': principled('red_lanyard', '#c9483e', 0.6),
        'clip_board': principled('clipboard', '#8a5a33', 0.5),
        'screen_monitor': image_material('screen_monitor', 'screen_monitor.png', strength=1.6),
        'screen_laptop': image_material('screen_laptop', 'screen_laptop.png', strength=1.3),
        'screen_clock': image_material('screen_clock', 'screen_clock.png', strength=2.5),
        'screen_phone': image_material('screen_phone', 'screen_phone.png', strength=1.0),
        'poster': image_material('poster_print', 'poster.png', emissive=False, rough=0.7),
        # photo quads carry a tiny placeholder image only so the export keeps their UV map
        'photo_slot': image_material('photo_slot', 'photo_slot.png', emissive=False, rough=0.8),
        'window_night': image_material('window_view', 'window_night.png', strength=1.2),
    }

    # --- Room shell -------------------------------------------------------
    shell = empty('room_shell')
    # Single-sided planes (only the faces you can see), so the bake doesn't waste texture space.
    WL, WD, WH = XR - 5.0, -4.8, 4.0
    plane('floor', [(WL, WD, 0), (XR, WD, 0), (XR, 0, 0), (WL, 0, 0)], M['floor'], shell)
    plane('wall_back', [(WL, 0, 0), (XR, 0, 0), (XR, 0, WH), (WL, 0, WH)], M['wall'], shell)
    plane('wall_right', [(XR, 0, 0), (XR, WD, 0), (XR, WD, WH), (XR, 0, WH)], M['wall'], shell)
    box('baseboard_back', (5.0, 0.02, 0.09), (XR - 2.5, -0.01, 0.045), M['trim'], shell, bev=0.003)
    box('baseboard_right', (0.02, 4.8, 0.09), (XR - 0.01, -2.4, 0.045), M['trim'], shell, bev=0.003)

    # --- Desk ---------------------------------------------------------------
    desk = empty('desk')
    x0, x1 = -1.50, 0.95
    dx, dw = (x0 + x1) / 2, x1 - x0
    box('desk_top', (dw, 0.86, 0.05), (dx, -0.45, DESK_Z - 0.025), M['desk_wood'], desk, bev=0.018, segs=4)
    # black body: two pedestals, back panel, apron
    box('desk_ped_l', (0.42, 0.78, DESK_Z - 0.05), (x0 + 0.23, -0.43, (DESK_Z - 0.05) / 2), M['black'], desk, bev=0.01)
    box('desk_ped_r', (0.42, 0.78, DESK_Z - 0.05), (x1 - 0.23, -0.43, (DESK_Z - 0.05) / 2), M['black'], desk, bev=0.01)
    box('desk_back', (dw - 0.8, 0.03, DESK_Z - 0.05), (dx, -0.06, (DESK_Z - 0.05) / 2), M['black'], desk, bev=0.004)
    box('desk_apron', (dw - 0.84, 0.7, 0.07), (dx, -0.44, DESK_Z - 0.085), M['black'], desk, bev=0.006)
    # pull-out tray (in the reference it holds a piano; here it's the coach's tray)
    tray_y = -0.8
    box('tray', (dw - 0.9, 0.62, 0.025), (dx, tray_y, 0.6), M['desk_wood'], desk, bev=0.008)
    box('tray_lip', (dw - 0.9, 0.025, 0.05), (dx, tray_y - 0.31, 0.62), M['black'], desk, bev=0.006)
    # riser (hutch) across the back of the desk
    rx0, rx1 = -1.32, 0.38
    box('riser_top', (rx1 - rx0, 0.36, 0.03), ((rx0 + rx1) / 2, -0.23, RISER_Z - 0.015), M['desk_wood'], desk, bev=0.01)
    for i, xx in enumerate((rx0 + 0.02, rx1 - 0.02, (rx0 + rx1) / 2)):
        box(f'riser_leg_{i}', (0.03, 0.34, RISER_Z - DESK_Z - 0.03), (xx, -0.23, (RISER_Z + DESK_Z - 0.03) / 2), M['black'], desk, bev=0.004)
    led = box('glow_riser_led', (rx1 - rx0 - 0.06, 0.008, 0.006), ((rx0 + rx1) / 2, -0.405, RISER_Z - 0.035), M['led_blue'], desk, bev=0)

    # --- Monitor (Projects) ------------------------------------------------------
    hit = empty('hit_monitor')
    mx, my = -0.47, -0.2
    box('monitor_base', (0.3, 0.2, 0.012), (mx, my, RISER_Z + 0.006), M['silver'], hit, bev=0.004)
    box('monitor_neck', (0.05, 0.03, 0.2), (mx, my + 0.05, RISER_Z + 0.11), M['silver'], hit, bev=0.008)
    mon = box('monitor_body', (0.86, 0.035, 0.38), (mx, my + 0.02, RISER_Z + 0.27), M['black_gloss'], hit, bev=0.01)
    mon.rotation_euler = (D(-4), 0, 0)
    scr = quad('screen_monitor', 0.83, 0.355, (mx, my + 0.001, RISER_Z + 0.27), M['screen_monitor'], hit, rot=(D(-4), 0, 0))
    # keyboard, mouse and desk mat belong to the monitor group
    box('deskmat', (0.95, 0.34, 0.004), (-0.42, -0.64, DESK_Z + 0.002), M['deskmat'], hit, bev=0.002)
    box('keyboard', (0.36, 0.125, 0.022), (-0.5, -0.64, DESK_Z + 0.015), M['white_plastic'], hit, bev=0.006)
    bm = bmesh.new()
    kw, kd = 0.0185, 0.0185
    for r in range(5):
        for c in range(17):
            x = -0.5 - 0.165 + c * 0.0206 + (r % 2) * 0.004
            y = -0.64 + 0.045 - r * 0.0215
            cube = bmesh.ops.create_cube(bm, size=1.0)['verts']
            for v in cube:
                v.co.x = v.co.x * kw + x
                v.co.y = v.co.y * kd + y
                v.co.z = v.co.z * 0.012 + DESK_Z + 0.031
    keys = from_bmesh('keycaps', bm, [M['white_plastic'], M['keycap_purple']], hit, smooth=False)
    for i, p in enumerate(keys.data.polygons):
        if (i // 6) % 9 == 4 or (i // 6) in (16, 33, 50, 67, 84):
            p.material_index = 1
    add_bevel(keys, 0.0025, 2)
    sphere('mouse', 0.032, (-0.12, -0.63, DESK_Z + 0.012), M['white_plastic'], hit, scale=(0.95, 1.5, 0.55))

    # headphones hanging on the monitor's top-right corner (decor, part of monitor)
    hp = empty('headphones', hit)
    hp.location = (mx + 0.36, my + 0.02, RISER_Z + 0.43)
    hp.rotation_euler = (0, D(12), D(-18))
    torus('headband', 0.085, 0.011, (0, 0, 0), M['speaker'], hp, arc=math.pi, rot=(D(90), 0, 0))
    for s in (-1, 1):
        cyl(f'ear_cup_{s}', 0.045, 0.035, (s * 0.088, 0, -0.025), M['speaker'], hp, rot=(0, D(90), 0), bev=0.012)

    # --- Speakers (decor) -----------------------------------------------------------
    for name, sx, sy, sz in (('speaker_l', -1.12, -0.22, RISER_Z), ('speaker_r', 0.18, -0.22, RISER_Z)):
        sp = empty(name)
        sp.location = (sx, sy, sz)
        sp.rotation_euler = (0, 0, D(12 if sx < 0 else -12))
        box(name + '_body', (0.17, 0.2, 0.25), (0, 0, 0.125), M['speaker'], sp, bev=0.02, segs=4)
        cyl(name + '_woofer_ring', 0.062, 0.01, (0, -0.1, 0.085), M['speaker_cone'], sp, rot=(D(90), 0, 0), bev=0.004)
        sphere(name + '_woofer_dome', 0.03, (0, -0.103, 0.085), M['speaker_cone'], sp, scale=(1, 0.35, 1))
        cyl(name + '_tweeter', 0.03, 0.01, (0, -0.1, 0.195), M['speaker_cone'], sp, rot=(D(90), 0, 0), bev=0.004)

    # --- PC case (Games) --------------------------------------------------------------
    hit = empty('hit_pc')
    pc = empty('pc', hit)
    pc.location = (0.66, -0.34, DESK_Z)
    pc.rotation_euler = (0, 0, D(-8))
    W_, Dp, H_ = 0.24, 0.44, 0.46
    box('pc_body', (W_, Dp, H_), (0, 0, H_ / 2), M['black_gloss'], pc, bev=0.012)
    box('pc_glass', (0.006, Dp - 0.05, H_ - 0.06), (-W_ / 2 - 0.002, 0, H_ / 2), M['glass_dark'], pc, bev=0.002)
    for k in range(3):
        z = 0.085 + k * 0.145
        torus(f'glow_pc_fan_{k}', 0.05, 0.007, (0, -Dp / 2 - 0.004, z), M['fan_ring'], pc, rot=(D(90), 0, 0), segv=8)
        cyl(f'pc_fan_hub_{k}', 0.018, 0.006, (0, -Dp / 2 - 0.003, z), M['black'], pc, rot=(D(90), 0, 0), bev=0.002)
        # same fans seen through the side glass
        torus(f'glow_pc_inner_{k}', 0.05, 0.006, (-W_ / 2 + 0.03, 0.02, z), M['fan_ring'], pc, rot=(0, D(90), 0), segv=8)
    box('pc_top_vent', (W_ - 0.04, Dp - 0.06, 0.004), (0, 0, H_ + 0.001), M['black'], pc, bev=0.001)
    # gamepad next to the case
    gp = empty('gamepad', hit)
    gp.location = (0.42, -0.72, DESK_Z + 0.018)
    gp.rotation_euler = (0, 0, D(20))
    box('gamepad_body', (0.13, 0.06, 0.028), (0, 0, 0), M['black'], gp, bev=0.012)
    for s in (-1, 1):
        sphere(f'gamepad_grip_{s}', 0.03, (s * 0.055, -0.025, -0.002), M['black'], gp, scale=(1, 1.3, 0.7))
        cyl(f'gamepad_stick_{s}', 0.009, 0.012, (s * 0.03, -0.004, 0.018), M['speaker_cone'], gp, bev=0.003)

    # --- Laptop (Work) -----------------------------------------------------------------
    hit = empty('hit_laptop')
    lp = empty('laptop', hit)
    lp.location = (-1.17, -0.62, DESK_Z)
    lp.rotation_euler = (0, 0, D(22))
    box('laptop_base', (0.32, 0.22, 0.014), (0, 0, 0.007), M['silver'], lp, bev=0.004)
    lid = empty('laptop_lid', lp)
    lid.location = (0, 0.11, 0.014)
    lid.rotation_euler = (D(-14), 0, 0)
    box('laptop_lid_shell', (0.32, 0.008, 0.21), (0, 0.004, 0.105), M['silver'], lid, bev=0.003)
    quad('screen_laptop', 0.3, 0.19, (0, -0.0005, 0.107), M['screen_laptop'], lid)

    # --- Phone (Contact) ------------------------------------------------------------------
    hit = empty('hit_phone')
    ph = empty('phone', hit)
    ph.location = (-0.86, -0.75, DESK_Z + 0.004)
    ph.rotation_euler = (0, 0, D(-12))
    box('phone_body', (0.075, 0.155, 0.008), (0, 0, 0), M['phone'], ph, bev=0.004)
    scr = quad('screen_phone', 0.068, 0.146, (0, 0, 0.0042), M['screen_phone'], ph, rot=(D(90), 0, 0))

    # --- Mug (decor) ---------------------------------------------------------------------
    mug = empty('mug')
    mug.location = (0.3, -0.62, DESK_Z)
    cyl('saucer', 0.065, 0.008, (0, 0, 0.004), M['ceramic'], mug, r2=0.055, bev=0.003)
    cyl('mug_body', 0.035, 0.065, (0, 0, 0.041), M['ceramic'], mug, r2=0.04, bev=0.004)
    cyl('mug_coffee', 0.036, 0.002, (0, 0, 0.068), M['coffee'], mug, bev=0)
    torus('mug_handle', 0.019, 0.006, (0.045, 0, 0.042), M['ceramic'], mug, rot=(D(90), 0, 0))

    # --- Coaching tray: clipboard + whistle -------------------------------------------------
    hit = empty('hit_clipboard')
    cb = empty('clipboard', hit)
    cb.location = (-0.35, -0.86, 0.6125)
    cb.rotation_euler = (0, 0, D(-6))
    box('clipboard_board', (0.24, 0.32, 0.006), (0, 0, 0.003), M['clip_board'], cb, bev=0.003)
    box('clipboard_paper', (0.21, 0.27, 0.001), (0, -0.01, 0.0065), M['paper'], cb, bev=0)
    box('clipboard_clip', (0.09, 0.03, 0.012), (0, 0.145, 0.01), M['silver'], cb, bev=0.003)
    for r in range(7):
        box(f'clip_line_{r}', (0.15 - (r % 3) * 0.03, 0.004, 0.0005), (-0.015, 0.09 - r * 0.03, 0.0072), M['speaker_cone'], cb, bev=0)
    # a simple 5-player formation sketch
    for k, (px, py) in enumerate([(-0.05, -0.08), (0.05, -0.08), (0, -0.04), (-0.06, -0.11), (0.06, -0.11)]):
        cyl(f'clip_dot_{k}', 0.007, 0.0006, (px, py, 0.0072), M['red'], cb, bev=0)
    wh = empty('whistle', hit)
    wh.location = (0.02, -0.88, 0.62)
    wh.rotation_euler = (0, 0, D(30))
    cyl('whistle_body', 0.018, 0.03, (0, 0, 0), M['silver'], wh, rot=(D(90), 0, 0), bev=0.004)
    box('whistle_mouth', (0.014, 0.04, 0.01), (0, -0.03, 0.006), M['silver'], wh, bev=0.003)
    torus('whistle_lanyard', 0.09, 0.003, (0.02, 0.1, -0.012), M['red'], wh, rot=(0, 0, 0), segv=6)

    # --- Wall shelf -------------------------------------------------------------------------
    shelf = empty('shelf')
    box('shelf_board', (1.85, 0.22, 0.04), (-0.47, -0.11, SHELF_Z - 0.02), M['shelf_wood'], shelf, bev=0.008)
    for xx in (-1.2, 0.26):
        box(f'shelf_bracket_{xx}', (0.025, 0.16, 0.025), (xx, -0.08, SHELF_Z - 0.052), M['black'], shelf, bev=0.003)

    def plant(name, x, y, z, parent, scale=1.0):
        p = empty(name, parent)
        p.location = (x, y, z)
        p.scale = (scale,) * 3
        cyl(name + '_pot', 0.055, 0.09, (0, 0, 0.045), M['pot'], p, r2=0.065, bev=0.006)
        cyl(name + '_soil', 0.058, 0.004, (0, 0, 0.086), M['soil'], p, bev=0)
        for k in range(9):
            a = k / 9 * 2 * math.pi + (k % 2) * 0.3
            tilt = D(35 + (k % 3) * 12)
            leaf = sphere(f'{name}_leaf_{k}', 0.05, (math.cos(a) * 0.035, math.sin(a) * 0.035, 0.13 + (k % 3) * 0.012),
                          M['leaf'] if k % 2 else M['leaf_dark'], p, scale=(0.42, 1.0, 0.12), segs=16)
            leaf.rotation_euler = (tilt, 0, a - math.pi / 2)

    plant('plant_shelf', -1.27, -0.1, SHELF_Z, shelf)

    # Books (Skills)
    hit = empty('hit_books')
    bx = -1.12
    mats = ['book_a', 'book_e', 'book_b', 'book_d', 'book_c', 'book_a', 'book_e', 'book_b']
    for k, mname in enumerate(mats):
        th = 0.024 + (k * 7 % 5) * 0.004
        hgt = 0.17 + (k * 5 % 4) * 0.018
        box(f'book_{k}', (th, 0.15, hgt), (bx + th / 2, -0.1, SHELF_Z + hgt / 2), M[mname], hit, bev=0.003)
        bx += th + 0.002
    lean = box('book_leaning', (0.026, 0.15, 0.19), (bx + 0.045, -0.1, SHELF_Z + 0.093), M['book_d'], hit, bev=0.003)
    lean.rotation_euler = (0, D(-24), 0)
    box('bookend', (0.012, 0.11, 0.12), (bx + 0.1, -0.1, SHELF_Z + 0.06), M['black'], hit, bev=0.003)

    # Clock (decor, live time on the web)
    ck = empty('clock')
    ck.location = (-0.6, -0.11, SHELF_Z)
    box('clock_body', (0.26, 0.085, 0.1), (0, 0, 0.05), M['black_gloss'], ck, bev=0.012)
    quad('screen_clock', 0.22, 0.075, (0, -0.0435, 0.05), M['screen_clock'], ck)

    # Trophies (Achievements)
    hit = empty('hit_trophies')

    def trophy(name, x, mat, s=1.0):
        t = empty(name, hit)
        t.location = (x, -0.1, SHELF_Z)
        t.scale = (s,) * 3
        box(name + '_base', (0.075, 0.075, 0.035), (0, 0, 0.0175), M['black_gloss'], t, bev=0.004)
        box(name + '_plate', (0.04, 0.002, 0.014), (0, -0.0385, 0.018), M['gold'], t, bev=0)
        cyl(name + '_stem', 0.008, 0.06, (0, 0, 0.065), mat, t, bev=0.002)
        cyl(name + '_foot', 0.022, 0.01, (0, 0, 0.04), mat, t, bev=0.003)
        cyl(name + '_cup', 0.045, 0.075, (0, 0, 0.13), mat, t, r2=0.018, bev=0.003, rot=(D(180), 0, 0))
        for side in (-1, 1):
            torus(name + f'_handle_{side}', 0.022, 0.004, (side * 0.045, 0, 0.14), mat, t, arc=math.pi, rot=(D(90), 0, D(-90 if side > 0 else 90)), segv=8)

    trophy('trophy_finalist_1', -0.36, M['gold'], 1.15)
    trophy('trophy_finalist_2', -0.22, M['gold'], 1.15)
    trophy('trophy_other', -0.09, M['silver_trophy'], 0.9)

    # Framed print (About), standing on the shelf and leaning on the wall
    hit = empty('hit_poster')
    fr = empty('frame', hit)
    fr.location = (0.15, -0.06, SHELF_Z)
    fr.rotation_euler = (D(-7), 0, D(-4))
    box('frame_border', (0.32, 0.018, 0.4), (0, 0, 0.2), M['black_gloss'], fr, bev=0.004)
    quad('poster_print', 0.28, 0.336, (0, -0.0095, 0.2), M['poster'], fr)
    # the photo in the print is drawn by the website (screen_print_photo), over a plain baked mat
    pp = quad('screen_print_photo', 0.22, 0.264, (0, -0.0111, 0.212), M['photo_slot'], fr)
    hide_from_bake(pp)

    plant('plant_shelf_r', 0.36, -0.1, SHELF_Z, shelf, 0.9)

    # --- Corkboard (Organizations), left of the shelf --------------------------------------------
    hit = empty('hit_corkboard')
    cx, cz = -1.8, 1.9
    box('cork_frame', (0.7, 0.03, 0.98), (cx, -0.015, cz), M['shelf_wood'], hit, bev=0.006)
    box('cork_board', (0.64, 0.012, 0.92), (cx, -0.032, cz), M['cork'], hit, bev=0)
    # Seven pinned photo cards (polaroid style). The paper is baked; the photo itself is a
    # screen_photo_<k> quad drawn by the website on top of the baked paper, so it picks up the
    # paper's lighting and pin shadow and can be swapped by editing content (Organizations photos).
    CARD_W, CARD_H = 0.19, 0.17
    PH_W, PH_H = 0.17, 0.1275  # 4:3 photo area
    PH_TOP = 0.024  # paper above the photo, room for the pin
    cards = [(-0.21, 0.28, 3), (0.0, 0.29, -4), (0.21, 0.27, 2),
             (-0.12, 0.0, -3), (0.13, 0.01, 4),
             (-0.15, -0.27, 4), (0.08, -0.27, -3)]
    for k, (ox, oz, ang) in enumerate(cards):
        slot = empty(f'cork_slot_{k}', hit)
        slot.location = (cx + ox, -0.04, cz + oz)
        slot.rotation_euler = (0, D(ang), 0)
        box(f'cork_card_{k}', (CARD_W, 0.002, CARD_H), (0, 0, 0), M['paper'], slot, bev=0)
        ph = quad(f'screen_photo_{k}', PH_W, PH_H, (0, -0.0016, CARD_H / 2 - PH_TOP - PH_H / 2), M['photo_slot'], slot)
        hide_from_bake(ph)
        sphere(f'cork_pin_{k}', 0.009, (0, -0.006, CARD_H / 2 - 0.012), M['red'] if k % 3 else M['book_a'], slot)
    # an ID lanyard hanging from the corner
    box('cork_badge', (0.07, 0.003, 0.1), (cx + 0.25, -0.045, cz - 0.42), M['paper'], hit, bev=0.002)
    box('cork_lanyard', (0.008, 0.002, 0.2), (cx + 0.25, -0.043, cz - 0.27), M['book_a'], hit, bev=0)

    # --- Wall banner (Organizations): the AWS Student Builder Group banner above the shelf ----------
    # Cloth is baked plain; the website draws the banner picture on it (screen_banner_photo).
    hit = empty('hit_banner')
    bn = empty('banner', hit)
    BW, BH = 0.95, 0.95 * 315 / 851
    bn.location = (-0.5, -0.018, 2.31)
    bn.rotation_euler = (D(3), 0, 0)
    box('banner_cloth', (BW, 0.003, BH), (0, 0, 0), M['paper'], bn, bev=0)
    bp = quad('screen_banner_photo', BW - 0.004, BH - 0.004, (0, -0.0022, 0), M['photo_slot'], bn)
    hide_from_bake(bp)
    cyl('banner_rod', 0.007, BW + 0.06, (0, 0, BH / 2 + 0.006), M['black'], bn, rot=(0, D(90), 0), segs=16, bev=0)
    for sx in (-1, 1):
        box(f'banner_hook_{sx}', (0.012, 0.02, 0.012), (sx * (BW / 2 - 0.05), 0.009, BH / 2 + 0.012), M['black'], bn, bev=0.002)

    # --- Acoustic foam (decor) between the shelf and the corner --------------------------------------
    foam_panel('foam_panel', 0.64, 0.98, (0.86, -0.012, 2.12), M['foam'])

    # --- Right wall: window + curtain ----------------------------------------------------------------
    win = empty('window')
    wy0, wy1, wz0, wz1 = -1.45, -2.65, 0.85, 2.45
    wcy, wcz, ww, wh_ = (wy0 + wy1) / 2, (wz0 + wz1) / 2, abs(wy1 - wy0), wz1 - wz0
    view = quad('window_view', ww, wh_, (XR - 0.004, wcy, wcz), M['window_night'], win, rot=(0, 0, D(-90)))
    for nm, sz, loc in [
        ('win_frame_top', (0.06, ww + 0.1, 0.06), (XR - 0.03, wcy, wz1 + 0.03)),
        ('win_frame_bot', (0.1, ww + 0.14, 0.05), (XR - 0.05, wcy, wz0 - 0.025)),
        ('win_frame_l', (0.06, 0.05, wh_), (XR - 0.03, wy0 + 0.025, wcz)),
        ('win_frame_r', (0.06, 0.05, wh_), (XR - 0.03, wy1 - 0.025, wcz)),
        ('win_frame_mid', (0.04, 0.035, wh_), (XR - 0.02, wcy, wcz)),
    ]:
        box(nm, sz, loc, M['white_plastic'], win, bev=0.006)
    cur = empty('curtains')
    curtain('curtain_l', 1.5, 2.72, (XR - 0.1, -0.12, 0.06), M['curtain'], cur, folds=9)
    curtain('curtain_r', 0.5, 2.72, (XR - 0.1, -2.7, 0.06), M['curtain'], cur, folds=4)
    cyl('curtain_rod', 0.012, 2.6, (XR - 0.1, -1.6, 2.82), M['black'], cur, rot=(D(90), 0, 0), bev=0.002)

    # --- Chair (decor) ----------------------------------------------------------------------------
    ch = empty('chair')
    ch.location = (0.62, -1.2, 0)
    ch.rotation_euler = (0, 0, D(8))
    for k in range(5):
        a = k / 5 * 2 * math.pi
        leg = box(f'chair_leg_{k}', (0.3, 0.035, 0.03), (math.cos(a) * 0.15, math.sin(a) * 0.15, 0.08), M['chair_dark'], ch, bev=0.01)
        leg.rotation_euler = (0, D(-6), a)
        sphere(f'chair_wheel_{k}', 0.025, (math.cos(a) * 0.29, math.sin(a) * 0.29, 0.03), M['chair_dark'], ch)
    cyl('chair_gas', 0.025, 0.32, (0, 0, 0.25), M['silver'], ch, bev=0.002)
    box('chair_seat_base', (0.4, 0.4, 0.04), (0, 0, 0.42), M['chair_dark'], ch, bev=0.01)
    box('chair_seat', (0.5, 0.48, 0.07), (0, 0.02, 0.47), M['chair_seat'], ch, bev=0.03, segs=4)
    for s in (-1, 1):
        box(f'chair_arm_post_{s}', (0.03, 0.04, 0.2), (s * 0.27, -0.02, 0.56), M['chair_frame'], ch, bev=0.008)
        box(f'chair_arm_pad_{s}', (0.07, 0.24, 0.03), (s * 0.27, 0.02, 0.67), M['chair_dark'], ch, bev=0.012)
    back = empty('chair_back', ch)
    back.location = (0, -0.24, 0.5)
    back.rotation_euler = (D(-10), 0, 0)
    box('chair_spine', (0.06, 0.03, 0.22), (0, 0, 0.08), M['chair_frame'], back, bev=0.01)
    box('chair_back_frame', (0.46, 0.04, 0.58), (0, 0, 0.5), M['chair_frame'], back, bev=0.03, segs=4)
    box('chair_back_mesh', (0.4, 0.045, 0.52), (0, 0.004, 0.5), M['chair_mesh'], back, bev=0.02)
    box('chair_headrest', (0.3, 0.06, 0.12), (0, 0.01, 0.9), M['chair_frame'], back, bev=0.03)

    # --- Lights -----------------------------------------------------------------------------------
    def area(name, loc, rot, size, energy, color, shape='RECTANGLE', size_y=None):
        L = bpy.data.lights.new(name, 'AREA')
        L.shape = shape
        L.size = size
        L.size_y = size_y or size
        L.energy = energy
        L.color = color
        o = bpy.data.objects.new(name, L)
        o.location = loc
        o.rotation_euler = rot
        return link(o)

    # warm key light from above-front-left (like a ceiling lamp outside the frame)
    area('light_key', (-1.2, -2.4, 3.0), (D(32), D(-14), 0), 2.8, 240, (1.0, 0.8, 0.6), size_y=2.0)
    # cool fill from the window
    area('light_window', (XR - 0.25, -2.05, 1.65), (0, D(-90), 0), 1.2, 22, (0.62, 0.74, 1.0), size_y=1.5)
    # blue wash on the wall behind the monitor
    area('light_monitor_back', (-0.47, -0.15, RISER_Z + 0.27), (D(90), 0, 0), 0.8, 16, (0.08, 0.28, 1.0), size_y=0.3)
    # blue glow inside the PC
    p = bpy.data.lights.new('light_pc', 'POINT')
    p.energy = 6
    p.color = (0.3, 0.55, 1.0)
    p.shadow_soft_size = 0.05
    po = bpy.data.objects.new('light_pc', p)
    po.location = (0.64, -0.34, DESK_Z + 0.23)
    link(po)

    world = bpy.data.worlds.new('World')
    scene.world = world
    try:
        world.use_nodes = True
    except Exception:
        pass
    bg = world.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (*lin('#3a2c26'), 1)
    bg.inputs['Strength'].default_value = 0.22

    # --- Camera ------------------------------------------------------------------------------------
    # Level camera (straight verticals) framed with lens shift, like an architectural shot.
    cam = bpy.data.cameras.new('camera')
    cam.lens = 30
    cam.sensor_width = 36
    cam.sensor_fit = 'HORIZONTAL'
    cam.shift_y = -0.13
    cam.clip_start = 0.05
    cam.clip_end = 30
    co = bpy.data.objects.new('camera', cam)
    co.location = (-2.36, -3.18, 1.82)
    co.rotation_euler = (D(90), 0, D(-35))
    link(co)
    scene.camera = co

    # --- Render settings ----------------------------------------------------------------------------
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 64
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 6
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 798
    scene.view_settings.view_transform = 'AgX'
    for look in ('AgX - Medium High Contrast', 'Medium High Contrast'):
        try:
            scene.view_settings.look = look
            break
        except TypeError:
            continue

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    print('saved', OUT_BLEND)


if __name__ == '__main__':
    build()
