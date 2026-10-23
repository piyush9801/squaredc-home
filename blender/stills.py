"""Key-pose stills for the Square DC home page universe (render a few frames before animating anything).

blender -b --factory-startup --python stills.py -- <shot> <out.png> [samples] [scale%]
shots: s1 (Enter the universe), s3 (Gravity), s5 (Birth of a world)
"""
import bpy, sys, os, math, random, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib, lib
importlib.reload(lib)
from lib import *
from mathutils import Vector, Euler, Matrix, noise

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
SHOT = argv[0] if argv else 's1'
OUT = argv[1] if len(argv) > 1 else '/tmp/sdc_still.png'
SAMPLES = int(argv[2]) if len(argv) > 2 else 128
PCT = int(argv[3]) if len(argv) > 3 else 100

bpy.ops.wm.read_homefile(use_empty=True)
scene = bpy.context.scene
scene.frame_set(1)
WORLD = new_collection('WORLD')
FX = new_collection('FX')


def no_emission_sampling(m):
    for target in (m, getattr(m, 'cycles', None)):
        try: target.emission_sampling = 'NONE'; return
        except Exception: pass


# ----------------------------------------------------------------------------------------------- pieces
def starfield(n=3600, r=700.0, seed=11):
    rnd = random.Random(seed)
    pts, size, bright = [], [], []
    for _ in range(n):
        v = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized()
        d = r * (0.75 + 0.25 * rnd.random())
        pts.append(v * d)
        b = rnd.random() ** 5
        bright.append(b)
        size.append((0.07 + 0.22 * b) * d / 700)
    m = instance_mat('star', lin('#fff3e2'), 0.6, 16.0, tint_b=lin('#c9d6ff'))
    no_emission_sampling(m)
    inst = tiny_sphere('star_inst', m, FX, subdiv=1)
    o = points_object('STARS', pts, {'size': size, 'bright': bright}, WORLD)
    gn_instancer(o, inst, 'size')
    set_vis(o, diffuse=False, glossy=False, transmission=True, scatter=False, shadow=False)
    return o


def dust(n, centre, half, seed=3, size=(0.0015, 0.006), strength=(0.05, 2.5), avoid=None, avoid_r=0.0,
         col='#ffe9c9', col_b='#b9a8ff', name='DUST', cam_pos=None):
    rnd = random.Random(seed)
    pts, sz, br = [], [], []
    c = Vector(centre)
    while len(pts) < n:
        p = c + Vector(((rnd.random() * 2 - 1) * half[0], (rnd.random() * 2 - 1) * half[1], (rnd.random() * 2 - 1) * half[2]))
        if avoid is not None and (p - Vector(avoid)).length < avoid_r: continue
        if avoid is not None and cam_pos is not None:
            # keep the sightline to the subject clean: no specks drawn over it
            ax = (Vector(avoid) - Vector(cam_pos)); t = (p - Vector(cam_pos)).dot(ax.normalized())
            if 0 < t < ax.length:
                off = ((p - Vector(cam_pos)) - ax.normalized() * t).length
                if off < avoid_r * 1.25 * t / ax.length: continue
        pts.append(p); b = rnd.random() ** 3; br.append(b)
        sz.append(size[0] + (size[1] - size[0]) * rnd.random() ** 2)
    m = instance_mat(name + '_m', lin(col), strength[0], strength[1], tint_b=lin(col_b), glossy=True)
    no_emission_sampling(m)
    inst = tiny_sphere(name + '_inst', m, FX, subdiv=2)
    o = points_object(name, pts, {'size': sz, 'bright': br}, WORLD)
    gn_instancer(o, inst, 'size')
    set_vis(o, diffuse=False, shadow=False, scatter=False)
    return o


def backlight(cam, star_pos, target, radius, disc=500.0, sun=5.0, col='#fff0d4', corona=60.0, corona_size=14.0):
    """The star behind the subject: a visible disc, a soft corona the subject can eclipse, and a sun lamp
    pointing from the star at the subject for the rim light."""
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, segments=48, ring_count=24, location=star_pos)
    s = bpy.context.object; s.name = 'STAR'
    s.data.materials.append(emission_mat('star disc', lin(col), disc))
    set_vis(s, diffuse=False, shadow=False, scatter=False)
    # corona billboard (additive, so whatever stands in front of it eclipses it)
    bpy.ops.mesh.primitive_plane_add(size=radius * corona_size * 2, location=star_pos)
    cp = bpy.context.object; cp.name = 'CORONA'
    d = (cam.location - Vector(star_pos)); cp.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    m, nt, out = mat_nodes('corona'); N = nt.nodes; Lk = nt.links
    tc = N.new('ShaderNodeTexCoord'); sub = N.new('ShaderNodeVectorMath'); sub.operation = 'SUBTRACT'
    sub.inputs[1].default_value = (0.5, 0.5, 0.0)
    Lk.new(tc.outputs['Generated'], sub.inputs[0])
    ln = N.new('ShaderNodeVectorMath'); ln.operation = 'LENGTH'; Lk.new(sub.outputs[0], ln.inputs[0])
    # 1 - 2d, then a steep power: bright core, long soft skirt
    mr = N.new('ShaderNodeMapRange'); mr.inputs['From Max'].default_value = 0.5
    mr.inputs['To Min'].default_value = 1.0; mr.inputs['To Max'].default_value = 0.0
    Lk.new(ln.outputs['Value'], mr.inputs['Value'])
    pw = N.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 5.0
    Lk.new(mr.outputs[0], pw.inputs[0])
    ml = N.new('ShaderNodeMath'); ml.operation = 'MULTIPLY'; ml.inputs[1].default_value = corona
    Lk.new(pw.outputs[0], ml.inputs[0])
    em = N.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (*lin(col), 1)
    Lk.new(ml.outputs[0], em.inputs['Strength'])
    tr = N.new('ShaderNodeBsdfTransparent'); ad = N.new('ShaderNodeAddShader')
    Lk.new(tr.outputs[0], ad.inputs[0]); Lk.new(em.outputs[0], ad.inputs[1]); Lk.new(ad.outputs[0], out.inputs['Surface'])
    no_emission_sampling(m)
    cp.data.materials.append(m)
    set_vis(cp, diffuse=False, glossy=False, transmission=True, scatter=False, shadow=False)
    # rim light
    ld = bpy.data.lights.new('SUN', 'SUN'); ld.energy = sun; ld.angle = math.radians(0.8); ld.color = lin(col)
    so = link(bpy.data.objects.new('SUN', ld))
    so.rotation_euler = (Vector(target) - Vector(star_pos)).to_track_quat('-Z', 'Y').to_euler()
    return s


def area(name, loc, target, size, power, col, shape='DISK'):
    ld = bpy.data.lights.new(name, 'AREA'); ld.shape = shape; ld.size = size; ld.energy = power; ld.color = lin(col)
    o = link(bpy.data.objects.new(name, ld)); o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    o.visible_camera = False
    return o


def point(name, loc, power, col, radius=0.2):
    ld = bpy.data.lights.new(name, 'POINT'); ld.energy = power; ld.color = lin(col); ld.shadow_soft_size = radius
    o = link(bpy.data.objects.new(name, ld)); o.location = loc
    return o


def reflection_card(name, loc, target, w, h, strength, col):
    """Big soft card only glossy/transmission rays see, so glass and lacquer have something to reflect."""
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc)
    o = bpy.context.object; o.name = name; o.scale = (w, h, 1)
    o.rotation_euler = (Vector(loc) - Vector(target)).to_track_quat('Z', 'Y').to_euler()
    m = emission_mat(name + '_m', lin(col), strength); no_emission_sampling(m)
    o.data.materials.append(m)
    set_vis(o, camera=False, diffuse=False, glossy=True, transmission=True, scatter=False, shadow=False)
    return o


def place_camera(pos, target, lens=50, fstop=8.0, focus=None):
    cam = make_camera('CAM', lens)
    cam.location = Vector(pos); look_at(cam, target)
    cam.data.dof.aperture_fstop = fstop
    cam.data.dof.focus_distance = focus if focus else (Vector(target) - Vector(pos)).length
    return cam


def finish(cam, star_pos, comp_overrides=None):
    render_setup(scene, samples=SAMPLES, threshold=0.015, mblur=False)
    scene.render.resolution_percentage = PCT
    scene.render.image_settings.file_format = 'PNG'; scene.render.image_settings.color_mode = 'RGB'
    scene.world = deep_space_world(1.0)
    comp = compositor(scene)
    sp = screen_pos(scene, cam, star_pos)
    comp['sun'].inputs['Sun Position'].default_value = (sp.x, sp.y)
    print('STAR SCREEN POS', round(sp.x, 3), round(sp.y, 3))
    for (node, sock), v in (comp_overrides or {}).items():
        comp[node].inputs[sock].default_value = v
    scene.render.filepath = OUT
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print('RENDER SECONDS', round(time.time() - t, 1))
    bpy.ops.wm.save_as_mainfile(filepath=OUT.rsplit('.', 1)[0] + '.blend', compress=True)


def star_behind(cam_pos, through, dist):
    d = (Vector(through) - Vector(cam_pos)).normalized()
    return Vector(cam_pos) + d * dist


# ----------------------------------------------------------------------------------------------- shots
def tune(root, coat=None, coat_rough=None, emit_mult=None, rough=None):
    for b in scale_emission(root):
        if coat is not None: b.inputs['Coat Weight'].default_value = coat
        if coat_rough is not None: b.inputs['Coat Roughness'].default_value = coat_rough
        if rough is not None: b.inputs['Roughness'].default_value = rough
        if emit_mult is not None: b.inputs['Emission Strength'].default_value *= emit_mult


def shot_s1():
    """Scene 01: the yellow square alone in the dark, the star rising behind its upper-right edge."""
    cube = import_shape('pixel')
    cube.rotation_euler = Euler((math.radians(4), math.radians(-6), math.radians(38)))
    tune(cube, coat=0.65, coat_rough=0.035, emit_mult=0.7)
    cam_pos = Vector((0.0, -3.7, 1.05)); tgt = Vector((0.0, 0.0, 0.08))
    cam = place_camera(cam_pos, tgt, lens=50, fstop=7.0)
    bpy.context.view_layer.update()
    # aim the star just inside the cube's upper-right silhouette so it is half eclipsed
    star = star_behind(cam_pos, (0.27, 0.10, 0.47), 120.0)
    backlight(cam, star, (0, 0, 0), radius=0.9, disc=650, sun=8.0, corona=34, corona_size=16)
    # violet fill from camera-left so the front faces keep their colour, a cool kicker from the right
    area('FILL', (-2.6, -2.6, 1.6), (0, 0, 0), 3.0, 16, '#8c7cff')
    area('KICK', (2.8, 1.6, 0.4), (0, 0, 0), 1.2, 40, '#5d8dff')
    reflection_card('CARD_TOP', (-0.6, -1.2, 3.4), (0, 0, 0), 4, 2, 0.8, '#efe6ff')
    starfield()
    dust(1300, (0, 0.6, 0.1), (2.8, 3.0, 1.6), seed=7, avoid=(0, 0, 0), avoid_r=0.8, cam_pos=cam_pos,
         size=(0.0012, 0.004), strength=(0.3, 6.0))
    finish(cam, star)


ORBITS = [  # shape, orbit radius, angle (deg, 90 = far side), scale, tilt
    ('octa', 1.9, 300, 0.62), ('sphere', 2.7, 128, 0.42), ('arch', 3.5, 58, 0.46),
    ('torus', 4.3, 192, 0.36), ('cube', 5.1, 343, 0.48), ('dome', 5.9, 258, 0.40), ('cone', 6.4, 22, 0.44),
]


def orbit_trail(name, radius, ang_deg, col, n=1600, seed=1, tilt=0.0):
    rnd = random.Random(seed)
    pts, sz, br = [], [], []
    a0 = math.radians(ang_deg)
    for i in range(n):
        if i < n * 0.62:   # the comet tail behind the shape (orbit runs counter-clockwise)
            d = rnd.expovariate(1 / 0.75)
            if d > 2.6: continue
            b = math.exp(-d / 0.9) * (0.4 + 0.6 * rnd.random())
        else:              # the faint full orbit
            d = rnd.random() * math.tau; b = 0.05 + 0.08 * rnd.random()
        a = a0 - d - 0.08
        rr = radius + rnd.gauss(0, 0.035 + 0.02 * d)
        z = rnd.gauss(0, 0.018 + 0.01 * d)
        pts.append(Vector((rr * math.cos(a), rr * math.sin(a), z)))
        br.append(b); sz.append(0.004 + 0.012 * rnd.random() ** 2)
    m = instance_mat(name + '_m', lin('#fff1dc'), 0.2, 9.0, tint_b=lin(col), glossy=True)
    no_emission_sampling(m)
    inst = tiny_sphere(name + '_inst', m, FX, subdiv=1)
    o = points_object(name, pts, {'size': sz, 'bright': br}, WORLD)
    gn_instancer(o, inst, 'size')
    set_vis(o, diffuse=False, shadow=False, scatter=False)
    return o


SHAPE_TINT = {'octa': '#4f7dff', 'sphere': '#3aa36a', 'arch': '#ff5f8f', 'torus': '#ffc23a', 'cube': '#3f62ff',
              'dome': '#59b6ff', 'cone': '#ff9a3a'}


def shot_s3():
    """Scene 03: creative gravity. The shapes on their orbits round an unseen centre, dust trailing behind each."""
    centre = import_shape('pixel', 'pixel_c')
    centre.scale = (0.72,) * 3; centre.rotation_euler = Euler((math.radians(12), math.radians(-8), math.radians(32)))
    for o in shape_children(centre): o.visible_shadow = False
    point('PIXEL_LIGHT', (0, 0, 0), 90, '#ffbf3d', radius=0.25)
    rnd = random.Random(4)
    for i, (k, r, ang, s) in enumerate(ORBITS):
        sh = import_shape(k)
        a = math.radians(ang)
        sh.location = (r * math.cos(a), r * math.sin(a), rnd.uniform(-0.12, 0.12))
        sh.scale = (s,) * 3
        sh.rotation_euler = Euler((rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5), rnd.uniform(0, 6.28)))
        orbit_trail('TRAIL_' + k, r, ang, SHAPE_TINT[k], seed=20 + i)
    el = math.radians(24); dist = 15.5
    cam_pos = Vector((0.0, -dist * math.cos(el), dist * math.sin(el)))
    tgt = Vector((0, 0.3, -0.25))
    cam = place_camera(cam_pos, tgt, lens=40, fstop=11.0, focus=(cam_pos - Vector((0, 0, 0))).length)
    star = star_behind(cam_pos, (0.55, 0.0, 1.05), 220.0)
    backlight(cam, star, (0, 0, 0), radius=1.8, disc=650, sun=3.2, corona=26, corona_size=18)
    area('FILL', (-7, -12, 9), (0, 0, 0), 10, 900, '#a99cff')
    area('KICK', (9, 4, 2), (0, 0, 0), 5, 500, '#6a8dff')
    reflection_card('CARD_TOP', (-3, -8, 12), (0, 0, 0), 18, 8, 1.1, '#f1eaff')
    reflection_card('CARD_SIDE', (12, -6, 3), (0, 0, 0), 4, 10, 1.6, '#7fa2ff')
    starfield()
    dust(2400, (0, 0, 0), (9, 9, 3), seed=9, size=(0.004, 0.012), strength=(0.03, 1.4))
    finish(cam, star)


def sdc_planet(R=3.0, n=22, seed=5):
    """A world made of square tiles: a cube projected onto a sphere, every tile a bevelled block standing on a
    glowing core, so light escapes through the seams. Raised districts follow slow noise."""
    rnd = random.Random(seed)
    faces = []
    for ax in range(3):
        for sgn in (1, -1):
            nrm = Vector([0, 0, 0]); nrm[ax] = sgn
            u = Vector([0, 0, 0]); u[(ax + 1) % 3] = 1
            v = nrm.cross(u)
            faces.append((nrm, u, v))
    pts, rots, scl, lit = [], [], [], []
    for nrm, u, v in faces:
        for i in range(n):
            for j in range(n):
                a = -1 + (2 * i + 1) / n; b = -1 + (2 * j + 1) / n
                dirv = (nrm + u * a + v * b).normalized()
                x = (u - dirv * u.dot(dirv)).normalized(); y = dirv.cross(x)
                rot = Matrix((x, y, dirv)).transposed().to_euler()
                w = ((nrm + u * (a + 1 / n) + v * b).normalized() - (nrm + u * (a - 1 / n) + v * b).normalized()).length * R
                hh = ((nrm + u * a + v * (b + 1 / n)).normalized() - (nrm + u * a + v * (b - 1 / n)).normalized()).length * R
                nz = noise.noise(dirv * 1.7 + Vector((3.1, 0.7, 1.9)))
                raise_ = max(0.0, nz - 0.05) * 1.1
                if rnd.random() < 0.02: raise_ += rnd.uniform(0.15, 0.4)
                height = 0.09 + raise_ * 0.42
                pts.append(dirv * (R + height / 2 - 0.05))
                rots.append(rot); scl.append((w * 0.86, hh * 0.86, height))
                lit.append(1.0 if (raise_ > 0.12 and rnd.random() < 0.10) else 0.0)
    # tile instance: bevelled unit cube
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, -9999))
    tile = bpy.context.object; tile.name = 'tile_inst'
    bv = tile.modifiers.new('bev', 'BEVEL'); bv.width = 0.06; bv.segments = 3
    for c in tile.users_collection: c.objects.unlink(tile)
    FX.objects.link(tile)
    m, nt, out = mat_nodes('tile'); N = nt.nodes; Lk = nt.links
    b = N.new('ShaderNodeBsdfPrincipled')
    oi = N.new('ShaderNodeObjectInfo')
    cr = N.new('ShaderNodeValToRGB'); r = cr.color_ramp
    r.elements[0].position = 0.0; r.elements[0].color = (*[c * 0.55 for c in lin('#1829F3')], 1)
    r.elements[1].position = 1.0; r.elements[1].color = (*[c * 0.9 for c in lin('#2a1866')], 1)
    e = r.elements.new(0.55); e.color = (*[c * 0.7 for c in lin('#1858FD')], 1)
    Lk.new(oi.outputs['Random'], cr.inputs['Fac']); Lk.new(cr.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.32; b.inputs['Coat Weight'].default_value = 0.7
    b.inputs['Coat Roughness'].default_value = 0.08
    at = N.new('ShaderNodeAttribute'); at.attribute_type = 'INSTANCER'; at.attribute_name = 'lit'
    b.inputs['Emission Color'].default_value = (*lin('#FBB100'), 1)
    ml = N.new('ShaderNodeMath'); ml.operation = 'MULTIPLY'; ml.inputs[1].default_value = 7.0
    Lk.new(at.outputs['Fac'], ml.inputs[0]); Lk.new(ml.outputs[0], b.inputs['Emission Strength'])
    Lk.new(b.outputs[0], out.inputs['Surface'])
    tile.data.materials.append(m)
    o = points_object('PLANET_TILES', pts, {'scl': scl, 'rot': rots, 'lit': lit}, WORLD)
    gn_instancer(o, tile, scale_vec_attr='scl', rot_attr='rot')
    # glowing core seen through the seams
    bpy.ops.mesh.primitive_uv_sphere_add(radius=R - 0.09, segments=96, ring_count=48)
    core = bpy.context.object; core.name = 'PLANET_CORE'
    for p in core.data.polygons: p.use_smooth = True
    core.data.materials.append(emission_mat('core', lin('#ffb020'), 9.0))
    core.visible_shadow = False
    # thin atmosphere: light only at the limb
    bpy.ops.mesh.primitive_uv_sphere_add(radius=R + 0.42, segments=96, ring_count=48)
    atm = bpy.context.object; atm.name = 'PLANET_ATMO'
    for p in atm.data.polygons: p.use_smooth = True
    m, nt, out = mat_nodes('atmo'); N = nt.nodes; Lk = nt.links
    lw = N.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.5
    pw = N.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 3.5
    Lk.new(lw.outputs['Facing'], pw.inputs[0])
    ml = N.new('ShaderNodeMath'); ml.operation = 'MULTIPLY'; ml.inputs[1].default_value = 2.4
    Lk.new(pw.outputs[0], ml.inputs[0])
    em = N.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (*lin('#6f9dff'), 1)
    Lk.new(ml.outputs[0], em.inputs['Strength'])
    tr = N.new('ShaderNodeBsdfTransparent'); ad = N.new('ShaderNodeAddShader')
    Lk.new(tr.outputs[0], ad.inputs[0]); Lk.new(em.outputs[0], ad.inputs[1]); Lk.new(ad.outputs[0], out.inputs['Surface'])
    no_emission_sampling(m)
    atm.data.materials.append(m)
    set_vis(atm, diffuse=False, glossy=False, shadow=False, scatter=False)
    return o


def glitter_ring(R=3.0, n=30000, seed=8, tilt=(math.radians(-16), math.radians(6), math.radians(18))):
    rnd = random.Random(seed)
    bands = [(1.38, 1.55, 0.18), (1.6, 1.98, 0.42), (2.06, 2.12, 0.06), (2.2, 2.55, 0.26), (2.62, 2.7, 0.08)]
    tot = sum(b[2] for b in bands)
    pts, sz, br = [], [], []
    for _ in range(n):
        x = rnd.random() * tot
        for lo, hi, w in bands:
            if x < w: break
            x -= w
        rr = R * (lo + (hi - lo) * rnd.random())
        a = rnd.random() * math.tau
        pts.append(Vector((rr * math.cos(a), rr * math.sin(a), rnd.gauss(0, 0.012))))
        b = rnd.random() ** 2.2; br.append(b)
        sz.append(0.006 + 0.022 * rnd.random() ** 3)
    m = instance_mat('ring_m', lin('#f6e7c8'), 0.15, 7.5, tint_b=lin('#FBB100'), glossy=True)
    # a few brand sparks: pink and blue
    no_emission_sampling(m)
    inst = tiny_sphere('ring_inst', m, FX, subdiv=1)
    o = points_object('RING', pts, {'size': sz, 'bright': br}, WORLD)
    gn_instancer(o, inst, 'size')
    o.rotation_euler = Euler(tilt)
    set_vis(o, diffuse=False, scatter=False)
    # brand sparks
    pts2, sz2, br2 = [], [], []
    for _ in range(1400):
        lo, hi, w = bands[rnd.randrange(len(bands))]
        rr = R * (lo + (hi - lo) * rnd.random()); a = rnd.random() * math.tau
        pts2.append(Vector((rr * math.cos(a), rr * math.sin(a), rnd.gauss(0, 0.012))))
        br2.append(rnd.random()); sz2.append(0.01 + 0.02 * rnd.random())
    m2 = instance_mat('spark_m', lin('#F66FD6'), 1.0, 14.0, tint_b=lin('#1858FD'), glossy=True)
    no_emission_sampling(m2)
    inst2 = tiny_sphere('spark_inst', m2, FX, subdiv=1)
    o2 = points_object('RING_SPARKS', pts2, {'size': sz2, 'bright': br2}, WORLD)
    gn_instancer(o2, inst2, 'size'); o2.rotation_euler = Euler(tilt)
    set_vis(o2, diffuse=False, scatter=False)
    return o


def shot_s5():
    """Scene 05: a Square DC world is born. Tiled planet, glitter ring, the star breaking over its limb."""
    R = 3.0
    sdc_planet(R)
    glitter_ring(R)
    cam_pos = Vector((3.2, -13.2, 2.4)); tgt = Vector((1.2, 0.0, 0.2))
    cam = place_camera(cam_pos, tgt, lens=35, fstop=11.0, focus=(cam_pos - Vector((0, 0, 0))).length)
    # limb point toward upper left as seen from the camera
    view = (Vector((0, 0, 0)) - cam_pos).normalized()
    up = Vector((0, 0, 1)); right = view.cross(up).normalized(); up2 = right.cross(view).normalized()
    limb = (-right * 0.55 + up2 * 0.83).normalized() * (R + 0.16)
    star = star_behind(cam_pos, limb, 260.0)
    backlight(cam, star, (0, 0, 0), radius=2.6, disc=700, sun=4.0, corona=30, corona_size=18)
    area('FILL', (-6, -10, 6), (0, 0, 0), 8, 260, '#8c7cff')
    reflection_card('CARD_TOP', (-2, -6, 9), (0, 0, 0), 12, 6, 0.9, '#efe6ff')
    starfield()
    dust(1800, (0, 0, 0), (9, 9, 4), seed=12, size=(0.004, 0.012), strength=(0.03, 1.2))
    finish(cam, star)


{'s1': shot_s1, 's3': shot_s3, 's5': shot_s5}[SHOT]()
