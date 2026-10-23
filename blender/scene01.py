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
        n.inputs['Subsurface Radius'].default_value = (1.0, 0.9, 0.32)
        n.inputs['Subsurface Scale'].default_value = 0.2
cube.data.materials.append(m)
ROT_END = (8, -9, 40)
plane = (math.radians(-6), math.radians(-12), math.radians(8))
M = Euler(plane).to_matrix()
AXIS = tuple(M @ Vector((0, 0, 1)))
front = -100.0

# ----------------------------------------------------------------------------------------------- the cube forms
# Before anything else the cube gathers out of the dark (the particle-shape reference, run the other way): gold and
# violet grains drift in a loose cloud, then spiral in and settle onto its surface, and the surface forms behind them,
# bottom to top, with a warm edge. One field decides both: a grain lands where, and when, the surface appears.
FORM_F0, FORM_DUR, FORM_SPAN = 2.0, 20.0, 26.0            # grains leave 2..28, land 22..48; the surface 22..48


def form_field(x, y, z):                                  # organic patches all over: it crystallises everywhere at once
    return max(0.0, min(1.0, 0.5 + (math.sin(10.4 * x + 6.5 * y + 4.3 * z + 1.3) + math.sin(-3.3 * x + 9.4 * y + 4.6 * z + 0.4)
                                    + math.sin(5.4 * x - 3.0 * y + 10.3 * z + 2.1)) / 6.0))


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
    d = Vector((rf.gauss(0, 1), rf.gauss(0, 1), rf.gauss(0, 0.55))).normalized()
    if d.dot(cam_l) > 0.15: d = (d - 2 * d.dot(cam_l) * cam_l).normalized()          # never between cube and lens
    f_tgt.append(p); f_start.append(p + d * (0.3 + 1.1 * rf.random() ** 0.8))
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
for f_, h_ in ((1, False), (54, False), (55, True)):                                # done: out of every later render
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
fld_ = _cm('ADD', 0.5, _cm('DIVIDE', _cm('ADD', _cm('ADD', _wave(10.4, 6.5, 4.3, 1.3), _wave(-3.3, 9.4, 4.6, 0.4)),
                                       _wave(5.4, -3.0, 10.3, 2.1)), 6.0))           # the same field as form_field()
rv_c = Nc.new('ShaderNodeValue'); rv_c.name = 'FORM_REVEAL'; rv_c.outputs[0].default_value = 1.2
dd_ = _cm('SUBTRACT', rv_c.outputs[0], fld_)
mask_ = Nc.new('ShaderNodeMapRange'); mask_.interpolation_type = 'SMOOTHSTEP'; Lc.new(dd_, mask_.inputs['Value'])
mask_.inputs['From Min'].default_value = 0.0; mask_.inputs['From Max'].default_value = 0.035
edge_ = _cm('MULTIPLY', _cm('SUBTRACT', 1.0, _cm('DIVIDE', _cm('ABSOLUTE', dd_), 0.024), clamp=True), 3.0)
em_c = Nc.new('ShaderNodeEmission'); em_c.inputs['Color'].default_value = (*lin('#FFC24A'), 1); Lc.new(edge_, em_c.inputs['Strength'])
ad_c = Nc.new('ShaderNodeAddShader'); Lc.new(src_c, ad_c.inputs[0]); Lc.new(em_c.outputs[0], ad_c.inputs[1])
# while it is open, its inside is not drawn: it reads as shards assembling, not a hollow box (closed, it never shows)
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
P1 = dict(az=-10.0, el=12.0, d=5.3, tgt=Vector((0.06, 0.0, -0.04)), fstop=2.8)


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

gold_orb = worn_material('orb gold', '#FFC21A', metallic=0.0, rough=0.4, coat=0.4, wear=0.1, emit_hex='#FFB21F', emit=0.5)
vio_orb = worn_material('orb violet', '#6a52f0', metallic=0.0, rough=0.4, coat=0.4, wear=0.1, emit_hex='#7a5cff', emit=0.7)


def on_ring(r, want_x, want_y):
    best_ = min(range(0, 360, 2), key=lambda dg: (screen_pos(scene, cam, M @ Vector((r * math.cos(math.radians(dg)), r * math.sin(math.radians(dg)), 0))).x - want_x) ** 2 +
                (screen_pos(scene, cam, M @ Vector((r * math.cos(math.radians(dg)), r * math.sin(math.radians(dg)), 0))).y - want_y) ** 2)
    # the orbs ride the outer spinner: start them 8 degrees back so they arrive on their mark
    return M @ Vector((r * math.cos(math.radians(best_ - 8)), r * math.sin(math.radians(best_ - 8)), 0))


orbs = []
for r, sx, sy, rad, mat_ in ((1.6, 0.17, 0.4, 0.026, gold_orb), (1.95, 0.12, 0.3, 0.02, vio_orb),
                             (1.95, 0.83, 0.72, 0.018, vio_orb), (2.35, 0.72, 0.17, 0.028, gold_orb),
                             (2.48, 0.93, 0.6, 0.022, gold_orb)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=rad, segments=32, ring_count=16, location=on_ring(r, sx, sy))
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
scene.world = sleek_world(glow_dir=(0.6, -0.4, -0.5), base='#12042a', haze='#2c0e58', haze_power=1.3)
stars(WORLD, FX, n=700, seed=31, max_b=5.0)

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
anim_float(L_(star_sun), 'energy', [(1, 0.0), (18, 0.0), (48, 10.0)])
star_em = next(n for n in star.data.materials[0].node_tree.nodes if n.bl_idname == 'ShaderNodeEmission')
anim_input(star_em, 'Strength', [(1, 0.0), (18, 0.0), (46, 1100.0)])
cor_mat = bpy.data.objects['CORONA'].data.materials[0]
cor_ml = next(n for n in cor_mat.node_tree.nodes if n.bl_idname == 'ShaderNodeMath' and n.operation == 'MULTIPLY')
for f_, v_ in ((1, 0.0), (20, 0.0), (50, 5.0)):
    cor_ml.inputs[1].default_value = v_; cor_ml.inputs[1].keyframe_insert('default_value', frame=f_)
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
anim_node_value(sun_v, [(1, 0.0), (22, 0.0), (60, 1.0)])
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
S4_MODES = ('s4', 's4final', 'dry4', 'fore4', 'fore4final')
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
        for ch in shape_children(root):
            for sl in ch.material_slots: add_wear(sl.material, 0.6)
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

    # light for the wider system, rising from nothing so the hero frame is untouched at the hand-off
    sys_key = area('SYS_KEY', (-6.0, -5.0, 7.0), (0, 0, 0), 6.0, 700, '#FFE6C0'); sys_key.visible_glossy = False
    sys_rim = area('SYS_RIM', (0.5, 9.0, 3.0), (0, 0, 0), 7.0, 900, '#6a5cff'); sys_rim.visible_glossy = False
    anim_float(L_(sys_key), 'energy', [(N, 0.0), (N + 1, 0.0), (N + 40, 700.0)])
    anim_float(L_(sys_rim), 'energy', [(N, 0.0), (N + 1, 0.0), (N + 40, 900.0)])
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
S4_0, S4_1 = S3_1 + 1, S3_1 + 435                        # 566-1000
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
    anim_input(star_em, 'Strength', [(S2_1, 1100.0), (S2_1 + 40, 0.0)])
    anim_node_value(sun_v, [(S2_1, 1.0), (S2_1 + 40, 0.0)])
    for f_, v_ in ((S2_1, 5.0), (S2_1 + 40, 0.0)):
        cor_ml.inputs[1].default_value = v_; cor_ml.inputs[1].keyframe_insert('default_value', frame=f_)

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
            anim_node_value(nt.nodes['GAIN'], [(S2_1, 0.0), (F_MOM, 0.0), (F_MOM + 16, 1.0)])
        else:
            anim_node_value(nt.nodes['TAIL'], [(S2_1, 14.7 / S3_LEN), (F_MOM, 18.9 / S3_LEN), (F_B, 72 / S3_LEN), (F_C, 96 / S3_LEN)])
            anim_node_value(nt.nodes['GAIN'], [(S2_1, 0.0), (S2_1 + 14, 0.6), (F_MOM, 0.6), (F_B, 0.9)])  # quiet under the words

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
    # the order they are drawn in, and when: the cube turns onto its edge first, then the pieces come one by one
    FLIGHT = {'dome': (F_T - 10, F_T + 35), 'arch': (F_T + 5, F_T + 52), 'sphere': (F_T + 22, F_T + 65),
              'cone': (F_T + 38, F_T + 85), 'octa': (F_T + 52, F_T + 95)}
    CUBE_TURN = (F_T - 20, F_T + 20)
    print('S4 TOTEM: cube at', tuple(round(x, 3) for x in P_T), 'height', round(z_octa + h['octa'] / 2 - z_arch + h['arch'] / 2, 2))

    def smoother(x):
        x = max(0.0, min(1.0, x)); return x * x * x * (x * (6 * x - 15) + 10)

    totem = []
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
            root.scale = (s_,) * 3
            root.keyframe_insert('location', frame=f); root.keyframe_insert('rotation_euler', frame=f)
            root.keyframe_insert('scale', frame=f)

    # the cube turns onto its edge: a diamond facing the camera, turned a little so it keeps its depth
    q_c0 = cube.rotation_euler.to_quaternion()
    q_c1 = (yaw @ Matrix.Rotation(math.radians(20), 3, 'Z') @ Matrix.Rotation(math.radians(45), 3, 'Y')).to_quaternion()
    for f in range(S4_0, S4_1 + 1, 2):
        e = smoother((f - CUBE_TURN[0]) / (CUBE_TURN[1] - CUBE_TURN[0]))
        cube.rotation_euler = q_c0.slerp(q_c1, e).to_euler('XYZ', cube.rotation_euler)
        cube.keyframe_insert('rotation_euler', frame=f)

    # Scene 03's helices let go as the system stops
    for nm in list(orbits_full) + ['pixel']:
        nt = bpy.data.objects[f'HELIX_{nm}'].data.materials[0].node_tree
        anim_node_value(nt.nodes['GAIN'], [(S3_1, 0.9 if nm != 'pixel' else 1.0), (S3_1 + 40, 0.0)])

    # ignition: the cube lights from inside, the band flares, the dust bursts outward and stays wider (a world)
    pr = next(n_ for n_ in cube.data.materials[0].node_tree.nodes if n_.bl_idname == 'ShaderNodeBsdfPrincipled')
    F_IG = F_DONE + 10
    anim_input(pr, 'Emission Strength', [(F_DONE, 0.0), (F_IG + 30, 2.6), (F_HEAD, 1.1), (S4_1, 3.4)])   # and as the
    anim_float(L_(capture), 'energy', [(F_DONE, 140.0), (F_IG + 30, 420.0), (F_HEAD, 220.0), (S4_1, 600.0)])  # camera
    # leaves it glows on, gently: the one shape that remains
    # the totem's own light: a soft key from the camera's side, above, and a violet rim behind for its silhouette
    side_t = toward.cross(Vector((0, 0, 1))).normalized()
    tk = area('TOTEM_KEY', P_T + toward * 9 + side_t * 4 + Vector((0, 0, 5)), P_T, 6.0, 1600, '#FFF1DE'); tk.visible_glossy = False
    tr_ = area('TOTEM_RIM', P_T - toward * 8 - side_t * 3 + Vector((0, 0, 4)), P_T, 6.0, 1400, '#7a5cff'); tr_.visible_glossy = False
    # the hero frame's sun leaves as the camera comes round: its pin-point highlight on the glossy pieces flares
    anim_float(L_(star_sun), 'energy', [(640, 10.0), (680, 0.0)])
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
           'T': (toward * 19.5, (0.6, 0.5), Z_UP),
           'T2': (toward_at(AZ_T - 3, EL_T) * 18.6, (0.62, 0.5), Z_UP),
           'H': (toward_at(AZ_T - 4, EL_T) * 17.0, (0.627, 0.5), Z_UP),
           'F': (toward_at(AZ_T - 8, 6.0) * 95.0, (0.5, 0.64), Z_UP)}
    tgt4 = {k: aim(v[0], Vector((0, 0, 0)), v[1][0], v[1][1], v[2]) for k, v in ST4.items()}
    tgt4['C'] = tgt_off['C']
    keys4 = [(S3_1, 'C'), (F_T, 'T'), (F_DONE, 'T2'), (F_HEAD, 'H'), (S4_1, 'F')]
    cam.data.clip_end = max(cam.data.clip_end, 5000.0)

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
        ln = oa.length + (ob.length - oa.length) * (t if nb != 'F' else t ** 2.2)   # the pull-back gathers pace
        off = dirn * ln
        P = cpos(f) + (P_T - cpos(F_STOP))                         # the cube itself (the system's origin is close by)
        loc = P + off
        up = ST4[na][2].lerp(ST4[nb][2], t).normalized()
        tgt = P + tgt4[na].lerp(tgt4[nb], t)
        cam.location = loc
        view = (tgt - loc).normalized(); r_, u_, b_ = basis(view, up)
        cam.rotation_euler = Matrix((r_, u_, b_)).transposed().to_euler('XYZ', cam.rotation_euler)
        cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
        cam.data.dof.focus_distance = (loc - P).length; cam.data.dof.aperture_fstop = 4.0
        cam.data.dof.keyframe_insert('focus_distance', frame=f); cam.data.dof.keyframe_insert('aperture_fstop', frame=f)
        mw = Matrix.Translation(loc) @ Matrix((r_, u_, b_)).transposed().to_4x4()
        c_ = project(mw, P); e_ = project(mw, P + r_ * 0.62)
        q_ = [project(mw, p_) for p_ in corners4]
        track4.append({'f': f, 'c': [round(c_[0], 4), round(c_[1], 4)], 'r': round(abs(e_[0] - c_[0]), 5),
                       'q': None if None in q_ else [[round(p_[0], 4), round(p_[1], 4)] for p_ in q_]})
    # THE TWO WORLDS (after the reference of a small sphere between two giant rim-lit horizons): as the camera pulls
    # back for the last words, two enormous dark planets curve across the frame's corners, their inner edges lit by the
    # creation between them. Different worlds, one universe. Out of every frame before the pull-back.
    loc_F = P_T + ST4['F'][0]; view_F = (P_T + tgt4['F'] - loc_F).normalized()
    rF, uF, _ = basis(view_F, Z_UP)
    def world_at(sx, sy, dist_):                             # a point straight out from the final camera at (sx, sy)
        d_ = (view_F + rF * (sx - 0.5) / FX_K - uF * (sy - 0.5) / (FX_K * 16 / 9)).normalized()
        return loc_F + d_ * dist_
    for nm_, (sx, sy), r_scr, rim_hex in (('WORLD_A', (-0.55, -0.75), 0.95, '#cdbdff'), ('WORLD_B', (1.55, 1.8), 0.95, '#ffd9a6')):
        D_ = 900.0; R_ = D_ * math.sin(math.atan(r_scr / FX_K))
        bpy.ops.mesh.primitive_uv_sphere_add(radius=R_, segments=128, ring_count=64, location=world_at(sx, sy, D_))
        pl = bpy.context.object; pl.name = nm_
        for poly in pl.data.polygons: poly.use_smooth = True
        mt_, ntp, outp = mat_nodes(nm_.lower()); Np, Lp = ntp.nodes, ntp.links
        body = Np.new('ShaderNodeBsdfPrincipled'); body.inputs['Base Color'].default_value = (*lin('#05030b'), 1)
        body.inputs['Roughness'].default_value = 0.85
        lw = Np.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.3
        geo_p = Np.new('ShaderNodeNewGeometry')
        tw_ = Np.new('ShaderNodeVectorMath'); tw_.operation = 'DOT_PRODUCT'; Lp.new(geo_p.outputs['Normal'], tw_.inputs[0])
        tw_.inputs[1].default_value = tuple((P_T - pl.location).normalized())                 # the side facing the creation
        side_ = Np.new('ShaderNodeMath'); side_.operation = 'MAXIMUM'; side_.inputs[1].default_value = 0.0; Lp.new(tw_.outputs['Value'], side_.inputs[0])
        pw_ = Np.new('ShaderNodeMapRange'); pw_.interpolation_type = 'SMOOTHSTEP'   # a crisp band at the silhouette only
        pw_.inputs['From Min'].default_value = 0.86; pw_.inputs['From Max'].default_value = 1.0
        Lp.new(lw.outputs['Facing'], pw_.inputs['Value'])
        rk_ = Np.new('ShaderNodeMath'); rk_.operation = 'MULTIPLY'; Lp.new(pw_.outputs['Result'], rk_.inputs[0]); Lp.new(side_.outputs[0], rk_.inputs[1])
        rimv = Np.new('ShaderNodeValue'); rimv.name = 'RIM'; rimv.outputs[0].default_value = 0.0
        rs_ = Np.new('ShaderNodeMath'); rs_.operation = 'MULTIPLY'; Lp.new(rk_.outputs[0], rs_.inputs[0]); Lp.new(rimv.outputs[0], rs_.inputs[1])
        em_p = Np.new('ShaderNodeEmission'); em_p.inputs['Color'].default_value = (*lin(rim_hex), 1); Lp.new(rs_.outputs[0], em_p.inputs['Strength'])
        ad_p = Np.new('ShaderNodeAddShader'); Lp.new(body.outputs[0], ad_p.inputs[0]); Lp.new(em_p.outputs[0], ad_p.inputs[1])
        Lp.new(ad_p.outputs[0], outp.inputs['Surface'])
        pl.data.materials.append(mt_)
        anim_node_value(rimv, [(F_HEAD + 20, 0.0), (S4_1 - 25, 4.0)])
        for f_, h_ in ((1, True), (F_HEAD - 1, True), (F_HEAD, False)):
            pl.hide_render = h_; pl.keyframe_insert('hide_render', frame=f_)

    if MODE == 'dry4':
        for f in (S4_0, F_STOP, F_T, F_T + 60, F_DONE, F_HEAD, F_HEAD + 60, S4_1):
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
    F0, F1 = (FORE4_0, FORE4_1) if MODE in ('fore4', 'fore4final') else (S4_0, S4_1)
if S3:
    if os.environ.get('SDC_RANGE'):                       # re-render part of the scene: SDC_RANGE=first,last
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

prev = MODE in ('preview', 'loop', 's2', 's3', 'fore3', 's4', 'fore4')
render_setup(scene, w=960 if prev else 1600, h=540 if prev else 900, samples=20 if prev else 128,
             threshold=0.04 if prev else 0.012, mblur=os.environ.get('SDC_MBLUR', '0') == '1')
scene.render.motion_blur_shutter = 0.5
scene.cycles.transparent_max_bounces = 64       # dozens of see-through ring strands overlap: 8 turned them black
os.makedirs(OUT, exist_ok=True)
if MODE in ('fore3', 'fore3final', 'fore4', 'fore4final'):
    # the matte: coverage (alpha) plus the brightness of light trails, written linear as one grey channel
    c_ = scene.cycles
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
    scene.render.image_settings.color_mode = 'RGB'
    lens(scene, flare=True, sun_pos=(sc.x, sc.y), fog=0.32, bloom=0.34, beams=0.0, streak=0.08, ghosts=0.13, burst=0.14,
         diffuse=0.04, vignette=0.5, halo=0.4)
    scene.render.filepath = os.path.join(OUT, 'f_')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'scene01.blend'), compress=True)
scene.frame_start, scene.frame_end = F0, F1
t0 = time.time()
only = [int(x) for x in os.environ.get('SDC_FRAMES', '').split(',') if x.strip()]
if only:                                  # a handful of stills from the timeline (composition checks)
    base = scene.render.filepath
    for f in only:
        scene.frame_set(f); scene.render.filepath = base + f'{f:04d}'
        bpy.ops.render.render(write_still=True)
else:
    bpy.ops.render.render(animation=True)
print('ANIMATION SECONDS', round(time.time() - t0, 1), 'frames', N)
