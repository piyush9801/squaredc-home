"""Scene 01, Enter the universe: the approved key still, animated for scroll (frames 1..N, played by scroll position).

  1-20    darkness: faint stars, a few grains of dust catching light
  8-40    the cube lights up from inside first (light captured), then the star behind it blooms
  28-75   the key light comes up from above; the rings draw themselves round the cube, the dust gathers into bands
  1-N     the camera eases back from a close-up to the approved frame; the cube turns very slowly; the dust orbits

blender -b --factory-startup --python scene01.py -- <preview|final|dry> <outdir> [frames]
"""
import bpy, sys, os, math, random, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import keys                                      # empty scene, collections and every helper of the key stills
from keys import *
from mathutils import Vector, Euler, Matrix, noise, Quaternion
from designed_light import designed_spot

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
MODE = argv[0] if argv else 'preview'
OUT = os.path.abspath(argv[1]) if len(argv) > 1 else '/tmp/s01'
N = int(argv[2]) if len(argv) > 2 else 120
F0 = int(argv[3]) if len(argv) > 3 else 1          # optional sub-range to render
F1 = int(argv[4]) if len(argv) > 4 else N
scene = keys.scene
scene.frame_start, scene.frame_end = 1, N


def ease(x):
    x = max(0.0, min(1.0, x)); return x * x * x * (x * (6 * x - 15) + 10)


def ramp(f, a, b):
    return ease((f - a) / (b - a)) if b > a else float(f >= b)


def key_value(sock_owner, attr, pairs, data_path='default_value'):
    for f, v in pairs:
        setattr(sock_owner, attr, v) if attr else None
        sock_owner.keyframe_insert(data_path, frame=f)


def anim_float(target, path, pairs):
    """Keyframe a float property with eased (bezier) keys."""
    for f, v in pairs:
        setattr(target, path, v); target.keyframe_insert(path, frame=f)


def anim_node_value(node, pairs):
    for f, v in pairs:
        node.outputs[0].default_value = v; node.outputs[0].keyframe_insert('default_value', frame=f)


def anim_input(node, name, pairs):
    for f, v in pairs:
        node.inputs[name].default_value = v; node.inputs[name].keyframe_insert('default_value', frame=f)


def fcurves_of(id_):
    ad = getattr(id_, 'animation_data', None)
    if not ad or not ad.action: return []
    act = ad.action
    try:
        if len(act.fcurves): return list(act.fcurves)
    except Exception: pass
    out = []
    try:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(act, ad.action_slot)
        if cb: return list(cb.fcurves)
    except Exception: pass
    for layer in getattr(act, 'layers', []):
        for strip in layer.strips:
            for cb in getattr(strip, 'channelbags', []):
                out += list(cb.fcurves)
    return out


def set_linear(id_, extrapolate=False):
    for fc in fcurves_of(id_):
        for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
        if extrapolate: fc.extrapolation = 'LINEAR'


def spinner(name, axis, deg_total):
    """An empty at the origin turning about the ring normal; children orbit with it."""
    e = bpy.data.objects.new(name, None); scene.collection.objects.link(e)
    e.rotation_mode = 'AXIS_ANGLE'
    for f, a in ((1, 0.0), (N, math.radians(deg_total))):
        e.rotation_axis_angle = (a, *axis); e.keyframe_insert('rotation_axis_angle', frame=f)
    set_linear(e, extrapolate=True)      # constant angular speed that carries on past the end (the idle loop)
    return e


def parent_to(obj, par):
    obj.parent = par; obj.matrix_parent_inverse = Matrix.Identity(4)


# ----------------------------------------------------------------------------------------------- the scene
rnd = random.Random(11)
cube = crisp_cube('PIXEL', 0.88, 0.036, 6, coll=SHAPES)
m = worn_material('pixel resin', '#FFD21A', metallic=0.0, rough=0.34, coat=0.6, coat_rough=0.04, subsurface=1.0,
                  wear=0.3, mottle=0.08, edge_hex='#FFE680', dust_hex='#f2dfa0', bump=0.1, emit_hex='#FFC400', emit=0.0)
for n in m.node_tree.nodes:
    if n.bl_idname == 'ShaderNodeBsdfPrincipled':
        n.subsurface_method = 'RANDOM_WALK'
        n.inputs['Subsurface Radius'].default_value = (1.0, 0.85, 0.3)
        n.inputs['Subsurface Scale'].default_value = 0.55               # (V4: translucent gold, lit from within)
        n.inputs['Emission Color'].default_value = (*lin('#FFAE1A'), 1)
        n.inputs['Roughness'].default_value = 0.22
cube.data.materials.append(m)
for n in m.node_tree.nodes:                                         # an inner glow, stronger at the core than the rim
    if n.bl_idname == 'ShaderNodeBsdfPrincipled':
        lw_ = m.node_tree.nodes.new('ShaderNodeLayerWeight'); lw_.inputs['Blend'].default_value = 0.45
        mr_ = m.node_tree.nodes.new('ShaderNodeMapRange'); mr_.inputs['To Min'].default_value = 0.9; mr_.inputs['To Max'].default_value = 0.25
        m.node_tree.links.new(lw_.outputs['Facing'], mr_.inputs['Value'])
        gl_ = m.node_tree.nodes.new('ShaderNodeValue'); gl_.name = 'INNER_GLOW'; gl_.outputs[0].default_value = 0.42
        mu_ = m.node_tree.nodes.new('ShaderNodeMath'); mu_.operation = 'MULTIPLY'
        m.node_tree.links.new(mr_.outputs['Result'], mu_.inputs[0]); m.node_tree.links.new(gl_.outputs[0], mu_.inputs[1])
        # bright edges: a thin rim of light where the faces turn away (luminous amber, not plastic)
        rw_ = m.node_tree.nodes.new('ShaderNodeLayerWeight'); rw_.inputs['Blend'].default_value = 0.06
        rr_ = m.node_tree.nodes.new('ShaderNodeMapRange'); rr_.inputs['From Min'].default_value = 0.35
        rr_.inputs['To Max'].default_value = 2.4; rr_.clamp = True
        m.node_tree.links.new(rw_.outputs['Fresnel'], rr_.inputs['Value'])
        rg_ = m.node_tree.nodes.new('ShaderNodeMath'); rg_.operation = 'MULTIPLY'
        m.node_tree.links.new(rr_.outputs['Result'], rg_.inputs[0]); m.node_tree.links.new(gl_.outputs[0], rg_.inputs[1])
        sm_ = m.node_tree.nodes.new('ShaderNodeMath'); sm_.operation = 'ADD'
        m.node_tree.links.new(mu_.outputs[0], sm_.inputs[0]); m.node_tree.links.new(rg_.outputs[0], sm_.inputs[1])
        # (V4 15, after the storyboard) the yellow world: liquid gold with fine threads of light swirling under its surface
        # and sparks caught in it, faded in once it is world-sized (no tiles, no plates)
        NT_ = m.node_tree.nodes; LK_ = m.node_tree.links
        def mth(op, a, b=None, clamp=False):
            n_ = NT_.new('ShaderNodeMath'); n_.operation = op; n_.use_clamp = clamp
            for i_, v_ in enumerate((a, b)):
                if v_ is None: continue
                if isinstance(v_, (int, float)): n_.inputs[i_].default_value = v_
                else: LK_.new(v_, n_.inputs[i_])
            return n_.outputs[0]
        def tex_noise(vec, scale, detail, rough=0.6, w=None):
            n_ = NT_.new('ShaderNodeTexNoise'); n_.noise_dimensions = '4D'
            n_.inputs['Scale'].default_value = scale; n_.inputs['Detail'].default_value = detail; n_.inputs['Roughness'].default_value = rough
            LK_.new(vec, n_.inputs['Vector'])
            if w is not None: LK_.new(w, n_.inputs['W'])
            return n_
        tc_ = NT_.new('ShaderNodeTexCoord')
        sw_ = NT_.new('ShaderNodeValue'); sw_.name = 'SKIN_W'; sw_.outputs[0].default_value = 0.0
        wn_ = tex_noise(tc_.outputs['Object'], 3.0, 2.0, w=sw_.outputs[0])                 # the slow swirl
        ws_ = NT_.new('ShaderNodeVectorMath'); ws_.operation = 'SCALE'; ws_.inputs['Scale'].default_value = 0.45
        LK_.new(wn_.outputs['Color'], ws_.inputs[0])
        wp_ = NT_.new('ShaderNodeVectorMath'); wp_.operation = 'ADD'; LK_.new(tc_.outputs['Object'], wp_.inputs[0]); LK_.new(ws_.outputs[0], wp_.inputs[1])
        th_ = tex_noise(wp_.outputs[0], 24.0, 8.0, rough=0.62, w=sw_.outputs[0])         # threads: thin contours of it
        thr_ = mth('POWER', mth('SUBTRACT', 1.0, mth('MULTIPLY', mth('ABSOLUTE', mth('SUBTRACT', th_.outputs['Fac'], 0.5)), 11.0), clamp=True), 3.0)
        mk_ = tex_noise(tc_.outputs['Object'], 4.5, 3.0, w=sw_.outputs[0])                # brighter here, quieter there
        thr_ = mth('MULTIPLY', thr_, mth('MULTIPLY', mth('SUBTRACT', mk_.outputs['Fac'], 0.38), 3.0, clamp=True))
        vo_ = NT_.new('ShaderNodeTexVoronoi'); vo_.voronoi_dimensions = '3D'; vo_.inputs['Scale'].default_value = 70.0
        LK_.new(tc_.outputs['Object'], vo_.inputs['Vector'])
        spk_ = NT_.new('ShaderNodeSeparateColor'); LK_.new(vo_.outputs['Color'], spk_.inputs[0])
        spark_ = mth('MULTIPLY', mth('POWER', mth('SUBTRACT', 1.0, mth('DIVIDE', vo_.outputs['Distance'], 0.1), clamp=True), 2.0),
                     mth('POWER', spk_.outputs[0], 4.0))                                         # sparks caught in the gold
        sk_ = NT_.new('ShaderNodeValue'); sk_.name = 'WORLD_SKIN'; sk_.outputs[0].default_value = 0.0
        sk2_ = mth('MULTIPLY', mth('ADD', mth('MULTIPLY', thr_, 4.0), mth('MULTIPLY', spark_, 10.0)), sk_.outputs[0])
        s3_ = NT_.new('ShaderNodeMath'); s3_.operation = 'ADD'; LK_.new(sk2_, s3_.inputs[0]); LK_.new(sm_.outputs[0], s3_.inputs[1])
        if not n.inputs['Emission Strength'].links:
            m.node_tree.links.new(s3_.outputs[0], n.inputs['Emission Strength'])
ROT_END = (8, -9, 40)
plane = (math.radians(-6), math.radians(-12), math.radians(8))
M = Euler(plane).to_matrix()
AXIS = tuple(M @ Vector((0, 0, 1)))
front = -100.0

# ----------------------------------------------------------------------------------------------- the cube forms
# Before anything else the cube gathers out of the dark: gold and violet grains rise from below in a loose swirl and
# settle onto its surface, and the cube builds behind them from the bottom up, slowly, a glowing layer rising inside it
# like resin filling a mould (feedback: never all at once in one spot, never holed like cheese). One field decides
# both: a grain lands where, and when, the surface reaches it.
FORM_F0, FORM_DUR, FORM_SPAN = 4.0, 22.0, 34.0            # grains leave 4..38, land 26..60; the surface 26..60


def form_field(x, y, z):                                  # its height, with a slight living wobble to the edge
    return max(0.0, min(1.0, 0.5 + 0.5 * z / 0.44 * 0.94 + 0.025 * math.sin(7.0 * x + 5.0 * y + 2.0)))


deps_ = bpy.context.evaluated_depsgraph_get()
ev_ = cube.evaluated_get(deps_); me_ev = ev_.to_mesh(); me_ev.calc_loop_triangles()
tris_ = [[me_ev.vertices[i].co.copy() for i in t.vertices] for t in me_ev.loop_triangles]
ev_.to_mesh_clear()
areas_ = [(b - a).cross(c - a).length / 2 for a, b, c in tris_]
acc_, tot_ = [], 0.0
for a_ in areas_: tot_ += a_; acc_.append(tot_)
import bisect
rf = random.Random(5)
cam_l = (Euler((math.radians(ROT_END[0]), math.radians(ROT_END[1]), math.radians(ROT_END[2] - 12))).to_matrix().inverted()
         @ Vector((math.sin(math.radians(-2)), -math.cos(math.radians(-2)), math.tan(math.radians(7))))).normalized()
f_tgt, f_start, f_delay, f_spin, f_size, f_bright, f_tone = [], [], [], [], [], [], []
for _ in range(6000):
    a, b, c = tris_[min(len(tris_) - 1, bisect.bisect_left(acc_, rf.random() * tot_))]
    u, v = rf.random(), rf.random()
    if u + v > 1: u, v = 1 - u, 1 - v
    p = a + (b - a) * u + (c - a) * v
    d = Vector((rf.gauss(0, 0.45), rf.gauss(0, 0.45), -1.0)).normalized()             # they come up from below
    if d.dot(cam_l) > 0.15: d = (d - 2 * d.dot(cam_l) * cam_l).normalized()          # never between cube and lens
    f_tgt.append(p); f_start.append(p + d * (0.5 + 1.3 * rf.random() ** 0.8))
    f_delay.append(FORM_F0 + form_field(p.x, p.y, p.z) * FORM_SPAN + rf.uniform(-1.5, 1.5))
    f_spin.append(rf.uniform(1.4, 3.4))
    f_size.append(0.0016 + 0.003 * rf.random() ** 2)
    f_bright.append(0.1 + 0.45 * rf.random() ** 2.5); f_tone.append(min(1.0, rf.random() ** 1.6 * 0.9))
form = points_object('FORM_GRAINS', f_tgt, {'start': f_start, 'delay': f_delay, 'spin': f_spin, 'size': f_size,
                                            'bright': f_bright, 'tone': f_tone}, FX)
parent_to(form, cube)
fm_mat = glow_mat('form grains', DUST_STOPS, 4.5)
fm_src = tiny_sphere('FORM_src', fm_mat, FX, subdiv=2)
ng_f = bpy.data.node_groups.new('FORM_GN', 'GeometryNodeTree')
ng_f.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
ng_f.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
Ng, Lg = ng_f.nodes, ng_f.links
gi_ = Ng.new('NodeGroupInput'); go_ = Ng.new('NodeGroupOutput')
def _na(name, kind):
    n_ = Ng.new('GeometryNodeInputNamedAttribute'); n_.data_type = kind; n_.inputs['Name'].default_value = name
    return n_.outputs['Attribute']
def _gm(op, a, b=None, clamp=False):
    n_ = Ng.new('ShaderNodeMath'); n_.operation = op; n_.use_clamp = clamp
    for i_, v_ in enumerate((a, b)):
        if v_ is None: continue
        if isinstance(v_, (int, float)): n_.inputs[i_].default_value = v_
        else: Lg.new(v_, n_.inputs[i_])
    return n_.outputs[0]
st_ = Ng.new('GeometryNodeInputSceneTime')
tt_ = _gm('DIVIDE', _gm('SUBTRACT', st_.outputs['Frame'], _na('delay', 'FLOAT')), FORM_DUR, clamp=True)
mr_ = Ng.new('ShaderNodeMapRange'); mr_.interpolation_type = 'SMOOTHERSTEP'; Lg.new(tt_, mr_.inputs['Value'])
e_ = mr_.outputs['Result']
mx_ = Ng.new('ShaderNodeMix'); mx_.data_type = 'VECTOR'
Lg.new(e_, mx_.inputs['Factor']); Lg.new(_na('start', 'FLOAT_VECTOR'), mx_.inputs[4])
ps_ = Ng.new('GeometryNodeInputPosition'); Lg.new(ps_.outputs['Position'], mx_.inputs[5])
one_e = _gm('SUBTRACT', 1.0, e_)
vr_ = Ng.new('ShaderNodeVectorRotate'); vr_.rotation_type = 'Z_AXIS'
Lg.new(mx_.outputs[1], vr_.inputs['Vector']); Lg.new(_gm('MULTIPLY', _na('spin', 'FLOAT'), _gm('MULTIPLY', one_e, one_e)), vr_.inputs['Angle'])
sp_ = Ng.new('GeometryNodeSetPosition'); Lg.new(gi_.outputs['Geometry'], sp_.inputs['Geometry']); Lg.new(vr_.outputs['Vector'], sp_.inputs['Position'])
appear_ = _gm('POWER', _gm('DIVIDE', _gm('ADD', _gm('SUBTRACT', st_.outputs['Frame'], _na('delay', 'FLOAT')), 14.0), 9.0, clamp=True), 1.5)
# each grain comes out of the dark just before it sets off, so the cloud stays sparse and builds as it goes
land_ = Ng.new('ShaderNodeMapRange'); Lg.new(e_, land_.inputs['Value'])
land_.inputs['From Min'].default_value = 0.82; land_.inputs['From Max'].default_value = 1.0
land_.inputs['To Min'].default_value = 1.0; land_.inputs['To Max'].default_value = 0.0      # gone into the surface
scl_ = _gm('MULTIPLY', _gm('MULTIPLY', _na('size', 'FLOAT'), appear_), land_.outputs['Result'])
iop_ = Ng.new('GeometryNodeInstanceOnPoints')
oi_ = Ng.new('GeometryNodeObjectInfo'); oi_.inputs['Object'].default_value = fm_src; oi_.inputs['As Instance'].default_value = True
Lg.new(sp_.outputs['Geometry'], iop_.inputs['Points']); Lg.new(oi_.outputs['Geometry'], iop_.inputs['Instance'])
Lg.new(scl_, iop_.inputs['Scale'])
Lg.new(iop_.outputs['Instances'], go_.inputs['Geometry'])
form.modifiers.new('GN', 'NODES').node_group = ng_f
set_vis(form, diffuse=False, shadow=False, scatter=False)
for f_, h_ in ((1, False), (64, False), (65, True)):                                # done: out of every later render
    form.hide_render = h_; form.keyframe_insert('hide_render', frame=f_)

# the surface forms where the grains land: the same field against a REVEAL that sweeps bottom to top, a warm edge
ntc = m.node_tree; Nc, Lc = ntc.nodes, ntc.links
out_c = next(n_ for n_ in Nc if n_.bl_idname == 'ShaderNodeOutputMaterial' and n_.is_active_output)
src_c = out_c.inputs['Surface'].links[0].from_socket
def _cm(op, a, b=None, clamp=False):
    n_ = Nc.new('ShaderNodeMath'); n_.operation = op; n_.use_clamp = clamp
    for i_, v_ in enumerate((a, b)):
        if v_ is None: continue
        if isinstance(v_, (int, float)): n_.inputs[i_].default_value = v_
        else: Lc.new(v_, n_.inputs[i_])
    return n_.outputs[0]
tco = Nc.new('ShaderNodeTexCoord'); sxc = Nc.new('ShaderNodeSeparateXYZ'); Lc.new(tco.outputs['Object'], sxc.inputs[0])
X_, Y_, Z_ = sxc.outputs['X'], sxc.outputs['Y'], sxc.outputs['Z']
def _wave(kx, ky, kz, ph):
    return _cm('SINE', _cm('ADD', _cm('ADD', _cm('ADD', _cm('MULTIPLY', X_, kx), _cm('MULTIPLY', Y_, ky)), _cm('MULTIPLY', Z_, kz)), ph))
fld_ = _cm('ADD', _cm('ADD', 0.5, _cm('MULTIPLY', Z_, 0.5 / 0.44 * 0.94)),
           _cm('MULTIPLY', _cm('SINE', _cm('ADD', _cm('ADD', _cm('MULTIPLY', X_, 7.0), _cm('MULTIPLY', Y_, 5.0)), 2.0)), 0.025))   # = form_field()
rv_c = Nc.new('ShaderNodeValue'); rv_c.name = 'FORM_REVEAL'; rv_c.outputs[0].default_value = 1.2
dd_ = _cm('SUBTRACT', rv_c.outputs[0], fld_)
mask_ = Nc.new('ShaderNodeMapRange'); mask_.interpolation_type = 'SMOOTHSTEP'; Lc.new(dd_, mask_.inputs['Value'])
mask_.inputs['From Min'].default_value = 0.0; mask_.inputs['From Max'].default_value = 0.035
edge_ = _cm('MULTIPLY', _cm('SUBTRACT', 1.0, _cm('DIVIDE', _cm('ABSOLUTE', dd_), 0.024), clamp=True), 3.0)
em_c = Nc.new('ShaderNodeEmission'); em_c.inputs['Color'].default_value = (*lin('#FFC24A'), 1); Lc.new(edge_, em_c.inputs['Strength'])
ad_c = Nc.new('ShaderNodeAddShader'); Lc.new(src_c, ad_c.inputs[0]); Lc.new(em_c.outputs[0], ad_c.inputs[1])
# while it is open its inside walls are not drawn; the rising layer (below) closes it
geo_c = Nc.new('ShaderNodeNewGeometry'); in_c = Nc.new('ShaderNodeBsdfTransparent')
bf_c = Nc.new('ShaderNodeMixShader'); Lc.new(geo_c.outputs['Backfacing'], bf_c.inputs['Fac'])
Lc.new(ad_c.outputs[0], bf_c.inputs[1]); Lc.new(in_c.outputs[0], bf_c.inputs[2])
tr_c = Nc.new('ShaderNodeBsdfTransparent'); mx_c = Nc.new('ShaderNodeMixShader')
Lc.new(mask_.outputs['Result'], mx_c.inputs['Fac']); Lc.new(tr_c.outputs[0], mx_c.inputs[1]); Lc.new(bf_c.outputs[0], mx_c.inputs[2])
Lc.new(mx_c.outputs[0], out_c.inputs['Surface'])
for f_, v_ in ((1, -0.1), (FORM_F0 + FORM_DUR, -0.02), (FORM_F0 + FORM_DUR + FORM_SPAN, 1.06), (FORM_F0 + FORM_DUR + FORM_SPAN + 6, 1.2)):
    rv_c.outputs[0].default_value = v_; rv_c.outputs[0].keyframe_insert('default_value', frame=f_)
for fc in fcurves_of(ntc):
    if 'FORM_REVEAL' in fc.data_path:
        for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
REV_KEYS = [(1, -0.1), (FORM_F0 + FORM_DUR, -0.02), (FORM_F0 + FORM_DUR + FORM_SPAN, 1.06), (FORM_F0 + FORM_DUR + FORM_SPAN + 6, 1.2)]
def reveal_at(f):
    for (fa, va), (fb, vb) in zip(REV_KEYS, REV_KEYS[1:]):
        if fa <= f <= fb: return va + (vb - va) * (f - fa) / (fb - fa)
    return REV_KEYS[-1][1]
# the mould (storyboard): a clear glass cube is there first, catching the light at its edges; the gold fills it
shell = crisp_cube('FORM_SHELL', 0.895, 0.03, 4, coll=SHAPES); parent_to(shell, cube)
gm_, ntg_, outg_ = mat_nodes('form glass'); Ng_ = ntg_.nodes                  # thin glass: clear, bright at its edges
tg_ = Ng_.new('ShaderNodeBsdfTransparent'); tg_.inputs['Color'].default_value = (*lin('#fff6e6'), 1)
# (a glossy here mirrored the studio that lights the shapes' reflections: a grey floor inside a box in space. The
# sheen is drawn instead, a pale lilac that rises where the glass turns away)
gg_ = Ng_.new('ShaderNodeEmission'); gg_.inputs['Color'].default_value = (*lin('#d9ccff'), 1); gg_.inputs['Strength'].default_value = 0.42
lw_g = Ng_.new('ShaderNodeLayerWeight'); lw_g.inputs['Blend'].default_value = 0.12
mg_ = Ng_.new('ShaderNodeMixShader'); ntg_.links.new(lw_g.outputs['Fresnel'], mg_.inputs['Fac'])
ntg_.links.new(tg_.outputs[0], mg_.inputs[1]); ntg_.links.new(gg_.outputs[0], mg_.inputs[2])
ntg_.links.new(mg_.outputs[0], outg_.inputs['Surface']); shell.data.materials.append(gm_)
shell.visible_shadow = False
H_S = 0.4475                                                                   # its edges glow faintly gold
sh_corners = [Vector((x, y, z)) for x in (-H_S, H_S) for y in (-H_S, H_S) for z in (-H_S, H_S)]
for k_, (a_, b_) in enumerate([(a_, b_) for i_, a_ in enumerate(sh_corners) for b_ in sh_corners[i_ + 1:]
                               if sum(abs(a_[j] - b_[j]) > 1e-6 for j in range(3)) == 1]):
    eo_ = light_trail(f'FORM_EDGE_{k_}', [a_.lerp(b_, i / 30) for i in range(31)],
                      Vector((0, 0, 1)) if abs((b_ - a_).normalized().z) < 0.9 else Vector((1, 0, 0)),
                      (lambda u: 0.7), 0.0015, 1.5, taper=0.0, coll=FX, stops=GOLD_STOPS, anim=True)
    parent_to(eo_, cube)
    nte_ = eo_.data.materials[0].node_tree
    anim_node_value(nte_.nodes['REVEAL'], [(1, 0.0), (6 + k_, 0.0), (16 + k_, 1.06)])
    anim_node_value(nte_.nodes['GAIN'], [(1, 1.0), (56, 1.0), (64, 0.0)])
    for f_, h_ in ((1, True), (5 + k_, True), (6 + k_, False)):      # (a trail shows a stub before it draws: the gold
        eo_.hide_render = h_; eo_.keyframe_insert('hide_render', frame=f_)   # ticks scattered over the opening frame)
for f_, s_ in ((1, 0.0), (6, 0.0), (18, 1.0), (60, 1.0), (64, 0.0)):
    shell.scale = (s_,) * 3; shell.keyframe_insert('scale', frame=f_)
# the layer that rises with the cut: the cube fills, warm and glowing at its top, never a hollow box
bpy.ops.mesh.primitive_plane_add(size=0.87)
cap = bpy.context.object; cap.name = 'FORM_CAP'
for c_ in list(cap.users_collection): c_.objects.unlink(cap)
SHAPES.objects.link(cap); parent_to(cap, cube)
cm_, nt_cap, out_cap = mat_nodes('form cap'); b_cap = nt_cap.nodes.new('ShaderNodeBsdfPrincipled')
b_cap.inputs['Base Color'].default_value = (*lin('#FFD21A'), 1); b_cap.inputs['Roughness'].default_value = 0.3
b_cap.inputs['Emission Color'].default_value = (*lin('#FFB21F'), 1); b_cap.inputs['Emission Strength'].default_value = 2.4
nt_cap.links.new(b_cap.outputs[0], out_cap.inputs['Surface']); cap.data.materials.append(cm_)
for f_ in range(1, 70):
    r_ = reveal_at(f_)
    on_ = 1.0 if -0.01 < r_ < 0.985 else 0.0
    cap.location = (0, 0, max(-0.43, min(0.43, (r_ - 0.5) * 0.44 / 0.5 / 0.94)))
    cap.scale = (on_, on_, on_)
    cap.keyframe_insert('location', frame=f_); cap.keyframe_insert('scale', frame=f_)

spin_gold = spinner('SPIN_GOLD', AXIS, 12.0)
spin_vio = spinner('SPIN_VIOLET', AXIS, 6.0)
spin_in = spinner('SPIN_DUST_IN', AXIS, 18.0)
spin_out = spinner('SPIN_DUST_OUT', AXIS, 8.0)

trails = []   # (object, reveal start, reveal end)
for i in range(44):
    f = i / 43
    r = 0.93 + 0.44 * f ** 1.15 + rnd.uniform(-0.006, 0.006)
    span = rnd.uniform(250, 345); start = rnd.uniform(-245, -175)
    c, sg = rnd.uniform(0.5, 0.8), rnd.uniform(0.12, 0.26)
    uf = (front - start) / span
    o = light_trail(f'GOLD_{i}', *ring_path(r, math.radians(start), math.radians(start + span), plane),
                    (lambda u, c=c, sg=sg, uf=uf: 0.1 + 0.9 * max(math.exp(-((u - c) / sg) ** 2), 0.75 * math.exp(-((u - uf) / 0.13) ** 2))),
                    0.0012 + 0.0016 * rnd.random(), rnd.uniform(3.0, 9.0) * (1 - 0.45 * f), coll=SHAPES, stops=GOLD_STOPS, anim=True)
    parent_to(o, spin_gold)
    s0 = 34 + 26 * f + rnd.uniform(-4, 4)          # inner strands first, outer ones follow
    trails.append((o, s0, s0 + 34))
glow = light_band('GOLD_GLOW', *ring_path(1.13, math.radians(-235), math.radians(125), plane),
                  (lambda u: 0.2 + 0.8 * max(math.exp(-((u - 0.68) / 0.22) ** 2), 0.8 * math.exp(-((u - (front + 235) / 360) / 0.15) ** 2))),
                  0.26, 1.5, coll=SHAPES, stops=GOLD_STOPS, anim=True)
parent_to(glow, spin_gold); trails.append((glow, 46, 96))
for j, r in enumerate((1.6, 1.66, 1.95, 2.35)):
    span = rnd.uniform(300, 350); start = rnd.uniform(-250, -190)
    c = rnd.uniform(0.55, 0.78)
    o = light_trail(f'VIOLET_{j}', *ring_path(r, math.radians(start), math.radians(start + span), plane),
                    (lambda u, c=c: 0.08 + 0.92 * math.exp(-((u - c) / 0.22) ** 2)),
                    0.0011 + 0.0011 * rnd.random(), rnd.uniform(1.4, 2.6), coll=SHAPES, stops=VIOLET_STOPS, anim=True)
    parent_to(o, spin_vio)
    trails.append((o, 58 + 7 * j, 100 + 5 * j))


def dust_mat(name, stops, s_max):
    """glow_mat plus a per-grain `birth` (0..1) against a GROW value: grains appear as GROW passes their birth."""
    mt = glow_mat(name, stops, s_max)
    nt = mt.node_tree; Nn = nt.nodes; Lk = nt.links
    em = next(n for n in Nn if n.bl_idname == 'ShaderNodeEmission')
    src = em.inputs['Strength'].links[0].from_socket
    bt = Nn.new('ShaderNodeAttribute'); bt.attribute_type = 'INSTANCER'; bt.attribute_name = 'birth'
    gv = Nn.new('ShaderNodeValue'); gv.name = 'GROW'; gv.outputs[0].default_value = 1.0
    df = Nn.new('ShaderNodeMath'); df.operation = 'SUBTRACT'; Lk.new(gv.outputs[0], df.inputs[0]); Lk.new(bt.outputs['Fac'], df.inputs[1])
    mk = Nn.new('ShaderNodeMapRange'); mk.inputs['From Min'].default_value = 0.0; mk.inputs['From Max'].default_value = 0.06
    mk.clamp = True; Lk.new(df.outputs[0], mk.inputs['Value'])
    ml = Nn.new('ShaderNodeMath'); ml.operation = 'MULTIPLY'; Lk.new(src, ml.inputs[0]); Lk.new(mk.outputs['Result'], ml.inputs[1])
    Lk.new(ml.outputs[0], em.inputs['Strength'])
    # a grain not yet born is not there at all (not a black speck that hides what is behind it)
    out_ = next(n for n in Nn if n.bl_idname == 'ShaderNodeOutputMaterial')
    tr_ = Nn.new('ShaderNodeBsdfTransparent'); mx_ = Nn.new('ShaderNodeMixShader')
    Lk.new(mk.outputs['Result'], mx_.inputs['Fac']); Lk.new(tr_.outputs[0], mx_.inputs[1]); Lk.new(em.outputs[0], mx_.inputs[2])
    Lk.new(mx_.outputs[0], out_.inputs['Surface'])
    return mt


def ring_dust(name, n, r_lo, r_hi, bands, gaps, arms, arm_amp, pitch, seed, tone_lo, tone_hi, s_max, bias=None, early=0.06):
    rd = random.Random(seed)
    pts, tans, lens_, wid, br, tone, birth = [], [], [], [], [], [], []
    while len(pts) < n:
        r = r_lo + (r_hi - r_lo) * rd.random(); th = rd.random() * math.tau
        dens = sum(a_ * math.exp(-((r - c_) / w_) ** 2) for c_, w_, a_ in bands)
        for c_, w_ in gaps: dens *= 1 - 0.92 * math.exp(-((r - c_) / w_) ** 2)
        dens *= 1 + arm_amp * math.sin(arms * (th - pitch * math.log(r)) + 0.7)
        dens *= 0.55 + 0.9 * (noise.noise(Vector((r * 4.0, math.cos(th) * 3.0, math.sin(th) * 3.0))) * 0.5 + 0.5)
        if bias: dens *= bias(r, math.degrees(th))
        if rd.random() * 2.2 > dens: continue
        deg = math.degrees(th)
        heat = 0.3 + 0.7 * max(math.exp(-(((deg - 25 + 180) % 360 - 180) / 60) ** 2),
                               0.8 * math.exp(-(((deg - front + 180) % 360 - 180) / 45) ** 2))
        big = rd.random() < 0.025
        pts.append(M @ Vector((r * math.cos(th), r * math.sin(th), rd.gauss(0, 0.003 + 0.002 * r))))
        tans.append(tuple(M @ Vector((-math.sin(th), math.cos(th), 0.0))))
        lens_.append(0.0015 + 0.011 * rd.random() ** 3)
        wid.append(0.0018 if big else 0.0005 + 0.0005 * rd.random() ** 2)
        br.append(min(1.0, heat * (0.15 + 0.85 * rd.random() ** 3) * (1.6 if big else 1.0)))
        tone.append(min(1.0, max(0.0, tone_lo + (tone_hi - tone_lo) * (r - r_lo) / (r_hi - r_lo) + rd.gauss(0, 0.06))))
        # a few grains are there from the first frame; the rest arrive, the brightest last
        birth.append(rd.random() * early if rd.random() < 0.05 else early + (1 - early) * rd.random() ** 0.9)
    rots, scl = [], []
    for p_, t_, l_, w_ in zip(pts, tans, lens_, wid):
        z = Vector(t_).normalized(); x = z.orthogonal().normalized(); y = z.cross(x)
        rots.append(Matrix((x, y, z)).transposed().to_euler()); scl.append((w_, w_, l_))
    mt = dust_mat(name + '_m', DUST_STOPS, s_max)
    src = tiny_sphere(name + '_src', mt, FX, subdiv=2)
    o = points_object(name, pts, {'scl': scl, 'rot': rots, 'bright': br, 'tone': tone, 'birth': birth}, WORLD)
    gn_instancer(o, src, scale_vec_attr='scl', rot_attr='rot')
    set_vis(o, diffuse=False, shadow=False, scatter=False)
    return o, mt


dust_in, dm_in = ring_dust('DUST_IN', 36000, 0.95, 1.55, [(1.0, 0.05, 1.0), (1.1, 0.04, 0.75), (1.22, 0.06, 0.95), (1.38, 0.06, 0.55)],
                           [(1.17, 0.012), (1.31, 0.01)], 2, 0.45, 2.6, 71, 0.0, 0.25, 8.0)
dust_out, dm_out = ring_dust('DUST_OUT', 15000, 1.5, 3.7, [(1.72, 0.08, 0.7), (1.98, 0.1, 0.55), (2.3, 0.14, 0.45), (2.9, 0.3, 0.3)],
                             [(2.12, 0.02), (2.62, 0.03)], 3, 0.6, 2.2, 73, 0.18, 0.95, 3.2,
                             bias=lambda r, dg: 0.45 + 1.4 * math.exp(-(((dg + 60 + 180) % 360 - 180) / 50) ** 2) * math.exp(-(r - 1.5) / 1.8))
parent_to(dust_in, spin_in); parent_to(dust_out, spin_out)

# ----------------------------------------------------------------------------------------------- camera
cam = make_camera('CAM', 50)
P0 = dict(az=-2.0, el=7.0, d=2.55, tgt=Vector((0.0, 0.0, 0.03)), fstop=2.0)
P1 = dict(az=-10.0, el=12.0, d=4.6, tgt=Vector((0.06, 0.0, -0.04)), fstop=2.8)          # (V4: a larger hero cube)


def cam_at(f):
    t = ease((f - 1) / (N - 1))
    az = math.radians(P0['az'] + (P1['az'] - P0['az']) * t)
    el = math.radians(P0['el'] + (P1['el'] - P0['el']) * t)
    d = P0['d'] + (P1['d'] - P0['d']) * t
    tgt = P0['tgt'].lerp(P1['tgt'], t)
    loc = Vector((d * math.cos(el) * math.sin(az), -d * math.cos(el) * math.cos(az), d * math.sin(el)))
    return loc, tgt, P0['fstop'] + (P1['fstop'] - P0['fstop']) * t


# the final frame is the approved still: place everything that was framed by that camera first
loc1, tgt1, _ = cam_at(N)
cam.location = loc1; look_at(cam, tgt1); bpy.context.view_layer.update()

def glass_orb(name, tint, glow):                                # (V4: small glass orbs with a warm heart)
    m_, nt_, out_ = mat_nodes(name); b_ = nt_.nodes.new('ShaderNodeBsdfPrincipled')
    b_.inputs['Base Color'].default_value = (*lin(tint), 1); b_.inputs['Transmission Weight'].default_value = 1.0
    b_.inputs['Roughness'].default_value = 0.04; b_.inputs['IOR'].default_value = 1.45
    b_.inputs['Emission Color'].default_value = (*lin(glow), 1); b_.inputs['Emission Strength'].default_value = 0.6
    nt_.links.new(b_.outputs[0], out_.inputs['Surface']); return m_
gold_orb = glass_orb('orb gold', '#FFD58A', '#FFB21F')
vio_orb = glass_orb('orb violet', '#c9b8ff', '#7a5cff')


def on_ring(r, want_x, want_y):
    best_ = min(range(0, 360, 2), key=lambda dg: (screen_pos(scene, cam, M @ Vector((r * math.cos(math.radians(dg)), r * math.sin(math.radians(dg)), 0))).x - want_x) ** 2 +
                (screen_pos(scene, cam, M @ Vector((r * math.cos(math.radians(dg)), r * math.sin(math.radians(dg)), 0))).y - want_y) ** 2)
    # the orbs ride the outer spinner: start them 8 degrees back so they arrive on their mark
    return M @ Vector((r * math.cos(math.radians(best_ - 8)), r * math.sin(math.radians(best_ - 8)), 0))


orbs = []
for r, sx, sy, rad, mat_ in ((1.6, 0.17, 0.4, 0.026, gold_orb), (1.95, 0.12, 0.3, 0.02, vio_orb),
                             (1.95, 0.83, 0.72, 0.018, vio_orb), (2.35, 0.72, 0.17, 0.028, gold_orb),
                             (2.48, 0.93, 0.6, 0.022, gold_orb)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=rad * 1.7, segments=48, ring_count=24, location=on_ring(r, sx, sy))
    o_ = bpy.context.object; o_.data.materials.append(mat_)
    for pl in o_.data.polygons: pl.use_smooth = True
    parent_to(o_, spin_out); orbs.append(o_)

# the star: fixed far behind the cube's top corner as seen from the final camera. From the close start it hides
# behind the cube; as the camera pulls back it rises over the corner (parallax does the reveal).
cube.rotation_euler = Euler([math.radians(v) for v in ROT_END]); bpy.context.view_layer.update()
corners = [cube.matrix_world @ Vector((x, y, z)) for x in (-.44, .44) for y in (-.44, .44) for z in (-.44, .44)]
best = max(corners, key=lambda c: screen_pos(scene, cam, c).x + 1.4 * screen_pos(scene, cam, c).y)
sc = screen_pos(scene, cam, best)
star_pos = at_screen(cam, sc.x - 0.001, sc.y - 0.002, 160.0)
star, star_sun = backlight(cam, star_pos, (0, 0, 0), radius=0.3, disc=1100, sun=10.0, col='#fff6e4', corona=5, corona_size=5)
to_star = (star_pos - Vector((0, 0, 0))).normalized()
key = designed_spot('TOP_KEY', Vector((0.9, 1.3, 3.4)), (0, 0, 0.25), 1500, kelvin=5200, size_deg=80, cup=(38, 18),
                    hot=(10, 3), cup_k=0.55, hot_k=1.0, amb_k=0.14, shimmer=0.07, radius=0.25, gobo=0.28)
behind = (Vector((0, 0, 0)) - cam.location).normalized() * 0.95 + Vector((0, 0, 0.05))
capture = point('CAPTURE', behind, 140, '#FFC873', radius=0.18); capture.visible_glossy = False
back_soft = area('BACK_SOFT', to_star * 3.2 + Vector((0, 0, 0.35)), (0, 0, 0.1), 2.4, 420, '#FFEFCF')
band_lights = []
for k_ in range(7):
    a = math.radians(front - 54 + 18 * k_)
    bl_ = point(f'BAND_L{k_}', M @ Vector((1.08 * math.cos(a), 1.08 * math.sin(a), -0.12)), 2.2, '#FFD860', radius=0.12)
    bl_.visible_glossy = False; band_lights.append(bl_)
ds = area('DARK_SIDE', (-3.2, -2.0, 0.6), (0, 0, 0), 3.0, 4, '#6b52d8'); ds.visible_glossy = False
fc = max(corners, key=lambda c: -(c - cam.location).length)
fg = area('FACE_GRAD', fc + (fc - Vector((0, 0, 0))).normalized() * 0.5 + Vector((0.55, 0.2, 0.45)), fc + Vector((0.3, 0.2, 0.2)), 0.35, 10, '#FFE7A0')
fg.visible_glossy = False
haze = light_band('VIOLET_HAZE', *ring_path(2.4, math.radians(-240), math.radians(120), plane),
                  (lambda u: 0.4 + 0.6 * math.sin(math.pi * u)), 0.7, 0.045, coll=WORLD, stops=VIOLET_STOPS, anim=True)
scene.world = nebula_world(base='#08031a', strength=1.9, cover=0.24, wisps=0.32, glitter=8.0, env=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'hdri', 'studio_small_09_2k.hdr'), env_strength=1.1)        # (V4: the universe is a place: a nebula, not a void)
stars(WORLD, FX, n=6000, seed=31, max_b=14.0, size_k=1.6)
# (storyboard) dust drifting in the foreground and between the stars: out of focus, it becomes bokeh and depth
rb_ = random.Random(77); bk_p, bk_s, bk_b, bk_t = [], [], [], []
for _ in range(1500):
    d_ = Vector((rb_.gauss(0, 1), rb_.gauss(0, 1), rb_.gauss(0, 0.6))).normalized()
    bk_p.append(d_ * (1.4 + 7.0 * rb_.random() ** 0.8)); bk_s.append(0.004 + 0.013 * rb_.random() ** 2)
    bk_b.append(0.2 + 1.0 * rb_.random() ** 3); bk_t.append(rb_.random() * 0.9)
bk_o = glitter('BOKEH_DUST', FX, WORLD, bk_p, bk_b, bk_s, s_max=4.0, stops=(('#7a5cff', 0.0), ('#FFC94F', 0.55), ('#fff1d6', 1.0)))
bpy.data.objects['BOKEH_DUST'].hide_render = True      # (feedback Oct 25: the dots felt cluttered) the stars are enough
# Feedback (Oct 2026): no ring round the cube. Its gold strands, glow band, both dust discs, the lights along the band
# and the violet haze band are still built (later code reaches for them) but never rendered. The thin violet orbit
# lines stay.
for o_ in [o for o, *_ in trails if o.name.startswith('GOLD')] + [dust_in, dust_out, haze] + band_lights:
    o_.hide_render = True

# ----------------------------------------------------------------------------------------------- animation
for f in range(1, N + 1):                                          # camera: baked per frame, eased dolly-out
    loc, tgt, fs = cam_at(f)
    cam.location = loc; look_at(cam, tgt)
    cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
    cam.data.dof.focus_distance = (loc - Vector((0, 0, 0))).length - 0.1; cam.data.dof.aperture_fstop = fs
    cam.data.dof.keyframe_insert('focus_distance', frame=f); cam.data.dof.keyframe_insert('aperture_fstop', frame=f)
for f in range(1, N + 1):                                          # the cube turns very slowly and breathes
    t = (f - 1) / (N - 1)
    cube.rotation_euler = Euler((math.radians(ROT_END[0]), math.radians(ROT_END[1]), math.radians(ROT_END[2] - 12 * (1 - t))))
    cube.location = (0, 0, 0.012 * math.sin(t * math.pi * 1.5))
    cube.keyframe_insert('rotation_euler', frame=f); cube.keyframe_insert('location', frame=f)

L_ = lambda o: o.data
anim_float(L_(capture), 'energy', [(1, 0.0), (10, 0.0), (36, 140.0)])                 # light captured first
# THE LIGHT, as a sunrise (feedback: not a sun that sits there; Oct 25: the warp lines did not feel cinematic). Once
# the cube is whole a pinpoint breaks over its corner, as a sun over a planet's limb; rays fan out round the edges; the
# light swells and blooms warm over the whole frame and holds a breath; then it recedes as an eye adjusts, and a slow
# drift of embers floats out past the camera, leaving the cube in its own light.
L_GROW, L_PEAK, L_GONE = 58, 92, 110
anim_float(L_(star_sun), 'energy', [(1, 0.0), (L_GROW, 0.0), (L_PEAK - 10, 10.0), (L_PEAK, 24.0), (L_PEAK + 8, 20.0), (L_GONE, 0.0)])
star_em = next(n for n in star.data.materials[0].node_tree.nodes if n.bl_idname == 'ShaderNodeEmission')
anim_input(star_em, 'Strength', [(1, 0.0), (L_GROW, 0.0), (L_GROW + 8, 900.0), (L_GROW + 22, 7000.0), (L_PEAK, 50000.0),
                                 (L_PEAK + 8, 36000.0), (L_GONE, 0.0)])
cor_mat = bpy.data.objects['CORONA'].data.materials[0]
cor_ml = next(n for n in cor_mat.node_tree.nodes if n.bl_idname == 'ShaderNodeMath' and n.operation == 'MULTIPLY')
for f_, v_ in ((1, 0.0), (L_GROW, 0.0), (L_GROW + 14, 4.0), (L_PEAK, 34.0), (L_PEAK + 8, 26.0), (L_GONE, 0.0)):
    cor_ml.inputs[1].default_value = v_; cor_ml.inputs[1].keyframe_insert('default_value', frame=f_)
for f_, v_ in ((1, -0.3), (L_GROW + 16, -0.3), (L_PEAK - 8, 0.45), (L_PEAK, 1.45), (L_PEAK + 8, 1.6), (L_GONE - 4, 0.35),
               (L_GONE + 4, -0.3)):                                                  # a warm bloom, held, then gone
    scene.view_settings.exposure = v_; scene.keyframe_insert('view_settings.exposure', frame=f_)
# the sparks it breaks into: from where it stood, out across the frame and past the lens
rk = random.Random(17); sk_p, sk_v, sk_s, sk_r, sk_b, sk_t = [], [], [], [], [], []
vdir = (tgt1 - loc1).normalized(); rgt = vdir.cross(Vector((0, 0, 1))).normalized(); upv_ = rgt.cross(vdir).normalized()
origin_ = best + to_star * 0.8
for _ in range(220):                                                 # embers: round, slow, a few near the lens
    a_ = rk.uniform(0, math.tau); sp_ = 0.010 + 0.034 * rk.random() ** 1.6
    vel = (rgt * math.cos(a_) + upv_ * math.sin(a_)) * sp_ - vdir * sp_ * rk.uniform(0.4, 1.6)
    sk_v.append(vel); sk_p.append(origin_ + vel.normalized() * rk.uniform(0.0, 0.35) - vel * L_PEAK)
    w_ = 0.004 + 0.011 * rk.random() ** 2.0
    sk_s.append((w_, w_, w_)); sk_r.append(Euler((0, 0, 0)))
    sk_b.append(0.25 + 0.75 * rk.random() ** 2); sk_t.append(rk.random() * 0.5)
sparks = points_object('LIGHT_SPARKS', sk_p, {'vel': sk_v, 'scl': sk_s, 'rot': sk_r, 'bright': sk_b, 'tone': sk_t}, FX)
em_mat = glow_mat('light sparks', DUST_STOPS, 6.0)
nt_e = em_mat.node_tree                                        # pure light: as they cool they fade, never dark specks
em_n = next(n for n in nt_e.nodes if n.bl_idname == 'ShaderNodeEmission')
out_e = next(n for n in nt_e.nodes if n.bl_idname == 'ShaderNodeOutputMaterial')
tr_e = nt_e.nodes.new('ShaderNodeBsdfTransparent'); add_e = nt_e.nodes.new('ShaderNodeAddShader')
nt_e.links.new(em_n.outputs[0], add_e.inputs[0]); nt_e.links.new(tr_e.outputs[0], add_e.inputs[1]); nt_e.links.new(add_e.outputs[0], out_e.inputs['Surface'])
gn_instancer(sparks, tiny_sphere('SPARK_src', em_mat, FX), drift_attr='vel', drift_rate=1.0, scale_vec_attr='scl', rot_attr='rot')
set_vis(sparks, diffuse=False, shadow=False, scatter=False)
em_k = next(n for n in em_mat.node_tree.nodes if n.bl_idname == 'ShaderNodeMapRange')          # they cool as they drift
anim_input(em_k, 'To Max', [(L_PEAK, 6.0), (L_GONE, 3.0), (118, 0.0)])
for f_, h_ in ((1, True), (L_PEAK - 1, True), (L_PEAK, False), (118, False), (119, True)):
    sparks.hide_render = h_; sparks.keyframe_insert('hide_render', frame=f_)
# (storyboard) a warm aura round the cube: a soft glow seen by the camera (and through glass), on a card through the
# cube's centre that always faces the lens, so the cube hides the middle and only a halo shows round its edges. It
# carries over when the cube becomes a world (it scales with it): an atmosphere.
am_, at_, ao_ = mat_nodes('cube aura'); A_ = at_.nodes; AL_ = at_.links
tca_ = A_.new('ShaderNodeTexCoord')
sub_ = A_.new('ShaderNodeVectorMath'); sub_.operation = 'SUBTRACT'; sub_.inputs[1].default_value = (0.5, 0.5, 0.0)
AL_.new(tca_.outputs['UV'], sub_.inputs[0])
len_ = A_.new('ShaderNodeVectorMath'); len_.operation = 'LENGTH'; AL_.new(sub_.outputs[0], len_.inputs[0])
fo_ = A_.new('ShaderNodeMapRange'); fo_.inputs['From Max'].default_value = 0.5; fo_.inputs['To Min'].default_value = 1.0
fo_.inputs['To Max'].default_value = 0.0; fo_.clamp = True; AL_.new(len_.outputs['Value'], fo_.inputs['Value'])
pw_ = A_.new('ShaderNodeMath'); pw_.operation = 'POWER'; pw_.inputs[1].default_value = 2.4; AL_.new(fo_.outputs['Result'], pw_.inputs[0])
ak_ = A_.new('ShaderNodeValue'); ak_.name = 'AURA_K'; ak_.outputs[0].default_value = 0.0
mk_ = A_.new('ShaderNodeMath'); mk_.operation = 'MULTIPLY'; AL_.new(pw_.outputs[0], mk_.inputs[0]); AL_.new(ak_.outputs[0], mk_.inputs[1])
ae_ = A_.new('ShaderNodeEmission'); ae_.inputs['Color'].default_value = (*lin('#FFB43C'), 1); AL_.new(mk_.outputs[0], ae_.inputs['Strength'])
atr_ = A_.new('ShaderNodeBsdfTransparent'); aad_ = A_.new('ShaderNodeAddShader')
AL_.new(atr_.outputs[0], aad_.inputs[0]); AL_.new(ae_.outputs[0], aad_.inputs[1]); AL_.new(aad_.outputs[0], ao_.inputs['Surface'])
no_emission_sampling(am_)
AURA_SIZE = 4.2
me_a = bpy.data.meshes.new('aura')
me_a.from_pydata([(-AURA_SIZE / 2, -AURA_SIZE / 2, 0), (AURA_SIZE / 2, -AURA_SIZE / 2, 0), (AURA_SIZE / 2, AURA_SIZE / 2, 0), (-AURA_SIZE / 2, AURA_SIZE / 2, 0)], [], [(0, 1, 2, 3)])
uv_a = me_a.uv_layers.new(name='UVMap')
for lp_ in me_a.loops:
    v_ = me_a.vertices[lp_.vertex_index].co; uv_a.data[lp_.index].uv = (v_.x / AURA_SIZE + 0.5, v_.y / AURA_SIZE + 0.5)
me_a.materials.append(am_)
aura = bpy.data.objects.new('CUBE_AURA', me_a); FX.objects.link(aura); parent_to(aura, cube)
ct_a = aura.constraints.new('TRACK_TO'); ct_a.target = cam; ct_a.track_axis = 'TRACK_Z'; ct_a.up_axis = 'UP_Y'
set_vis(aura, camera=True, diffuse=False, glossy=False, transmission=True, scatter=False, shadow=False)
AURA_N = ak_
anim_node_value(AURA_N, [(1, 0.0), (L_PEAK + 8, 0.0), (L_GONE + 10, 0.6)])
# THE SUN, after the reference: as the camera pulls back the star clears the cube's corner, as a sun clears a
# planet's limb, and blooms: long uneven beams fan out from it and a faint rainbow halo arcs above. A large card at the
# star, facing the hero camera; the cube eclipses it, so the beams break out round the corner as it is revealed.
SUN_HALF = 62.0
bpy.ops.mesh.primitive_plane_add(size=SUN_HALF * 2, location=star_pos)
rays = bpy.context.object; rays.name = 'SUNRAYS'
rays.rotation_euler = (loc1 - star_pos).to_track_quat('Z', 'Y').to_euler()
m_r, nt_r, out_r = mat_nodes('sun rays'); Nr = nt_r.nodes; Lr = nt_r.links
def _m(op, a, b=None, clamp=False):
    n_ = Nr.new('ShaderNodeMath'); n_.operation = op; n_.use_clamp = clamp
    for i_, v_ in enumerate((a, b)):
        if v_ is None: continue
        if isinstance(v_, (int, float)): n_.inputs[i_].default_value = v_
        else: Lr.new(v_, n_.inputs[i_])
    return n_.outputs[0]
tc_ = Nr.new('ShaderNodeTexCoord'); sx_ = Nr.new('ShaderNodeSeparateXYZ'); Lr.new(tc_.outputs['Generated'], sx_.inputs[0])
x_ = _m('SUBTRACT', sx_.outputs['X'], 0.5); y_ = _m('SUBTRACT', sx_.outputs['Y'], 0.5)
r_ = _m('SQRT', _m('ADD', _m('MULTIPLY', x_, x_), _m('MULTIPLY', y_, y_)))
ang_ = _m('ARCTAN2', y_, x_)
cx_ = _m('COSINE', ang_); sy_ = _m('SINE', ang_)
cb_ = Nr.new('ShaderNodeCombineXYZ'); Lr.new(_m('MULTIPLY', cx_, 3.2), cb_.inputs['X']); Lr.new(_m('MULTIPLY', sy_, 3.2), cb_.inputs['Y'])
cb_.inputs['Z'].default_value = 7.3
nz_ = Nr.new('ShaderNodeTexNoise'); nz_.inputs['Detail'].default_value = 3.0; nz_.inputs['Roughness'].default_value = 0.62
nz_.inputs['Scale'].default_value = 1.0; Lr.new(cb_.outputs[0], nz_.inputs['Vector'])
spk_ = _m('POWER', _m('MULTIPLY', _m('SUBTRACT', nz_.outputs['Fac'], 0.515), 5.5, clamp=True), 1.8)    # a fan of uneven beams
reach_ = _m('POWER', _m('SUBTRACT', 1.0, _m('DIVIDE', r_, 0.5), clamp=True), 3.0)                       # fading outward
beams_ = _m('MULTIPLY', _m('MULTIPLY', spk_, reach_), 2.5)
core_ = _m('MULTIPLY', _m('POWER', _m('SUBTRACT', 1.0, _m('DIVIDE', r_, 0.045), clamp=True), 3.0), 40.0)  # the bloom
haze_ = _m('MULTIPLY', _m('POWER', _m('SUBTRACT', 1.0, _m('DIVIDE', r_, 0.22), clamp=True), 2.5), 0.8)    # soft halo
# the rainbow arc: a thin ring at 0.3, red outside to violet inside, only over the upper left
band_ = _m('DIVIDE', _m('SUBTRACT', r_, 0.33), 0.016)
rb_ = Nr.new('ShaderNodeValToRGB'); cr_ = rb_.color_ramp
cr_.elements[0].position, cr_.elements[0].color = 0.0, (0, 0, 0, 1)
cr_.elements[1].position, cr_.elements[1].color = 1.0, (0, 0, 0, 1)
for p_, c_ in ((0.18, (0.55, 0.4, 0.95)), (0.36, (0.45, 0.6, 1.0)), (0.52, (0.55, 1.0, 0.7)), (0.68, (1.0, 0.92, 0.55)), (0.84, (1.0, 0.55, 0.4))):
    e_ = cr_.elements.new(p_); e_.color = (*c_, 1)
Lr.new(_m('ADD', _m('MULTIPLY', band_, 0.5), 0.5), rb_.inputs['Fac'])
arcm_ = _m('POWER', _m('MULTIPLY', _m('ADD', _m('COSINE', _m('SUBTRACT', ang_, 2.25)), -0.35), 1.6, clamp=True), 1.5)
arc_ = Nr.new('ShaderNodeMix'); arc_.data_type = 'RGBA'; arc_.blend_type = 'MULTIPLY'; arc_.inputs['Factor'].default_value = 1.0
Lr.new(rb_.outputs['Color'], arc_.inputs['A']); arc_.inputs['B'].default_value = (1, 1, 1, 1)
arc_s = Nr.new('ShaderNodeVectorMath'); arc_s.operation = 'SCALE'; Lr.new(arc_.outputs['Result'], arc_s.inputs[0])
Lr.new(_m('MULTIPLY', arcm_, 0.1), arc_s.inputs['Scale'])
sun_v = Nr.new('ShaderNodeValue'); sun_v.name = 'SUN'; sun_v.outputs[0].default_value = 1.0
warm_ = Nr.new('ShaderNodeEmission'); warm_.inputs['Color'].default_value = (*lin('#ffe9c8'), 1)
Lr.new(_m('MULTIPLY', _m('ADD', _m('ADD', beams_, core_), haze_), sun_v.outputs[0]), warm_.inputs['Strength'])
rain_ = Nr.new('ShaderNodeEmission'); Lr.new(arc_s.outputs[0], rain_.inputs['Color'])
Lr.new(sun_v.outputs[0], rain_.inputs['Strength'])
tr_r = Nr.new('ShaderNodeBsdfTransparent'); ad1 = Nr.new('ShaderNodeAddShader'); ad2 = Nr.new('ShaderNodeAddShader')
Lr.new(tr_r.outputs[0], ad1.inputs[0]); Lr.new(warm_.outputs[0], ad1.inputs[1])
Lr.new(ad1.outputs[0], ad2.inputs[0]); Lr.new(rain_.outputs[0], ad2.inputs[1]); Lr.new(ad2.outputs[0], out_r.inputs['Surface'])
no_emission_sampling(m_r); rays.data.materials.append(m_r)
set_vis(rays, diffuse=False, glossy=False, transmission=False, scatter=False, shadow=False)
anim_node_value(sun_v, [(1, 0.0), (L_GROW, 0.0), (L_GROW + 12, 0.5), (L_GROW + 24, 1.4), (L_PEAK, 3.6), (L_PEAK + 8, 2.6), (L_GONE, 0.0)])
for f_, s_ in ((1, 1.0), (L_GROW + 12, 1.0), (L_PEAK, 2.2), (L_GONE, 2.9)):                 # the beams reach out as it swells
    rays.scale = (s_,) * 3; rays.keyframe_insert('scale', frame=f_)
q_r0 = rays.rotation_euler.to_quaternion()
for f_, a_ in ((L_GROW, 0.0), (L_GONE, 9.0)):                                                # and turn, slowly
    rays.rotation_euler = (q_r0 @ Quaternion(Vector((0, 0, 1)), math.radians(a_))).to_euler(); rays.keyframe_insert('rotation_euler', frame=f_)
anim_float(L_(key), 'energy', [(1, 0.0), (26, 0.0), (72, 1500.0)])
anim_float(L_(back_soft), 'energy', [(1, 0.0), (30, 0.0), (72, 420.0)])
anim_float(L_(fg), 'energy', [(1, 0.0), (30, 0.0), (72, 10.0)])
anim_float(L_(ds), 'energy', [(1, 0.0), (20, 0.0), (60, 4.0)])
for bl_ in band_lights:
    anim_float(L_(bl_), 'energy', [(1, 0.0), (44, 0.0), (90, 2.2)])
for o, s0, s1 in trails:                                            # rings draw themselves round the cube
    nt = o.data.materials[0].node_tree
    anim_node_value(nt.nodes['REVEAL'], [(1, 0.0), (int(s0), 0.0), (int(s1), 1.06)])
    anim_node_value(nt.nodes['GAIN'], [(1, 0.0), (int(s0), 0.0), (int(s0) + 10, 1.0)])
hz = haze.data.materials[0].node_tree
anim_node_value(hz.nodes['REVEAL'], [(1, 1.06)]); anim_node_value(hz.nodes['GAIN'], [(1, 0.0), (40, 0.0), (100, 1.0)])
anim_node_value(dm_in.node_tree.nodes['GROW'], [(1, 0.06), (14, 0.06), (96, 1.0)])     # dust gathers into its bands
anim_node_value(dm_out.node_tree.nodes['GROW'], [(1, 0.06), (30, 0.06), (108, 1.0)])
for o_ in orbs:                                                     # orbs condense onto their rails
    for f_, s_ in ((1, 0.0), (70, 0.0), (104, 1.0)):
        o_.scale = (s_,) * 3; o_.keyframe_insert('scale', frame=f_)

# ----------------------------------------------------------------------------------------------- idle loop
LOOP_L, LOOP_C = 96, 24                 # loop length and crossfade frames (rendered N+1 .. N+L+C)
for o, s0, s1 in trails:
    nt = o.data.materials[0].node_tree
    anim_node_value(nt.nodes['PULSE'], [(N, 0.0), (N + 1, 1.0)])
    for fc in fcurves_of(nt):
        if 'PULSE' in fc.data_path:
            for kp in fc.keyframe_points: kp.interpolation = 'CONSTANT'
    anim_node_value(nt.nodes['PHASE'], [(N, 0.0), (N + LOOP_L, 1.0)])
    for fc in fcurves_of(nt):
        if 'PHASE' in fc.data_path:
            for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
            fc.extrapolation = 'LINEAR'
for f in range(N + 1, N + LOOP_L + LOOP_C + 1):          # the cube breathes: periodic, so the loop has no seam
    u = (f - N) / LOOP_L
    cube.location = (0, 0, -0.012 + 0.006 * (1 - math.cos(math.tau * u)))
    cube.rotation_euler = Euler((math.radians(ROT_END[0]), math.radians(ROT_END[1]), math.radians(ROT_END[2] + 0.8 * math.sin(math.tau * u))))
    cube.keyframe_insert('location', frame=f); cube.keyframe_insert('rotation_euler', frame=f)

# ----------------------------------------------------------------------------------------------- scene 02
# The Shapes Arrive. One continuous move out of the hero frame: the camera rises and pulls back into a three-quarter
# view of the system; orbit lines draw themselves out round the golden band; the library shapes enter one at a time,
# each with its own movement language from the brief, and settle onto the orbits.
S4_MODES = ('s4', 's4final', 'dry4', 'fore4', 'fore4final', 's5', 's5final')
S2 = MODE in ('s2', 's2final', 'dry2', 's3', 's3final', 'dry3', 'fore3', 'fore3final') + S4_MODES
S2_LEN = 140
S2_0, S2_1 = N + 1, N + S2_LEN
if S2:
    Q0 = dict(az=P1['az'], el=P1['el'], d=P1['d'], tgt=P1['tgt'], fstop=P1['fstop'])
    Q1 = dict(az=-24.0, el=22.0, d=13.0, tgt=Vector((0.45, 0.55, -0.3)), fstop=4.5)

    def cam2(f):
        t = ease((f - N) / S2_LEN)
        az = math.radians(Q0['az'] + (Q1['az'] - Q0['az']) * t)
        el = math.radians(Q0['el'] + (Q1['el'] - Q0['el']) * t)
        d = Q0['d'] + (Q1['d'] - Q0['d']) * t
        tgt = Q0['tgt'].lerp(Q1['tgt'], t)
        loc = Vector((d * math.cos(el) * math.sin(az), -d * math.cos(el) * math.cos(az), d * math.sin(el)))
        return loc, tgt, Q0['fstop'] + (Q1['fstop'] - Q0['fstop']) * t

    loc_e, tgt_e, _ = cam2(S2_1)
    cam.location = loc_e; look_at(cam, tgt_e); bpy.context.view_layer.update()
    ORB2 = [2.7, 3.15, 3.6, 4.1]

    def ring_pt(r, deg, lift=0.0):
        a = math.radians(deg); return M @ Vector((r * math.cos(a), r * math.sin(a), lift))

    def angle_for(r, sx, sy):
        return min(range(0, 360, 2), key=lambda dg: (screen_pos(scene, cam, ring_pt(r, dg)).x - sx) ** 2 + (screen_pos(scene, cam, ring_pt(r, dg)).y - sy) ** 2)

    # shape, scale, orbit, final screen spot, start frame, flight frames, movement language
    SPEC = [('sphere', 0.30, 0, (0.24, 0.6), 136, 52, 'orbital'),
            ('cone', 0.32, 1, (0.8, 0.36), 148, 40, 'diagonal'),
            ('arch', 0.27, 1, (0.72, 0.72), 160, 46, 'spin_in'),
            ('cube', 0.38, 2, (0.18, 0.3), 172, 48, 'steps'),
            ('torus', 0.22, 3, (0.9, 0.56), 184, 54, 'circle'),
            ('dome', 0.20, 2, (0.47, 0.17), 196, 44, 'descend'),
            ('octa', 0.45, 3, (0.6, 0.86), 208, 46, 'tumble')]
    orbit_first = {}
    shapes2 = []
    for shp, sc_, k, (sx, sy), f0, du, lang in SPEC:            # (not `key`: that name holds the key light)
        r = ORB2[k]; deg = angle_for(r, sx, sy)
        root = import_shape(shp, f'S2_{shp}'); into(root, SHAPES)
        brand_glow(root, shp)                                     # (brand colours, the storyboard's luminous finish)
        shapes2.append((root, sc_, r, deg, f0, du, lang))
        orbit_first.setdefault(k, (f0, du))
        print(f'S2 SHAPE {shp}: orbit {r} at {deg} deg, screen target ({sx}, {sy})')

    def shape_state(f, sc_, r, deg, f0, du, lang, seed):
        u = max(0.0, min(1.0, (f - f0) / du))
        drift = max(0.0, f - (f0 + du)) * 0.12                    # once home, it keeps orbiting, slowly
        end = ring_pt(r, deg + drift)
        rot = Euler((0.35 * math.sin(seed), 0.25 * math.cos(seed), seed + math.radians(drift * 2)))
        if lang == 'orbital':                                     # sphere: a slow spiral in along the orbit plane
            e = 1 - (1 - u) ** 3
            pos = ring_pt(r * (1 + 1.4 * (1 - e)), deg + drift + 150 * (1 - e), 1.2 * (1 - e))
        elif lang == 'diagonal':                                  # triangle: a sharp straight cut from top right
            e = u * u * (3 - 2 * u)
            start = end + Vector((3.8, 2.8, 3.2))
            pos = start.lerp(end, e)
            dirv = (end - start).normalized()
            q_fly = dirv.to_track_quat('Z', 'Y'); q_home = Euler((0.0, 0.0, seed)).to_quaternion()
            rot = q_fly.slerp(q_home, ease((u - 0.7) / 0.3)).to_euler()
        elif lang == 'spin_in':                                   # arch: turns slowly while moving inward
            e = 1 - (1 - u) ** 2.5
            pos = (end + Vector((4.8, -1.6, 1.1))).lerp(end, e)
            rot = Euler((math.radians(12) * (1 - e), 0.0, seed + math.radians(200) * (1 - e)))
        elif lang == 'steps':                                     # cube: structured, three right-angle moves
            S0 = end + Vector((-3.2, -2.4, 2.2))
            W1 = Vector((end.x, S0.y, S0.z)); W2 = Vector((end.x, end.y, S0.z))
            leg = min(2, int(u * 3)); lu = ease(u * 3 - leg)
            a_, b_ = [(S0, W1), (W1, W2), (W2, end)][leg]
            pos = a_.lerp(b_, lu) if u < 1 else end
            rot = Euler((0.0, 0.0, seed + math.radians(90) * (leg + lu) if u < 1 else seed + math.radians(270)))
        elif lang == 'circle':                                    # ring: travels a circle round the system
            e = ease(u)
            pos = ring_pt(r, deg + drift - 300 * (1 - e), 0.8 * (1 - e))
            rot = Euler((math.radians(70) + 0.2 * math.sin(f * 0.05), 0.0, f * 0.03))
        elif lang == 'descend':                                   # dome: settles from above
            e = 1 - (1 - u) ** 3
            pos = end + Vector((0.4 * math.sin(u * 3.0) * (1 - e), 0.0, 3.6 * (1 - e)))
            rot = Euler((0.0, 0.0, seed))
        elif lang == 'tumble':                                    # faceted crystal: tumbles in on a curve
            e = 1 - (1 - u) ** 2.2
            start = end + Vector((-2.6, 3.6, 2.6))
            mid = (start + end) / 2 + Vector((1.2, 0.0, 0.8))
            pos = (1 - e) ** 2 * start + 2 * (1 - e) * e * mid + e * e * end
            rot = Euler((math.tau * (1 - e) * 1.2, math.tau * (1 - e) * 0.8, seed + math.tau * (1 - e)))
        appear = ease((f - f0) / 10.0)                             # out of the dark: grows in over the first frames
        return pos, rot, sc_ * appear

    for f in range(S2_0, S2_1 + 1):
        for i, (root, sc_, r, deg, f0, du, lang) in enumerate(shapes2):
            pos, rot, s_ = shape_state(f, sc_, r, deg, f0, du, lang, seed=1.3 * i + 0.4)
            root.location = pos; root.rotation_euler = rot; root.scale = (max(s_, 1e-4),) * 3
            root.keyframe_insert('location', frame=f); root.keyframe_insert('rotation_euler', frame=f)
            root.keyframe_insert('scale', frame=f)
    for root, *_ in shapes2:          # parked and hidden until their entrance
        root.scale = (1e-4,) * 3; root.keyframe_insert('scale', frame=N)

    # the orbit lines draw themselves as their first shape comes in
    for k, r in enumerate(ORB2):
        o = light_trail(f'ORBIT2_{k}', *ring_path(r, math.radians(-180), math.radians(180), plane),
                        (lambda u, k=k: 0.25 + 0.75 * max(math.exp(-((u - 0.55 - 0.1 * k) / 0.16) ** 2), 0.5 * math.exp(-((u - 0.2) / 0.1) ** 2))),
                        0.0014, 3.2 if k % 2 == 0 else 2.6, coll=SHAPES, stops=GOLD_STOPS if k % 2 == 0 else VIOLET_STOPS, anim=True)
        f0, du = orbit_first[k]
        nt = o.data.materials[0].node_tree
        anim_node_value(nt.nodes['REVEAL'], [(N, 0.0), (int(f0 + 0.3 * du), 0.0), (int(f0 + du + 24), 1.06)])
        anim_node_value(nt.nodes['GAIN'], [(N, 0.0), (int(f0 + 0.3 * du), 0.0), (int(f0 + 0.3 * du) + 10, 1.0)])
        trails.append((o, 0, 0))
        # (storyboard) fine gold dust along each orbit, a few brighter beads among it
        ro_ = random.Random(100 + k); od_p, od_b, od_s = [], [], []
        for _ in range(1500):
            th_ = ro_.uniform(0, math.tau); rr_ = r + ro_.gauss(0, 0.045)
            od_p.append(M @ Vector((rr_ * math.cos(th_), rr_ * math.sin(th_), ro_.gauss(0, 0.012))))
            big_ = ro_.random() < 0.02
            od_b.append(min(1.0, (0.15 + 0.85 * ro_.random() ** 3) * (2.5 if big_ else 1.0)))
            od_s.append((0.012 if big_ else 0.003 + 0.004 * ro_.random() ** 2))
        od = glitter(f'ORBIT_DUST_{k}', FX, WORLD, od_p, od_b, od_s, s_max=5.0)
        for f_, h_ in ((1, True), (int(f0 + du) - 1, True), (int(f0 + du), False), (S2_1 + 40, False), (S2_1 + 41, True)):
            od.hide_render = h_; od.keyframe_insert('hide_render', frame=f_)

    # light for the wider system, rising from nothing so the hero frame is untouched at the hand-off
    # (look-dev) a neutral soft key large enough to lay long highlights on gloss and gold; a violet rim tying the
    # shapes to the nebula; a cool fill from the front so the brand reds and greens never go muddy
    sys_key = area('SYS_KEY', (-6.0, -5.0, 7.0), (0, 0, 0), 10.0, 1150, '#F3F0FF'); sys_key.visible_glossy = True
    sys_rim = area('SYS_RIM', (0.5, 9.0, 3.0), (0, 0, 0), 7.0, 1200, '#6a5cff'); sys_rim.visible_glossy = False
    sys_fill = area('SYS_FILL', (7.0, -6.5, 1.5), (0, 0, 0), 8.0, 380, '#C9D4FF'); sys_fill.visible_glossy = True
    anim_float(L_(sys_key), 'energy', [(N, 0.0), (N + 1, 0.0), (N + 40, 1150.0)])
    anim_float(L_(sys_rim), 'energy', [(N, 0.0), (N + 1, 0.0), (N + 40, 1200.0)])
    anim_float(L_(sys_fill), 'energy', [(N, 0.0), (N + 1, 0.0), (N + 40, 380.0)])
    bc = card('SYS_CARD', (0, 15, 2.5), (0, 0, 0), 26, 12, 1.0, '#7d6bff')    # seen through the glass shapes
    bmr = next(n for n in bc.data.materials[0].node_tree.nodes if n.bl_idname == 'ShaderNodeMapRange')
    for f_, v_ in ((N, 0.0), (N + 30, 0.0), (N + 70, 1.8)):
        bmr.inputs['To Min'].default_value = v_; bmr.inputs['To Min'].keyframe_insert('default_value', frame=f_)

    for f in range(S2_0, S2_1 + 1):                              # the camera move, baked per frame
        loc, tgt, fs = cam2(f)
        cam.location = loc; look_at(cam, tgt)
        cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
        cam.data.dof.focus_distance = (loc - Vector((0, 0, 0))).length - 0.1; cam.data.dof.aperture_fstop = fs
        cam.data.dof.keyframe_insert('focus_distance', frame=f); cam.data.dof.keyframe_insert('aperture_fstop', frame=f)
    if MODE == 'dry2':
        for f in (S2_0, 160, 200, 240, S2_1):
            scene.frame_set(f)
            vis = []
            for root, *_ in shapes2:
                v = screen_pos(scene, cam, root.matrix_world.translation)
                vis.append(f'{root.name[3:]}({v.x:.2f},{v.y:.2f})')
            print(f'S2 FRAME {f}: ' + ' '.join(vis))
        sys.exit(0)

# ----------------------------------------------------------------------------------------------- scene 03
# Gravity, then the journey. The shapes start answering the cube: pulled in, faster, their orbits tipping out of the
# plane, each drawing a comet of light. The camera settles low over the rings and close: THE MOMENT. The headline
# stands inside the system, split round the cube, on a plane through the cube's centre: whatever is nearer than that
# plane is drawn over the type (a matte rendered for those frames), the rest passes behind it. Then the cube breaks
# away up the frame and the shapes follow it, braiding helices (after the 'sun through the galaxy' reference); the
# camera tracks alongside, then comes round ahead and looks back down the spiral.
S3 = MODE in ('s3', 's3final', 'dry3', 'fore3', 'fore3final') + S4_MODES
S4 = MODE in S4_MODES
S3_LEN = 305
S3_0, S3_1 = S2_1 + 1, S2_1 + S3_LEN
F_MOM, F_B, F_C = S2_1 + 65, S2_1 + 165, S3_1            # the three rests: the moment, alongside, looking back. The
                                                         # moves after the moment get many frames (100, 140): the camera
                                                         # travels a long way there, and scrubbing must stay smooth
FORE_0, FORE_1 = F_MOM - 30, F_MOM + 52                  # frames that need the matte (the headline is on screen)
TEXT_W, TEXT_BOX = 0.86, (2000, 360)                     # headline: share of frame width at the moment; HTML box px
TEXT_FS, TEXT_MT, TEXT_GL, TEXT_GR = 134, 112, 814, 1605      # the headline's layout in that box (styles.css)
TEXT_EM = (5.825, 2.545)                                  # 'Ideas attract', 'ideas.' in em (Axiforma Light, -0.045em)
# Scenes 04-06 run on from Scene 03 (their constants are here because Scene 03's motion is extended into them)
S4_0, S4_1 = S3_1 + 1, S3_1 + 810                        # 566-1375
T5_FLY, T5_ORB, T5_BACK, T5_END = 50, 40, 60, 40          # (feedback Oct 25) the projects: one world at a time
S5_0, S5_1 = S4_1 + 1, S4_1 + 4 * (T5_FLY + T5_ORB) + T5_BACK + T5_END   # 1376-1835
S5_END0 = S5_1 - T5_END                                   # back on the whole universe: the brand's last words
# V4: Scene 05 (the formation becomes a world) and Scene 06 (its universe), one continuous move
E_RES0 = 900                                              # 900-925  the totem resonates; light threads to the diamond
COLLAPSE = {'arch': (925, 957), 'dome': (934, 961), 'sphere': (941, 964), 'cone': (946, 967),   # 925-972 it collapses
            'octa': (950, 969), 'torus': (953, 971), 'cube': (955, 972)}                         # (slow, then a rush)
E_SHOCK = 998                                             # 975-1010 energy builds; the shockwave
T_IMP0, T_IMP1 = 925, 972
T_PL0, T_PL1 = 1012, 1062                                 # 1012-1062 the cube grows into a world (S_W times)
S_W = 40.0
E_WORLD, E_FINAL = 1085, 1335                             # the world revealed; the universe settled
HUM = {'arch': 0.9, 'dome': 1.33, 'sphere': 1.71, 'cone': 1.12, 'octa': 2.05, 'torus': 1.47, 'cube': 1.9}
F_STOP, F_T = S3_1 + 60, S3_1 + 135                      # the system comes to rest; the camera reaches the totem
F_DONE, F_HEAD = S3_1 + 235, S3_1 + 315                  # the totem is built; the headline stands beside it
FORE4_0, FORE4_1 = F_HEAD - 42, F_HEAD + 58              # frames that need the second matte
TEXT4_FS, TEXT4_MT, TEXT4_GL, TEXT4_GR = 112, 124, 969, 1620   # 'And ideas become' | totem | 'worlds.' (styles.css)
END = S4_1 if MODE in S4_MODES else S3_1
if S3:
    AX = Vector(AXIS)
    FX_K = 50.0 / 36.0                                       # focal / sensor width: the projection, done by hand

    def plane_dir(az, el):                                   # a direction in the ring plane's own frame
        a, e = math.radians(az), math.radians(el)
        return (M @ Vector((math.cos(e) * math.sin(a), -math.cos(e) * math.cos(a), math.sin(e)))).normalized()

    def basis(view, up):                                     # camera right / up / back for a view direction
        r_ = view.cross(up).normalized(); u_ = r_.cross(view).normalized()
        return r_, u_, -view

    # the moment camera: 6 degrees over the ring plane, so the rings run level through the type like Saturn's; far
    # enough back that the bright gold band stays inside the gap between the words and only finer rings cross them
    back_m = plane_dir(-16.0, 6.0); D_MOM = 12.5
    right_m, up_m, _ = basis(-back_m, AX)
    D = (right_m * math.cos(math.radians(30)) + up_m * math.sin(math.radians(30))).normalized()   # up and right
    fwd = D; side = fwd.cross(Vector((0, 0, 1))).normalized(); upv = side.cross(fwd).normalized()
    dist = {S2_1: 0.0}
    for f in range(S3_0, END + 1):
        v = 0.12 * ease((f - F_MOM) / 50.0)                 # at rest through the moment, then away, then cruising (slow
                                                            # enough against the orbits that the trails coil into helices)
        if f > S3_1: v = 0.12 * (1 - ease((f - S3_1) / (F_STOP - S3_1)))   # Scene 04: it comes to rest
        dist[f] = dist[f - 1] + v
    cpos = lambda f: D * dist.get(f, 0.0)


    system = bpy.data.objects.new('SYSTEM', None); scene.collection.objects.link(system)
    for f in range(S2_1, END + 1):
        system.location = cpos(f); system.keyframe_insert('location', frame=f)
    carried = [spin_gold, spin_vio, spin_in, spin_out, cube, key, capture, back_soft, fg, ds, sys_key, sys_rim,
               bpy.data.objects['SYS_CARD'], haze] + band_lights
    for o in carried:
        if o.parent is None:
            parent_to(o, system)
    for f in range(S2_1, S3_1 + 1, 4):                       # the cube keeps turning, slowly, as it goes
        cube.rotation_euler = Euler((math.radians(ROT_END[0]), math.radians(ROT_END[1]), math.radians(ROT_END[2] + 0.15 * (f - S2_1))))
        cube.keyframe_insert('rotation_euler', frame=f)
    # the lights built for the hero close-up are for the cube (and the orbs on its rails): the shapes drawn in close
    # now must not pass through their hot spots. Scene 03 only, so Scenes 01-02 are untouched.
    rx = bpy.data.collections.new('CUBE_LIGHT_RX'); rx.objects.link(cube)
    for o_ in orbs: rx.objects.link(o_)
    for l_ in [key, capture, back_soft, fg, ds] + band_lights:
        l_.light_linking.receiver_collection = rx
    # Scene 02's orbit lines are where the shapes used to be: they let go as gravity takes over
    for k in range(4):
        nt = bpy.data.objects[f'ORBIT2_{k}'].data.materials[0].node_tree
        anim_node_value(nt.nodes['GAIN'], [(S2_1, 1.0), (S2_1 + 40, 0.0)])
    # the star belonged to the hero frame: it goes out as the camera leaves, so nothing flares beside the words
    # (the light dispersed in Scene 01: nothing to put out here)

    # camera. Each station: an offset from the cube, the spot in frame where the cube sits, and the camera's up. The
    # aim is solved so the cube lands on its spot; offsets swing round the cube (direction slerped, length lerped).
    # (Defined before the shapes: the moment's rest frame is laid out with this camera.)
    def aim(loc, P, sx, sy, up):
        view = (P - loc).normalized(); right, upc, _ = basis(view, up)
        d_ = (P - loc).length; W = d_ * 36.0 / 50.0; H = W * 9.0 / 16.0
        return P + right * (0.5 - sx) * W + upc * (0.5 - sy) * H

    MOM_SPOT = (0.59, 0.5)                                   # the cube sits in the gap of the headline
    ST = {'M': (back_m * D_MOM, MOM_SPOT, AX),
          'B': (back_m * 13.0 + up_m * 0.8, (0.56, 0.42), AX),       # room ahead of the cube for its line
          'C': (fwd * 6.6 + upv * 3.6 + side * 4.6, (0.42, 0.46), AX)}       # ahead, 45 degrees off: the spiral recedes
    tgt_off = {k: aim(v[0], Vector((0, 0, 0)), v[1][0], v[1][1], v[2]) for k, v in ST.items()}
    ST['S2'] = (loc_e - cpos(S2_1), None, Vector((0, 0, 1))); tgt_off['S2'] = tgt_e - cpos(S2_1)
    keys3 = [(S2_1, 'S2'), (F_MOM, 'M'), (F_B, 'B'), (F_C, 'C')]

    # the headline's plane: through the cube's centre at the moment, square to the moment camera
    cam_m = cpos(F_MOM) + ST['M'][0]
    view_m = (cpos(F_MOM) + tgt_off['M'] - cam_m).normalized()
    rm, um, n_txt = basis(view_m, AX)
    P_TXT = cpos(F_MOM)
    centre_txt = cam_m + view_m * ((P_TXT - cam_m).dot(n_txt) / view_m.dot(n_txt))     # frame centre on the plane
    wt = TEXT_W * 2 * (P_TXT - cam_m).dot(-n_txt) * 0.5 / FX_K
    ht = wt * TEXT_BOX[1] / TEXT_BOX[0]
    corners_txt = [centre_txt - rm * wt / 2 + um * ht / 2, centre_txt + rm * wt / 2 + um * ht / 2,
                   centre_txt + rm * wt / 2 - um * ht / 2, centre_txt - rm * wt / 2 - um * ht / 2]   # tl tr br bl

    def project(mw, p):                                      # world -> frame (x right, y down), 0..1, and depth
        q = mw.inverted() @ p
        if q.z > -1e-4: return None
        return (0.5 + FX_K * q.x / -q.z, 0.5 - FX_K * q.y / -q.z * 16.0 / 9.0, -q.z)

    # the moment camera, for laying out the rest frame
    _r, _u, _b = basis((cpos(F_MOM) + tgt_off['M'] - cam_m).normalized(), AX)
    mw_m = Matrix.Translation(cam_m) @ Matrix((_r, _u, _b)).transposed().to_4x4()
    # where the letters are at the moment, in frame units (x right, y down): the two words' boxes, cap height to baseline
    def box_to_frame(x, y):
        return 0.5 - TEXT_W / 2 + x / TEXT_BOX[0] * TEXT_W, 0.5 - TEXT_W * TEXT_BOX[1] / TEXT_BOX[0] * 16 / 9 / 2 + y / TEXT_BOX[1] * TEXT_W * TEXT_BOX[1] / TEXT_BOX[0] * 16 / 9
    base_y = TEXT_MT + 0.771 * TEXT_FS; cap_y = base_y - 0.739 * TEXT_FS; pad = 0.04 * TEXT_FS
    LETTERS = [(*box_to_frame(TEXT_GL - pad - TEXT_EM[0] * TEXT_FS, cap_y), *box_to_frame(TEXT_GL - pad, base_y)),
               (*box_to_frame(TEXT_GR + pad, cap_y), *box_to_frame(TEXT_GR + pad + TEXT_EM[1] * TEXT_FS, base_y))]

    # shapes: pulled in (radius shrinks), faster (Kepler-ish), and their orbits tip out of the plane, each its own
    # way: the sphere changes its orbital path, the triangle turns to face the centre, the ring speeds up, the arch
    # comes into alignment, the cube is drawn in furthest. (inclination, node line) in degrees
    WARM = ('cone', 'arch', 'torus')                     # their trails run gold; the cool shapes' run violet
    INC = {'sphere': (26, 20), 'cone': (-14, 110), 'arch': (3, 200), 'cube': (16, 290), 'torus': (-20, 60),
           'dome': (-22, 250), 'octa': (-24, 330)}

    def orbit(i, k, last=S3_1):
        """Shape i's path from Scene 02's end to `last` when its speed up to the moment is scaled by k (eased back
        to 1 after). Scene 04 carries the same orbits on until each shape is drawn out of its orbit."""
        root, sc_, r, deg, f0, du, lang = shapes2[i]
        nm = root.name.split('_')[-1]
        inc, node = INC[nm]
        nl = Vector((math.cos(math.radians(node)), math.sin(math.radians(node)), 0.0))
        pull = 0.4 if nm == 'cube' else 0.32
        w_t = 1.7 * (1.25 if nm == 'torus' else 1.0) * (2.7 / r) ** 1.5      # unhurried: they glide, not whip
        th = deg + max(0.0, S2_1 - (f0 + du)) * 0.12
        pts = []
        for f in range(S2_1, last + 1):
            g = ease((f - S2_1) / (F_MOM - S2_1 + 10))                  # gravity takes hold through the moment
            R = r * (1 - pull * g - 0.12 * ease((f - F_MOM) / 120))     # and keeps drawing them in on the journey
            w = 0.12 + (w_t * (r / R) ** 1.5 - 0.12) * ease((f - S2_1) / 50)
            s_ = k + (1 - k) * ease((f - F_MOM) / 30)
            if f > S2_1: th += w * s_
            tilt = Matrix.Rotation(math.radians(inc) * g, 3, nl)
            pts.append(cpos(f) + M @ (tilt @ Vector((R * math.cos(math.radians(th)), R * math.sin(math.radians(th)), 0.0))))
        return pts

    # The rest frame is read, so it is laid out: each shape's pace up to the moment is tuned (0.7x-1.5x) so that at the
    # moment none stands over the words or the cube, none is cut by the frame, and they keep apart. (0.5x-1.7x)
    def spot(i, k):
        p_ = orbit(i, k)[F_MOM - S2_1]
        x_, y_, z_ = project(mw_m, p_)
        rad = 0.62 * shapes2[i][1] / z_ * FX_K
        return x_, y_, rad, (p_ - P_TXT).dot(n_txt) > 0

    def cost(i, k, others):
        x_, y_, rad, front = spot(i, k)
        c_ = 0.8 * abs(k - 1)
        for x0, y0, x1, y1 in LETTERS:
            if x0 - rad < x_ < x1 + rad and y0 - rad * 16 / 9 < y_ < y1 + rad * 16 / 9:
                c_ += 10 if front else 3
        if abs(x_ - MOM_SPOT[0]) < 0.07 + rad and abs(y_ - (1 - MOM_SPOT[1])) < 0.13 + rad * 16 / 9: c_ += 6
        if not (0.06 < x_ < 0.94 and 0.14 < y_ < 0.86): c_ += 4
        for xo, yo in others:
            d_ = math.hypot(x_ - xo, (y_ - yo) * 9 / 16)
            if d_ < 0.09: c_ += 5 * (0.09 - d_) / 0.09
        return c_

    KS = [0.5 + 0.05 * j for j in range(25)]
    pace = [1.0] * len(shapes2)
    for _pass in range(3):
        for i in range(len(shapes2)):
            others = [spot(j, pace[j])[:2] for j in range(len(shapes2)) if j != i]
            pace[i] = min(KS, key=lambda k: cost(i, k, others))
    for i, (root, *_) in enumerate(shapes2):
        x_, y_, rad, front = spot(i, pace[i])
        print(f"S3 MOMENT {root.name.split('_')[-1]}: pace {pace[i]:.2f} at ({x_:.2f},{y_:.2f}) {'front' if front else 'behind'}"
              f" cost {cost(i, pace[i], [spot(j, pace[j])[:2] for j in range(len(shapes2)) if j != i]):.2f}")

    paths, orbits_full = {}, {}
    for i, (root, sc_, r, deg, f0, du, lang) in enumerate(shapes2):
        nm = root.name.split('_')[-1]
        pts = orbit(i, pace[i], END); orbits_full[nm] = pts
        q0 = root.rotation_euler.to_quaternion()
        for f in range(S3_0, S3_1 + 1):
            pos = pts[f - S2_1]
            root.location = pos
            if nm == 'cone':                                           # the triangle turns its point to the centre
                q_in = (cpos(f) - pos).to_track_quat('Z', 'Y')
                root.rotation_euler = q0.slerp(q_in, ease((f - S2_1) / 50)).to_euler('XYZ', root.rotation_euler)
            else:
                root.rotation_euler = Euler((root.rotation_euler.x, root.rotation_euler.y, root.rotation_euler.z + 0.02))
            root.keyframe_insert('location', frame=f); root.keyframe_insert('rotation_euler', frame=f)
        paths[nm] = pts[:S3_LEN + 1]                                  # the trails are Scene 03's alone
    paths['pixel'] = [cpos(f) for f in range(F_MOM, S3_1 + 1)]

    # the trails: each body's whole path as one light trail. The head sits on the body (no lead), the tail fades
    # with age: short comets through the moment, long helices on the journey.
    for nm, pts in paths.items():
        stops = TRAIL_STOPS if nm == 'pixel' else GOLD_STOPS if nm in WARM else VIOLET_STOPS   # the universe's two
        o = light_trail(f'HELIX_{nm}', pts, (pts[-1] - pts[0] + Vector((0, 0, 1e-3))).normalized().orthogonal(),
                        (lambda u: 0.62 if nm != 'pixel' else 0.75), 0.0032 if nm != 'pixel' else 0.006,
                        2.4 if nm != 'pixel' else 6.0, taper=0.0, coll=SHAPES, stops=stops, anim=True)   # fine and faint
        nt = o.data.materials[0].node_tree
        for n_ in nt.nodes:
            if n_.bl_idname == 'ShaderNodeMapRange' and abs(n_.inputs['From Min'].default_value + 0.06) < 1e-6:
                n_.inputs['From Min'].default_value = -0.003
        a_, n_f = (F_MOM, S3_1 - F_MOM) if nm == 'pixel' else (S2_1, S3_LEN)
        for f in sorted(set(range(a_, S3_1 + 1, 2)) | {S3_1}):
            nt.nodes['REVEAL'].outputs[0].default_value = (f - a_) / n_f + 0.0015
            nt.nodes['REVEAL'].outputs[0].keyframe_insert('default_value', frame=f)
        for fc in fcurves_of(nt):
            if 'REVEAL' in fc.data_path:
                for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
        if nm == 'pixel':
            anim_node_value(nt.nodes['TAIL'], [(F_MOM, 72 / (S3_1 - F_MOM))])        # tails measured in frames of travel
            anim_node_value(nt.nodes['GAIN'], [(S2_1, 0.0), (F_MOM, 0.0), (F_MOM + 16, 0.45)])     # (feedback: fainter)
        else:
            anim_node_value(nt.nodes['TAIL'], [(S2_1, 14.7 / S3_LEN), (F_MOM, 18.9 / S3_LEN), (F_B, 72 / S3_LEN), (F_C, 96 / S3_LEN)])
            anim_node_value(nt.nodes['GAIN'], [(S2_1, 0.0), (S2_1 + 14, 0.28), (F_MOM, 0.28), (F_B, 0.4)])  # quiet, fine lines

    # THE SHAPES SHED (the particle reference, run forward): as gravity takes hold, each shape sheds a stream of fine
    # grains that spiral in and flatten round the cube, and settle into a galaxy (after dgreenheck's webgpu-galaxy, Oct
    # 25): two arms that turn together, the brand's blue where the arms are dense, warm gold scattered between them;
    # the disc melts into the rings just before the cube breaks away, so nothing of it is left for the journey.
    SHED_END = F_MOM + 40                                 # (storyboard: the disc glows round the cube through the headline)
    Minv = M.inverted()
    rs_ = random.Random(23)
    sh = {k: [] for k in ('b', 'T', 'r0', 'th0', 'z0', 'r1', 'dth', 'zt', 'size', 'bright', 'tone')}
    for nm, pts in paths.items():
        if nm == 'pixel': continue
        for _ in range(5200):
            b = rs_.uniform(S2_1 + 2, S2_1 + 30)
            p_ = pts[int(b) - S2_1] - cpos(int(b)) + Vector((rs_.gauss(0, 0.07), rs_.gauss(0, 0.07), rs_.gauss(0, 0.07)))
            q = Minv @ p_
            r1 = 1.0 + 2.6 * rs_.random() ** 1.3                  # denser toward the core
            dense = rs_.random() < 0.8
            th_t = rs_.choice((0.0, math.pi)) + 4.4 * math.log(r1)   # on one of the two arms (a logarithmic spiral, ~1 turn)
            th_t += rs_.gauss(0, 0.11 + 0.04 * r1) if dense else rs_.uniform(-math.pi, math.pi)
            core = r1 < 1.55 and rs_.random() < 0.75                  # the bulge round the cube: warm, like a galaxy's
            th0 = math.atan2(q.y, q.x)
            sh['b'].append(b); sh['T'].append(rs_.uniform(26, 44))
            sh['r0'].append(math.hypot(q.x, q.y)); sh['th0'].append(th0); sh['z0'].append(q.z)
            sh['r1'].append(r1); sh['dth'].append((th_t - th0 + math.pi) % math.tau - math.pi)   # the short way round
            sh['zt'].append(rs_.gauss(0, 0.035 * (1.6 - r1 / 3.6)))                             # thin, a little thicker inside
            sh['size'].append((0.003 + 0.005 * rs_.random() ** 2) * (1.15 if dense else 0.9))
            sh['bright'].append((0.2 + 0.65 * rs_.random() ** 2.2) * (1.15 if core else 1.0 if dense else 0.7))
            sh['tone'].append(rs_.uniform(0.0, 0.3) if core else rs_.uniform(0.6, 0.97) if dense else rs_.uniform(0.05, 0.36))
    shed = points_object('SHED_GRAINS', [(0, 0, 0)] * len(sh['b']), sh, FX)
    parent_to(shed, system)
    sh_mat = glow_mat('shed grains', [(0.0, '#ffd2b0'), (0.18, '#ffb28a'), (0.38, '#FFC94F'), (0.62, '#a9bcff'), (0.8, '#4f7dff'),
                                      (1.0, '#1858FD')], 7.0)              # warm and sparse .. the brand's blue, dense
    sh_src = tiny_sphere('SHED_src', sh_mat, FX, subdiv=2)
    ng_s = bpy.data.node_groups.new('SHED_GN', 'GeometryNodeTree')
    ng_s.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng_s.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    Ns, Ls = ng_s.nodes, ng_s.links
    gi_s = Ns.new('NodeGroupInput'); go_s = Ns.new('NodeGroupOutput')
    def _sa(name):
        n_ = Ns.new('GeometryNodeInputNamedAttribute'); n_.data_type = 'FLOAT'; n_.inputs['Name'].default_value = name
        return n_.outputs['Attribute']
    def _sm(op, a, b=None, clamp=False):
        n_ = Ns.new('ShaderNodeMath'); n_.operation = op; n_.use_clamp = clamp
        for i_, v_ in enumerate((a, b)):
            if v_ is None: continue
            if isinstance(v_, (int, float)): n_.inputs[i_].default_value = v_
            else: Ls.new(v_, n_.inputs[i_])
        return n_.outputs[0]
    st_s = Ns.new('GeometryNodeInputSceneTime'); F_ = st_s.outputs['Frame']
    age = _sm('SUBTRACT', F_, _sa('b'))
    mrs = Ns.new('ShaderNodeMapRange'); mrs.interpolation_type = 'SMOOTHERSTEP'
    Ls.new(_sm('DIVIDE', age, _sa('T'), clamp=True), mrs.inputs['Value']); es = mrs.outputs['Result']
    rr_ = _sm('ADD', _sa('r0'), _sm('MULTIPLY', _sm('SUBTRACT', _sa('r1'), _sa('r0')), es))      # drawn in to its ring
    zz_ = _sm('ADD', _sm('MULTIPLY', _sa('z0'), _sm('SUBTRACT', 1.0, es)), _sm('MULTIPLY', _sa('zt'), es))   # flattened
    th_ = _sm('ADD', _sm('ADD', _sa('th0'), _sm('MULTIPLY', _sa('dth'), es)),                       # onto its arm,
              _sm('MULTIPLY', math.radians(0.55), _sm('MAXIMUM', age, 0.0)))                        # the arms turning as one
    cb_s = Ns.new('ShaderNodeCombineXYZ')
    Ls.new(_sm('MULTIPLY', rr_, _sm('COSINE', th_)), cb_s.inputs['X']); Ls.new(_sm('MULTIPLY', rr_, _sm('SINE', th_)), cb_s.inputs['Y'])
    Ls.new(zz_, cb_s.inputs['Z'])
    rot_s = Ns.new('ShaderNodeVectorRotate'); rot_s.rotation_type = 'EULER_XYZ'
    Ls.new(cb_s.outputs[0], rot_s.inputs['Vector']); rot_s.inputs['Rotation'].default_value = plane
    sp_s = Ns.new('GeometryNodeSetPosition'); Ls.new(gi_s.outputs['Geometry'], sp_s.inputs['Geometry'])
    Ls.new(rot_s.outputs['Vector'], sp_s.inputs['Position'])
    born = _sm('DIVIDE', age, 6.0, clamp=True)                                                      # it leaves the shape
    melt = _sm('SUBTRACT', 1.0, _sm('DIVIDE', _sm('SUBTRACT', F_, SHED_END - 16), 16.0, clamp=True)) # into the rings
    scl_s = _sm('MULTIPLY', _sm('MULTIPLY', _sa('size'), born), melt)
    iop_s = Ns.new('GeometryNodeInstanceOnPoints')
    oi_s = Ns.new('GeometryNodeObjectInfo'); oi_s.inputs['Object'].default_value = sh_src; oi_s.inputs['As Instance'].default_value = True
    Ls.new(sp_s.outputs['Geometry'], iop_s.inputs['Points']); Ls.new(oi_s.outputs['Geometry'], iop_s.inputs['Instance'])
    Ls.new(scl_s, iop_s.inputs['Scale'])
    Ls.new(iop_s.outputs['Instances'], go_s.inputs['Geometry'])
    shed.modifiers.new('GN', 'NODES').node_group = ng_s
    set_vis(shed, diffuse=False, shadow=False, scatter=False)
    for f_, h_ in ((1, True), (S2_1, True), (S2_1 + 1, False), (SHED_END, False), (SHED_END + 1, True)):
        shed.hide_render = h_; shed.keyframe_insert('hide_render', frame=f_)

    # space dust along the route, ahead of the moment: it streams past once the system moves, so travel reads as speed
    rd = random.Random(91); md_pts, md_b, md_s = [], [], []
    while len(md_pts) < 4200:
        t_ = rd.uniform(1.5, 50); a_ = rd.uniform(0, math.tau); rr = 3.0 + 13 * rd.random() ** 1.5
        md_pts.append(D * t_ + (side * math.cos(a_) + upv * math.sin(a_)) * rr)
        md_b.append(rd.random() ** 3); md_s.append(0.004 + 0.01 * rd.random() ** 2)
    glitter('SPACE_DUST', FX, WORLD, md_pts, md_b, md_s, s_max=3.0,
            stops=(('#2a1a66', 0.0), ('#8f7cff', 0.5), ('#ffe7c4', 1.0)))

    track = []
    for f in range(S3_0, S3_1 + 1):
        for (fa, na), (fb, nb) in zip(keys3, keys3[1:]):
            if fa <= f <= fb: break
        t = ease((f - fa) / (fb - fa))
        oa, ob = ST[na][0], ST[nb][0]
        dirn = oa.normalized().to_track_quat('Z', 'Y').slerp(ob.normalized().to_track_quat('Z', 'Y'), t) @ Vector((0, 0, 1))
        off = dirn * (oa.length + (ob.length - oa.length) * t)
        P = cpos(f)
        loc = P + off
        up = ST[na][2].lerp(ST[nb][2], t).normalized()
        tgt = P + tgt_off[na].lerp(tgt_off[nb], t)
        cam.location = loc
        view = (tgt - loc).normalized(); r_, u_, b_ = basis(view, up)
        cam.rotation_euler = Matrix((r_, u_, b_)).transposed().to_euler('XYZ', cam.rotation_euler)
        cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
        cam.data.dof.focus_distance = (loc - P).length; cam.data.dof.aperture_fstop = 4.0
        cam.data.dof.keyframe_insert('focus_distance', frame=f); cam.data.dof.keyframe_insert('aperture_fstop', frame=f)
        mw = Matrix.Translation(loc) @ Matrix((r_, u_, b_)).transposed().to_4x4()
        c_ = project(mw, P); e_ = project(mw, P + r_ * 0.62)
        q_ = [project(mw, p_) for p_ in corners_txt]
        track.append({'f': f, 'c': [round(c_[0], 4), round(c_[1], 4)], 'r': round(abs(e_[0] - c_[0]), 4),
                      'q': None if None in q_ else [[round(p_[0], 4), round(p_[1], 4)] for p_ in q_]})
    if MODE == 'dry3':
        for f in (S3_0, S2_1 + 40, F_MOM, F_MOM + 30, F_MOM + 52, F_B, F_C):
            tr_ = track[f - S3_0]
            scene.frame_set(f)
            vis = ' '.join(f"{r_o.name.split('_')[-1]}({screen_pos(scene, cam, r_o.matrix_world.translation).x:.2f},{1 - screen_pos(scene, cam, r_o.matrix_world.translation).y:.2f})" for r_o, *_ in shapes2)
            v = screen_pos(scene, cam, cube.matrix_world.translation)
            print(f"S3 FRAME {f}: cube blender({v.x:.3f},{1 - v.y:.3f}) track{tr_['c']} r{tr_['r']} text{tr_['q']} | {vis}")
        sys.exit(0)
    if MODE in ('s3', 's3final'):
        import json
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, 'track.json'), 'w') as fh:
            json.dump({'from': S3_0, 'box': TEXT_BOX, 'moment': F_MOM, 'b': F_B, 'c': F_C, 'fore': [FORE_0, FORE_1],
                       'frames': track}, fh, separators=(',', ':'))

    if MODE in ('fore3', 'fore3final'):
        # THE MATTE: what is nearer than the headline's plane. Every surface behind the plane becomes a holdout, the
        # cube is held in front whole (it stands in the gap of the type), the world is transparent. Light trails are
        # emission over transparency (no alpha), so the matte is coverage plus their brightness.
        cube['fore'] = 1.0
        for o in (haze, bpy.data.objects['SYS_CARD'], star, bpy.data.objects.get('CORONA'), rays):
            if o: o.hide_render = True
        for mt in bpy.data.materials:
            if not mt.node_tree: continue
            nt = mt.node_tree; Nn = nt.nodes; Lk = nt.links
            out = next((n_ for n_ in Nn if n_.bl_idname == 'ShaderNodeOutputMaterial' and n_.is_active_output), None)
            if not out or not out.inputs['Surface'].links: continue
            src = out.inputs['Surface'].links[0].from_socket
            geo = Nn.new('ShaderNodeNewGeometry')
            sb = Nn.new('ShaderNodeVectorMath'); sb.operation = 'SUBTRACT'
            Lk.new(geo.outputs['Position'], sb.inputs[0]); sb.inputs[1].default_value = P_TXT
            dt = Nn.new('ShaderNodeVectorMath'); dt.operation = 'DOT_PRODUCT'
            Lk.new(sb.outputs[0], dt.inputs[0]); dt.inputs[1].default_value = n_txt
            mr = Nn.new('ShaderNodeMapRange'); mr.clamp = True
            mr.inputs['From Min'].default_value = 0.015; mr.inputs['From Max'].default_value = -0.015
            Lk.new(dt.outputs['Value'], mr.inputs['Value'])
            fa = Nn.new('ShaderNodeAttribute'); fa.attribute_type = 'OBJECT'; fa.attribute_name = 'fore'
            kp_ = Nn.new('ShaderNodeMath'); kp_.operation = 'SUBTRACT'; kp_.inputs[0].default_value = 1.0
            Lk.new(fa.outputs['Fac'], kp_.inputs[1])
            k_ = Nn.new('ShaderNodeMath'); k_.operation = 'MULTIPLY'; k_.use_clamp = True
            Lk.new(mr.outputs['Result'], k_.inputs[0]); Lk.new(kp_.outputs[0], k_.inputs[1])
            ho = Nn.new('ShaderNodeHoldout')
            mx = Nn.new('ShaderNodeMixShader')
            Lk.new(k_.outputs[0], mx.inputs['Fac']); Lk.new(src, mx.inputs[1]); Lk.new(ho.outputs[0], mx.inputs[2])
            Lk.new(mx.outputs[0], out.inputs['Surface'])
# ----------------------------------------------------------------------------------------------- scenes 04-06
# The creation, a world is born, the reveal. The system comes to rest and the shapes are drawn out of their orbits
# into the brand book's 'Structure For Clarity' totem, balanced in space like stones: the arch, the dome on its crown,
# the yellow cube stood on its edge as the diamond (its gold ring a belt round the middle), the sphere, the triangle
# balanced on its point, the crystal. The ring and the glass cube keep orbiting it. Built, it ignites: the cube glows,
# the dust bursts outward, and 'And ideas become worlds.' stands in the gap beside it. Then the camera pulls far back
# until the creation is one gently glowing point in calm space, for the final words.
if S4:
    scene.frame_set(F_STOP); bpy.context.view_layer.update()
    P_T = cube.matrix_world.translation.copy()                 # where the cube comes to rest: the totem's heart
    AZ_T, EL_T = -12.0, -4.0                                    # the totem camera: a touch to the left, a touch below
    a_, e_ = math.radians(AZ_T), math.radians(EL_T)
    toward = Vector((math.sin(a_) * math.cos(e_), -math.cos(a_) * math.cos(e_), math.sin(e_)))  # cube -> camera
    yaw = Matrix.Rotation(a_, 3, 'Z')                           # pieces face that camera

    # slots, bottom to top: (shape, scale, rotation, centre height above the cube's centre). Each sits on the one below
    # at a single point, as balanced stones do; heights come from the library's measured sizes.
    DIAG = 0.88 * math.sqrt(2) / 2                              # the cube on its edge: half its height
    H = {'arch': 1.6798, 'dome': 1.3216, 'sphere': 1.58, 'cone': 1.4804, 'octa': 0.9491}
    SC = {'arch': 0.91, 'dome': 0.65, 'sphere': 0.62, 'cone': 0.56, 'octa': 0.55}
    h = {k: H[k] * SC[k] for k in H}
    z_dome = -DIAG - h['dome'] / 2
    z_arch = -DIAG - h['dome'] - h['arch'] / 2
    z_sph = DIAG + h['sphere'] / 2
    z_cone = DIAG + h['sphere'] + h['cone'] / 2
    z_octa = DIAG + h['sphere'] + h['cone'] + h['octa'] / 2
    SLOT = {'arch': (z_arch, yaw), 'dome': (z_dome, yaw), 'sphere': (z_sph, yaw),
            'cone': (z_cone, yaw @ Matrix.Rotation(math.pi, 3, 'X')),           # the triangle stands on its point
            'octa': (z_octa, yaw @ Matrix.Rotation(math.radians(15), 3, 'Z'))}
    # stacked bottom up, as a column is built: arch, dome, the cube turning onto its edge, sphere, triangle, crystal.
    # The camera glides up the column with them (after the stacked-spheres reference), then draws back to show it whole.
    FLIGHT = {'arch': (F_T - 12, F_T + 24), 'dome': (F_T + 4, F_T + 38), 'sphere': (F_T + 30, F_T + 56),
              'cone': (F_T + 42, F_T + 68), 'octa': (F_T + 52, F_T + 78)}
    CUBE_TURN = (F_T + 16, F_T + 44)
    print('S4 TOTEM: cube at', tuple(round(x, 3) for x in P_T), 'height', round(z_octa + h['octa'] / 2 - z_arch + h['arch'] / 2, 2))

    def smoother(x):
        x = max(0.0, min(1.0, x)); return x * x * x * (x * (6 * x - 15) + 10)

    totem = []; piece_path = {}
    for i, (root, sc_, r, deg, f0, du, lang) in enumerate(shapes2):
        nm = root.name.split('_')[-1]
        pts = orbits_full[nm]
        rot = root.rotation_euler.copy()
        if nm in SLOT:
            z_, R_ = SLOT[nm]; slot = P_T + Vector((0, 0, z_)); q_slot = R_.to_quaternion()
            fa, fb = FLIGHT[nm]
            totem.append(root)
        for f in range(S4_0, S4_1 + 1):
            pos = pts[f - S2_1]
            if nm not in SLOT or f <= fa:                         # still orbiting: as in Scene 03
                rot = Euler((rot.x, rot.y, rot.z + 0.02))
                root.location = pos; root.rotation_euler = rot; s_ = sc_
                if nm in SLOT and f == fa: q_from = rot.to_quaternion()
            else:                                                 # drawn out of the orbit into its place
                e = smoother((f - fa) / (fb - fa))
                bob = 0.035 * math.sin(math.pi * (f - fb) / 16) * math.exp(-(f - fb) / 14) if f > fb else 0.0
                root.location = pos.lerp(slot, e) + Vector((0, 0, bob))     # it arrives, sinks a hair, settles
                root.rotation_euler = q_from.slerp(q_slot, e).to_euler('XYZ', root.rotation_euler)
                s_ = sc_ + (SC[nm] - sc_) * e
            if f > E_RES0 and nm in COLLAPSE:                     # it hums, each at its own rate; then it is drawn in
                ca, cb = COLLAPSE[nm]
                hum = 0.022 * ease((f - E_RES0) / 18) * (1 - ease((f - ca) / 6))
                w_ = HUM[nm]
                root.location = root.location + Vector((math.sin(f * w_), math.cos(f * w_ * 1.3), math.sin(f * w_ * 0.7))) * hum
                e_c = max(0.0, min(1.0, (f - ca) / (cb - ca)))
                root.location = root.location.lerp(P_T, e_c ** 2.4)     # accelerating into the cube
                s_ *= (1 - e_c ** 3)                                     # and gone into light as it arrives
                piece_path.setdefault(nm, {})[f] = (root.location.copy(), s_)
            root.scale = (s_,) * 3
            root.keyframe_insert('location', frame=f); root.keyframe_insert('rotation_euler', frame=f)
            root.keyframe_insert('scale', frame=f)

    # the cube turns onto its edge: a diamond facing the camera, turned a little so it keeps its depth
    q_c0 = cube.rotation_euler.to_quaternion()
    q_c1 = (yaw @ Matrix.Rotation(math.radians(20), 3, 'Z') @ Matrix.Rotation(math.radians(45), 3, 'Y')).to_quaternion()
    for f in range(S4_0, S4_1 + 1, 2):
        e = smoother((f - CUBE_TURN[0]) / (CUBE_TURN[1] - CUBE_TURN[0]))
        q_ = q_c0.slerp(q_c1, e)
        cube.rotation_euler = q_.to_euler('XYZ', cube.rotation_euler)
        cube.keyframe_insert('rotation_euler', frame=f)

    # the two that keep orbiting draw their orbits as thin lines as the column completes (after the reference's
    # line-drawn orbits): one full turn of each path, revealed head first
    for nm, hexc in (('torus', '#ffe2a8'), ('cube', '#c8bcff')):
        pts = orbits_full[nm]; i0 = F_DONE - S2_1
        j = min(range(i0 + 40, len(pts)), key=lambda j_: (pts[j_] - pts[i0]).length)   # back where it started
        loop_ = pts[i0:j + 1] + [pts[i0]]
        ln_ = light_trail(f'ORBIT_LINE_{nm}', loop_, (loop_[1] - loop_[0]).cross(loop_[len(loop_) // 4] - loop_[0]).normalized(),
                          (lambda u: 0.55), 0.0018, 1.4, taper=0.0, coll=SHAPES,
                          stops=[(0.0, '#16122a'), (0.5, hexc), (1.0, '#ffffff')], anim=True)
        ntl = ln_.data.materials[0].node_tree
        for f_, v_ in ((1, 0.0), (F_DONE - 24, 0.0), (F_DONE + 22, 1.06)):
            ntl.nodes['REVEAL'].outputs[0].default_value = v_; ntl.nodes['REVEAL'].outputs[0].keyframe_insert('default_value', frame=f_)
        for fc in fcurves_of(ntl):
            if 'REVEAL' in fc.data_path:
                for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'

    # Scene 03's helices let go as the system stops
    for nm in list(orbits_full) + ['pixel']:
        nt = bpy.data.objects[f'HELIX_{nm}'].data.materials[0].node_tree
        anim_node_value(nt.nodes['GAIN'], [(S3_1, 0.4 if nm != 'pixel' else 0.45), (S3_1 + 40, 0.0)])

    # ignition: the cube lights from inside, the band flares, the dust bursts outward and stays wider (a world)
    pr = next(n_ for n_ in cube.data.materials[0].node_tree.nodes if n_.bl_idname == 'ShaderNodeBsdfPrincipled')
    F_IG = F_DONE + 10
    glow_n = cube.data.materials[0].node_tree.nodes['INNER_GLOW']     # (the glow from within drives its light now)
    anim_node_value(glow_n, [(S3_1, glow_n.outputs[0].default_value), (F_DONE, 1.0), (F_IG + 30, 4.0), (F_HEAD, 2.0), (E_RES0, 2.0), (T_IMP1, 5.0), (E_SHOCK, 12.0),
                             (T_PL0 + 10, 3.0), (T_PL1, 1.2), (E_WORLD, 0.6), (S5_END0, 0.6), (S5_1, 0.5)])
    anim_node_value(AURA_N, [(S3_1, 0.6), (F_IG + 30, 1.3), (F_HEAD, 0.9), (T_IMP1, 1.4), (E_SHOCK, 2.4), (T_PL1, 0.9),
                             (E_WORLD, 0.55), (S5_END0, 0.55), (S5_1, 0.4)])
    nt_c = cube.data.materials[0].node_tree.nodes
    anim_node_value(nt_c['WORLD_SKIN'], [(T_PL0, 0.0), (T_PL0 + 24, 1.0), (S5_END0, 1.0), (S5_1, 0.7)])
    anim_node_value(nt_c['SKIN_W'], [(T_PL0, 0.0), (S5_1, 1.4 * (S5_1 - T_PL0) / (S4_1 - T_PL0))])     # (the same slow rate)
    for fc in fcurves_of(cube.data.materials[0].node_tree):
        if 'SKIN_W' in fc.data_path:
            for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
    anim_float(L_(capture), 'energy', [(F_DONE, 140.0), (F_IG + 30, 420.0), (F_HEAD, 220.0), (T_IMP1, 900.0), (T_PL0, 0.0)])
    # it glows up as everything draws into it, then it is the heart of the planet
    # the totem's own light: a soft key from the camera's side, above, and a violet rim behind for its silhouette
    side_t = toward.cross(Vector((0, 0, 1))).normalized()
    tk = area('TOTEM_KEY', P_T + toward * 9 + side_t * 4 + Vector((0, 0, 5)), P_T, 6.0, 1600, '#FFF1DE'); tk.visible_glossy = False
    tr_ = area('TOTEM_RIM', P_T - toward * 8 - side_t * 3 + Vector((0, 0, 4)), P_T, 6.0, 1400, '#7a5cff'); tr_.visible_glossy = False
    # the hero frame's sun leaves as the camera comes round: its pin-point highlight on the glossy pieces flares
    # small, hot lights seen through the glass pieces read as lens stars: they light, they are not seen
    for l_ in [capture, tk, tr_] + band_lights:
        l_.visible_transmission = False; l_.visible_glossy = False
    anim_float(L_(tk), 'energy', [(S3_1, 0.0), (F_T - 40, 0.0), (F_T, 1600.0)])
    anim_float(L_(tr_), 'energy', [(S3_1, 0.0), (F_T - 40, 0.0), (F_T, 1400.0)])
    for o, s0, s1 in trails[:45]:                                # the gold strands and the glow band
        anim_node_value(o.data.materials[0].node_tree.nodes['GAIN'], [(F_DONE, 1.0), (F_IG + 30, 1.7), (F_HEAD + 20, 1.15)])
    for sp_, k_ in ((spin_in, 1.5), (spin_out, 1.75)):
        sp_.scale = (1, 1, 1); sp_.keyframe_insert('scale', frame=F_IG)
        sp_.scale = (k_,) * 3; sp_.keyframe_insert('scale', frame=F_HEAD + 10)

    # camera: from looking back down the spiral to the totem, a slow drift while it is built, a push for the words,
    # then far back until the creation is a point of light
    def toward_at(az, el):
        a2, e2 = math.radians(az), math.radians(el)
        return Vector((math.sin(a2) * math.cos(e2), -math.cos(a2) * math.cos(e2), math.sin(e2)))
    Z_UP = Vector((0, 0, 1))
    ST4 = {'C': ST['C'],
           'T': (toward * 8.5 + Vector((0, 0, z_arch + 0.3)), (0.5, 0.5), Z_UP),     # close, low: where the column starts
           'T2': (toward_at(AZ_T - 3, EL_T) * 18.6, (0.62, 0.5), Z_UP),
           'H': (toward_at(AZ_T - 4, EL_T) * 17.0, (0.627, 0.5), Z_UP),
           'P': (toward_at(AZ_T - 6, EL_T + 4) * 15.5, (0.5, 0.54), Z_UP),       # the new planet, whole
           'U': (toward_at(AZ_T - 14, 9.0) * 62.0, (0.5, 0.67), Z_UP)}   # (aim: up from the bottom)           # its universe of planets
    tgt4 = {k: aim(v[0], Vector((0, 0, 0)), v[1][0], v[1][1], v[2]) for k, v in ST4.items()}
    tgt4['C'] = tgt_off['C']; tgt4['T'] = Vector((0, 0, z_arch + 0.3))
    # the glide up the column: the camera's height follows the piece that is landing
    CRANE = [(F_T, z_arch + 0.3), (F_T + 22, z_arch + 0.3), (F_T + 36, z_dome), (F_T + 46, 0.0), (F_T + 58, z_sph),
             (F_T + 70, z_cone), (F_T + 82, z_octa - 0.25)]
    def crane_z(f):
        for (fa_, za), (fb_, zb) in zip(CRANE, CRANE[1:]):
            if fa_ <= f <= fb_: return za + (zb - za) * ease((f - fa_) / (fb_ - fa_))
        return CRANE[-1][1]
    keys4 = [(S3_1, 'C'), (F_T, 'T'), (F_DONE, 'T2'), (F_HEAD, 'H'), (T_PL1 + 2, 'P'), (S4_1, 'U')]
    cam.data.clip_end = max(cam.data.clip_end, 8000.0)

    # V4 camera, from the headline on: a slow push in, under the diamond looking up while it all collapses, still while
    # the energy builds, pushed back by the cube as it grows (a face fills the lens), then accelerating away and arcing
    # wide through the universe until it settles on the last frame. Positions relative to the cube.
    dH = toward_at(AZ_T - 4, EL_T)
    rH = (-dH).cross(Z_UP).normalized()
    def rot_z(v, deg): return Matrix.Rotation(math.radians(deg), 3, 'Z') @ v
    def lift(v, el):
        h_ = Vector((v.x, v.y, 0)).normalized(); return (h_ * math.cos(math.radians(el)) + Z_UP * math.sin(math.radians(el))).normalized()
    D_FIN = 400.0
    posF = lift(rot_z(dH, 46), 9.0) * D_FIN
    tgtF = aim(posF, Vector((0, 0, 0)), 0.5, 0.70, Z_UP)       # the world in the upper centre (aim measures from below)
    CK = [(F_HEAD, ST4['H'][0], tgt4['H']),
          (905, dH * 14.0 + Z_UP * 0.25, Vector((0, 0, 0.35)) + rH * 0.9),
          (927, dH * 11.5 + Z_UP * 0.1 + rH * 0.5, Vector((0, 0, 0.3))),
          (972, dH * 8.6 - Z_UP * 2.3 + rH * 1.1, Vector((0, 0, 0.55))),
          (1008, dH * 8.4 - Z_UP * 2.1 + rH * 1.2, Vector((0, 0, 0.6))),
          (1046, rot_z(dH, 6) * 31.0 - Z_UP * 3.0, Vector((0, 0, 0))),
          (E_WORLD, lift(rot_z(dH, 14), 6.0) * 125.0, rot_z(rH, 14) * 16.0),
          (1115, lift(rot_z(dH, 18), 7.0) * 140.0, rot_z(rH, 18) * 16.0),
          (1210, lift(rot_z(dH, 32), 8.0) * 245.0, rot_z(rH, 32) * 10.0),
          (E_FINAL, posF, tgtF),
          (S4_1, posF, tgtF)]
    def cat(p0, p1, p2, p3, t):
        return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)
    def cube_scale(f):
        return 1.0 if f <= T_PL0 else S_W ** ease((f - T_PL0) / (T_PL1 - T_PL0))
    def cam_end(f):
        for i_ in range(len(CK) - 1):
            if CK[i_][0] <= f <= CK[i_ + 1][0]: break
        fa_, fb_ = CK[i_][0], CK[i_ + 1][0]
        t_ = (f - fa_) / (fb_ - fa_) if fb_ > fa_ else 0.0
        t_ = t_ * t_ * (3 - 2 * t_) if i_ in (0, 3, len(CK) - 3) else t_       # settle into the rests
        P_ = [CK[max(0, min(len(CK) - 1, j_))] for j_ in (i_ - 1, i_, i_ + 1, i_ + 2)]
        loc_ = cat(*(c_[1] for c_ in P_), t_); tgt_ = cat(*(c_[2] for c_ in P_), t_)
        safe = 0.80 * cube_scale(f) + 2.5                     # never inside the growing cube
        if loc_.length < safe: loc_ = loc_.normalized() * safe
        return loc_, tgt_

    # the second headline's plane: through the cube at its rest, square to the camera at the words
    cam_h = P_T + ST4['H'][0]
    view_h = (P_T + tgt4['H'] - cam_h).normalized()
    rh, uh, n_txt4 = basis(view_h, Z_UP)
    P_TXT4 = P_T.copy()
    ctr4 = cam_h + view_h * ((P_TXT4 - cam_h).dot(n_txt4) / view_h.dot(n_txt4))
    wt4 = TEXT_W * (P_TXT4 - cam_h).dot(-n_txt4) / FX_K
    ht4 = wt4 * TEXT_BOX[1] / TEXT_BOX[0]
    corners4 = [ctr4 - rh * wt4 / 2 + uh * ht4 / 2, ctr4 + rh * wt4 / 2 + uh * ht4 / 2,
                ctr4 + rh * wt4 / 2 - uh * ht4 / 2, ctr4 - rh * wt4 / 2 - uh * ht4 / 2]

    track4 = []
    for f in range(S4_0, S4_1 + 1):
        for (fa_, na), (fb_, nb) in zip(keys4, keys4[1:]):
            if fa_ <= f <= fb_: break
        t = ease((f - fa_) / (fb_ - fa_))
        oa, ob = ST4[na][0], ST4[nb][0]
        dirn = oa.normalized().to_track_quat('Z', 'Y').slerp(ob.normalized().to_track_quat('Z', 'Y'), t) @ Vector((0, 0, 1))
        ln = oa.length + (ob.length - oa.length) * (t if nb != 'U' else t ** 1.7)   # the pull-back gathers pace
        off = dirn * ln
        P = cpos(f) + (P_T - cpos(F_STOP))                         # the cube itself (the system's origin is close by)
        loc = P + off
        up = ST4[na][2].lerp(ST4[nb][2], t).normalized()
        tgt = P + tgt4[na].lerp(tgt4[nb], t)
        if f >= F_HEAD:                                           # V4: the one long move to the end
            l_, t_ = cam_end(f); loc = P + l_; tgt = P + t_; up = Z_UP
        if F_T < f < F_DONE:                                      # the glide, then the draw back to the whole totem
            zc = crane_z(f); tw = Matrix.Rotation(math.radians(-0.07 * (f - F_T)), 3, 'Z') @ toward
            loc = P + tw * 8.5 + Vector((0, 0, zc)); tgt = P + Vector((0, 0, zc)); up = Z_UP
            if f > F_T + 82:
                s2 = ease((f - F_T - 82) / (F_DONE - F_T - 82))
                loc = loc.lerp(P + ST4['T2'][0], s2); tgt = tgt.lerp(P + tgt4['T2'], s2)
        cam.location = loc
        view = (tgt - loc).normalized(); r_, u_, b_ = basis(view, up)
        cam.rotation_euler = Matrix((r_, u_, b_)).transposed().to_euler('XYZ', cam.rotation_euler)
        cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
        cam.data.dof.focus_distance = (loc - tgt).length if F_T < f < F_DONE else max(0.5, (loc - P).length - 0.4 * cube_scale(f))
        cam.data.dof.aperture_fstop = 4.0 if f < 1030 else 4.0 + 12.0 * ease((f - 1030) / 60)   # deep focus: it is vast
        cam.data.dof.keyframe_insert('focus_distance', frame=f); cam.data.dof.keyframe_insert('aperture_fstop', frame=f)
        mw = Matrix.Translation(loc) @ Matrix((r_, u_, b_)).transposed().to_4x4()
        c_ = project(mw, P); e_ = project(mw, P + r_ * 0.62)
        q_ = [project(mw, p_) for p_ in corners4]
        track4.append({'f': f, 'c': [round(c_[0], 4), round(c_[1], 4)], 'r': round(abs(e_[0] - c_[0]), 5),
                       'q': None if None in q_ else [[round(p_[0], 4), round(p_[1], 4)] for p_ in q_]})
    # ======================================================================== V4 SCENE 05: THE FORMATION BECOMES A WORLD
    # 14A: threads of light run inside the totem from each piece to the diamond, as the pieces begin to hum
    for k_, o_ in enumerate(totem):
        nm_ = o_.name.split('_')[-1]
        z_, _ = SLOT[nm_]; a_ = P_T + Vector((0, 0, z_))
        th_ = light_trail(f'THREAD_{nm_}', [a_.lerp(P_T, i / 40) for i in range(41)], rH, (lambda u: 0.6 + 0.4 * u),
                          0.0022, 2.2, taper=0.0, coll=FX, stops=GOLD_STOPS, anim=True)
        ntt = th_.data.materials[0].node_tree
        anim_node_value(ntt.nodes['REVEAL'], [(1, 0.0), (E_RES0 + 2 + 3 * k_, 0.0), (E_RES0 + 14 + 3 * k_, 1.06)])
        anim_node_value(ntt.nodes['GAIN'], [(1, 1.0), (COLLAPSE[nm_][0], 1.0), (COLLAPSE[nm_][0] + 8, 0.0)])

    def flow_grains(name, targets, starts, delays, durs, sizes, brights, tones, stops, s_max, swirl=1.2):
        """Grains that travel from `start` to their own position over [delay, delay + dur], then are gone."""
        o_ = points_object(name, targets, {'start': starts, 'delay': delays, 'dur': durs, 'size': sizes,
                                           'bright': brights, 'tone': tones}, FX)
        src_ = tiny_sphere(name + '_src', glow_mat(name.lower(), stops, s_max), FX, subdiv=2)
        ng = bpy.data.node_groups.new(name + '_GN', 'GeometryNodeTree')
        ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
        Nn, Ll = ng.nodes, ng.links
        gi = Nn.new('NodeGroupInput'); go = Nn.new('NodeGroupOutput')
        def na(nm, kind):
            n_ = Nn.new('GeometryNodeInputNamedAttribute'); n_.data_type = kind; n_.inputs['Name'].default_value = nm
            return n_.outputs['Attribute']
        def mm(op, a, b=None, clamp=False):
            n_ = Nn.new('ShaderNodeMath'); n_.operation = op; n_.use_clamp = clamp
            for i_, v_ in enumerate((a, b)):
                if v_ is None: continue
                if isinstance(v_, (int, float)): n_.inputs[i_].default_value = v_
                else: Ll.new(v_, n_.inputs[i_])
            return n_.outputs[0]
        st = Nn.new('GeometryNodeInputSceneTime')
        t = mm('DIVIDE', mm('SUBTRACT', st.outputs['Frame'], na('delay', 'FLOAT')), na('dur', 'FLOAT'), clamp=True)
        mr = Nn.new('ShaderNodeMapRange'); mr.interpolation_type = 'SMOOTHERSTEP'; Ll.new(t, mr.inputs['Value'])
        e = mr.outputs['Result']
        mx = Nn.new('ShaderNodeMix'); mx.data_type = 'VECTOR'
        Ll.new(e, mx.inputs['Factor']); Ll.new(na('start', 'FLOAT_VECTOR'), mx.inputs[4])
        ps = Nn.new('GeometryNodeInputPosition'); Ll.new(ps.outputs['Position'], mx.inputs[5])
        sub = Nn.new('ShaderNodeVectorMath'); sub.operation = 'SUBTRACT'; Ll.new(mx.outputs[1], sub.inputs[0])
        Ll.new(ps.outputs['Position'], sub.inputs[1])
        vr = Nn.new('ShaderNodeVectorRotate'); vr.rotation_type = 'Z_AXIS'           # a swirl round its own target
        Ll.new(sub.outputs[0], vr.inputs['Vector']); one = mm('SUBTRACT', 1.0, e)
        Ll.new(mm('MULTIPLY', swirl, one), vr.inputs['Angle'])
        add = Nn.new('ShaderNodeVectorMath'); add.operation = 'ADD'; Ll.new(vr.outputs['Vector'], add.inputs[0])
        Ll.new(ps.outputs['Position'], add.inputs[1])
        sp = Nn.new('GeometryNodeSetPosition'); Ll.new(gi.outputs['Geometry'], sp.inputs['Geometry']); Ll.new(add.outputs[0], sp.inputs['Position'])
        appear = mm('DIVIDE', mm('SUBTRACT', st.outputs['Frame'], na('delay', 'FLOAT')), 3.0, clamp=True)
        land = Nn.new('ShaderNodeMapRange'); Ll.new(e, land.inputs['Value'])
        land.inputs['From Min'].default_value = 0.85; land.inputs['From Max'].default_value = 1.0
        land.inputs['To Min'].default_value = 1.0; land.inputs['To Max'].default_value = 0.0
        sc = mm('MULTIPLY', mm('MULTIPLY', na('size', 'FLOAT'), appear), land.outputs['Result'])
        ip = Nn.new('GeometryNodeInstanceOnPoints')
        oi = Nn.new('GeometryNodeObjectInfo'); oi.inputs['Object'].default_value = src_; oi.inputs['As Instance'].default_value = True
        Ll.new(sp.outputs['Geometry'], ip.inputs['Points']); Ll.new(oi.outputs['Geometry'], ip.inputs['Instance'])
        Ll.new(sc, ip.inputs['Scale']); Ll.new(ip.outputs['Instances'], go.inputs['Geometry'])
        o_.modifiers.new('GN', 'NODES').node_group = ng
        set_vis(o_, diffuse=False, shadow=False, scatter=False)
        return o_

    # 14B: each piece, as it is drawn in, comes apart into light that streams into the cube
    rg_ = random.Random(29); fp, fs_, fd, fu, fz, fb, ft = [], [], [], [], [], [], []
    for nm_, (ca, cb) in COLLAPSE.items():
        if nm_ not in piece_path: continue
        f_s = int(ca + 0.5 * (cb - ca)); base_, sc0 = piece_path[nm_].get(f_s, (P_T, 0.3))
        for _ in range(320):
            d_ = Vector((rg_.gauss(0, 1), rg_.gauss(0, 1), rg_.gauss(0, 1))).normalized()
            fp.append(P_T + d_ * rg_.uniform(0.0, 0.08)); fs_.append(base_ + d_ * rg_.uniform(0.05, 0.45) * max(0.25, sc0))
            fd.append(f_s + rg_.uniform(-3, 5)); fu.append((cb - f_s) + rg_.uniform(4, 9))
            fz.append(0.004 + 0.009 * rg_.random() ** 2); fb.append(0.3 + 0.7 * rg_.random() ** 2)
            ft.append(rg_.random() * 0.4 if nm_ in ('arch', 'cone', 'torus') else 0.45 + 0.5 * rg_.random())
    inflow = flow_grains('INFLOW', fp, fs_, fd, fu, fz, fb, ft, DUST_STOPS, 7.0)
    for f_, h_ in ((1, True), (T_IMP0 - 2, True), (T_IMP0 - 1, False), (T_IMP1 + 14, False), (T_IMP1 + 15, True)):
        inflow.hide_render = h_; inflow.keyframe_insert('hide_render', frame=f_)

    # 14C: light races along the cube's edges; a shockwave; the dust that was drawn in is thrown out
    Hc = 0.442
    cc_ = [Vector((x, y, z)) for x in (-Hc, Hc) for y in (-Hc, Hc) for z in (-Hc, Hc)]
    for k_, (a_, b_) in enumerate([(a_, b_) for i_, a_ in enumerate(cc_) for b_ in cc_[i_ + 1:]
                                   if sum(abs(a_[j] - b_[j]) > 1e-6 for j in range(3)) == 1]):
        eo_ = light_trail(f'CUBE_EDGE_{k_}', [a_.lerp(b_, i / 24) for i in range(25)],
                          Vector((0, 0, 1)) if abs((b_ - a_).normalized().z) < 0.9 else Vector((1, 0, 0)),
                          (lambda u: 0.85), 0.0028, 4.0, taper=0.0, coll=FX, stops=GOLD_STOPS, anim=True)
        parent_to(eo_, cube)
        nte_ = eo_.data.materials[0].node_tree
        anim_node_value(nte_.nodes['REVEAL'], [(1, 0.0), (978 + int(1.6 * k_), 0.0), (986 + int(1.6 * k_), 1.06)])
        anim_node_value(nte_.nodes['GAIN'], [(1, 1.0), (T_PL0 + 2, 1.0), (T_PL0 + 10, 0.0)])
    sh_dir = (cam_end(E_SHOCK)[0]).normalized()                  # the ring faces the lens
    for k_ in range(2):
        bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.01, major_segments=128, minor_segments=8, location=P_T)
        w_ = bpy.context.object; w_.name = f'SHOCK4_{k_}'
        w_.rotation_euler = sh_dir.to_track_quat('Z', 'Y').to_euler()
        wm, ntw, outw = mat_nodes(f'shock4 {k_}'); ew = ntw.nodes.new('ShaderNodeEmission')
        ew.inputs['Color'].default_value = (*lin('#FFD98A' if k_ == 0 else '#c4b6ff'), 1)
        tw = ntw.nodes.new('ShaderNodeBsdfTransparent'); aw = ntw.nodes.new('ShaderNodeAddShader')
        ntw.links.new(tw.outputs[0], aw.inputs[0]); ntw.links.new(ew.outputs[0], aw.inputs[1]); ntw.links.new(aw.outputs[0], outw.inputs['Surface'])
        no_emission_sampling(wm); w_.data.materials.append(wm); into(w_, FX)
        set_vis(w_, diffuse=False, glossy=False, transmission=False, scatter=False, shadow=False)
        t0 = E_SHOCK + 6 * k_
        for f_ in range(E_SHOCK - 2, E_SHOCK + 50, 2):
            x_ = max(0.0, min(1.0, (f_ - t0) / 34)); r_ = 0.6 + 13.0 * (1 - (1 - x_) ** 3)
            w_.scale = (r_, r_, r_); w_.keyframe_insert('scale', frame=f_)
        anim_input(ew, 'Strength', [(1, 0.0), (t0 - 1, 0.0), (t0 + 1, 26.0), (t0 + 34, 0.0)])
        for f_, h_ in ((1, True), (t0 - 2, True), (t0 - 1, False), (t0 + 36, False), (t0 + 37, True)):
            w_.hide_render = h_; w_.keyframe_insert('hide_render', frame=f_)
    # the energy dust: a shell round the cube, drawn in a little while it collapses, flung out at the shockwave
    rd_ = random.Random(31); ed_p, ed_s, ed_b, ed_t = [], [], [], []
    for _ in range(1600):
        d_ = Vector((rd_.gauss(0, 1), rd_.gauss(0, 1), rd_.gauss(0, 1))).normalized()
        ed_p.append(P_T + d_ * (1.3 + 4.2 * rd_.random() ** 1.3)); ed_s.append(0.003 + 0.008 * rd_.random() ** 2)
        ed_b.append(0.15 + 0.75 * rd_.random() ** 2.5); ed_t.append(rd_.random() * 0.8)
    edust = points_object('ENERGY_DUST', ed_p, {'size': ed_s, 'bright': ed_b, 'tone': ed_t}, FX)
    esrc = tiny_sphere('EDUST_src', glow_mat('energy dust', DUST_STOPS, 5.0), FX, subdiv=1)
    ng = bpy.data.node_groups.new('EDUST_GN', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    Nn, Ll = ng.nodes, ng.links
    gi = Nn.new('NodeGroupInput'); go = Nn.new('NodeGroupOutput'); st = Nn.new('GeometryNodeInputSceneTime')
    def mm(op, a, b=None, clamp=False):
        n_ = Nn.new('ShaderNodeMath'); n_.operation = op; n_.use_clamp = clamp
        for i_, v_ in enumerate((a, b)):
            if v_ is None: continue
            if isinstance(v_, (int, float)): n_.inputs[i_].default_value = v_
            else: Ll.new(v_, n_.inputs[i_])
        return n_.outputs[0]
    F_ = st.outputs['Frame']
    disp = mm('ADD', mm('MULTIPLY', mm('DIVIDE', mm('SUBTRACT', F_, 930.0), 65.0, clamp=True), -0.5),
              mm('MULTIPLY', mm('POWER', mm('MAXIMUM', mm('SUBTRACT', F_, float(E_SHOCK)), 0.0), 1.25), 0.32))
    ps = Nn.new('GeometryNodeInputPosition')
    rel = Nn.new('ShaderNodeVectorMath'); rel.operation = 'SUBTRACT'; Ll.new(ps.outputs['Position'], rel.inputs[0])
    rel.inputs[1].default_value = tuple(P_T)
    nrm = Nn.new('ShaderNodeVectorMath'); nrm.operation = 'NORMALIZE'; Ll.new(rel.outputs[0], nrm.inputs[0])
    scl = Nn.new('ShaderNodeVectorMath'); scl.operation = 'SCALE'; Ll.new(nrm.outputs[0], scl.inputs[0]); Ll.new(disp, scl.inputs['Scale'])
    sp = Nn.new('GeometryNodeSetPosition'); Ll.new(gi.outputs['Geometry'], sp.inputs['Geometry']); Ll.new(scl.outputs[0], sp.inputs['Offset'])
    sz = Nn.new('GeometryNodeInputNamedAttribute'); sz.data_type = 'FLOAT'; sz.inputs['Name'].default_value = 'size'
    ip = Nn.new('GeometryNodeInstanceOnPoints')
    oi = Nn.new('GeometryNodeObjectInfo'); oi.inputs['Object'].default_value = esrc; oi.inputs['As Instance'].default_value = True
    Ll.new(sp.outputs['Geometry'], ip.inputs['Points']); Ll.new(oi.outputs['Geometry'], ip.inputs['Instance'])
    Ll.new(mm('MULTIPLY', sz.outputs['Attribute'], mm('DIVIDE', mm('SUBTRACT', F_, float(E_RES0)), 16.0, clamp=True)), ip.inputs['Scale'])
    Ll.new(ip.outputs['Instances'], go.inputs['Geometry'])
    edust.modifiers.new('GN', 'NODES').node_group = ng
    set_vis(edust, diffuse=False, shadow=False, scatter=False)
    for f_, h_ in ((1, True), (E_RES0 - 1, True), (E_RES0, False), (E_SHOCK + 46, False), (E_SHOCK + 47, True)):
        edust.hide_render = h_; edust.keyframe_insert('hide_render', frame=f_)

    # 15A: the cube grows into a world, faster than the camera can get away; one face fills the lens
    for f_ in range(S4_0, S4_1 + 1, 2):
        cube.scale = (cube_scale(f_),) * 3; cube.keyframe_insert('scale', frame=f_)
    cube.visible_shadow = False                                   # its light reaches the other worlds
    face_dir = cam_end(1046)[0].normalized()
    q_face = face_dir.to_track_quat('X', 'Z')                     # a face square to the lens as it overwhelms it
    q_world = (Quaternion(Vector((0, 0, 1)), math.radians(34)) @ Quaternion(face_dir.cross(Vector((0, 0, 1))).normalized(),
                                                                              math.radians(-20)) @ q_face)
    q_c1n = q_c1
    for f_ in range(978, S5_1 + 1, 2):
        q_ = q_c1n.slerp(q_face, smoother((f_ - 978) / (1046 - 978)))
        if f_ > 1060: q_ = q_face.slerp(q_world, smoother((f_ - 1060) / (1110 - 1060)))
        if f_ > 1110: q_ = Quaternion(Vector((0, 0, 1)), math.radians(0.03 * (f_ - 1110))) @ q_   # barely turning: a world
        cube.rotation_euler = q_.to_euler('XYZ', cube.rotation_euler); cube.keyframe_insert('rotation_euler', frame=f_)
    for nm_ in ('torus', 'cube'):                                 # the orbits drawn round the totem let go
        ln_ = bpy.data.objects.get(f'ORBIT_LINE_{nm_}')
        if ln_: anim_node_value(ln_.data.materials[0].node_tree.nodes['GAIN'], [(E_RES0, 1.0), (T_IMP0 + 10, 0.0)])
    for o_, *_ in trails:                                         # and the violet orbit lines
        if o_.name.startswith('VIOLET'):
            anim_node_value(o_.data.materials[0].node_tree.nodes['GAIN'], [(E_RES0, 1.0), (T_IMP0 + 10, 0.0)])
    for o_ in orbs:
        o_.keyframe_insert('scale', frame=E_RES0); o_.scale = (0, 0, 0); o_.keyframe_insert('scale', frame=T_IMP0 + 10)

    # the light hands over: the close lights (now inside the world) go out; the universe is lit by a far sun, a violet
    # rim, and the world itself
    scene.frame_set(T_PL0)
    for lo_ in [o_ for o_ in bpy.data.objects if o_.type == 'LIGHT']:
        e0_ = lo_.data.energy
        lo_.data.energy = e0_; lo_.data.keyframe_insert('energy', frame=T_PL0)
        lo_.data.energy = 0.0; lo_.data.keyframe_insert('energy', frame=T_PL0 + 16)
    def sun_(name, hexc, direction, power):
        ld_ = bpy.data.lights.new(name, 'SUN'); ld_.color = lin(hexc); ld_.angle = math.radians(3)
        lo_ = bpy.data.objects.new(name, ld_); scene.collection.objects.link(lo_)
        lo_.rotation_euler = Vector(direction).normalized().to_track_quat('-Z', 'Y').to_euler()
        anim_float(ld_, 'energy', [(S4_0, 0.0), (T_PL0, 0.0), (T_PL0 + 20, power), (S5_END0, power), (S5_1, power * 0.45)])
        return lo_
    fwdF = (-posF).normalized(); rF_ = fwdF.cross(Z_UP).normalized()
    sun_('WORLD_KEY', '#FFF1DD', fwdF + rF_ * 0.9 - Z_UP * 0.8, 3.2)       # from upper left of the last frame (near neutral)
    sun_('WORLD_RIM', '#8a6bff', -fwdF + Z_UP * 0.3, 2.4)                  # violet, from behind
    glow_c = point('CREATION_LIGHT', P_T, 0.0, '#FFE2B0', radius=4.0)
    anim_float(L_(glow_c), 'energy', [(S4_0, 0.0), (T_PL0, 0.0), (T_PL1, 2.8e6), (S5_END0, 2.8e6), (S5_1, 1.1e6)])

    # 15B: a few grains drift across its face: minute against it, they give it its size
    rc_ = random.Random(41); cl_p, cl_v, cl_s, cl_b, cl_t = [], [], [], [], []
    face_pt = P_T + cam_end(1095)[0].normalized() * (0.47 * S_W + 1.0)
    side_ = cam_end(1095)[0].normalized().cross(Z_UP).normalized()
    for _ in range(260):
        v_ = side_ * rc_.uniform(0.04, 0.09) + Z_UP * rc_.uniform(-0.01, 0.02)
        cl_v.append(v_); cl_p.append(face_pt + side_ * rc_.uniform(-6, 2) + Z_UP * rc_.gauss(0, 2.5) - v_ * 1080)
        cl_s.append(0.03 + 0.07 * rc_.random() ** 2); cl_b.append(0.3 + 0.7 * rc_.random()); cl_t.append(rc_.random() * 0.3)
    clus = points_object('FACE_GRAINS', cl_p, {'vel': cl_v, 'size': cl_s, 'bright': cl_b, 'tone': cl_t}, FX)
    gn_instancer(clus, tiny_sphere('FACEG_src', glow_mat('face grains', DUST_STOPS, 6.0), FX), scale_attr='size',
                 drift_attr='vel', drift_rate=1.0)
    set_vis(clus, diffuse=False, shadow=False, scatter=False)
    for f_, h_ in ((1, True), (E_WORLD - 6, True), (E_WORLD - 5, False), (1190, False), (1191, True)):
        clus.hide_render = h_; clus.keyframe_insert('hide_render', frame=f_)

    # ======================================================================== V4 SCENE 06: THE UNIVERSE
    # The other worlds are Square DC's shapes at the size of planets, each a jewel, each with its own entrance: the
    # sapphire found by the camera's arc, the gold torus framing the yellow world, the ruby arch sweeping past the lens,
    # the green sphere coming out of the dark. Placed as the last frame sees them (and the torus on the line of sight).
    loc_U = P_T + posF; view_U = (P_T + tgtF - loc_U).normalized()
    rU, uU, _ = basis(view_U, Z_UP)
    def world_at(sx, sy, dist_):                             # a point straight out from the last camera at (sx, sy)
        d_ = (view_U + rU * (sx - 0.5) / FX_K - uU * (sy - 0.5) / (FX_K * 16 / 9)).normalized()
        return loc_U + d_ * dist_
    def shape_world(key_, R_, loc_, rot_, spin_, appear_):
        root_w = import_shape(key_, f'W_{key_}'); into(root_w, SHAPES)
        k_ = R_ / root_w['radius']
        brand_glow(root_w, key_, glow=0.25)
        root_w.location = loc_; root_w.scale = (k_,) * 3
        e0 = Euler([math.radians(v) for v in rot_])
        for f_ in (S4_0, S5_1):
            root_w.rotation_euler = Euler((e0.x, e0.y, e0.z + math.radians(spin_ * (f_ - S4_0))))
            root_w.keyframe_insert('rotation_euler', frame=f_)
        for fc in fcurves_of(root_w):
            for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
        for o_ in [root_w] + list(root_w.children_recursive):
            for f_, h_ in ((1, True), (appear_ - 1, True), (appear_, False)):
                o_.hide_render = h_; o_.keyframe_insert('hide_render', frame=f_)
        return root_w
    W_OCTA = shape_world('octa', 40.0, world_at(0.25, 0.31, 760.0), (24, 30, 12), 0.05, T_PL1)    # sapphire, upper left
    TOR_A, TOR_B = 1090, 1215                              # the gold torus rises from behind the yellow world, a moon
    W_TORUS = shape_world('torus', 32.0, world_at(0.80, 0.20, 540.0), (64, 6, 28), 0.06, TOR_A)   # gold, upper right
    tor_end = W_TORUS.location.copy(); tor_start = P_T + (-cam_end(TOR_A)[0]).normalized() * 330.0   # hidden behind it
    for f_ in range(TOR_A, TOR_B + 1, 3):
        W_TORUS.location = tor_start.lerp(tor_end, smoother((f_ - TOR_A) / (TOR_B - TOR_A)))
        W_TORUS.keyframe_insert('location', frame=f_)
    W_SPHERE = shape_world('sphere', 22.0, world_at(0.28, 0.76, 400.0), (0, 0, 0), 0.03, T_PL1)   # green, lower left
    def cam_at(f_, sx, sy, dist_):                        # a point at (sx, sy) of the frame as the camera is at f_
        l_, t_ = cam_end(f_); v_ = (t_ - l_).normalized(); r_, u_, _ = basis(v_, Z_UP)
        return P_T + l_ + (v_ + r_ * (sx - 0.5) / FX_K - u_ * (sy - 0.5) / (FX_K * 16 / 9)).normalized() * dist_
    W_ARCH = shape_world('arch', 22.0, world_at(0.86, 0.86, 140.0), (8, -6, -28), 0.04, 1200)
    for f_ in range(1200, E_FINAL + 1, 3):                # the ruby arch crosses the frame close to the lens, then settles
        x_ = smoother((f_ - 1200) / (E_FINAL - 1200))
        W_ARCH.location = cam_at(f_, -0.6 + 1.46 * x_, 0.95 - 0.09 * x_ - 0.16 * math.sin(math.pi * x_), 75.0 + 65.0 * x_)
        W_ARCH.keyframe_insert('location', frame=f_)

    # 17C: the worlds dim for the brand, leaving the yellow world glowing faintly (the lights above already fall)
    if MODE == 'dry4':
        near = {}
        for f_ in range(T_PL1, S4_1 + 1, 6):
            scene.frame_set(f_); c_ = P_T + cam_end(f_)[0]
            for w_, R_ in ((W_OCTA, 40.0), (W_TORUS, 32.0), (W_ARCH, 22.0), (W_SPHERE, 22.0)):
                if w_.hide_render: continue
                d_ = (c_ - w_.matrix_world.translation).length
                if d_ < near.get(w_.name, (1e9,))[0]: near[w_.name] = (d_, f_, R_, screen_pos(scene, cam, w_.matrix_world.translation))
        for k_, (d_, f_, R_, v_) in near.items():
            print(f'S4 WORLD {k_}: closest {d_:.1f} at frame {f_} (radius {R_}, fills {math.degrees(2 * math.asin(min(1, R_ / d_))):.0f} deg, screen {v_.x:.2f},{1 - v_.y:.2f})')

    # ======================================================================== V4 SCENE 07: THE PROJECTS
    # (feedback Oct 25) The worlds are Square DC's projects. From the universe the camera flies to each in turn, deeper
    # in each time (the arch, the sphere, the torus, the octahedron), eases into a slow orbit beside it while its name is
    # on the page (the world on one side of the frame, the words on the other), then draws back to the whole universe for
    # the brand's last words. Offsets from P_T, as in cam_end.
    tour = [(world_at(0.86, 0.86, 140.0), 22.0, 0.64, 16.0), (W_SPHERE.location.copy(), 22.0, 0.36, -16.0),
            (tor_end, 32.0, 0.64, 16.0), (W_OCTA.location.copy(), 40.0, 0.36, -16.0)]
    CK5 = [(S4_1, posF, tgtF)]; f5 = S4_1; TOUR5 = []
    for C_, R_, sx_, az_ in tour:
        c_ = C_ - P_T
        d0 = lift(rot_z((posF - c_).normalized(), az_), 5.0)           # from it, back toward where the universe was seen
        d1 = rot_z(d0, -9.0 if sx_ > 0.5 else 9.0)                      # the orbit carries the world toward the centre
        dist_ = 7.2 * R_
        o0, o1 = c_ + d0 * dist_, c_ + d1 * dist_ * 0.95
        t0 = aim(P_T + o0, C_, sx_, 0.5, Z_UP) - P_T; t1 = aim(P_T + o1, C_, sx_, 0.5, Z_UP) - P_T
        f5 += T5_FLY; CK5.append((f5, o0, t0)); a5 = f5
        f5 += T5_ORB; CK5.append((f5, o1, t1)); TOUR5.append((a5, f5))
    f5 += T5_BACK; CK5.append((f5, posF, tgtF))
    f5 += T5_END; CK5.append((f5, posF, tgtF))
    assert f5 == S5_1, (f5, S5_1)
    print('S5 TOUR orbits', TOUR5, 'end', S5_END0, S5_1)
    # the sapphire is glass: lit from behind while the camera is beside it, so its facets glow rather than go dark
    C_o = tour[3][0]; d_o = lift(rot_z((posF - (C_o - P_T)).normalized(), tour[3][3]), 5.0)
    ob_l = area('OCTA_BACK', C_o - d_o * 95.0 + Z_UP * 30.0, C_o, 60.0, 0.0, '#9fb6ff')
    anim_float(L_(ob_l), 'energy', [(1, 0.0), (TOUR5[3][0] - 40, 0.0), (TOUR5[3][0] - 5, 2.4e6), (TOUR5[3][1] + 5, 2.4e6),
                                    (TOUR5[3][1] + 40, 0.0)])
    orbit_starts = {a5 for a5, _ in TOUR5} | {S5_END0}
    def via(a_, b_):                       # a flight bends round the yellow world: its middle kept 3.5 world-radii clear
        m_ = (a_ + b_) / 2; clear_ = 3.5 * 0.62 * S_W
        if m_.length < clear_: m_ = (m_ + Z_UP * 0.35 * clear_).normalized() * clear_
        return 2 * m_ - (a_ + b_) / 2      # the control point that puts the curve through that middle halfway along
    def cam5(f):
        for i_ in range(len(CK5) - 1):
            if CK5[i_][0] <= f <= CK5[i_ + 1][0]: break
        (fa_, la_, ta_), (fb_, lb_, tb_) = CK5[i_], CK5[i_ + 1]
        x_ = smoother((f - fa_) / (fb_ - fa_))
        if fb_ in orbit_starts:            # a flight: one curve, eased end to end
            c_ = via(la_, lb_); loc_ = la_ * (1 - x_) ** 2 + c_ * 2 * (1 - x_) * x_ + lb_ * x_ * x_
        else:                              # the slow orbit beside a world, or the rest at the end
            loc_ = la_.lerp(lb_, x_)
        return loc_, ta_.lerp(tb_, x_)
    scene.frame_set(S4_1)                                         # (the camera's last rotation: the euler branch to follow)
    for f in range(S5_0, S5_1 + 1):
        l_, t_ = cam5(f); loc = P_T + l_; tgt = P_T + t_
        cam.location = loc
        view = (tgt - loc).normalized(); r_, u_, b_ = basis(view, Z_UP)
        cam.rotation_euler = Matrix((r_, u_, b_)).transposed().to_euler('XYZ', cam.rotation_euler)
        cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
        cam.data.dof.focus_distance = (loc - tgt).length; cam.data.dof.keyframe_insert('focus_distance', frame=f)
    if MODE == 'dry4':
        near5 = {}
        for f in range(S5_0, S5_1 + 1, 2):
            c_ = P_T + cam5(f)[0]
            for nm_, C_, R_ in (('arch', tour[0][0], 22.0), ('sphere', tour[1][0], 22.0), ('torus', tour[2][0], 32.0),
                                ('octa', tour[3][0], 40.0), ('cube', P_T, 0.62 * S_W)):
                d_ = (c_ - C_).length / R_
                if d_ < near5.get(nm_, (1e9,))[0]: near5[nm_] = (d_, f)
        print('S5 closest (in radii):', {k_: (round(v_[0], 2), v_[1]) for k_, v_ in near5.items()})
        for (a5, b5), (C_, R_, sx_, az_) in zip(TOUR5, tour):
            for f in (a5, b5):
                scene.frame_set(f); v_ = screen_pos(scene, cam, C_)
                print(f'S5 PROJECT frame {f}: world at ({v_.x:.2f}, {1 - v_.y:.2f}), {2 * math.degrees(math.atan(R_ / (cam.matrix_world.translation - C_).length)):.0f} deg')

    if MODE == 'dry4':
        for f in (F_HEAD, 950, 990, 1046, E_WORLD, 1165, 1260, E_FINAL):
            tr_ = track4[f - S4_0]
            scene.frame_set(f)
            vis = ' '.join(f"{r_o.name.split('_')[-1]}({screen_pos(scene, cam, r_o.matrix_world.translation).x:.2f},{1 - screen_pos(scene, cam, r_o.matrix_world.translation).y:.2f})" for r_o, *_ in shapes2)
            v = screen_pos(scene, cam, cube.matrix_world.translation)
            print(f"S4 FRAME {f}: cube blender({v.x:.3f},{1 - v.y:.3f}) track{tr_['c']} r{tr_['r']} text{tr_['q']} | {vis}")
        sys.exit(0)
    if MODE in ('s4', 's4final'):
        import json
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, 'track.json'), 'w') as fh:
            json.dump({'from': S4_0, 'box': TEXT_BOX, 'done': F_DONE, 'head': F_HEAD, 'end': S4_1,
                       'fore': [FORE4_0, FORE4_1], 'frames': track4}, fh, separators=(',', ':'))

    if MODE in ('fore4', 'fore4final'):
        # the second matte, as Scene 03's: nearer than the headline's plane; the totem itself is held in front whole
        for o in [cube] + totem:
            o['fore'] = 1.0
            for ch in o.children_recursive: ch['fore'] = 1.0
        for o in (haze, bpy.data.objects['SYS_CARD'], star, bpy.data.objects.get('CORONA'), rays):
            if o: o.hide_render = True
        P_TXT, n_txt = P_TXT4, n_txt4
        for mt in bpy.data.materials:
            if not mt.node_tree: continue
            nt = mt.node_tree; Nn = nt.nodes; Lk = nt.links
            out = next((n_ for n_ in Nn if n_.bl_idname == 'ShaderNodeOutputMaterial' and n_.is_active_output), None)
            if not out or not out.inputs['Surface'].links: continue
            src = out.inputs['Surface'].links[0].from_socket
            geo = Nn.new('ShaderNodeNewGeometry')
            sb = Nn.new('ShaderNodeVectorMath'); sb.operation = 'SUBTRACT'
            Lk.new(geo.outputs['Position'], sb.inputs[0]); sb.inputs[1].default_value = P_TXT
            dt = Nn.new('ShaderNodeVectorMath'); dt.operation = 'DOT_PRODUCT'
            Lk.new(sb.outputs[0], dt.inputs[0]); dt.inputs[1].default_value = n_txt
            mr = Nn.new('ShaderNodeMapRange'); mr.clamp = True
            mr.inputs['From Min'].default_value = 0.015; mr.inputs['From Max'].default_value = -0.015
            Lk.new(dt.outputs['Value'], mr.inputs['Value'])
            fa = Nn.new('ShaderNodeAttribute'); fa.attribute_type = 'OBJECT'; fa.attribute_name = 'fore'
            kp_ = Nn.new('ShaderNodeMath'); kp_.operation = 'SUBTRACT'; kp_.inputs[0].default_value = 1.0
            Lk.new(fa.outputs['Fac'], kp_.inputs[1])
            k_ = Nn.new('ShaderNodeMath'); k_.operation = 'MULTIPLY'; k_.use_clamp = True
            Lk.new(mr.outputs['Result'], k_.inputs[0]); Lk.new(kp_.outputs[0], k_.inputs[1])
            ho = Nn.new('ShaderNodeHoldout')
            mx = Nn.new('ShaderNodeMixShader')
            Lk.new(k_.outputs[0], mx.inputs['Fac']); Lk.new(src, mx.inputs[1]); Lk.new(ho.outputs[0], mx.inputs[2])
            Lk.new(mx.outputs[0], out.inputs['Surface'])
# ----------------------------------------------------------------------------------------------- render
if MODE == 'loop':
    F0, F1 = N + 1, N + LOOP_L + LOOP_C
if S2:
    F0, F1 = S2_0, S2_1
if S3:
    F0, F1 = (FORE_0, FORE_1) if MODE in ('fore3', 'fore3final') else (S3_0, S3_1)
if S4:
    F0, F1 = (FORE4_0, FORE4_1) if MODE in ('fore4', 'fore4final') else (S5_0, S5_1) if MODE in ('s5', 's5final') else (S4_0, S4_1)
if os.environ.get('SDC_RANGE'):                           # part of any scene: SDC_RANGE=first,last (batched renders)
    F0, F1 = (int(x) for x in os.environ['SDC_RANGE'].split(','))
if MODE == 'dry':
    for f in (60, N, N + 24, N + 96):
        scene.frame_set(f)
        ph = trails[0][0].data.materials[0].node_tree.nodes['PHASE'].outputs[0].default_value
        pu = trails[0][0].data.materials[0].node_tree.nodes['PULSE'].outputs[0].default_value
        print(f'LOOPCHECK {f}: spin_in {math.degrees(spin_in.rotation_axis_angle[0]):.2f} deg, phase {ph:.3f}, pulse {pu:.0f}, '
              f'fcurves spin_in={len(fcurves_of(spin_in))}')
    for f in (1, 20, 40, 60, 80, 100, N):
        scene.frame_set(f)
        v = screen_pos(scene, cam, star_pos)
        hit, *_ = scene.ray_cast(bpy.context.evaluated_depsgraph_get(), cam.location, (star_pos - cam.location).normalized(), distance=20.0)
        print(f'FRAME {f}: star screen ({v.x:.3f}, {v.y:.3f}) hidden-by-something-near={hit}')
    sys.exit(0)

prev = MODE in ('preview', 'loop', 's2', 's3', 'fore3', 's4', 'fore4', 's5')
render_setup(scene, w=960 if prev else 1600, h=540 if prev else 900, samples=20 if prev else 128,
             threshold=0.04 if prev else 0.012, mblur=os.environ.get('SDC_MBLUR', '0') == '1')
scene.render.motion_blur_shutter = 0.5
scene.cycles.transparent_max_bounces = 64       # dozens of see-through ring strands overlap: 8 turned them black
if os.environ.get('SDC_RES'):                     # production: e.g. SDC_RES=1920x1080 SDC_SAMPLES=64 SDC_THRESH=0.01
    scene.render.resolution_x, scene.render.resolution_y = (int(v) for v in os.environ['SDC_RES'].split('x'))
if os.environ.get('SDC_SAMPLES'): scene.cycles.samples = int(os.environ['SDC_SAMPLES'])
if os.environ.get('SDC_THRESH'): scene.cycles.adaptive_threshold = float(os.environ['SDC_THRESH'])
os.makedirs(OUT, exist_ok=True)
if MODE in ('fore3', 'fore3final', 'fore4', 'fore4final'):
    # the matte: coverage (alpha) plus the brightness of light trails, written linear as one grey channel
    c_ = scene.cycles
    bpy.data.objects['CUBE_AURA'].hide_render = True          # a glow, not a surface: the headlines stay in front of it
    c_.samples = 32; c_.use_adaptive_sampling = False; c_.use_denoising = False
    c_.max_bounces = 0; c_.transparent_max_bounces = 64
    scene.render.film_transparent = True
    vts = [e.identifier for e in scene.view_settings.bl_rna.properties['view_transform'].enum_items]
    print('VIEW TRANSFORMS', vts)
    scene.view_settings.view_transform = 'Raw' if 'Raw' in vts else 'Standard'
    scene.view_settings.exposure = 0.0; scene.view_settings.look = 'None'
    ng = bpy.data.node_groups.new('SDC fore', 'CompositorNodeTree')
    ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    scene.compositing_node_group = ng; scene.render.use_compositing = True
    rl = ng.nodes.new('CompositorNodeRLayers')
    bw = ng.nodes.new('CompositorNodeRGBToBW'); ng.links.new(rl.outputs['Image'], bw.inputs[0])
    kk = ng.nodes.new('ShaderNodeMath'); kk.operation = 'MULTIPLY'; kk.inputs[1].default_value = float(os.environ.get('SDC_FORE_K', '1.4'))
    ng.links.new(bw.outputs[0], kk.inputs[0])
    ad = ng.nodes.new('ShaderNodeMath'); ad.operation = 'ADD'; ad.use_clamp = True
    ng.links.new(kk.outputs[0], ad.inputs[0]); ng.links.new(rl.outputs['Alpha'], ad.inputs[1])
    go = ng.nodes.new('NodeGroupOutput'); ng.links.new(ad.outputs[0], go.inputs[0])
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'BW'
    scene.render.image_settings.color_depth = '8'
    scene.render.filepath = os.path.join(OUT, 'm_')
else:
    scene.render.image_settings.file_format = 'WEBP'
    scene.render.image_settings.quality = 80 if prev else 86
    if os.environ.get('SDC_QUALITY'): scene.render.image_settings.quality = int(os.environ['SDC_QUALITY'])
    scene.render.image_settings.color_mode = 'RGB'
    s01_ = not (S2 or S3 or S4)                     # Scene 01 and its loop: the sunrise gets the anamorphic streak
    lens(scene, flare=True, sun_pos=(sc.x, sc.y), fog=0.42, bloom=0.48, beams=0.0, streak=0.3 if s01_ else 0.08,
         ghosts=0.0, burst=0.14,                                   # (lens ghosts read as more dots: none)
         diffuse=0.06, vignette=0.5, halo=0.4, fog_thr=1.5, bloom_thr=0.9)          # (glow on what is truly bright)
    scene.render.filepath = os.path.join(OUT, 'f_')
if os.environ.get('SDC_FAST'):                   # a quick draft to judge motion and light before the real render:
    scene.render.resolution_x, scene.render.resolution_y = 640, 360        # the same engine, small and noisy
    scene.cycles.samples = int(os.environ.get('SDC_FAST_SAMPLES', '4')); scene.cycles.adaptive_threshold = 0.1
    scene.cycles.max_bounces = 4; scene.cycles.transmission_bounces = 4
    scene.render.use_motion_blur = False
    scene.render.image_settings.quality = 70
    print('FAST ENGINE', scene.render.engine)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'scene01.blend'), compress=True)
scene.frame_start, scene.frame_end = F0, F1
t0 = time.time()
only = [int(x) for x in os.environ.get('SDC_FRAMES', '').split(',') if x.strip()]
if only and os.environ.get('SDC_VIEW_COMPARE') == '1':     # look-dev: one frame, two colour pipelines, side by side
    base = scene.render.filepath
    ex_fc = [fc for fc in fcurves_of(scene) if fc.data_path == 'view_settings.exposure']
    def shift_exposure(d):                                 # the exposure is animated: move its whole curve
        for fc in ex_fc:
            for kp in fc.keyframe_points:
                kp.co.y += d; kp.handle_left.y += d; kp.handle_right.y += d
            fc.update()
    want = os.environ.get('SDC_COMPARE', 'khronos,agx_mhc,agx_punchy').split(',')
    for tag, vt, lk, d in (('khronos', 'Khronos PBR Neutral', 'None', 0.0), ('agx_mhc', 'AgX', 'AgX - Medium High Contrast', 0.3),
                           ('agx_punchy', 'AgX', 'AgX - Punchy', 0.3)):
        if tag not in want: continue
        scene.view_settings.view_transform = vt; scene.view_settings.look = lk
        print('COMPARE', tag, vt, scene.view_settings.look, 'exposure shift', d, 'curves', len(ex_fc))
        shift_exposure(d)
        for f in only:
            scene.frame_set(f); scene.render.filepath = base + f'{tag}_{f:04d}'
            bpy.ops.render.render(write_still=True)
        shift_exposure(-d)
    sys.exit(0)
if only:                                  # a handful of stills from the timeline (composition checks)
    base = scene.render.filepath
    for f in only:
        scene.frame_set(f); scene.render.filepath = base + f'{f:04d}'
        bpy.ops.render.render(write_still=True)
else:
    if os.environ.get('SDC_RESUME') == '1':
        scene.render.use_overwrite = False          # a restarted chain picks up where it stopped (frames on disk are kept)
    bpy.ops.render.render(animation=True)
print('ANIMATION SECONDS', round(time.time() - t0, 1), 'frames', N)
