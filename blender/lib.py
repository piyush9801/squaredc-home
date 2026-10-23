"""Square DC universe: shared building blocks (no side effects on import).

Everything is built from the official eight-shape library (Shape_Assets_2026-09-09), lit by a star placed
behind the subject so light spills round the shapes, and finished in the compositor (glow, streaks, sun beams).
"""
import bpy, math, random, mathutils
from mathutils import Vector, Euler, Matrix
from bpy_extras.object_utils import world_to_camera_view

LIB = "/Users/piyushkumar/Documents/New project/Shape_Assets_2026-09-09/All_Eight_Assets.blend"
ASSETS = {
    'pixel': 'ASSET • Yellow Square', 'torus': 'ASSET • Torus', 'sphere': 'ASSET • Sphere',
    'cube': 'ASSET • Cube', 'dome': 'ASSET • Half-sphere', 'cone': 'ASSET • Cone',
    'arch': 'ASSET • Arch', 'octa': 'ASSET • Octahedron',
}

# Brand colours (sRGB hex) from the Work page tokens and the shape library.
SPACE = '#100026'; SAND = '#F2EBD9'; YELLOW = '#FBB100'; BLUE = '#1858FD'; DEEP = '#1829F3'; PINK = '#F66FD6'


def lin(h):
    h = h.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c)


def link(obj, coll=None):
    (coll or bpy.context.scene.collection).objects.link(obj)
    return obj


def new_collection(name, parent=None):
    c = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(c)
    return c


def set_vis(o, camera=True, diffuse=True, glossy=True, transmission=True, scatter=True, shadow=True):
    o.visible_camera = camera; o.visible_diffuse = diffuse; o.visible_glossy = glossy
    o.visible_transmission = transmission; o.visible_volume_scatter = scatter; o.visible_shadow = shadow


# ----------------------------------------------------------------------------------------------- materials
def mat_nodes(name):
    m = bpy.data.materials.new(name)
    try: m.use_nodes = True
    except Exception: pass
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    return m, nt, out


def emission_mat(name, color, strength):
    m, nt, out = mat_nodes(name)
    e = nt.nodes.new('ShaderNodeEmission'); e.inputs['Color'].default_value = (*color, 1); e.inputs['Strength'].default_value = strength
    nt.links.new(e.outputs[0], out.inputs['Surface'])
    return m


def principled(name, color, rough=0.4, metal=0.0, emit=None, emit_strength=0.0, coat=0.0, transmission=0.0, ior=1.45):
    m, nt, out = mat_nodes(name)
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    b.inputs['Base Color'].default_value = (*color, 1); b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal; b.inputs['Coat Weight'].default_value = coat
    b.inputs['Transmission Weight'].default_value = transmission; b.inputs['IOR'].default_value = ior
    if emit:
        b.inputs['Emission Color'].default_value = (*emit, 1); b.inputs['Emission Strength'].default_value = emit_strength
    nt.links.new(b.outputs[0], out.inputs['Surface'])
    return m, b


# ----------------------------------------------------------------------------------------------- shapes
def import_shape(key, name=None, coll=None):
    """Append one ASSET collection from the library and parent its parts to an empty at their bounds centre."""
    with bpy.data.libraries.load(LIB, link=False) as (src, dst):
        dst.collections = [ASSETS[key]]
    col = dst.collections[0]
    col.name = 'SRC_' + (name or key)
    (coll or bpy.context.scene.collection).children.link(col)
    meshes = [o for o in col.objects if o.type == 'MESH']
    bpy.context.view_layer.update()
    lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
    for o in meshes:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
    centre = (lo + hi) / 2
    root = bpy.data.objects.new('SH_' + (name or key), None)
    root.empty_display_type = 'PLAIN_AXES'
    link(root, coll)
    for o in col.objects:
        if o.parent is None:
            o.location -= centre
            o.parent = root
    root['radius'] = max((hi - lo)) / 2
    return root


def shape_children(root):
    return [c for c in root.children_recursive if c.type == 'MESH']


def scale_emission(root, factor_socket_name='Emission Strength'):
    """Return the principled nodes on a shape so callers can animate their glow."""
    nodes = []
    for o in shape_children(root):
        for s in o.material_slots:
            if s.material and s.material.node_tree:
                for n in s.material.node_tree.nodes:
                    if n.bl_idname == 'ShaderNodeBsdfPrincipled':
                        nodes.append(n)
    return nodes


# ----------------------------------------------------------------------------------------------- point clouds
def points_object(name, positions, attrs=None, coll=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in positions], [], [])
    for k, vals in (attrs or {}).items():
        if hasattr(vals[0], '__len__'):
            a = me.attributes.new(k, 'FLOAT_VECTOR', 'POINT'); a.data.foreach_set('vector', [float(c) for v in vals for c in tuple(v)])
        else:
            a = me.attributes.new(k, 'FLOAT', 'POINT'); a.data.foreach_set('value', list(vals))
    me.update()
    o = bpy.data.objects.new(name, me)
    return link(o, coll)


def gn_instancer(obj, inst_obj, scale_attr='size', drift_attr=None, drift_rate=0.0, scale_vec_attr=None, rot_attr=None):
    """Instance `inst_obj` on every vertex of `obj`, scaled by a per-point attribute.

    drift_attr: per-point velocity (m/frame) added as  pos + vel * frame * drift_rate.
    scale_vec_attr / rot_attr: per-point vector scale and Euler rotation (else a random rotation).
    """
    ng = bpy.data.node_groups.new(obj.name + '_GN', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    fac = ng.interface.new_socket('Drift', in_out='INPUT', socket_type='NodeSocketFloat'); fac.default_value = drift_rate
    N = ng.nodes; L = ng.links
    gi = N.new('NodeGroupInput'); go = N.new('NodeGroupOutput')
    geo = gi.outputs['Geometry']
    if drift_attr:
        na = N.new('GeometryNodeInputNamedAttribute'); na.data_type = 'FLOAT_VECTOR'; na.inputs['Name'].default_value = drift_attr
        st = N.new('GeometryNodeInputSceneTime')
        m1 = N.new('ShaderNodeMath'); m1.operation = 'MULTIPLY'
        L.new(st.outputs['Frame'], m1.inputs[0]); L.new(gi.outputs['Drift'], m1.inputs[1])
        vs = N.new('ShaderNodeVectorMath'); vs.operation = 'SCALE'
        L.new(na.outputs['Attribute'], vs.inputs[0]); L.new(m1.outputs[0], vs.inputs['Scale'])
        sp = N.new('GeometryNodeSetPosition')
        L.new(geo, sp.inputs['Geometry']); L.new(vs.outputs[0], sp.inputs['Offset'])
        geo = sp.outputs['Geometry']
    iop = N.new('GeometryNodeInstanceOnPoints')
    oi = N.new('GeometryNodeObjectInfo'); oi.inputs['Object'].default_value = inst_obj; oi.inputs['As Instance'].default_value = True
    L.new(geo, iop.inputs['Points']); L.new(oi.outputs['Geometry'], iop.inputs['Instance'])
    if scale_vec_attr:
        sa = N.new('GeometryNodeInputNamedAttribute'); sa.data_type = 'FLOAT_VECTOR'; sa.inputs['Name'].default_value = scale_vec_attr
        L.new(sa.outputs['Attribute'], iop.inputs['Scale'])
    elif scale_attr:
        sa = N.new('GeometryNodeInputNamedAttribute'); sa.data_type = 'FLOAT'; sa.inputs['Name'].default_value = scale_attr
        L.new(sa.outputs['Attribute'], iop.inputs['Scale'])
    if rot_attr:
        ra = N.new('GeometryNodeInputNamedAttribute'); ra.data_type = 'FLOAT_VECTOR'; ra.inputs['Name'].default_value = rot_attr
        er = N.new('FunctionNodeEulerToRotation')
        L.new(ra.outputs['Attribute'], er.inputs[0]); L.new(er.outputs[0], iop.inputs['Rotation'])
    else:
        rr = N.new('FunctionNodeRandomValue'); rr.data_type = 'FLOAT_VECTOR'
        rr.inputs['Max'].default_value = (6.283, 6.283, 6.283)
        L.new(rr.outputs['Value'], iop.inputs['Rotation'])
    L.new(iop.outputs['Instances'], go.inputs['Geometry'])
    mod = obj.modifiers.new('GN', 'NODES'); mod.node_group = ng
    return mod


def tiny_sphere(name, mat, coll, subdiv=1):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdiv, radius=1.0, location=(0, 0, -9999))
    o = bpy.context.object; o.name = name
    for p in o.data.polygons: p.use_smooth = True
    o.data.materials.append(mat)
    for c in o.users_collection: c.objects.unlink(o)
    coll.objects.link(o)
    o.hide_render = False; o.hide_viewport = False
    return o


def instance_mat(name, base_col, strength_lo, strength_hi, tint_b=None, glossy=False, attr='bright'):
    """Emission whose strength and tint come from per-instance attributes (instancer `bright`)."""
    m, nt, out = mat_nodes(name)
    N = nt.nodes; L = nt.links
    at = N.new('ShaderNodeAttribute'); at.attribute_type = 'INSTANCER'; at.attribute_name = attr
    oi = N.new('ShaderNodeObjectInfo')
    mr = N.new('ShaderNodeMapRange'); mr.inputs['To Min'].default_value = strength_lo; mr.inputs['To Max'].default_value = strength_hi
    L.new(at.outputs['Fac'], mr.inputs['Value'])
    mix = N.new('ShaderNodeMix'); mix.data_type = 'RGBA'
    mix.inputs['A'].default_value = (*base_col, 1); mix.inputs['B'].default_value = (*(tint_b or base_col), 1)
    L.new(oi.outputs['Random'], mix.inputs['Factor'])
    em = N.new('ShaderNodeEmission'); L.new(mix.outputs['Result'], em.inputs['Color']); L.new(mr.outputs['Result'], em.inputs['Strength'])
    if glossy:
        g = N.new('ShaderNodeBsdfGlossy'); g.inputs['Roughness'].default_value = 0.15
        g.inputs['Color'].default_value = (1, 1, 1, 1)
        add = N.new('ShaderNodeAddShader'); L.new(em.outputs[0], add.inputs[0]); L.new(g.outputs[0], add.inputs[1])
        L.new(add.outputs[0], out.inputs['Surface'])
    else:
        L.new(em.outputs[0], out.inputs['Surface'])
    return m


# ----------------------------------------------------------------------------------------------- world
def deep_space_world(strength=1.0):
    w = bpy.data.worlds.new('Deep Space')
    try: w.use_nodes = True
    except Exception: pass
    nt = w.node_tree; N = nt.nodes; L = nt.links; N.clear()
    out = N.new('ShaderNodeOutputWorld')
    tc = N.new('ShaderNodeTexCoord')
    # Nebula: two octaves of slow noise on view direction -> deep violet clouds with a faint magenta/blue hint.
    nz = N.new('ShaderNodeTexNoise'); nz.noise_dimensions = '3D'
    nz.inputs['Scale'].default_value = 1.6; nz.inputs['Detail'].default_value = 6.0; nz.inputs['Roughness'].default_value = 0.62
    nz.inputs['Distortion'].default_value = 0.35
    L.new(tc.outputs['Generated'], nz.inputs['Vector'])
    cr = N.new('ShaderNodeValToRGB'); r = cr.color_ramp
    r.elements[0].position = 0.38; r.elements[0].color = (*[c * 0.55 for c in lin('#0b0018')], 1)
    r.elements[1].position = 0.78; r.elements[1].color = (*lin('#2a1052'), 1)
    e = r.elements.new(0.62); e.color = (*lin('#170936'), 1)
    L.new(nz.outputs['Fac'], cr.inputs['Fac'])
    # Faint far star dust (the near stars are real geometry so they parallax).
    vor = N.new('ShaderNodeTexVoronoi'); vor.feature = 'F1'; vor.inputs['Scale'].default_value = 520
    vm = N.new('ShaderNodeVectorMath'); vm.operation = 'NORMALIZE'
    L.new(tc.outputs['Generated'], vm.inputs[0])
    vc = N.new('ShaderNodeVectorMath'); vc.operation = 'SUBTRACT'; vc.inputs[1].default_value = (0.5, 0.5, 0.5)
    L.new(tc.outputs['Generated'], vc.inputs[0]); L.new(vc.outputs[0], vm.inputs[0])
    L.new(vm.outputs[0], vor.inputs['Vector'])
    st = N.new('ShaderNodeMapRange'); st.inputs['From Min'].default_value = 0.0; st.inputs['From Max'].default_value = 0.06
    st.inputs['To Min'].default_value = 1.0; st.inputs['To Max'].default_value = 0.0
    L.new(vor.outputs['Distance'], st.inputs['Value'])
    # Only some cells host a star.
    gate = N.new('ShaderNodeMath'); gate.operation = 'GREATER_THAN'; gate.inputs[1].default_value = 0.72
    L.new(vor.outputs['Color'], gate.inputs[0])
    sm = N.new('ShaderNodeMath'); sm.operation = 'MULTIPLY'; L.new(st.outputs[0], sm.inputs[0]); L.new(gate.outputs[0], sm.inputs[1])
    sm2 = N.new('ShaderNodeMath'); sm2.operation = 'MULTIPLY'; sm2.inputs[1].default_value = 0.9; L.new(sm.outputs[0], sm2.inputs[0])
    add = N.new('ShaderNodeMix'); add.data_type = 'RGBA'; add.blend_type = 'ADD'
    add.inputs['Factor'].default_value = 1.0
    L.new(cr.outputs['Color'], add.inputs['A'])
    comb = N.new('ShaderNodeCombineColor')
    L.new(sm2.outputs[0], comb.inputs[0]); L.new(sm2.outputs[0], comb.inputs[1]); L.new(sm2.outputs[0], comb.inputs[2])
    L.new(comb.outputs[0], add.inputs['B'])
    bg = N.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = strength
    L.new(add.outputs['Result'], bg.inputs['Color'])
    L.new(bg.outputs[0], out.inputs['Surface'])
    w['bg'] = bg.name
    return w


# ----------------------------------------------------------------------------------------------- render + comp
def render_setup(scene, w=1600, h=900, samples=96, threshold=0.02, mblur=True):
    scene.render.engine = 'CYCLES'
    try:
        p = bpy.context.preferences.addons['cycles'].preferences
        p.compute_device_type = 'METAL'; p.get_devices()
        for d in p.devices: d.use = True
        scene.cycles.device = 'GPU'
    except Exception as e:
        print('GPU setup skipped:', e)
    c = scene.cycles
    c.samples = samples; c.use_adaptive_sampling = True; c.adaptive_threshold = threshold
    c.use_denoising = True; c.denoiser = 'OPENIMAGEDENOISE'
    try: c.denoising_use_gpu = True
    except Exception: pass
    c.max_bounces = 10; c.diffuse_bounces = 2; c.glossy_bounces = 4; c.transmission_bounces = 10
    c.volume_bounces = 0; c.transparent_max_bounces = 8
    c.caustics_reflective = False; c.caustics_refractive = False; c.blur_glossy = 1.0
    c.sample_clamp_indirect = 8.0
    scene.render.resolution_x = w; scene.render.resolution_y = h; scene.render.resolution_percentage = 100
    scene.render.use_persistent_data = True
    scene.render.use_motion_blur = mblur; scene.render.motion_blur_shutter = 0.45
    scene.render.film_transparent = False
    import os
    vt = os.environ.get('SDC_VIEW', 'Khronos PBR Neutral')
    scene.view_settings.view_transform = vt
    if vt == 'AgX':
        for lk in ('AgX - Punchy', 'Punchy'):
            try: scene.view_settings.look = lk; break
            except Exception: pass
    scene.view_settings.exposure = float(os.environ.get('SDC_EXPOSURE', '-0.3'))
    scene.render.image_settings.file_format = 'WEBP'
    scene.render.image_settings.quality = 88
    scene.render.image_settings.color_mode = 'RGB'


def compositor(scene):
    """Glow -> anamorphic streak -> sun beams -> lens ghosts -> slight dispersion. Returns the key nodes."""
    ng = bpy.data.node_groups.new('SDC • lens', 'CompositorNodeTree')
    ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    scene.compositing_node_group = ng
    scene.render.use_compositing = True
    N = ng.nodes; L = ng.links
    rl = N.new('CompositorNodeRLayers'); rl.location = (-900, 0)

    def glare(kind, **kw):
        g = N.new('CompositorNodeGlare')
        g.inputs['Type'].default_value = kind
        g.inputs['Quality'].default_value = 'High'
        for k, v in kw.items(): g.inputs[k].default_value = v
        return g

    # Thresholds are scene-linear: only the star disc and its corona (tens to hundreds) feed the beams, streaks
    # and ghosts; the shapes and the far stars only get the soft glow.
    fog = glare('Fog Glow', Threshold=2.5, Smoothness=0.4, Strength=0.32, Size=0.5, Saturation=1.0)
    blo = glare('Bloom', Threshold=1.4, Smoothness=0.3, Strength=0.22, Size=0.85, Saturation=1.0)
    stk = glare('Streaks', Threshold=40.0, Smoothness=0.2, Strength=0.25, Streaks=2, Iterations=4, Fade=0.95,
                **{'Streaks Angle': 0.0, 'Color Modulation': 0.35})
    sun = glare('Sun Beams', Threshold=22.0, Smoothness=0.5, Strength=0.7, Size=0.7, Jitter=0.2)
    sun.inputs['Sun Position'].default_value = (0.5, 0.6)
    gho = glare('Ghosts', Threshold=60.0, Smoothness=0.3, Strength=0.05, Iterations=3, **{'Color Modulation': 0.6})
    lens = N.new('CompositorNodeLensdist'); lens.inputs['Distortion'].default_value = 0.0
    lens.inputs['Dispersion'].default_value = 0.012
    go = N.new('NodeGroupOutput')
    chain = [rl, fog, blo, stk, sun, gho]
    for a, b in zip(chain, chain[1:]):
        L.new(a.outputs['Image'], b.inputs['Image'])
    L.new(gho.outputs['Image'], lens.inputs['Image'])
    L.new(lens.outputs['Image'], go.inputs['Image'])
    for i, n in enumerate(chain + [lens, go]): n.location = (-900 + i * 220, 0)
    return dict(tree=ng, fog=fog, bloom=blo, streaks=stk, sun=sun, ghosts=gho, lens=lens)


# ----------------------------------------------------------------------------------------------- camera
def make_camera(name='CAM', lens=50):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.sensor_width = 36; cd.clip_start = 0.05; cd.clip_end = 5000
    cd.dof.use_dof = True; cd.dof.aperture_fstop = 2.8; cd.dof.aperture_blades = 7; cd.dof.aperture_rotation = 0.3
    cam = link(bpy.data.objects.new(name, cd))
    bpy.context.scene.camera = cam
    return cam


def look_at(obj, target, roll=0.0):
    d = Vector(target) - obj.location
    q = d.to_track_quat('-Z', 'Y')
    e = q.to_euler()
    if roll:
        e = (q @ mathutils.Quaternion((0, 0, 1), roll)).to_euler()
    obj.rotation_euler = e


def screen_pos(scene, cam, p):
    v = world_to_camera_view(scene, cam, Vector(p))
    return v  # x,y in 0..1 (origin bottom-left), z = depth


# ----------------------------------------------------------------------------------------------- easing
def clamp01(x): return 0.0 if x < 0 else 1.0 if x > 1 else x
def smooth(x): x = clamp01(x); return x * x * (3 - 2 * x)
def smoother(x): x = clamp01(x); return x * x * x * (x * (6 * x - 15) + 10)
def ease_out(x, p=3): x = clamp01(x); return 1 - (1 - x) ** p
def ease_in(x, p=3): x = clamp01(x); return x ** p
def span(f, a, b): return clamp01((f - a) / (b - a)) if b != a else (1.0 if f >= b else 0.0)
def mix(a, b, t):
    if isinstance(a, (tuple, list, Vector)):
        return Vector(a).lerp(Vector(b), t)
    return a + (b - a) * t
