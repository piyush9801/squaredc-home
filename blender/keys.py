"""Four key stills to lock the look before any animation.

blender -b --factory-startup --python keys.py -- <shot> <out.png> [samples] [percent]
  s1  Enter the universe: the yellow square as a real, worn object, a star breaking over its corner
  s3  Gravity: the cube as the warm sun of the SDC system, the shapes on their orbits
  s5  Birth of a world: a planet tiled like the cube, a ring of pixels, the star behind its limb
  s12 The reveal: the orbits settle into the mark around the one glowing shape
"""
import bpy, sys, os, math, random, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib, lib, look
importlib.reload(lib); importlib.reload(look)
from lib import (lin, link, new_collection, import_shape, shape_children, points_object, gn_instancer, tiny_sphere,
                 set_vis, emission_mat, make_camera, look_at, screen_pos, render_setup, mat_nodes)
from look import *
from mathutils import Vector, Euler, Matrix, noise

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
SHOT = argv[0] if argv else 's1'
OUT = os.path.abspath(argv[1] if len(argv) > 1 else '/tmp/sdc_key.png')
SAMPLES = int(argv[2]) if len(argv) > 2 else 160
PCT = int(argv[3]) if len(argv) > 3 else 100

bpy.ops.wm.read_homefile(use_empty=True)
scene = bpy.context.scene
scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
WORLD = new_collection('WORLD'); FX = new_collection('FX'); SHAPES = new_collection('SHAPES'); PLANETS = new_collection('PLANETS')


def at_screen(cam, sx, sy, depth):
    return cam.location + ray_dir(scene, cam, sx, sy) * depth


def into(o, coll):
    for c in list(o.users_collection): c.objects.unlink(o)
    coll.objects.link(o)
    for ch in o.children_recursive:
        for c in list(ch.users_collection): c.objects.unlink(ch)
        coll.objects.link(ch)
    return o


def lights_only(light_obj, coll):
    try: light_obj.light_linking.receiver_collection = coll
    except Exception as e: print('light linking unavailable:', e)


def motes(n, centre, half, seed=3, size=(0.0012, 0.004), strength=(0.2, 5.0), col='#ffe7c4', name='MOTES'):
    rnd = random.Random(seed)
    pts, sz, br = [], [], []
    for _ in range(n):
        pts.append(Vector(centre) + Vector([(rnd.random() * 2 - 1) * h for h in half]))
        br.append(rnd.random() ** 3); sz.append(size[0] + (size[1] - size[0]) * rnd.random() ** 2)
    m = lib.instance_mat(name + '_m', lin(col), strength[0], strength[1], tint_b=lin('#c9b8ff'), glossy=True)
    no_emission_sampling(m)
    inst = tiny_sphere(name + '_inst', m, FX, subdiv=2)
    o = points_object(name, pts, {'size': sz, 'bright': br}, WORLD)
    gn_instancer(o, inst, 'size')
    set_vis(o, diffuse=False, shadow=False, scatter=False)
    return o


def pixels(name, pts, sizes, mat, rots=None):
    """Tiny worn cubes (the system's small bodies and debris) instanced on points."""
    src = crisp_cube(name + '_src', 1.0, 0.06, 3, coll=FX); src.location = (0, 0, -9999)
    src.data.materials.append(mat)
    attrs = {'size': sizes}
    o = points_object(name, pts, attrs, WORLD)
    gn_instancer(o, src, 'size')
    return o


def finish(cam, flare=True, star=None, **lens_kw):
    render_setup(scene, w=1920, h=1080, samples=SAMPLES, threshold=0.01, mblur=False)
    scene.render.resolution_percentage = PCT
    scene.render.image_settings.file_format = 'PNG'; scene.render.image_settings.color_mode = 'RGB'
    sp = (0.5, 0.5)
    if star is not None:
        v = screen_pos(scene, cam, star); sp = (v.x, v.y); print('STAR SCREEN', round(v.x, 3), round(v.y, 3))
    lens(scene, flare=flare, sun_pos=sp, **lens_kw)
    scene.render.filepath = OUT
    t = time.time(); bpy.ops.render.render(write_still=True)
    print('RENDER SECONDS', round(time.time() - t, 1))
    bpy.ops.wm.save_as_mainfile(filepath=OUT.rsplit('.', 1)[0] + '.blend', compress=True)



# ================================================================================================= S1 (sleek)
DUST_STOPS = [(0.0, '#fff1cc'), (0.18, '#FFC94F'), (0.38, '#FFA21F'), (0.6, '#a37ad8'), (0.8, '#6a52f0'), (1.0, '#3a2a9a')]
GOLD_STOPS = [(0.0, '#2a1400'), (0.35, '#c47f00'), (0.6, '#FFC000'), (0.8, '#FFDA4A'), (0.94, '#FFF0B8'), (1.0, '#FFFFFF')]


def shot_s1():
    """Scene 01, reproduced from the supplied colour reference: a luminous lemon-yellow resin cube with a star
    glinting on its far top corner; one dense glowing band of fine golden strands hugging it and crossing in front
    of its lower third, a gap, then a few violet rings; glitter gathered along the golden band; a few orbs; deep
    violet space."""
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
    cube.rotation_euler = Euler((math.radians(8), math.radians(-9), math.radians(40)))
    plane = (math.radians(-6), math.radians(-12), math.radians(8))
    M = Euler(plane).to_matrix()
    front = -100.0
    # ---- the golden band: many fine strands a hair apart, hot on the right and where they cross in front
    for i in range(44):
        f = i / 43
        r = 0.93 + 0.44 * f ** 1.15 + rnd.uniform(-0.006, 0.006)
        span = rnd.uniform(250, 345); start = rnd.uniform(-245, -175)
        c, sg = rnd.uniform(0.5, 0.8), rnd.uniform(0.12, 0.26)
        uf = (front - start) / span
        light_trail(f'GOLD_{i}', *ring_path(r, math.radians(start), math.radians(start + span), plane),
                    (lambda u, c=c, sg=sg, uf=uf: 0.1 + 0.9 * max(math.exp(-((u - c) / sg) ** 2), 0.75 * math.exp(-((u - uf) / 0.13) ** 2))),
                    0.0012 + 0.0016 * rnd.random(), rnd.uniform(3.0, 9.0) * (1 - 0.45 * f), coll=SHAPES, stops=GOLD_STOPS)
    light_band('GOLD_GLOW', *ring_path(1.13, math.radians(-235), math.radians(125), plane),
               (lambda u: 0.2 + 0.8 * max(math.exp(-((u - 0.68) / 0.22) ** 2), 0.8 * math.exp(-((u - (front + 235) / 360) / 0.15) ** 2))),
               0.26, 1.5, coll=SHAPES, stops=GOLD_STOPS)
    # ---- a gap, then a few violet rings further out and one faint pale one
    for j, r in enumerate((1.6, 1.66, 1.95, 2.35)):
        span = rnd.uniform(300, 350); start = rnd.uniform(-250, -190)
        c = rnd.uniform(0.55, 0.78)
        light_trail(f'VIOLET_{j}', *ring_path(r, math.radians(start), math.radians(start + span), plane),
                    (lambda u, c=c: 0.08 + 0.92 * math.exp(-((u - c) / 0.22) ** 2)),
                    0.0011 + 0.0011 * rnd.random(), rnd.uniform(1.4, 2.6), coll=SHAPES, stops=VIOLET_STOPS)
    # ---- ring dust with a natural rhythm: density bands and gaps across the radius (like Saturn's rings), soft
    # spiral wakes around the orbit, clumping noise; every grain a short streak along its orbit, most tiny, a few big.
    def ring_dust(name, n, r_lo, r_hi, bands, gaps, arms, arm_amp, pitch, seed, tone_lo, tone_hi, s_max, bias=None):
        rd = random.Random(seed)
        pts, tans, lens_, wid, br, tone = [], [], [], [], [], []
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
        streaks(name, pts, tans, lens_, wid, br, tone, glow_mat(name + '_m', DUST_STOPS, s_max))

    ring_dust('DUST_IN', 36000, 0.95, 1.55, [(1.0, 0.05, 1.0), (1.1, 0.04, 0.75), (1.22, 0.06, 0.95), (1.38, 0.06, 0.55)],
              [(1.17, 0.012), (1.31, 0.01)], 2, 0.45, 2.6, 71, 0.0, 0.25, 8.0)
    ring_dust('DUST_OUT', 15000, 1.5, 3.7, [(1.72, 0.08, 0.7), (1.98, 0.1, 0.55), (2.3, 0.14, 0.45), (2.9, 0.3, 0.3)],
              [(2.12, 0.02), (2.62, 0.03)], 3, 0.6, 2.2, 73, 0.18, 0.95, 3.2,
              bias=lambda r, dg: 0.45 + 1.4 * math.exp(-(((dg + 60 + 180) % 360 - 180) / 50) ** 2) * math.exp(-(r - 1.5) / 1.8))
    cam = make_camera('CAM', 50)
    az, el, d = math.radians(-10), math.radians(12), 5.3
    cam.location = Vector((d * math.cos(el) * math.sin(az), -d * math.cos(el) * math.cos(az), d * math.sin(el)))
    look_at(cam, (0.06, 0.0, -0.04))
    cam.data.dof.aperture_fstop = 2.8; cam.data.dof.focus_distance = d
    bpy.context.view_layer.update()
    # ---- orbs ride the rings at set intervals, like planets on rails
    gold_orb = worn_material('orb gold', '#FFC21A', metallic=0.0, rough=0.4, coat=0.4, wear=0.1, emit_hex='#FFB21F', emit=0.5)
    vio_orb = worn_material('orb violet', '#6a52f0', metallic=0.0, rough=0.4, coat=0.4, wear=0.1, emit_hex='#7a5cff', emit=0.7)
    def on_ring(r, want_x, want_y):
        # the angle on this ring that lands closest to the wanted screen spot
        best_ = min(range(0, 360, 2), key=lambda dg: (screen_pos(scene, cam, M @ Vector((r * math.cos(math.radians(dg)), r * math.sin(math.radians(dg)), 0))).x - want_x) ** 2 +
                    (screen_pos(scene, cam, M @ Vector((r * math.cos(math.radians(dg)), r * math.sin(math.radians(dg)), 0))).y - want_y) ** 2)
        return M @ Vector((r * math.cos(math.radians(best_)), r * math.sin(math.radians(best_)), 0))
    for r, sx, sy, rad, mat_ in ((1.6, 0.17, 0.4, 0.026, gold_orb), (1.95, 0.12, 0.3, 0.02, vio_orb),
                                 (1.95, 0.83, 0.72, 0.018, vio_orb), (2.35, 0.72, 0.17, 0.028, gold_orb),
                                 (2.48, 0.93, 0.6, 0.022, gold_orb)):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=rad, segments=32, ring_count=16, location=on_ring(r, sx, sy))
        o_ = bpy.context.object; o_.data.materials.append(mat_)
        for pl in o_.data.polygons: pl.use_smooth = True
    # ---- light with intent: the star behind the far top corner is the key (sheen across the top, rim down the
    # right edge); the golden band lights the lower faces from below; the side away from both falls into violet dark
    corners = [cube.matrix_world @ Vector((x, y, z)) for x in (-.44, .44) for y in (-.44, .44) for z in (-.44, .44)]
    best = max(corners, key=lambda c: screen_pos(scene, cam, c).x + 1.4 * screen_pos(scene, cam, c).y)
    sc = screen_pos(scene, cam, best)
    star = at_screen(cam, sc.x - 0.001, sc.y - 0.002, 160.0)
    backlight(cam, star, (0, 0, 0), radius=0.3, disc=1100, sun=10.0, col='#fff6e4', corona=5, corona_size=5)
    to_star = (star - Vector((0, 0, 0))).normalized()
    from designed_light import designed_spot
    designed_spot('TOP_KEY', Vector((0.9, 1.3, 3.4)), (0, 0, 0.25), 1500, kelvin=5200, size_deg=80, cup=(38, 18),
                  hot=(10, 3), cup_k=0.55, hot_k=1.0, amb_k=0.14, shimmer=0.07, radius=0.25, gobo=0.28)   # high, behind-right
    behind = (Vector((0, 0, 0)) - cam.location).normalized() * 0.95 + Vector((0, 0, 0.05))
    bk_ = point('CAPTURE', behind, 140, '#FFC873', radius=0.18); bk_.visible_glossy = False   # light captured: glows through
    area('BACK_SOFT', to_star * 3.2 + Vector((0, 0, 0.35)), (0, 0, 0.1), 2.4, 420, '#FFEFCF')   # rim down the right edge
    for k_ in range(7):        # the band's front arc, where it is hottest, throws warm light up onto the cube
        a = math.radians(front - 54 + 18 * k_)
        bl_ = point(f'BAND_L{k_}', M @ Vector((1.08 * math.cos(a), 1.08 * math.sin(a), -0.12)), 2.2, '#FFD860', radius=0.12)
        bl_.visible_glossy = False
    ds = area('DARK_SIDE', (-3.2, -2.0, 0.6), (0, 0, 0), 3.0, 4, '#6b52d8'); ds.visible_glossy = False
    # a small, close light off the front corner: fades across the front face so its far side drops into shadow
    fc = max(corners, key=lambda c: -(c - cam.location).length + 0.0 * c.z)
    fg = area('FACE_GRAD', fc + (fc - Vector((0, 0, 0))).normalized() * 0.5 + Vector((0.55, 0.2, 0.45)), fc + Vector((0.3, 0.2, 0.2)), 0.35, 10, '#FFE7A0')
    fg.visible_glossy = False    # light only; its disc must not show up as a reflection on the face
    # ---- a faint violet haze along the ring plane
    light_band('VIOLET_HAZE', *ring_path(2.4, math.radians(-240), math.radians(120), plane),
               (lambda u: 0.4 + 0.6 * math.sin(math.pi * u)), 0.7, 0.045, coll=WORLD, stops=VIOLET_STOPS)
    scene.world = sleek_world(glow_dir=(0.6, -0.4, -0.5), base='#12042a', haze='#2c0e58', haze_power=1.3)
    stars(WORLD, FX, n=700, seed=31, max_b=5.0)
    finish(cam, flare=True, star=star, fog=0.32, bloom=0.34, beams=0.06, streak=0.08, ghosts=0.0, burst=0.22, diffuse=0.04,
           vignette=0.5)


# ================================================================================================= S1 editorial
def _ed_cube(size=0.88, rot=(4, -6, 34)):
    cube = crisp_cube('PIXEL', size, 0.02, 6, coll=SHAPES)
    cube.data.materials.append(worn_material('pixel editorial', '#F2BC00', metallic=0.0, rough=0.42, coat=0.35,
                                             coat_rough=0.07, subsurface=0.15, wear=0.6, mottle=0.1, edge_hex='#FFDB6E',
                                             dust_hex='#e6d3a0', bump=0.22, emit_hex='#FFB21F', emit=0.0))
    cube.rotation_euler = Euler([math.radians(v) for v in rot])
    return cube


def _ed_orbit(radius, plane, rnd, strands=3, peak=6.0, hot=0.62, front=None, stops=None, width=0.0013, dust=1400):
    for j in range(strands):
        r = radius + (j - (strands - 1) / 2) * 0.016
        span = rnd.uniform(300, 345); start = rnd.uniform(-240, -190)
        uf = ((front - start) / span) if front is not None else -9
        light_trail(f'ORB_{radius:.2f}_{j}', *ring_path(r, math.radians(start), math.radians(start + span), plane),
                    (lambda u, uf=uf: 0.06 + 0.94 * max(math.exp(-((u - hot) / 0.2) ** 2), 0.6 * math.exp(-((u - uf) / 0.12) ** 2))),
                    width * rnd.uniform(0.8, 1.25), peak * rnd.uniform(0.6, 1.0), coll=SHAPES, stops=stops or GOLD_STOPS)
    if dust:
        M = Euler(plane).to_matrix(); g_pts, g_b, g_s = [], [], []
        for _ in range(dust):
            rr = radius + rnd.gauss(0, 0.05); a = rnd.random() * math.tau
            g_pts.append(M @ Vector((rr * math.cos(a), rr * math.sin(a), rnd.gauss(0, 0.004))))
            g_b.append(rnd.random() ** 3); g_s.append(0.0005 + 0.0008 * rnd.random() ** 2)
        glitter(f'DUST_{radius:.2f}', FX, WORLD, g_pts, g_b, g_s, s_max=5.0,
                stops=(('#5a3a06', 0.0), ('#FFB21F', 0.5), ('#FFE7A6', 0.85), ('#ffffff', 1.0)))


def _ed_cam(lens, az, el, d, target, shift_right=0.0, fstop=2.8, focus_obj=None):
    cam = make_camera('CAM', lens)
    cam.location = Vector((d * math.cos(math.radians(el)) * math.sin(math.radians(az)),
                           -d * math.cos(math.radians(el)) * math.cos(math.radians(az)), d * math.sin(math.radians(el))))
    look_at(cam, target); bpy.context.view_layer.update()
    if shift_right:   # move the subject off-axis: slide the camera sideways along its own right vector
        right = cam.matrix_world.to_3x3() @ Vector((1, 0, 0))
        cam.location += right * shift_right; bpy.context.view_layer.update()
    cam.data.dof.aperture_fstop = fstop
    cam.data.dof.focus_distance = (cam.location - Vector(target)).length if focus_obj is None else focus_obj
    return cam


def _ed_light(key_pos, key_size=2.2, key_power=230, rim_dir=(-0.55, -0.78, -0.3), rim=6.0, kick_pos=(-1.6, 1.9, -0.35)):
    """Still-life light: a big soft key close in (a gradient on every face), a sheen card over the top face,
    a hard rim from behind, and one cool violet kicker that edges the dark side away from the background."""
    area('KEY', key_pos, (0, 0, 0), key_size, key_power, '#FFF0D8')
    card('SHEEN', (-0.35, -0.7, 2.7), (0, 0, 0.3), 1.8, 1.1, 3.2, '#FFF6E6')
    ld = bpy.data.lights.new('RIM', 'SUN'); ld.energy = rim; ld.angle = math.radians(1.0); ld.color = lin('#FFD9A0')
    r_ = link(bpy.data.objects.new('RIM', ld)); r_.rotation_euler = Vector(rim_dir).to_track_quat('-Z', 'Y').to_euler()
    k_ = area('KICK', kick_pos, (0, 0, 0), 0.9, 70, '#8f7cff'); k_.visible_glossy = False


def _ed_finish(cam, glow_dir=(0.7, 1.0, 0.6)):
    scene.world = sleek_world(glow_dir=glow_dir, base='#07040d', haze='#241638', haze_power=2.6)
    stars(WORLD, FX, n=500, seed=37, max_b=3.0, size_k=0.8)
    finish(cam, flare=False, fog=0.16, bloom=0.14, vignette=0.62)


def shot_e1():
    """Editorial A, still life: the cube on the right third, one hairline orbit, a single Rembrandt key from the
    upper left and nothing filling the dark side; the left half is empty for the headline."""
    rnd = random.Random(3)
    cube = _ed_cube()
    plane = (math.radians(-8), math.radians(-10), math.radians(6))
    _ed_orbit(1.02, plane, rnd, strands=3, peak=7.0, front=-104.0)
    _ed_orbit(1.75, plane, rnd, strands=1, peak=2.2, stops=VIOLET_STOPS, dust=0)
    _ed_light((-1.8, -1.5, 2.0))
    cam = _ed_cam(85, -16, 8, 9.2, (0, 0, -0.02), shift_right=-0.85, fstop=2.8)
    _ed_finish(cam, glow_dir=(0.8, 1.0, 0.5))


def shot_e2():
    """Editorial B, the mark: a small cube dead centre in a field of dark, one wide orbit swooping through it
    (the Saturn-ring move), ~70% empty."""
    rnd = random.Random(5)
    cube = _ed_cube(rot=(10, -8, 40))
    plane = (math.radians(-17), math.radians(-14), math.radians(4))
    _ed_orbit(2.1, plane, rnd, strands=3, peak=8.0, front=-100.0, dust=2200)
    _ed_light((-1.6, -1.8, 2.2), rim_dir=(-0.5, -0.8, -0.35))
    cam = _ed_cam(85, -10, 9, 17.0, (0, 0, 0.0), fstop=4.0)
    _ed_finish(cam, glow_dir=(0.0, 1.0, 0.7))


def shot_e3():
    """Editorial C, Rembrandt crop: the cube large and bleeding off the right edge, lit hard from the upper left,
    its far side dissolving into black; one orbit arc sweeps out across the lower left and fades."""
    rnd = random.Random(9)
    cube = _ed_cube(rot=(2, -4, 28))
    plane = (math.radians(-6), math.radians(-8), math.radians(10))
    _ed_orbit(1.08, plane, rnd, strands=4, peak=7.5, front=-110.0, dust=1800)
    _ed_light((-1.9, -1.9, 1.9), key_size=1.6, key_power=200, rim_dir=(-0.6, -0.7, -0.4), rim=4.0)
    cam = _ed_cam(85, -20, 4, 6.4, (0, 0, 0.0), shift_right=-1.15, fstop=2.2)
    _ed_finish(cam, glow_dir=(-0.6, 1.0, 0.7))


# ================================================================================================= S1 (star)
def shot_s1star():
    cube = crisp_cube('PIXEL', 0.88, 0.02, 5, coll=SHAPES)
    cube.data.materials.append(pixel_paint())
    cube.rotation_euler = Euler((0, 0, math.radians(39)))
    cam = make_camera('CAM', 50)
    el = math.radians(13); d = 3.72
    cam.location = Vector((0.0, -d * math.cos(el), d * math.sin(el)))
    look_at(cam, (0.05, 0.0, 0.03))
    cam.data.dof.aperture_fstop = 8.0; cam.data.dof.focus_distance = d
    bpy.context.view_layer.update()
    # the star sits just inside the cube's upper-right silhouette corner, so it is half eclipsed
    corners = [cube.matrix_world @ Vector((x, y, z)) for x in (-.44, .44) for y in (-.44, .44) for z in (-.44, .44)]
    best = max(corners, key=lambda c: screen_pos(scene, cam, c).x + 0.8 * screen_pos(scene, cam, c).y)
    sc = screen_pos(scene, cam, best)
    star = at_screen(cam, sc.x - 0.006, sc.y - 0.005, 140.0)
    backlight(cam, star, (0, 0, 0), radius=1.05, disc=700, sun=9.0, corona=26, corona_size=12)
    area('KEY', (-3.0, -2.3, 2.7), (0, 0, 0), 3.0, 170, '#FFE7C4')
    area('FILL', (2.7, -2.7, 0.2), (0, 0, 0), 2.5, 30, '#9d8cff')
    card('CARD_L', (-2.9, 0.6, 0.35), (0, 0, 0), 3.4, 3.4, 12.0, '#FFF0DA')
    card('CARD_R', (2.9, -0.6, 0.35), (0, 0, 0), 3.0, 3.0, 4.0, '#FFE8C8')
    card('CARD_B', (0.0, 3.4, 0.75), (0, 0, 0), 4.2, 1.4, 1.2, '#FFD98F')
    scene.world = space_world(band_through(scene, cam, (0.27, 1.02), (-0.02, 0.16)), band_gain=0.9, violet=0.8, width=62.0)
    stars(WORLD, FX)
    motes(220, (0, 0.3, 0), (1.8, 1.6, 1.0), seed=5)
    finish(cam, flare=True, star=star, beams=0.32, ghosts=0.09)



# ================================================================================================= S1 (black-hole light)
def glow_mat(name, stops, s_max, s_min=0.0):
    """Emission coloured by a per-point `tone` (0..1 ramp) and scaled by a per-point `bright`."""
    m, nt, out = mat_nodes(name); N = nt.nodes; L = nt.links
    at = N.new('ShaderNodeAttribute'); at.attribute_type = 'INSTANCER'; at.attribute_name = 'bright'
    tt = N.new('ShaderNodeAttribute'); tt.attribute_type = 'INSTANCER'; tt.attribute_name = 'tone'
    mr = N.new('ShaderNodeMapRange'); mr.inputs['To Min'].default_value = s_min; mr.inputs['To Max'].default_value = s_max
    L.new(at.outputs['Fac'], mr.inputs['Value'])
    cr = N.new('ShaderNodeValToRGB'); r = cr.color_ramp
    r.elements[0].position, r.elements[0].color = stops[0][0], (*lin(stops[0][1]), 1)
    r.elements[1].position, r.elements[1].color = stops[-1][0], (*lin(stops[-1][1]), 1)
    for p_, c in stops[1:-1]:
        e = r.elements.new(p_); e.color = (*lin(c), 1)
    L.new(tt.outputs['Fac'], cr.inputs['Fac'])
    em = N.new('ShaderNodeEmission'); L.new(cr.outputs['Color'], em.inputs['Color']); L.new(mr.outputs['Result'], em.inputs['Strength'])
    L.new(em.outputs[0], out.inputs['Surface'])
    no_emission_sampling(m)
    return m


def streaks(name, pts, tans, lens_, widths, bright, tone, mat):
    """Short glowing streaks laid along a direction (orbital motion read as light trails)."""
    rots, scl = [], []
    for p_, t_, l_, w_ in zip(pts, tans, lens_, widths):
        z = Vector(t_).normalized(); x = z.orthogonal().normalized(); y = z.cross(x)
        rots.append(Matrix((x, y, z)).transposed().to_euler()); scl.append((w_, w_, l_))
    src = tiny_sphere(name + '_src', mat, FX, subdiv=2)
    o = points_object(name, pts, {'scl': scl, 'rot': rots, 'bright': bright, 'tone': tone}, WORLD)
    gn_instancer(o, src, scale_vec_attr='scl', rot_attr='rot')
    set_vis(o, diffuse=False, shadow=False, scatter=False)
    return o


DISK_STOPS = [(0.0, '#fff4dc'), (0.12, '#ffd98a'), (0.3, '#f6a93a'), (0.55, '#a57a6a'), (0.8, '#55608e'), (1.0, '#2f3560')]


def squircle(a, b, t, p=3.2):
    c, s_ = math.cos(t), math.sin(t)
    return (a * math.copysign(abs(c) ** (2 / p), c), b * math.copysign(abs(s_) ** (2 / p), s_))


def shot_s1bh():
    """Scene 01: the yellow square at the centre of an edge-on disk of light. Its far side bends up over the
    top in fine strands, a hidden star behind the cube rims its edges, the cube itself stays dark gold.
    Proportions follow the reference: cube ~10% of frame width, arcs ~25%, a razor-thin disk line."""
    rnd = random.Random(41)
    cube = crisp_cube('PIXEL', 0.88, 0.022, 5, coll=SHAPES)
    cube.data.materials.append(pixel_paint())
    cube.rotation_euler = Euler((math.radians(14), math.radians(-9), math.radians(30)))
    disk_mat = glow_mat('disk glow', DISK_STOPS, 40.0)
    arc_mat = glow_mat('arc glow', DISK_STOPS, 22.0)
    spark_mat = glow_mat('spark glow', [(0.0, '#fff6e6'), (1.0, '#cfe0ff')], 90.0)
    # ---- the disk: dense and hot at the centre, thinning and cooling outward; streaks follow the orbit
    pts, tans, lens_, wid, br, tone = [], [], [], [], [], []
    r_in, r_out, k = 0.62, 9.0, -0.5
    for _ in range(60000):
        u = rnd.random(); r = (r_in ** k + u * (r_out ** k - r_in ** k)) ** (1 / k)
        th = rnd.random() * math.tau
        h = 0.0008 + 0.0028 * r
        pts.append(Vector((r * math.cos(th), r * math.sin(th), rnd.gauss(0, h))))
        tans.append((-math.sin(th), math.cos(th), 0.0))
        lens_.append((0.01 + 0.05 * rnd.random()) * min(r, 2.0))
        wid.append(0.0014 + 0.0005 * r)
        br.append(min(1.0, (r_in / r) ** 1.5 * (0.2 + 0.8 * rnd.random() ** 2)))
        tone.append(min(1.0, max(0.0, (r - r_in) / 5.5) ** 0.6))
    streaks('DISK', pts, tans, lens_, wid, br, tone, disk_mat)
    # glints scattered through the disk
    pts, tans, lens_, wid, br, tone = [], [], [], [], [], []
    for _ in range(3500):
        r = r_in + rnd.expovariate(1 / 2.2); th = rnd.random() * math.tau
        pts.append(Vector((r * math.cos(th), r * math.sin(th), rnd.gauss(0, 0.002 + 0.003 * r))))
        tans.append((-math.sin(th), math.cos(th), 0.0)); lens_.append(0.006); wid.append(0.004 + 0.003 * rnd.random())
        br.append(rnd.random() ** 3); tone.append(rnd.random())
    streaks('GLINTS', pts, tans, lens_, wid, br, tone, spark_mat)
    # ---- the far side of the disk bent up over the top as separate strands; one faint image underneath
    pts, tans, lens_, wid, br, tone = [], [], [], [], [], []
    bands = 24
    for b_ in range(bands):
        f = b_ / (bands - 1)
        a = 0.66 + 0.6 * f ** 1.1; bb = 0.62 + 0.7 * f ** 1.0
        gain = rnd.uniform(0.25, 1.0) * (1 - f) ** 1.2
        for _ in range(int(700 * (1 - 0.45 * f))):
            t = rnd.uniform(0.0, math.pi)
            x, z = squircle(a, bb, t, 2.4)
            jit = 1 + rnd.gauss(0, 0.0025)
            x2, z2 = squircle(a, bb, t + 0.01, 2.4)
            pts.append(Vector((x * jit, 0.6, z * jit))); tans.append((x2 - x, 0.0, z2 - z))
            lens_.append(0.1 + 0.25 * rnd.random()); wid.append(0.0014)
            br.append(gain * (0.35 + 0.65 * math.sin(t) ** 0.5) * (0.3 + 0.7 * rnd.random()))
            tone.append(0.04 + 0.4 * f)
    for _ in range(900):
        t = rnd.uniform(math.pi, math.tau)
        x, z = squircle(0.68, 0.5, t, 2.4); x2, z2 = squircle(0.68, 0.5, t + 0.01, 2.4)
        pts.append(Vector((x * (1 + rnd.gauss(0, 0.003)), 0.6, z * (1 + rnd.gauss(0, 0.003)))))
        tans.append((x2 - x, 0.0, z2 - z)); lens_.append(0.08 + 0.18 * rnd.random()); wid.append(0.0014)
        br.append(0.45 * (0.3 + 0.7 * rnd.random())); tone.append(0.05)
    streaks('ARCS', pts, tans, lens_, wid, br, tone, arc_mat)
    cam = make_camera('CAM', 50)
    el = math.radians(4.0); d = 13.0
    cam.location = Vector((0.0, -d * math.cos(el), d * math.sin(el)))
    look_at(cam, (0.0, 0.0, 0.18))
    cam.data.dof.aperture_fstop = 16; cam.data.dof.focus_distance = d
    bpy.context.view_layer.update()
    # ---- a star hidden right behind the cube: its corona halos the silhouette, its lamp rims the edges
    star = cam.location + (Vector((0, 0, 0.05)) - cam.location).normalized() * (d + 3.0)
    backlight(cam, star, (0, 0, 0), radius=0.25, disc=600, sun=7.0, col='#ffdca0', corona=14, corona_size=11)
    for i in range(10):
        a = i / 10 * math.tau
        point(f'DISK_L{i}', (1.4 * math.cos(a), 1.4 * math.sin(a), 0.0), 7, '#FFC66B', radius=0.4)
    area('FRONT', (0.0, -7.0, 1.2), (0, 0, 0), 4.0, 9, '#b9a3ff')
    scene.world = space_world(band_through(scene, cam, (0.0, 0.8), (1.0, 0.95)), band_gain=0.1, width=60.0)
    stars(WORLD, FX, n=2600, seed=29, max_b=9.0)
    finish(cam, flare=True, star=None, fog=0.55, bloom=0.32, beams=0.0, streak=0.12, ghosts=0.0, burst=0.0)

# ================================================================================================= S3
ORB = [  # radius, colour, strength, tilt (x, y in degrees)
    (1.40, '#FFB52D', 2.4, (1.5, -1.0)), (2.10, '#8f7cff', 2.0, (-1.0, 2.0)),
    (2.85, '#FFB52D', 2.0, (2.5, 1.0)), (3.60, '#7389ff', 1.7, (-2.0, -1.5)),
]
DRY = os.environ.get('SDC_DRY') == '1'


def on_orbit(k, ang_deg, lift=0.0):
    r, _, _, (tx, ty) = ORB[k]
    a = math.radians(ang_deg)
    p = Vector((r * math.cos(a), r * math.sin(a), lift))
    return Euler((math.radians(tx), math.radians(ty), 0)).to_matrix() @ p


def glass(name, tint, absorb, density, rough=0.03, frost=0.0):
    return worn_material(name, tint, metallic=0.0, rough=rough + frost, transmission=1.0, ior=1.47, wear=0.6,
                         mottle=0.0, dust_hex='#ece6f6', bump=0.15, absorb_hex=absorb, absorb=density)


def ring_round(name, obj, radius, col, tilt, strength=3.0):
    bpy.ops.mesh.primitive_torus_add(major_radius=radius, minor_radius=0.0045, major_segments=160, minor_segments=8,
                                     location=obj.location)
    t = bpy.context.object; t.name = name; t.rotation_euler = Euler(tilt)
    m = emission_mat(name + '_m', lin(col), strength); no_emission_sampling(m)
    t.data.materials.append(m)
    set_vis(t, diffuse=False, shadow=False, scatter=False)
    return into(t, SHAPES)


def shot_s3():
    """Scene 03, sleek: the yellow square glowing as the sun of the system; every orbit a few fine light trails
    (gold, violet, gold, violet) with glitter along it; the library shapes lit from the centre with violet rims;
    dark planets with thin rims framing it; deep violet space."""
    rnd = random.Random(53)
    sun = crisp_cube('PIXEL_SUN', 1.1, 0.03, 6, coll=SHAPES)
    sun.data.materials.append(pixel_satin('pixel sun', emit=0.9))
    sun.rotation_euler = Euler((math.radians(8), math.radians(-6), math.radians(36)))
    sun.visible_shadow = False
    s_light = point('SUN_SHAPES', (0, 0, 0), 950, '#FFB247', radius=0.4)
    cols = [TRAIL_STOPS, VIOLET_STOPS, TRAIL_STOPS, VIOLET_STOPS]
    M_of = lambda k: Euler((math.radians(ORB[k][3][0]), math.radians(ORB[k][3][1]), 0)).to_matrix()
    for k, (r, _c, _s, (tx, ty)) in enumerate(ORB):
        orbit_trails(f'ORBIT_{k}', r, (math.radians(tx), math.radians(ty), 0), cols[k], 7.5 - 1.2 * k, rnd,
                     n=3, width=0.0026 + 0.0006 * k, coll=SHAPES, front_deg=-92.0)
        # glitter along the orbit
        g_pts, g_b, g_s = [], [], []
        for _ in range(1500):
            rr = r + rnd.gauss(0, 0.05 + 0.015 * k); a = rnd.random() * math.tau
            g_pts.append(M_of(k) @ Vector((rr * math.cos(a), rr * math.sin(a), rnd.gauss(0, 0.012))))
            g_b.append(rnd.random() ** 3); g_s.append(0.0018 + 0.003 * rnd.random() ** 2)
        st = (('#6a3a06', 0.0), ('#FFB21F', 0.45), ('#FFE7A6', 0.8), ('#ffffff', 1.0)) if k % 2 == 0 else \
             (('#1c0d55', 0.0), ('#6a52f0', 0.45), ('#c8bcff', 0.85), ('#ffffff', 1.0))
        glitter(f'GLIT_{k}', FX, WORLD, g_pts, g_b, g_s, s_max=8.0, stops=st)

    def put(key, k, ang, scale, name=None, lift=0.0, rot=None):
        o = import_shape(key, name or f'{key}_{k}_{ang}')
        o.location = on_orbit(k, ang, lift); o.scale = (scale,) * 3
        rr_ = random.Random(hash(name or key) & 0xffff)
        o.rotation_euler = rot or Euler((rr_.uniform(-.5, .5), rr_.uniform(-.5, .5), rr_.uniform(0, 6.28)))
        into(o, SHAPES)
        for ch in shape_children(o):
            for sl in ch.material_slots: add_wear(sl.material, 0.8)
        return o

    def halo(name, obj, radius, stops, tilt, peak=5.0):
        pts, nrm = ring_path(radius, math.radians(-200), math.radians(140), tilt, centre=obj.location)
        light_trail(name, pts, nrm, (lambda u: 0.15 + 0.85 * math.exp(-((u - 0.62) / 0.2) ** 2)), 0.0022, peak,
                    coll=SHAPES, stops=stops)

    put('octa', 0, 328, 0.27)
    pc = crisp_cube('gold_small', 0.16, 0.012, 3, coll=SHAPES); pc.data.materials.append(pixel_satin('gold small', 0.2))
    pc.location = on_orbit(0, 150); pc.rotation_euler = Euler((0.5, 0.3, 0.8))
    put('arch', 1, 38, 0.33)
    put('sphere', 1, 200, 0.27)
    sand = worn_material('sand ceramic', '#EFE6D6', rough=0.42, coat=0.2, wear=1.0, mottle=0.06)
    for k, ang, sc_ in ((1, 296, 0.12), (3, 112, 0.11), (2, 338, 0.1), (0, 238, 0.09)):
        c = crisp_cube(f'sand_{k}_{ang}', sc_, 0.01, 3, coll=SHAPES); c.data.materials.append(sand)
        c.location = on_orbit(k, ang); c.rotation_euler = Euler((ang * 0.03, 0.4, ang * 0.02))
    resin = worn_material('pink resin', '#F4A9E8', rough=0.3, coat=0.45, coat_rough=0.08, transmission=0.35,
                          subsurface=1.0, wear=0.7, mottle=0.04, dust_hex='#f3e6f1', bump=0.2)
    try: resin.node_tree.nodes['Principled BSDF'].inputs['Subsurface Radius'].default_value = (1.0, 0.45, 0.85)
    except Exception: pass
    bc = put('cube', 2, 128, 0.4, 'glass_blue_a')
    halo('halo_blue_a', bc, 0.42, VIOLET_STOPS, (math.radians(70), math.radians(18), 0))
    pk = crisp_cube('pink_a', 0.42, 0.03, 4, coll=SHAPES); pk.data.materials.append(resin)
    pk.location = on_orbit(2, 56); pk.rotation_euler = Euler((0.35, -0.2, 0.7))
    halo('halo_pink_a', pk, 0.44, TRAIL_STOPS, (math.radians(74), math.radians(-14), 0))
    put('torus', 2, 232, 0.2)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.09, segments=64, ring_count=32, location=on_orbit(2, 302))
    bs = bpy.context.object; bs.name = 'blue_small'
    for p in bs.data.polygons: p.use_smooth = True
    bs.data.materials.append(worn_material('sapphire enamel', '#2546d8', metallic=0.1, rough=0.18, coat=0.8, wear=0.7))
    into(bs, SHAPES)
    put('sphere', 3, 352, 0.31, 'sphere_b')
    put('cone', 3, 166, 0.27)
    put('dome', 3, 266, 0.24)
    put('cube', 3, 314, 0.33, 'glass_blue_b')
    pk2 = crisp_cube('pink_b', 0.36, 0.03, 4, coll=SHAPES); pk2.data.materials.append(resin)
    pk2.location = on_orbit(3, 214); pk2.rotation_euler = Euler((-0.3, 0.25, 0.4))
    halo('halo_pink_b', pk2, 0.38, VIOLET_STOPS, (math.radians(66), math.radians(20), 0))
    # debris: a thin disc of pixels round the sun
    gold = pixel_satin('gold debris', 0.25)
    pts, sz = [], []
    for _ in range(260):
        r = rnd.uniform(0.84, 1.25); a = rnd.uniform(0, math.tau)
        pts.append(Vector((r * math.cos(a), r * math.sin(a), rnd.gauss(0, 0.025)))); sz.append(0.008 + 0.026 * rnd.random() ** 3)
    deb = pixels('DEBRIS', pts, sz, gold); into(deb, SHAPES)
    motes(420, (0, 0, 0), (1.4, 1.4, 0.1), seed=8, size=(0.002, 0.006), strength=(0.5, 9.0), col='#ffcf7a', name='SUNDUST')
    cam = make_camera('CAM', 38)
    el = math.radians(27); d = 9.0
    cam.location = Vector((0.3, -d * math.cos(el), d * math.sin(el)))
    look_at(cam, (0.1, 0.15, -0.55))
    cam.data.dof.aperture_fstop = 11; cam.data.dof.focus_distance = d
    bpy.context.view_layer.update()
    key = area('KEY', (-5, -4, 6), (0, 0, 0), 5, 380, '#FFD9A0')
    rim = area('RIM', (1, 7, 3.5), (0, 0, 0), 6, 1400, '#6a5cff')
    for L_ in (s_light, key, rim): lights_only(L_, SHAPES)
    card('CARD_TOP', (0, -2, 7), (0, 0, 0), 9, 5, 1.0, '#efe6ff')
    card('CARD_BACK', (0, 15, 2.5), (0, 0, 0), 26, 12, 2.0, '#7d6bff')
    # dark worlds with a thin lit rim
    p_light = point('SUN_PLANETS', (0, 0, 0), 500, '#FFC27A', radius=0.6)
    lights_only(p_light, PLANETS)
    pal_a = ('#07040e', '#110a22', '#1e1238', '#2c1c4e', '#3e2a66')
    pal_b = ('#06030c', '#0f0920', '#1b1034', '#2a1a4a')
    planet('P_BIG', at_screen(cam, -0.05, -0.14, 14.0), 2.6, (0, 0, 0), pal_a, 7.0, 0.3, '#ffb36b', 9.0, PLANETS, atmo_pow=7.0)
    planet('P_MED', at_screen(cam, 0.975, 0.1, 17.0), 1.0, (0, 0, 0), pal_b, 5.0, 1.7, '#b9a2ff', 7.0, PLANETS, atmo_pow=7.0)
    planet('P_S1', at_screen(cam, 0.09, 0.88, 32.0), 0.5, (0, 0, 0), pal_b, 4.0, 2.9, '#c9a2ff', 5.0, PLANETS, atmo_pow=6.0)
    planet('P_S2', at_screen(cam, 0.87, 0.84, 30.0), 0.36, (0, 0, 0), pal_a, 4.0, 4.1, '#ffc27a', 5.0, PLANETS, atmo_pow=6.0)
    if DRY: return
    scene.world = sleek_world(glow_dir=(0.5, 1.0, 0.25), base='#070210', haze='#1c0a36', haze_power=1.8)
    stars(WORLD, FX, n=1400, seed=13, max_b=6.0)
    finish(cam, flare=False, fog=0.5, bloom=0.32)


# ================================================================================================= S5
def tile_planet(R=3.0, n=26, seed=5):
    rnd = random.Random(seed)
    faces = []
    for ax in range(3):
        for sgn in (1, -1):
            nrm = Vector([0, 0, 0]); nrm[ax] = sgn
            u = Vector([0, 0, 0]); u[(ax + 1) % 3] = 1
            faces.append((nrm, u, nrm.cross(u)))
    pts, rots, scl, tone = [], [], [], []
    for nrm, u, v in faces:
        for i in range(n):
            for j in range(n):
                a = -1 + (2 * i + 1) / n; b = -1 + (2 * j + 1) / n
                dv = (nrm + u * a + v * b).normalized()
                x = (u - dv * u.dot(dv)).normalized(); y = dv.cross(x)
                w = ((nrm + u * (a + 1 / n) + v * b).normalized() - (nrm + u * (a - 1 / n) + v * b).normalized()).length * R
                hh = ((nrm + u * a + v * (b + 1 / n)).normalized() - (nrm + u * a + v * (b - 1 / n)).normalized()).length * R
                nz = noise.noise(dv * 1.6 + Vector((3.1, 0.7, 1.9)))
                rise = max(0.0, nz) * 0.9 + (rnd.uniform(0.05, 0.25) if rnd.random() < 0.025 else 0.0)
                h = 0.07 + rise * 0.35
                pts.append(dv * (R + h / 2 - 0.04)); rots.append(Matrix((x, y, dv)).transposed().to_euler())
                scl.append((w * 0.9, hh * 0.9, h))
                q = rnd.random()
                tone.append(0.9 if q < 0.03 else 0.7 if q < 0.06 else 0.5 if q < 0.12 else 0.3 if q < 0.5 else 0.1)
    src = crisp_cube('tile_src', 1.0, 0.07, 3, coll=FX); src.location = (0, 0, -9999)
    m, nt, out = mat_nodes('planet tiles'); N = nt.nodes; L = nt.links
    b = N.new('ShaderNodeBsdfPrincipled')
    at = N.new('ShaderNodeAttribute'); at.attribute_type = 'INSTANCER'; at.attribute_name = 'tone'
    cr = N.new('ShaderNodeValToRGB'); cr.color_ramp.interpolation = 'CONSTANT'; r = cr.color_ramp
    r.elements[0].position = 0.0; r.elements[0].color = (*lin('#141f8a'), 1)           # deep blue (most)
    r.elements[1].position = 0.8; r.elements[1].color = (*lin('#F0A800'), 1)          # yellow
    for p, c in ((0.2, '#24157a'), (0.4, '#1d36c9'), (0.6, '#e9dfcc'), (0.65, '#F66FD6')):
        e = r.elements.new(p); e.color = (*lin(c), 1)
    L.new(at.outputs['Fac'], cr.inputs['Fac'])
    wg = N.new('ShaderNodeGroup'); wg.node_tree = wear_group(); wg.inputs['Scale'].default_value = 0.6
    oi = N.new('ShaderNodeObjectInfo')
    jit = N.new('ShaderNodeMapRange'); jit.inputs['To Min'].default_value = 0.8; jit.inputs['To Max'].default_value = 1.15
    L.new(oi.outputs['Random'], jit.inputs['Value'])
    mul = N.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs['Factor'].default_value = 1.0
    L.new(cr.outputs['Color'], mul.inputs['A'])
    cc = N.new('ShaderNodeCombineColor')
    for i in range(3): L.new(jit.outputs['Result'], cc.inputs[i])
    L.new(cc.outputs[0], mul.inputs['B']); L.new(mul.outputs['Result'], b.inputs['Base Color'])
    rr = N.new('ShaderNodeMath'); rr.operation = 'MULTIPLY_ADD'; rr.use_clamp = True
    L.new(wg.outputs['Rough'], rr.inputs[0]); rr.inputs[1].default_value = 1.0; rr.inputs[2].default_value = 0.3
    L.new(rr.outputs[0], b.inputs['Roughness'])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.3; bp.inputs['Distance'].default_value = 0.0006
    L.new(wg.outputs['Height'], bp.inputs['Height']); L.new(bp.outputs['Normal'], b.inputs['Normal'])
    b.inputs['Metallic'].default_value = 0.55; b.inputs['Coat Weight'].default_value = 0.5; b.inputs['Coat Roughness'].default_value = 0.06
    L.new(b.outputs[0], out.inputs['Surface'])
    src.data.materials.append(m)
    o = points_object('PLANET', pts, {'scl': scl, 'rot': rots, 'tone': tone}, WORLD)
    gn_instancer(o, src, scale_vec_attr='scl', rot_attr='rot')
    bpy.ops.mesh.primitive_uv_sphere_add(radius=R - 0.08, segments=96, ring_count=48)
    core = bpy.context.object; core.name = 'CORE'
    for p in core.data.polygons: p.use_smooth = True
    core.data.materials.append(emission_mat('core', lin('#FFB52D'), 7.0)); core.visible_shadow = False
    return o


def pixel_ring(R, tilt, n_cubes=7000, n_dust=14000, seed=8):
    rnd = random.Random(seed)
    bands = [(1.42, 1.58, 0.16), (1.64, 2.02, 0.44), (2.1, 2.16, 0.05), (2.24, 2.58, 0.27), (2.66, 2.74, 0.08)]
    tot = sum(b[2] for b in bands)

    def sample():
        x = rnd.random() * tot
        for lo, hi, w in bands:
            if x < w: break
            x -= w
        rr = R * (lo + (hi - lo) * rnd.random()); a = rnd.random() * math.tau
        return Vector((rr * math.cos(a), rr * math.sin(a), rnd.gauss(0, 0.012)))
    pts = [sample() for _ in range(n_cubes)]
    sz = [0.008 + 0.034 * rnd.random() ** 3 for _ in pts]
    gold = pixel_paint('ring gold')
    o = pixels('RING_PIXELS', pts, sz, gold); o.rotation_euler = Euler(tilt)
    dpts = [sample() for _ in range(n_dust)]
    m = lib.instance_mat('ring_dust_m', lin('#f3e2c2'), 0.1, 4.5, tint_b=lin('#ffb24a'), glossy=True)
    no_emission_sampling(m)
    inst = tiny_sphere('ring_dust_inst', m, FX, subdiv=1)
    d = points_object('RING_DUST', dpts, {'size': [0.004 + 0.008 * rnd.random() for _ in dpts],
                                          'bright': [rnd.random() ** 2 for _ in dpts]}, WORLD)
    gn_instancer(d, inst, 'size'); d.rotation_euler = Euler(tilt)
    set_vis(d, diffuse=False, scatter=False)


def burst(n=900, seed=21):
    """Energy leaving the creation point: short radial streaks, brighter and denser near the world."""
    rnd = random.Random(seed)
    pts, rots, scl, br = [], [], [], []
    for _ in range(n):
        v = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 0.55))).normalized()
        dist = 3.6 + rnd.expovariate(1 / 2.6)
        pts.append(v * dist)
        z = v; x = z.orthogonal().normalized(); y = z.cross(x)
        rots.append(Matrix((x, y, z)).transposed().to_euler())
        L_ = 0.08 + 0.5 * rnd.random() * min(1.0, dist / 6)
        scl.append((0.006, 0.006, L_)); br.append(rnd.random() ** 2 * math.exp(-(dist - 3.6) / 5))
    m = lib.instance_mat('burst_m', lin('#ffe2b0'), 0.5, 26.0, tint_b=lin('#ff9c3a'))
    no_emission_sampling(m)
    src = tiny_sphere('burst_src', m, FX, subdiv=2)
    o = points_object('BURST', pts, {'scl': scl, 'rot': rots, 'bright': br}, WORLD)
    gn_instancer(o, src, scale_vec_attr='scl', rot_attr='rot')
    set_vis(o, diffuse=False, shadow=False, scatter=False)


def shot_s5():
    R = 3.0
    tile_planet(R)
    tilt = (math.radians(-15), math.radians(7), math.radians(16))
    pixel_ring(R, tilt)
    burst()
    cam = make_camera('CAM', 35)
    cam.location = Vector((4.6, -12.6, 2.3)); look_at(cam, (1.55, 0.0, 0.45))
    cam.data.dof.aperture_fstop = 11; cam.data.dof.focus_distance = (cam.location).length
    bpy.context.view_layer.update()
    view = (Vector((0, 0, 0)) - cam.location).normalized()
    right = view.cross(Vector((0, 0, 1))).normalized(); up = right.cross(view).normalized()
    limb = (-right * 0.5 + up * 0.866).normalized() * (R + 0.12)
    star = cam.location + (limb - cam.location).normalized() * 300.0
    backlight(cam, star, (0, 0, 0), radius=3.0, disc=700, sun=6.0, corona=30, corona_size=18)
    area('FILL', (-6, -10, 5), (0, 0, 0), 8, 240, '#8c7cff')
    card('CARD_TOP', (-2, -6, 9), (0, 0, 0), 12, 6, 1.0, '#efe6ff')
    scene.world = space_world(band_through(scene, cam, (0.62, 1.02), (1.02, 0.25)), band_gain=1.1, violet=1.2)
    stars(WORLD, FX, seed=17)
    finish(cam, flare=True, star=star)


# ================================================================================================= S12
def shot_s12():
    u = 3.0 / 155.42                       # the lockup's D is 155.42 units tall; make it 3 m
    X = lambda x: (x - 39.05) * u
    Z = lambda y: (122.23 - y) * u         # svg y runs down; centre the D on z = 0
    px = crisp_cube('PIXEL', 39.05 * u, 0.018, 5, coll=SHAPES)
    px.data.materials.append(pixel_paint('pixel final', emit=1.1))
    px.location = (X(19.52), 0.0, Z(25.93)); px.rotation_euler = Euler((math.radians(-8), 0, math.radians(14)))
    px.visible_shadow = False
    point('PX_GLOW', px.location, 70, '#FFB247', radius=0.2)
    # D: flat side, top, half circle, bottom
    d_pts = [(X(39.05), 0, Z(199.94)), (X(39.05), 0, Z(44.52)), (X(116.76), 0, Z(44.52))]
    for i in range(1, 64):
        a = math.pi / 2 - math.pi * i / 64
        d_pts.append((X(116.76 + 77.71 * math.cos(a)), 0, Z(122.23 - 77.71 * math.sin(a))))
    d_pts += [(X(116.76), 0, Z(199.94))]
    polyline('MARK_D', d_pts, '#2f6bff', 5.0, 0.011, cyclic=True, coll=SHAPES)
    # C: the 3/4 arc, mouth open to the right between -45 and +33 degrees (svg angles, y down)
    cx, cy, cr = 197.755, 121.105, 84.86
    c_pts = []
    for i in range(97):
        a = math.radians(33 + (315 - 33) * i / 96)
        c_pts.append((X(cx + cr * math.cos(a)), 0, Z(cy + cr * math.sin(a))))
    polyline('MARK_C', c_pts, '#ff7fdc', 4.5, 0.011, coll=SHAPES)
    cam = make_camera('CAM', 50)
    mid = Vector((X(118.0), 0, 0.0)); tgt = Vector((0.15, 0.0, 0.1))
    cam.location = tgt + Vector((-2.4, -14.6, -0.7)); look_at(cam, tgt)
    cam.data.dof.aperture_fstop = 8; cam.data.dof.focus_distance = (cam.location - mid).length
    bpy.context.view_layer.update()
    area('KEY', (X(0) - 3, -4, 3), px.location, 3, 140, '#FFE1B4')
    card('CARD_L', (X(0) - 3, -1.5, 1.5), px.location, 2.6, 2.6, 4.0, '#FFE6C2')
    scene.world = space_world(band_through(scene, cam, (0.0, 0.92), (0.5, 1.05)), band_gain=0.45)
    stars(WORLD, FX, n=2200, seed=23, max_b=14.0)
    finish(cam, flare=False, fog=0.38, bloom=0.26)


if __name__ == '__main__':
    {'e1': shot_e1, 'e2': shot_e2, 'e3': shot_e3, 's1': shot_s1, 's1bh': shot_s1bh, 's1star': shot_s1star, 's3': shot_s3, 's5': shot_s5, 's12': shot_s12}[SHOT]()
