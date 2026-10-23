"""Scene 03b, The making: the 4D of the landing page's 'How We Work' (Define, Design, Develop, Deliver), played
between Scene 03 ('something new begins.') and Scene 04 (the totem). Frames 1001-1430, one take on the idea, a gold ball.
After the stacked-and-spun spheres, marble-run and assembling-cube references.

  1001-1100 Define   the ball spirals up an axis drawing a fine gold line; a blueprint cube, its grid and orbits draw
  1100-1200 Design   27 blocks in the brand colours swirl in and lock into the blueprint; a wave turns them yellow and
                     the seams close: the cube
  1200-1330 Develop  the ball rolls off the cube; a gold slide builds itself just ahead of it as it races down round
                     the cube, through gold coils ('make things happen at full throttle')
  1330-1430 Deliver  a lip throws it in an arc into a gold ring; the ring lights and sends a shockwave out; the camera
                     pulls back to the whole machine

blender -b --factory-startup --python scene_make.py -- <preview|final|dry> <outdir>
  SDC_FRAMES=a,b,c  render only those frames;  SDC_RANGE=a,b  render a sub-range
"""
import bpy, sys, os, math, random, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import keys                                      # empty scene, collections and every helper of the key stills
from keys import *
from mathutils import Vector, Euler, Matrix, Quaternion

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
MODE = argv[0] if argv else 'preview'
OUT = os.path.abspath(argv[1]) if len(argv) > 1 else '/tmp/s03b'
F0, F1 = 1001, 1430
scene = keys.scene
scene.frame_start, scene.frame_end = F0, F1
Z = Vector((0, 0, 1))


def ease(x):
    x = max(0.0, min(1.0, x)); return x * x * x * (x * (6 * x - 15) + 10)


def ramp(f, a, b):
    return ease((f - a) / (b - a))


def back(x, k=1.1):                                  # ease out with a small overshoot: it lands, sinks a hair, settles
    x = max(0.0, min(1.0, x)); return 1 + (k + 1) * (x - 1) ** 3 + k * (x - 1) ** 2


def fcurves_of(id_):
    ad = getattr(id_, 'animation_data', None)
    if not ad or not ad.action: return []
    act = ad.action
    try:
        if len(act.fcurves): return list(act.fcurves)
    except Exception: pass
    try:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(act, ad.action_slot)
        if cb: return list(cb.fcurves)
    except Exception: pass
    out = []
    for layer in getattr(act, 'layers', []):
        for strip in layer.strips:
            for cb in getattr(strip, 'channelbags', []):
                out += list(cb.fcurves)
    return out


def linear_keys(id_, token):
    for fc in fcurves_of(id_):
        if token in fc.data_path:
            for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'


def anim_node_value(node, pairs):
    for f, v in pairs:
        node.outputs[0].default_value = v; node.outputs[0].keyframe_insert('default_value', frame=f)


def anim_input(node, name, pairs):
    for f, v in pairs:
        node.inputs[name].default_value = v; node.inputs[name].keyframe_insert('default_value', frame=f)


def anim_energy(light_obj, pairs):
    for f, v in pairs:
        light_obj.data.energy = v; light_obj.data.keyframe_insert('energy', frame=f)


def drawn_line(name, pts, stops, width, peak, reveal, gain, coll=FX):
    """A fine glowing line that draws itself: REVEAL keyed (frame, 0..1), GAIN keyed (frame, value)."""
    t = (pts[-1] - pts[0]); nrm = Z if abs(t.normalized().dot(Z)) < 0.9 else Vector((1, 0, 0))
    o = light_trail(name, pts, nrm, (lambda u: 0.8), width, peak, taper=0.0, coll=coll, stops=stops, anim=True)
    nt = o.data.materials[0].node_tree
    for n_ in nt.nodes:                                  # the lit head sits on the pen, not a stretch ahead of it
        if n_.bl_idname == 'ShaderNodeMapRange' and abs(n_.inputs['From Min'].default_value + 0.06) < 1e-6:
            n_.inputs['From Min'].default_value = -0.002
    anim_node_value(nt.nodes['REVEAL'], reveal)
    anim_node_value(nt.nodes['GAIN'], gain)
    linear_keys(nt, 'REVEAL')
    return o


GOLD_LINE = [(0.0, '#2e1404'), (0.4, '#c47f00'), (0.7, '#FFC000'), (0.9, '#FFE9A8'), (1.0, '#FFFFFF')]
rnd = random.Random(7)
scene.world = sleek_world(glow_dir=(0.6, -0.4, -0.5), base='#12042a', haze='#2c0e58', haze_power=1.3)
stars(WORLD, FX, n=900, seed=41, max_b=5.0)

# ----------------------------------------------------------------------------------------------- the idea
BALL_R = 0.1
bpy.ops.mesh.primitive_uv_sphere_add(radius=BALL_R, segments=48, ring_count=24)
ball = bpy.context.object; ball.name = 'IDEA'
for p in ball.data.polygons: p.use_smooth = True
ball.data.materials.append(worn_material('idea gold', '#FFC21A', rough=0.24, coat=0.7, wear=0.18, mottle=0.14,
                                         emit_hex='#FFB21F', emit=1.1))
into(ball, SHAPES)
ball.rotation_mode = 'QUATERNION'
glow = point('IDEA_GLOW', (0, 0, 0), 4.0, '#FFC24A', radius=0.03)     # lights the channel round it as it goes
glow.data.use_soft_falloff = False

# ----------------------------------------------------------------------------------------------- 01 Define
H = 1.2                                                     # the cube to come: 2.4 across, 3 x 3 x 3 cells of 0.8
HX_R, HX_TURNS, HX_Z0, HX_Z1, A0 = 1.75, 4.0, -1.45, 1.45, math.radians(-120)
D0, D1 = 1006, 1086


def helix_pt(s):
    a = A0 + s * HX_TURNS * math.tau
    return Vector((HX_R * math.cos(a), HX_R * math.sin(a), HX_Z0 + (HX_Z1 - HX_Z0) * s))


def def_s(f): return ease((f - D0) / (D1 - D0))


drawn_line('DEF_HELIX', [helix_pt(i / 1600) for i in range(1601)], GOLD_LINE, 0.0042, 3.2,
           [(F0, -0.01)] + [(f, def_s(f)) for f in range(D0, D1 + 1, 2)] + [(D1, 1.0)],
           [(F0, 1.0), (1150, 1.0), (1186, 0.0)])
corners = [Vector((x, y, z)) for x in (-H, H) for y in (-H, H) for z in (-H, H)]
edges = [(a, b) for i, a in enumerate(corners) for b in corners[i + 1:] if sum(abs(a[k] - b[k]) > 1e-6 for k in range(3)) == 1]
edges.sort(key=lambda e: ((e[0] + e[1]) / 2).z)
for k, (a, b) in enumerate(edges):                          # the blueprint: the cube's twelve edges, bottom up
    f0 = 1020 + 3.5 * k
    drawn_line(f'DEF_EDGE_{k}', [a.lerp(b, i / 60) for i in range(61)], VIOLET_STOPS, 0.0032, 2.6,
               [(F0, 0.0), (int(f0), 0.0), (int(f0 + 24), 1.0)], [(F0, 1.0), (1150, 1.0), (1194, 0.0)])
k = 0
for ax in range(3):                                         # and its grid: two lines each way on every face
    for sgn in (-H, H):
        for other in [o for o in range(3) if o != ax]:
            run = [o for o in range(3) if o not in (ax, other)][0]
            for g in (-0.4, 0.4):
                a = Vector((0, 0, 0)); a[ax] = sgn; a[other] = g; a[run] = -H
                b = a.copy(); b[run] = H
                f0 = 1046 + 1.4 * k; k += 1
                drawn_line(f'DEF_GRID_{k}', [a.lerp(b, i / 40) for i in range(41)], VIOLET_STOPS, 0.0018, 1.3,
                           [(F0, 0.0), (int(f0), 0.0), (int(f0 + 20), 1.0)], [(F0, 1.0), (1120, 1.0), (1170, 0.0)])
for k, rot in enumerate(((70, 0, 20), (70, 0, 140), (70, 0, 260))):   # three orbits round it, like an atom
    pts, _ = ring_path(2.65, 0, math.tau, rot=tuple(math.radians(r) for r in rot), n=480)
    f0 = 1036 + 9 * k
    drawn_line(f'DEF_ORBIT_{k}', pts, GOLD_LINE if k == 1 else VIOLET_STOPS, 0.0026, 1.8,
               [(F0, 0.0), (f0, 0.0), (f0 + 40, 1.0)], [(F0, 1.0), (1150, 1.0), (1188, 0.0)])

# ----------------------------------------------------------------------------------------------- 02 Design
CELL, BLK = 0.8, 0.76
PAL = ['#6a52f0', '#1858FD', '#F66FD6', '#2fb36b', '#F2EBD9', '#7a5cff', '#ff7a3d', '#1829F3']


def block_mat(name, hexc, f_yel):
    m_, nt, out = mat_nodes(name); N_ = nt.nodes; L_ = nt.links
    b = N_.new('ShaderNodeBsdfPrincipled')
    mx = N_.new('ShaderNodeMix'); mx.data_type = 'RGBA'
    mx.inputs['A'].default_value = (*lin(hexc), 1); mx.inputs['B'].default_value = (*lin('#FFD21A'), 1)
    v = N_.new('ShaderNodeValue'); v.name = 'YELLOW'
    L_.new(v.outputs[0], mx.inputs['Factor']); L_.new(mx.outputs['Result'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.34
    b.inputs['Coat Weight'].default_value = 0.6; b.inputs['Coat Roughness'].default_value = 0.04
    b.inputs['Emission Color'].default_value = (*lin('#FFC400'), 1)
    L_.new(b.outputs[0], out.inputs['Surface'])
    anim_node_value(v, [(F0, 0.0), (int(f_yel), 0.0), (int(f_yel) + 9, 1.0)])
    anim_input(b, 'Emission Strength', [(F0, 0.0), (int(f_yel), 0.0), (int(f_yel) + 4, 0.9), (int(f_yel) + 16, 0.0)])
    return m_


blocks = []
for kz in range(3):
    for jy in range(3):
        for ix in range(3):
            c = Vector(((ix - 1) * CELL, (jy - 1) * CELL, (kz - 1) * CELL))
            d = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 0.6))).normalized()
            s0 = c + d * rnd.uniform(4.5, 7.0)
            ts = 1102 + 15 * kz + rnd.uniform(0, 12); dur = rnd.uniform(30, 38)
            q0 = Euler((rnd.uniform(-3, 3), rnd.uniform(-3, 3), rnd.uniform(-3, 3))).to_quaternion()
            o = crisp_cube(f'BLK_{kz}{jy}{ix}', BLK, 0.03, 4, coll=SHAPES)
            o.data.materials.append(block_mat(f'blk {kz}{jy}{ix}', rnd.choice(PAL), 1176 + 4 * kz + rnd.uniform(0, 4)))
            o.rotation_mode = 'QUATERNION'
            blocks.append((o, c, s0, ts, dur, q0))
for o, c, s0, ts, dur, q0 in blocks:
    for f in range(F0, F1 + 1):
        x = (f - ts) / dur
        e = back(x); spin = (1 - ease(x)) * 1.3                  # it swirls in round the axis as it comes
        p = c + Matrix.Rotation(spin, 3, 'Z') @ (s0 - c) * (1 - e)
        o.location = p
        o.rotation_quaternion = q0.slerp(Quaternion(), ease(x))
        sc = ease((f - ts) / 8) * (1 + (CELL / BLK - 1) * ramp(f, 1190, 1199))   # out of nothing; the seams close
        o.scale = (sc,) * 3
        o.keyframe_insert('location', frame=f); o.keyframe_insert('rotation_quaternion', frame=f)
        o.keyframe_insert('scale', frame=f)

# ----------------------------------------------------------------------------------------------- 03 Develop: the slide
RT, TURNS, TZ0, TZ1 = 2.35, 2.0, 0.95, -3.05
TH0 = math.radians(-90)
E = Vector((0, -H, H))                                      # it leaves the cube at the middle of an edge


def helix_track(u):
    a = TH0 + u * TURNS * math.tau
    return Vector((RT * math.cos(a), RT * math.sin(a), TZ0 + (TZ1 - TZ0) * u))


def bez(p0, p1, p2, p3, t):
    return p0 * (1 - t) ** 3 + p1 * 3 * (1 - t) ** 2 * t + p2 * 3 * (1 - t) * t ** 2 + p3 * t ** 3


H0 = helix_track(0.0)
entry = [bez(E, E + Vector((0, -0.7, -0.1)), H0 + Vector((-0.75, 0, 0.12)), H0, i / 60) for i in range(60)]
hel = [helix_track(i / 1400) for i in range(1401)]
slope = (TZ1 - TZ0) / (TURNS * math.tau * RT)
hend = hel[-1]; tan_h = Vector((1, 0, 0))                    # at -90 degrees, going round anticlockwise: +x
LIP = 1.8
lip = [hend + tan_h * s + Vector((0, 0, slope * s + 0.19 * s * s)) for s in [LIP * i / 60 for i in range(1, 61)]]
track_pts = entry + hel + lip

cd = bpy.data.curves.new('SLIDE', 'CURVE'); cd.dimensions = '3D'; cd.twist_mode = 'Z_UP'
sp = cd.splines.new('POLY'); sp.points.add(len(track_pts) - 1)
for i, p in enumerate(track_pts): sp.points[i].co = (p.x, p.y, p.z, 1)
prof = bpy.data.curves.new('SLIDE_PROFILE', 'CURVE'); prof.dimensions = '2D'
pp = prof.splines.new('POLY')
RC_ = 0.14
u_pts = [(-0.2, 0.2), (-RC_, 0.19)] + [(RC_ * math.cos(a), RC_ + RC_ * math.sin(a)) for a in
                                         [math.pi + math.pi * i / 24 for i in range(25)]] + [(RC_, 0.19), (0.2, 0.2)]
pp.points.add(len(u_pts) - 1)
for i, (x, y) in enumerate(u_pts): pp.points[i].co = (x, y, 0, 1)
prof_o = link(bpy.data.objects.new('SLIDE_PROFILE', prof), FX); prof_o.hide_render = True
cd.bevel_mode = 'OBJECT'; cd.bevel_object = prof_o; cd.use_fill_caps = False
cd.bevel_factor_mapping_end = 'SPLINE'
slide = link(bpy.data.objects.new('SLIDE', cd), SHAPES)
sol = slide.modifiers.new('thick', 'SOLIDIFY'); sol.thickness = 0.022; sol.offset = -1.0
gm, nt_g, out_g = mat_nodes('slide gold'); bg = nt_g.nodes.new('ShaderNodeBsdfPrincipled')
bg.inputs['Base Color'].default_value = (*lin('#FFB13B'), 1); bg.inputs['Metallic'].default_value = 1.0
bg.inputs['Roughness'].default_value = 0.2; nt_g.links.new(bg.outputs[0], out_g.inputs['Surface'])
cd.materials.append(gm)


def up_of(t):
    return (Z - t * Z.dot(t)).normalized()


# the ball's road: across the cube's top to the edge, then down the slide's channel (centre 0.1 above its bottom)
REST = Vector((0, 0, H + BALL_R))
road, kinds = [], []
for i in range(40):
    road.append(REST.lerp(E + Z * BALL_R, i / 40)); kinds.append(0)
for i, p in enumerate(track_pts):
    t = (track_pts[min(i + 1, len(track_pts) - 1)] - track_pts[max(i - 1, 0)]).normalized()
    road.append(p + up_of(t) * BALL_R); kinds.append(2 if i >= len(entry) + len(hel) else 1)
acc = [0.0]
for a, b in zip(road, road[1:]): acc.append(acc[-1] + (b - a).length)
L_ROAD = acc[-1]; S_TRACK0 = acc[40]; S_LIP0 = acc[40 + len(entry) + len(hel)]
L_TRACK = L_ROAD - S_TRACK0


def road_at(s):
    s = max(0.0, min(L_ROAD, s))
    lo, hi = 0, len(acc) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if acc[mid] <= s: lo = mid
        else: hi = mid
    t = (s - acc[lo]) / max(1e-9, acc[hi] - acc[lo])
    return road[lo].lerp(road[hi], t), (road[hi] - road[lo]).normalized()


# full throttle: it gathers speed all the way down, and loses a little climbing the lip
T_ROLL, ACC_, DEC_ = 1198, 0.0043, 0.036
roll = {}; s_, v_ = 0.0, 0.0; f = T_ROLL
while s_ < L_ROAD and f < F1:
    roll[f] = s_
    v_ = max(0.25, v_ * 0.8) if s_ >= S_LIP0 else v_ + ACC_
    s_ += v_; f += 1
T_LAUNCH = f
p_prev, _ = road_at(roll[T_LAUNCH - 1]); p_end, t_end = road_at(L_ROAD)
V = t_end * v_
print(f'MAKE: road {L_ROAD:.1f}, slide {L_TRACK:.1f}, launch frame {T_LAUNCH}, speed {v_:.3f}')

# ----------------------------------------------------------------------------------------------- 04 Deliver
G_ = 0.02; DROP = 1.25
NFLY = (V.z + math.sqrt(V.z ** 2 + 2 * G_ * DROP)) / G_
T_LAND = T_LAUNCH + NFLY
LANDING = p_end + Vector((V.x, V.y, 0)) * NFLY + Z * (-DROP)
RING_MAJ, RING_MIN = 0.118, 0.028
SEAT = math.sqrt((BALL_R + RING_MIN) ** 2 - RING_MAJ ** 2)
RC = LANDING - Z * SEAT
print(f'MAKE: flight {NFLY:.1f} frames, lands {T_LAND:.1f} at {tuple(round(x, 2) for x in RC)}')
bpy.ops.mesh.primitive_torus_add(major_radius=RING_MAJ, minor_radius=RING_MIN, major_segments=64, minor_segments=16,
                                 location=RC)
ring = bpy.context.object; ring.name = 'RING'
rm, nt_r, out_r = mat_nodes('ring gold'); br = nt_r.nodes.new('ShaderNodeBsdfPrincipled')
br.inputs['Base Color'].default_value = (*lin('#FFB13B'), 1); br.inputs['Metallic'].default_value = 1.0
br.inputs['Roughness'].default_value = 0.18; br.inputs['Emission Color'].default_value = (*lin('#FFC24A'), 1)
nt_r.links.new(br.outputs[0], out_r.inputs['Surface']); ring.data.materials.append(rm)
into(ring, SHAPES)
TL = int(T_LAND)
anim_input(br, 'Emission Strength', [(F0, 0.0), (TL - 1, 0.0), (TL + 2, 26.0), (TL + 26, 5.0), (F1 - 22, 5.0), (F1, 60.0)])
# the target round the seat: a wider, finer gold ring that lights with it, so the landing reads from afar
bpy.ops.mesh.primitive_torus_add(major_radius=0.62, minor_radius=0.018, major_segments=128, minor_segments=12, location=RC)
halo = bpy.context.object; halo.name = 'RING_HALO'; halo.data.materials.append(rm); into(halo, SHAPES)
for f_, sc_ in ((F0, 1.0), (TL - 30, 1.0)):
    halo.scale = (sc_,) * 3; halo.keyframe_insert('scale', frame=f_)
ring_l = point('RING_LIGHT', RC + Z * 0.35, 0.0, '#FFC24A', radius=0.1)
anim_energy(ring_l, [(F0, 0.0), (TL - 1, 0.0), (TL + 2, 260.0), (TL + 26, 60.0), (F1 - 22, 60.0), (F1, 900.0)])
for k_ in range(2):                                         # the shockwave: two thin rings of light running out
    bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.006, major_segments=128, minor_segments=8,
                                     location=RC + Z * 0.01)
    w_ = bpy.context.object; w_.name = f'SHOCK_{k_}'
    wm, nt_w, out_w = mat_nodes(f'shock {k_}'); ew = nt_w.nodes.new('ShaderNodeEmission')
    ew.inputs['Color'].default_value = (*lin('#FFD98A' if k_ == 0 else '#c4b6ff'), 1)
    tw = nt_w.nodes.new('ShaderNodeBsdfTransparent'); aw = nt_w.nodes.new('ShaderNodeAddShader')   # unlit = gone
    nt_w.links.new(tw.outputs[0], aw.inputs[0]); nt_w.links.new(ew.outputs[0], aw.inputs[1])
    nt_w.links.new(aw.outputs[0], out_w.inputs['Surface']); no_emission_sampling(wm); w_.data.materials.append(wm)
    into(w_, FX); set_vis(w_, diffuse=False, glossy=False, transmission=False, scatter=False, shadow=False)
    t0 = TL + 1 + 7 * k_
    for f in range(F0, F1 + 1):
        x = (f - t0) / 40
        r_ = 0.12 + 7.5 * (1 - (1 - max(0.0, min(1.0, x))) ** 3)
        w_.scale = (r_, r_, 1.0); w_.keyframe_insert('scale', frame=f)
    anim_input(ew, 'Strength', [(F0, 0.0), (t0 - 1, 0.0), (t0 + 1, 30.0), (t0 + 40, 0.0)])
# grains thrown out flat from the ring as it lands
rg = random.Random(3); gp, gv, gs, gb, gt = [], [], [], [], []
for _ in range(900):
    a = rg.uniform(0, math.tau); spd = 0.03 + 0.11 * rg.random() ** 1.5
    vel = Vector((math.cos(a), math.sin(a), rg.gauss(0, 0.12))) * spd
    gv.append(vel); gp.append(RC + vel.normalized() * 0.12 - vel * T_LAND)
    gs.append(0.004 + 0.009 * rg.random() ** 2); gb.append(0.2 + 0.8 * rg.random() ** 2); gt.append(rg.random() * 0.75)
burst = points_object('LAND_GRAINS', gp, {'vel': gv, 'size': gs, 'bright': gb, 'tone': gt}, FX)
gn_instancer(burst, tiny_sphere('GRAIN_src', glow_mat('land grains', DUST_STOPS, 6.0), FX), scale_attr='size',
             drift_attr='vel', drift_rate=1.0)
set_vis(burst, diffuse=False, shadow=False, scatter=False)
for f_, h_ in ((F0, True), (TL, True), (TL + 1, False)):
    burst.hide_render = h_; burst.keyframe_insert('hide_render', frame=f_)

# ----------------------------------------------------------------------------------------------- the ball, frame by frame
HV = Vector((0, 0, 1.85))
ball_at, tan_at = {}, {}
q = Quaternion()
for f in range(F0, F1 + 1):
    t_ = None
    if f <= D1:                                              # Define: up the axis on its helix
        s = def_s(f); p = helix_pt(s); sc = ease((f - F0) / 6)
        t_ = (helix_pt(min(1, s + 0.002)) - helix_pt(max(0, s - 0.002))).normalized()
    elif f <= 1100:
        x = ramp(f, D1, 1100); p = helix_pt(1).lerp(HV, x) + Z * 0.25 * math.sin(math.pi * x); sc = 1
    elif f <= 1180:                                          # Design: it waits above while the blocks come
        p = HV + Z * 0.04 * math.sin((f - 1100) * 0.12); sc = 1
    elif f <= T_ROLL:
        x = (f - 1180) / (T_ROLL - 1180); p = HV.lerp(REST, back(x, 0.6)); sc = 1
    elif f < T_LAUNCH:                                       # Develop: rolling
        p, t_ = road_at(roll[f]); sc = 1
    else:                                                    # Deliver: in the air, into the ring, a bounce, still
        n = f - T_LAUNCH
        if n <= NFLY:
            p = p_end + V * n + Z * (-0.5 * G_ * n * n)
        else:
            m_ = f - T_LAND
            b_ = 0.11 * abs(math.sin(math.pi * min(m_, 9) / 9)) if m_ < 9 else 0.025 * abs(math.sin(math.pi * min(m_ - 9, 5) / 5)) if m_ < 14 else 0
            p = LANDING + Z * b_
        sc = 1
    ball_at[f] = p; tan_at[f] = t_
for f in range(F0, F1 + 1):                                  # it rolls where it rolls
    if f > F0 and T_ROLL <= f <= T_LAUNCH + 1:
        d = ball_at[f] - ball_at[f - 1]
        if d.length > 1e-6:
            ax_ = d.cross(up_of(d.normalized())).normalized() if abs(d.normalized().dot(Z)) < 0.99 else Vector((1, 0, 0))
            q = Quaternion(ax_, -d.length / BALL_R) @ q
    elif f > T_LAUNCH + 1 and f < T_LAND:
        q = Quaternion(Vector((0, 1, 0)), 0.25) @ q
    ball.location = ball_at[f]; ball.rotation_quaternion = q
    ball.scale = (ease((f - F0) / 6),) * 3
    ball.keyframe_insert('location', frame=f); ball.keyframe_insert('rotation_quaternion', frame=f)
    ball.keyframe_insert('scale', frame=f)
    glow.location = ball_at[f] + Z * 0.22; glow.keyframe_insert('location', frame=f)

# the slide builds itself just ahead of the ball, a hot spark at its tip; the coils come up as it reaches them
LEAD = 3.2
bevel_end = {}
for f in range(F0, F1 + 1):
    if f < 1188: e_ = 0.0
    elif f < T_ROLL: e_ = ramp(f, 1188, T_ROLL) * (LEAD / L_TRACK)
    elif f < T_LAUNCH: e_ = min(1.0, (max(0.0, roll[f] - S_TRACK0) + LEAD) / L_TRACK)
    else: e_ = 1.0
    bevel_end[f] = e_
    cd.bevel_factor_end = e_; cd.keyframe_insert('bevel_factor_end', frame=f)
spark = point('SPARK', (0, 0, 0), 0.0, '#FFE2A0', radius=0.02)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.035, segments=16, ring_count=8)
spark_o = bpy.context.object; spark_o.name = 'SPARK_GLOW'
sm, nt_s, out_s = mat_nodes('spark'); es = nt_s.nodes.new('ShaderNodeEmission')
es.inputs['Color'].default_value = (*lin('#FFE9B8'), 1); nt_s.links.new(es.outputs[0], out_s.inputs['Surface'])
no_emission_sampling(sm); spark_o.data.materials.append(sm); into(spark_o, FX)
set_vis(spark_o, diffuse=False, glossy=False, transmission=False, scatter=False, shadow=False)
for f in range(F0, F1 + 1):
    s_tip = S_TRACK0 + bevel_end[f] * L_TRACK
    p_tip, t_tip = road_at(s_tip)
    on = 1.0 if 1188 <= f < T_LAUNCH - 2 and bevel_end[f] < 0.999 else 0.0
    spark_o.location = p_tip - up_of(t_tip) * (BALL_R - 0.06); spark_o.scale = (on,) * 3
    spark.location = p_tip + up_of(t_tip) * 0.15; spark.data.energy = 30.0 * on
    spark_o.keyframe_insert('location', frame=f); spark_o.keyframe_insert('scale', frame=f)
    spark.keyframe_insert('location', frame=f); spark.data.keyframe_insert('energy', frame=f)
coils = []
for k_, u_ in enumerate((0.16, 0.38, 0.6, 0.82)):
    s_c = S_TRACK0 + u_ * L_TRACK
    p_c, t_c = road_at(s_c)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.27, minor_radius=0.024, major_segments=64, minor_segments=12,
                                     location=p_c)
    co = bpy.context.object; co.name = f'COIL_{k_}'
    co.rotation_euler = t_c.to_track_quat('Z', 'Y').to_euler()
    cm, nt_c, out_c = mat_nodes(f'coil {k_}'); bc = nt_c.nodes.new('ShaderNodeBsdfPrincipled')
    bc.inputs['Base Color'].default_value = (*lin('#FFB13B'), 1); bc.inputs['Metallic'].default_value = 1.0
    bc.inputs['Roughness'].default_value = 0.2; bc.inputs['Emission Color'].default_value = (*lin('#FFC24A'), 1)
    nt_c.links.new(bc.outputs[0], out_c.inputs['Surface']); co.data.materials.append(cm); into(co, SHAPES)
    f_up = next(f for f in range(F0, F1 + 1) if S_TRACK0 + bevel_end[f] * L_TRACK >= s_c)
    f_pass = next((f for f in range(T_ROLL, T_LAUNCH) if roll[f] >= s_c), T_LAUNCH)
    for f in range(F0, F1 + 1):
        co.scale = (back((f - f_up) / 10, 1.6),) * 3; co.keyframe_insert('scale', frame=f)
    anim_input(bc, 'Emission Strength', [(F0, 0.0), (f_pass - 1, 0.0), (f_pass + 1, 22.0), (f_pass + 14, 1.5)])

# ----------------------------------------------------------------------------------------------- light
key = area('KEY', (4.5, -6.5, 8.0), (0, 0, -0.5), 6.0, 1900, '#FFF1DE')
rim = area('RIM', (-6.5, 7.0, 4.0), (0, 0, -1.0), 6.0, 1700, '#7a5cff')
fill = area('FILL', (-5.0, -4.5, -5.0), (0, 0, -1.5), 5.0, 420, '#8fa6ff')
low = area('LOW_KEY', (RC.x + 2.5, RC.y - 4.0, RC.z + 3.0), RC, 4.0, 500, '#FFE6C4')    # for the landing

# ----------------------------------------------------------------------------------------------- camera: one take
cam = make_camera('CAM', lens=32)
cam.data.shift_x = -0.11                                     # the subject sits right of centre: the words go left
W1 = Vector((6.4, -7.6, 3.7))
# the whole machine at the end: its bounds (the cube, the slide, the ring), seen from the front and a little above
pts_all = corners + track_pts + [RC]
lo_ = Vector([min(p_[i] for p_ in pts_all) for i in range(3)]); hi_ = Vector([max(p_[i] for p_ in pts_all) for i in range(3)])
mid = (lo_ + hi_) / 2; rad_ = (hi_ - lo_).length / 2
mid = mid.lerp(RC, 0.32)                                   # weighted to the ring: it is lowest and nearest
W2 = mid + Vector((0.75, -1.0, 0.36)).normalized() * rad_ / math.tan(math.radians(17.3)) * 0.92   # fit the height
raw = {}


def orbit_cam(f):
    x = ramp(f, 1092, 1196)
    a = math.atan2(W1.y, W1.x) + math.radians(62) * x
    dist = 9.9 + (8.6 - 9.9) * x; hgt = 3.7 + (2.5 - 3.7) * x
    return Vector((dist * math.cos(a), dist * math.sin(a), hgt)), Vector((0, 0, 0.05 + 0.5 * x)), 5.6


def chase_cam(f):
    p = ball_at[f]
    t = tan_at.get(f) or Vector((0, -1, -0.1)).normalized()
    out = Vector((p.x, p.y, 0)); out = out.normalized() if out.length > 1e-3 else Vector((0, -1, 0))
    return p - t * 1.4 + up_of(t) * 0.36 + out * 0.6, p + t * 1.1 + up_of(t) * 0.08, 2.2


for f in range(F0, F1 + 1):
    p = ball_at[f]
    if f <= 1092:                                            # close on the pen, then back to see the drawing whole
        s = def_s(f); zc = HX_Z0 + (HX_Z1 - HX_Z0) * s
        a = math.radians(-100 + 50 * s); dn = 5.8 - 2.2 * ease((F0 + 10 - f) / 10)   # it rises with the pen
        near = (Vector((dn * math.cos(a), dn * math.sin(a), zc + 1.3)), Vector((0, 0, zc * 0.85)), 3.6)
        x = ramp(f, 1058, 1094)
        far = orbit_cam(1092)
        raw[f] = (near[0].lerp(far[0], x), near[1].lerp(far[1], x), 3.2 + 2.4 * x)
    elif f <= 1190:
        raw[f] = orbit_cam(f)
    elif f < T_LAUNCH:                                       # in behind it as it goes over the edge, then the chase
        o_ = orbit_cam(1190); c_ = chase_cam(max(f, T_ROLL))
        x = ramp(f, 1190, T_ROLL + 14)
        raw[f] = (o_[0].lerp(c_[0], x), o_[1].lerp(c_[1], x), 5.6 + (2.2 - 5.6) * x)
    else:                                                    # it flies: hold, watch it land, then back to the whole
        c_ = chase_cam(T_LAUNCH - 1)
        hold = (c_[0] + Vector((V.x, V.y, 0)) * 6 + Z * 0.6, p.copy(), 2.8)
        x = ramp(f, T_LAND - 4, T_LAND + 46)
        end_t = mid.copy()
        push = ramp(f, F1 - 18, F1)
        w2 = W2.lerp(RC + (W2 - RC) * 0.86, push)
        raw[f] = (hold[0].lerp(w2, x), hold[1].lerp(end_t.lerp(RC, push), x), 2.8 + (6.0 - 2.8) * x)


def smoothed(i, sig=2.5):
    fs = range(max(F0, int(i - 3 * sig)), min(F1, int(i + 3 * sig)) + 1)
    w = [math.exp(-0.5 * ((g - i) / sig) ** 2) for g in fs]
    tw_ = sum(w)
    return (sum((raw[g][0] * wi for g, wi in zip(fs, w)), Vector()) / tw_,
            sum((raw[g][1] * wi for g, wi in zip(fs, w)), Vector()) / tw_,
            sum(raw[g][2] * wi for g, wi in zip(fs, w)) / tw_)


for f in range(F0, F1 + 1):
    loc, tgt, fs_ = smoothed(f, 1.6 if T_ROLL <= f < T_LAUNCH else 3.0)
    cam.location = loc
    cam.rotation_euler = (tgt - loc).to_track_quat('-Z', 'Y').to_euler()
    cam.data.dof.focus_distance = (ball_at[f] - loc).length; cam.data.dof.aperture_fstop = fs_
    cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
    cam.data.dof.keyframe_insert('focus_distance', frame=f); cam.data.dof.keyframe_insert('aperture_fstop', frame=f)

if MODE == 'dry':
    for f in (TL, TL + 20, TL + 40, TL + 55, F1 - 26, F1 - 10, F1):
        scene.frame_set(f)
        v = screen_pos(scene, cam, ball.matrix_world.translation)
        r_ = screen_pos(scene, cam, RC); c_ = screen_pos(scene, cam, Vector((0, 0, 0))); h_ = screen_pos(scene, cam, hel[-1])
        print(f'MAKE FRAME {f}: ball ({v.x:.2f},{1 - v.y:.2f}) ring ({r_.x:.2f},{1 - r_.y:.2f}) cube ({c_.x:.2f},{1 - c_.y:.2f}) slide-end ({h_.x:.2f},{1 - h_.y:.2f})')
    sys.exit(0)

# ----------------------------------------------------------------------------------------------- render
prev = MODE == 'preview'
render_setup(scene, w=960 if prev else 1600, h=540 if prev else 900, samples=20 if prev else 128,
             threshold=0.04 if prev else 0.012, mblur=True)
scene.cycles.transparent_max_bounces = 64
scene.render.image_settings.file_format = 'WEBP'
scene.render.image_settings.quality = 80 if prev else 86
lens(scene, flare=False, fog=0.3, bloom=0.34, diffuse=0.04, vignette=0.5)
os.makedirs(OUT, exist_ok=True)
scene.render.filepath = os.path.join(OUT, 'f_')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'scene_make.blend'), compress=True)
a_, b_ = F0, F1
if os.environ.get('SDC_RANGE'): a_, b_ = (int(x) for x in os.environ['SDC_RANGE'].split(','))
scene.frame_start, scene.frame_end = a_, b_
only = [int(x) for x in os.environ.get('SDC_FRAMES', '').split(',') if x.strip()]
t0 = time.time()
if only:
    for f in only:
        scene.frame_set(f); scene.render.filepath = os.path.join(OUT, f'f_{f:04d}')
        bpy.ops.render.render(write_still=True)
else:
    bpy.ops.render.render(animation=True)
print('MAKE SECONDS', round(time.time() - t0, 1))
