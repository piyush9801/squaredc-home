"""The one look every Square DC universe shot shares, so nothing reads as pasted in:

1. One space   - very dark violet (#10041F), a faint violet Milky Way, real-looking stars.
2. One surface - every shape carries the same dust, micro scratches, smudges and edge wear.
3. One light   - a strong star behind the subject for the rim; the yellow cube is the warm sun of the system.
4. One lens    - soft glow everywhere; streak, starburst and ghosts only from the brightest light.
"""
import bpy, math, random, os
from mathutils import Vector, Matrix, Euler
from lib import lin, mat_nodes, link, points_object, gn_instancer, tiny_sphere, set_vis, emission_mat

SPACE = '#10041F'


def no_emission_sampling(m):
    for target in (m, getattr(m, 'cycles', None)):
        try: target.emission_sampling = 'NONE'; return
        except Exception: pass


# ----------------------------------------------------------------------------------------------- camera maths
def ray_dir(scene, cam, sx, sy):
    """World direction through normalised screen point (0..1, origin bottom-left)."""
    bpy.context.view_layer.update()
    cd = cam.data
    tan_h = (cd.sensor_width / 2) / cd.lens
    aspect = scene.render.resolution_y / scene.render.resolution_x
    v = Vector(((sx - 0.5) * 2 * tan_h, (sy - 0.5) * 2 * tan_h * aspect, -1.0))
    return (cam.matrix_world.to_3x3() @ v).normalized()


def band_through(scene, cam, p1, p2):
    """Galactic-plane normal so the Milky Way crosses the frame through two screen points."""
    return ray_dir(scene, cam, *p1).cross(ray_dir(scene, cam, *p2)).normalized()


# ----------------------------------------------------------------------------------------------- space
def space_world(band_normal=(0.3, -0.4, 0.86), band_gain=1.0, base=SPACE, violet=1.0, width=30.0, palette='warm'):
    w = bpy.data.worlds.new('SDC space')
    try: w.use_nodes = True
    except Exception: pass
    nt = w.node_tree; N = nt.nodes; L = nt.links; N.clear()
    out = N.new('ShaderNodeOutputWorld')
    tc = N.new('ShaderNodeTexCoord')
    nrm = N.new('ShaderNodeVectorMath'); nrm.operation = 'NORMALIZE'; L.new(tc.outputs['Generated'], nrm.inputs[0])
    D = nrm.outputs[0]

    def m(op, a, b=None, clamp=False):
        n = N.new('ShaderNodeMath'); n.operation = op; n.use_clamp = clamp
        for i, v in enumerate((a, b)):
            if v is None: continue
            if isinstance(v, (int, float)): n.inputs[i].default_value = v
            else: L.new(v, n.inputs[i])
        return n.outputs[0]

    def noise(vec, scale, detail, rough, dist=0.0):
        n = N.new('ShaderNodeTexNoise'); n.noise_dimensions = '3D'
        n.inputs['Scale'].default_value = scale; n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = rough; n.inputs['Distortion'].default_value = dist
        L.new(vec, n.inputs['Vector']); return n.outputs['Fac']

    def ramp(v, stops):
        n = N.new('ShaderNodeValToRGB'); r = n.color_ramp
        r.elements[0].position, r.elements[0].color = stops[0][0], (*stops[0][1], 1)
        r.elements[1].position, r.elements[1].color = stops[-1][0], (*stops[-1][1], 1)
        for p, c in stops[1:-1]:
            e = r.elements.new(p); e.color = (*c, 1)
        L.new(v, n.inputs['Fac']); return n.outputs['Color']

    def rgb_scale(col_socket, k):
        mx = N.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'; mx.inputs['Factor'].default_value = 1.0
        L.new(col_socket, mx.inputs['A'])
        cc = N.new('ShaderNodeCombineColor')
        for i in range(3): L.new(k, cc.inputs[i])
        L.new(cc.outputs[0], mx.inputs['B'])
        return mx.outputs['Result']

    def add(a, b):
        mx = N.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.blend_type = 'ADD'; mx.inputs['Factor'].default_value = 1.0
        L.new(a, mx.inputs['A']); L.new(b, mx.inputs['B']); return mx.outputs['Result']

    dp = N.new('ShaderNodeVectorMath'); dp.operation = 'DOT_PRODUCT'
    L.new(D, dp.inputs[0]); dp.inputs[1].default_value = tuple(Vector(band_normal).normalized())
    warp = noise(D, 2.0, 4, 0.55)
    gw = m('ADD', dp.outputs['Value'], m('MULTIPLY', m('SUBTRACT', warp, 0.5), 0.16))
    band = m('EXPONENT', m('MULTIPLY', m('MULTIPLY', gw, gw), -width))
    core = m('EXPONENT', m('MULTIPLY', m('MULTIPLY', gw, gw), -width * 4.6))
    # star clouds: bright knots along the band
    clouds = noise(D, 7.0, 12, 0.66, 0.35)
    clumps = m('POWER', m('MULTIPLY', clouds, 1.45, True), 3.0)
    # dust lanes: dark filaments strongest along the core
    rift_n = noise(D, 9.0, 10, 0.62, 0.9)
    lanes = m('POWER', m('MULTIPLY', rift_n, 1.32, True), 3.2)
    rift = m('SUBTRACT', 1.0, m('MULTIPLY', lanes, m('ADD', m('MULTIPLY', core, 0.9), 0.15)), True)
    glow = m('MULTIPLY', m('MULTIPLY', m('MULTIPLY', m('ADD', band, m('MULTIPLY', core, 1.5)), clumps), rift), 0.17 * band_gain)
    # warm star-light in the core, violet only in the faint wings
    tint = m('ADD', m('MULTIPLY', core, 0.75), m('MULTIPLY', clouds, 0.25))
    stops = {'warm': [(0.12, [c * violet for c in lin('#3a1866')]), (0.32, lin('#6a3a7e')), (0.55, lin('#b0848a')),
                      (0.8, lin('#e6cfae'))],
             'violet': [(0.1, lin('#2a0f58')), (0.3, lin('#5a1f96')), (0.55, lin('#9a4cc4')), (0.75, lin('#d58fd8')),
                        (0.92, lin('#f2c58e'))]}[palette]
    col = ramp(tint, stops)
    neb = rgb_scale(col, glow)
    # unresolved stars: dense fine grain inside the band
    gv = N.new('ShaderNodeTexVoronoi'); gv.inputs['Scale'].default_value = 1400; L.new(D, gv.inputs['Vector'])
    grain = m('POWER', m('SUBTRACT', 1.0, m('MULTIPLY', gv.outputs['Distance'], 2.1), True), 6.0)
    sg = m('MULTIPLY', m('MULTIPLY', grain, m('ADD', band, core)), m('MULTIPLY', m('ADD', m('MULTIPLY', rift, clumps), 0.25), 1.8 * band_gain))
    sgc = N.new('ShaderNodeCombineColor')
    for i, f in enumerate((1.0, 0.93, 0.9)): L.new(m('MULTIPLY', sg, f), sgc.inputs[i])
    basec = ramp(noise(D, 1.2, 3, 0.5), [(0.3, [c * 0.5 for c in lin(base)]), (0.75, [c * 1.3 for c in lin(base)])])
    sky = add(add(basec, neb), sgc.outputs[0])
    bg = N.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = 1.0
    L.new(sky, bg.inputs['Color'])
    # seen by the camera only; shapes are lit by lamps, so the sky can't wash them
    lp = N.new('ShaderNodeLightPath')
    dark = N.new('ShaderNodeBackground'); dark.inputs['Color'].default_value = (*[c * 0.6 for c in lin(base)], 1)
    mx = N.new('ShaderNodeMixShader')
    L.new(lp.outputs['Is Camera Ray'], mx.inputs['Fac']); L.new(dark.outputs[0], mx.inputs[1]); L.new(bg.outputs[0], mx.inputs[2])
    L.new(mx.outputs[0], out.inputs['Surface'])
    return w


def stars(coll, fx, n=4200, r=900.0, seed=11, max_b=24.0, size_k=1.0):
    rnd = random.Random(seed)
    pts, size, bright, tint = [], [], [], []
    for _ in range(n):
        v = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized()
        d = r * (0.8 + 0.2 * rnd.random())
        pts.append(v * d)
        b = rnd.random() ** 6
        bright.append(b); size.append((0.10 + 0.34 * b) * d / 900 * size_k); tint.append(rnd.random())
    m, nt, out = mat_nodes('stars'); N = nt.nodes; Lk = nt.links
    at = N.new('ShaderNodeAttribute'); at.attribute_type = 'INSTANCER'; at.attribute_name = 'bright'
    tt = N.new('ShaderNodeAttribute'); tt.attribute_type = 'INSTANCER'; tt.attribute_name = 'tint'
    mr = N.new('ShaderNodeMapRange'); mr.inputs['To Min'].default_value = 0.4; mr.inputs['To Max'].default_value = max_b
    Lk.new(at.outputs['Fac'], mr.inputs['Value'])
    cr = N.new('ShaderNodeValToRGB'); r_ = cr.color_ramp
    r_.elements[0].position = 0.0; r_.elements[0].color = (*lin('#ffad66'), 1)
    r_.elements[1].position = 1.0; r_.elements[1].color = (*lin('#a8c2ff'), 1)
    for p, c in ((0.22, '#ffe4c0'), (0.68, '#f5f2ff')):
        e = r_.elements.new(p); e.color = (*lin(c), 1)
    Lk.new(tt.outputs['Fac'], cr.inputs['Fac'])
    em = N.new('ShaderNodeEmission'); Lk.new(cr.outputs['Color'], em.inputs['Color']); Lk.new(mr.outputs['Result'], em.inputs['Strength'])
    Lk.new(em.outputs[0], out.inputs['Surface'])
    no_emission_sampling(m)
    inst = tiny_sphere('star_inst', m, fx, subdiv=1)
    o = points_object('STARS', pts, {'size': size, 'bright': bright, 'tint': tint}, coll)
    gn_instancer(o, inst, 'size')
    set_vis(o, diffuse=False, glossy=False, transmission=True, scatter=False, shadow=False)
    return o


# ----------------------------------------------------------------------------------------------- surface wear
def wear_group():
    """Shared wear in object space (marks stay on the object as it turns). Outputs a roughness offset, a bump
    height, a dust mask, an edge mask and a slow mottle."""
    if 'SDC wear' in bpy.data.node_groups: return bpy.data.node_groups['SDC wear']
    g = bpy.data.node_groups.new('SDC wear', 'ShaderNodeTree')
    I = g.interface
    s = I.new_socket('Scale', in_out='INPUT', socket_type='NodeSocketFloat'); s.default_value = 1.0
    for nm in ('Rough', 'Height', 'Dust', 'Edge', 'Mottle'):
        I.new_socket(nm, in_out='OUTPUT', socket_type='NodeSocketFloat')
    N = g.nodes; L = g.links
    gi = N.new('NodeGroupInput'); go = N.new('NodeGroupOutput')
    tc = N.new('ShaderNodeTexCoord')
    sc = N.new('ShaderNodeVectorMath'); sc.operation = 'DIVIDE'
    L.new(tc.outputs['Object'], sc.inputs[0])
    cs = N.new('ShaderNodeCombineXYZ')
    for i in range(3): L.new(gi.outputs['Scale'], cs.inputs[i])
    L.new(cs.outputs[0], sc.inputs[1])
    P = sc.outputs[0]

    def m(op, a, b=None, clamp=False):
        n = N.new('ShaderNodeMath'); n.operation = op; n.use_clamp = clamp
        for i, v in enumerate((a, b)):
            if v is None: continue
            if isinstance(v, (int, float)): n.inputs[i].default_value = v
            else: L.new(v, n.inputs[i])
        return n.outputs[0]

    def mp(vec, rot=(0, 0, 0), scale=(1, 1, 1), loc=(0, 0, 0)):
        n = N.new('ShaderNodeMapping'); n.inputs['Rotation'].default_value = rot
        n.inputs['Scale'].default_value = scale; n.inputs['Location'].default_value = loc
        L.new(vec, n.inputs['Vector']); return n.outputs['Vector']

    def noise(vec, scale, detail=2.0, rough=0.5, dist=0.0):
        n = N.new('ShaderNodeTexNoise'); n.noise_dimensions = '3D'
        n.inputs['Scale'].default_value = scale; n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = rough; n.inputs['Distortion'].default_value = dist
        L.new(vec, n.inputs['Vector']); return n.outputs['Fac']

    def rng(v, a, b, c=0.0, d=1.0):
        n = N.new('ShaderNodeMapRange'); n.clamp = True
        n.inputs['From Min'].default_value = a; n.inputs['From Max'].default_value = b
        n.inputs['To Min'].default_value = c; n.inputs['To Max'].default_value = d
        L.new(v, n.inputs['Value']); return n.outputs['Result']

    # micro scratches: contour lines of a stretched noise, broken into short runs, three directions
    scr = None
    for k, rot in enumerate([(0.2, 0.9, 0.3), (1.2, 0.4, 2.1), (2.3, 1.7, 0.9)]):
        v = mp(P, rot, (3.0, 3.0, 240.0), (k * 3.3, k * 1.7, 0))
        line = rng(m('ABSOLUTE', m('SUBTRACT', noise(v, 1.0, 1.0, 0.4), 0.5)), 0.0, 0.010, 1.0, 0.0)
        cut = rng(noise(mp(P, rot, (1, 1, 1), (k * 7.1, 0, 0)), 9.0, 2.0), 0.6, 0.67)
        lyr = m('MULTIPLY', line, cut)
        scr = lyr if scr is None else m('MAXIMUM', scr, lyr)
    # smudges with fingerprint whorls inside them
    blob = rng(noise(mp(P, (0.5, 0.2, 0.8), (1, 1, 1), (4.2, 1.1, 0.3)), 2.6, 3.0, 0.5), 0.57, 0.7)
    wv = N.new('ShaderNodeTexWave'); wv.wave_type = 'RINGS'; wv.rings_direction = 'SPHERICAL'
    wv.inputs['Scale'].default_value = 70.0; wv.inputs['Distortion'].default_value = 9.0
    wv.inputs['Detail'].default_value = 2.0; wv.inputs['Detail Scale'].default_value = 1.5
    L.new(P, wv.inputs['Vector'])
    smudge = m('MAXIMUM', m('MULTIPLY', blob, 0.45), m('MULTIPLY', rng(wv.outputs['Fac'], 0.35, 0.75), blob))
    # dust: fine specks and a thin film
    vor = N.new('ShaderNodeTexVoronoi'); vor.inputs['Scale'].default_value = 340.0
    L.new(P, vor.inputs['Vector'])
    speck = m('MULTIPLY', rng(vor.outputs['Distance'], 0.0, 0.12, 1.0, 0.0), rng(vor.outputs['Color'], 0.86, 0.9))
    dust = m('MAXIMUM', speck, m('MULTIPLY', rng(noise(P, 6.0, 6.0, 0.6), 0.45, 0.8), 0.25))
    # edge wear where the rounded normal parts from the true one, broken by noise
    bv = N.new('ShaderNodeBevel'); bv.samples = 8; bv.inputs['Radius'].default_value = 0.02
    geo = N.new('ShaderNodeNewGeometry')
    dt = N.new('ShaderNodeVectorMath'); dt.operation = 'DOT_PRODUCT'
    L.new(bv.outputs['Normal'], dt.inputs[0]); L.new(geo.outputs['Normal'], dt.inputs[1])
    edge = m('MULTIPLY', rng(dt.outputs['Value'], 0.995, 0.93), rng(noise(P, 28.0, 4.0, 0.6), 0.38, 0.62))
    mott = noise(P, 2.2, 5.0, 0.55)
    crk = N.new('ShaderNodeTexVoronoi'); crk.feature = 'DISTANCE_TO_EDGE'; crk.inputs['Scale'].default_value = 9.0
    L.new(mp(P, (0, 0, 0), (1, 1, 1), (2.0, 5.0, 1.0)), crk.inputs['Vector'])
    crack = m('MULTIPLY', rng(crk.outputs['Distance'], 0.0, 0.03, 1.0, 0.0), rng(noise(P, 3.0, 2.0), 0.55, 0.7))
    rough = m('ADD', m('ADD', m('MULTIPLY', scr, 0.28), m('MULTIPLY', smudge, 0.16)), m('MULTIPLY', dust, 0.35))
    height = m('ADD', m('ADD', m('MULTIPLY', scr, -1.0), m('MULTIPLY', speck, 0.6)), m('MULTIPLY', crack, -0.7))
    for nm, sock in (('Rough', rough), ('Height', height), ('Dust', dust), ('Edge', edge), ('Mottle', mott)):
        L.new(sock, go.inputs[nm])
    return g


def worn_material(name, base_hex, metallic=0.0, rough=0.3, coat=0.0, coat_rough=0.05, emit_hex=None, emit=0.0,
                  transmission=0.0, ior=1.45, subsurface=0.0, wear_scale=1.0, wear=1.0, mottle=0.12,
                  dust_hex='#d8cdbb', edge_hex=None, bump=0.35, absorb_hex=None, absorb=0.0):
    m, nt, out = mat_nodes(name); N = nt.nodes; L = nt.links
    b = N.new('ShaderNodeBsdfPrincipled')
    wg = N.new('ShaderNodeGroup'); wg.node_tree = wear_group(); wg.inputs['Scale'].default_value = wear_scale
    mo = N.new('ShaderNodeMapRange'); mo.inputs['To Min'].default_value = 1 - mottle; mo.inputs['To Max'].default_value = 1 + mottle
    L.new(wg.outputs['Mottle'], mo.inputs['Value'])
    c0 = N.new('ShaderNodeMix'); c0.data_type = 'RGBA'; c0.blend_type = 'MULTIPLY'; c0.inputs['Factor'].default_value = 1.0
    c0.inputs['A'].default_value = (*lin(base_hex), 1)
    gc = N.new('ShaderNodeCombineColor')
    for i in range(3): L.new(mo.outputs['Result'], gc.inputs[i])
    L.new(gc.outputs[0], c0.inputs['B'])
    dm = N.new('ShaderNodeMath'); dm.operation = 'MULTIPLY'; dm.inputs[1].default_value = 0.55 * wear
    L.new(wg.outputs['Dust'], dm.inputs[0])
    c1 = N.new('ShaderNodeMix'); c1.data_type = 'RGBA'; c1.inputs['B'].default_value = (*lin(dust_hex), 1)
    L.new(dm.outputs[0], c1.inputs['Factor']); L.new(c0.outputs['Result'], c1.inputs['A'])
    col = c1.outputs['Result']
    if edge_hex:
        em_ = N.new('ShaderNodeMath'); em_.operation = 'MULTIPLY'; em_.inputs[1].default_value = wear
        L.new(wg.outputs['Edge'], em_.inputs[0])
        c2 = N.new('ShaderNodeMix'); c2.data_type = 'RGBA'; c2.inputs['B'].default_value = (*lin(edge_hex), 1)
        L.new(em_.outputs[0], c2.inputs['Factor']); L.new(col, c2.inputs['A'])
        col = c2.outputs['Result']
    L.new(col, b.inputs['Base Color'])
    rr = N.new('ShaderNodeMath'); rr.operation = 'MULTIPLY_ADD'; rr.use_clamp = True
    L.new(wg.outputs['Rough'], rr.inputs[0]); rr.inputs[1].default_value = wear; rr.inputs[2].default_value = rough
    L.new(rr.outputs[0], b.inputs['Roughness'])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = bump * wear; bp.inputs['Distance'].default_value = 0.0006
    L.new(wg.outputs['Height'], bp.inputs['Height']); L.new(bp.outputs['Normal'], b.inputs['Normal'])
    for k, v in (('Metallic', metallic), ('Coat Weight', coat), ('Coat Roughness', coat_rough),
                 ('Transmission Weight', transmission), ('IOR', ior), ('Subsurface Weight', subsurface)):
        b.inputs[k].default_value = v
    if emit_hex:
        b.inputs['Emission Color'].default_value = (*lin(emit_hex), 1); b.inputs['Emission Strength'].default_value = emit
    L.new(b.outputs[0], out.inputs['Surface'])
    if absorb_hex:
        va = N.new('ShaderNodeVolumeAbsorption'); va.inputs['Color'].default_value = (*lin(absorb_hex), 1)
        va.inputs['Density'].default_value = absorb
        L.new(va.outputs[0], out.inputs['Volume'])
    return m


def add_wear(mat, amount=1.0, scale=1.0, bump=0.25):
    """Lay the shared wear onto a library material without changing its colour."""
    if not mat or not mat.node_tree: return
    nt = mat.node_tree; N = nt.nodes; L = nt.links
    for b in [n for n in N if n.bl_idname == 'ShaderNodeBsdfPrincipled']:
        wg = N.new('ShaderNodeGroup'); wg.node_tree = wear_group(); wg.inputs['Scale'].default_value = scale
        r_in = b.inputs['Roughness']
        if not r_in.is_linked:
            rr = N.new('ShaderNodeMath'); rr.operation = 'MULTIPLY_ADD'; rr.use_clamp = True
            L.new(wg.outputs['Rough'], rr.inputs[0]); rr.inputs[1].default_value = amount; rr.inputs[2].default_value = r_in.default_value
            L.new(rr.outputs[0], r_in)
        n_in = b.inputs['Normal']
        if not n_in.is_linked:
            bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = bump * amount; bp.inputs['Distance'].default_value = 0.0005
            L.new(wg.outputs['Height'], bp.inputs['Height']); L.new(bp.outputs['Normal'], n_in)


def pixel_paint(name='pixel paint', emit=0.0):
    """The yellow square as a real object: golden yellow metallic paint under a clear coat, worn."""
    return worn_material(name, '#FFC94F', metallic=0.76, rough=0.25, coat=0.5, coat_rough=0.05, wear=1.0, mottle=0.13,
                         edge_hex='#FFE6A6', dust_hex='#cdbb9c', bump=0.35, emit_hex='#FFB52D', emit=emit)


# ----------------------------------------------------------------------------------------------- geometry
def crisp_cube(name, size=0.88, bevel=0.022, segs=5, coll=None):
    bpy.ops.mesh.primitive_cube_add(size=size)
    o = bpy.context.object; o.name = name
    bv = o.modifiers.new('bevel', 'BEVEL'); bv.width = bevel; bv.segments = segs; bv.limit_method = 'NONE'
    bv.harden_normals = True
    for p in o.data.polygons: p.use_smooth = True
    if coll:
        for c in o.users_collection: c.objects.unlink(o)
        coll.objects.link(o)
    return o


def orbit_ring(name, radius, col_hex, strength=3.0, width=0.006, rot=(0, 0, 0), loc=(0, 0, 0), coll=None):
    bpy.ops.curve.primitive_bezier_circle_add(radius=radius, location=loc)
    o = bpy.context.object; o.name = name
    o.data.bevel_depth = width; o.data.bevel_resolution = 2; o.data.resolution_u = 96
    o.rotation_euler = Euler(rot)
    m = emission_mat(name + '_m', lin(col_hex), strength); no_emission_sampling(m)
    o.data.materials.append(m)
    set_vis(o, diffuse=False, glossy=True, transmission=True, scatter=False, shadow=False)
    if coll:
        for c in o.users_collection: c.objects.unlink(o)
        coll.objects.link(o)
    return o


def polyline(name, pts, col_hex, strength=3.0, width=0.006, cyclic=False, coll=None):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'
    cu.bevel_depth = width; cu.bevel_resolution = 2
    sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
    for p, q in zip(sp.points, pts): p.co = (*q, 1)
    sp.use_cyclic_u = cyclic
    o = link(bpy.data.objects.new(name, cu), coll)
    m = emission_mat(name + '_m', lin(col_hex), strength); no_emission_sampling(m)
    cu.materials.append(m)
    set_vis(o, diffuse=False, glossy=True, transmission=True, scatter=False, shadow=False)
    return o


def planet(name, loc, radius, sun_pos, palette, band_scale=5.0, seed=0.0, atmo_hex='#e48ad6', atmo=2.2, coll=None,
           rough=0.62, atmo_pow=4.0):
    """A purple world: soft gas bands, and a thin atmosphere that only glows on the lit limb."""
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, segments=160, ring_count=80, location=loc)
    o = bpy.context.object; o.name = name
    for p in o.data.polygons: p.use_smooth = True
    m, nt, out = mat_nodes(name + '_m'); N = nt.nodes; L = nt.links
    tc = N.new('ShaderNodeTexCoord')
    mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1.0, 1.0, band_scale)
    mp.inputs['Location'].default_value = (seed, seed * 0.7, 0)
    L.new(tc.outputs['Object'], mp.inputs['Vector'])
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 1.6 / radius; nz.inputs['Detail'].default_value = 9
    nz.inputs['Roughness'].default_value = 0.6; nz.inputs['Distortion'].default_value = 1.4
    L.new(mp.outputs['Vector'], nz.inputs['Vector'])
    cr = N.new('ShaderNodeValToRGB'); r = cr.color_ramp
    r.elements[0].position = 0.25; r.elements[0].color = (*lin(palette[0]), 1)
    r.elements[1].position = 0.8; r.elements[1].color = (*lin(palette[-1]), 1)
    for i, c in enumerate(palette[1:-1]):
        e = r.elements.new(0.25 + 0.55 * (i + 1) / (len(palette) - 1)); e.color = (*lin(c), 1)
    L.new(nz.outputs['Fac'], cr.inputs['Fac'])
    b = N.new('ShaderNodeBsdfPrincipled'); b.inputs['Roughness'].default_value = rough
    L.new(cr.outputs['Color'], b.inputs['Base Color'])
    L.new(b.outputs[0], out.inputs['Surface'])
    o.data.materials.append(m)
    # atmosphere shell
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius * 1.022, segments=160, ring_count=80, location=loc)
    a = bpy.context.object; a.name = name + '_atmo'
    for p in a.data.polygons: p.use_smooth = True
    m2, nt2, out2 = mat_nodes(name + '_atmo_m'); N2 = nt2.nodes; L2 = nt2.links
    lw = N2.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.5
    pw = N2.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = atmo_pow
    L2.new(lw.outputs['Facing'], pw.inputs[0])
    geo = N2.new('ShaderNodeNewGeometry')
    ldir = (Vector(sun_pos) - Vector(loc)).normalized()
    dp = N2.new('ShaderNodeVectorMath'); dp.operation = 'DOT_PRODUCT'; dp.inputs[1].default_value = tuple(ldir)
    L2.new(geo.outputs['Normal'], dp.inputs[0])
    lit = N2.new('ShaderNodeMapRange'); lit.inputs['From Min'].default_value = -0.25; lit.inputs['From Max'].default_value = 0.7
    lit.clamp = True; L2.new(dp.outputs['Value'], lit.inputs['Value'])
    ml = N2.new('ShaderNodeMath'); ml.operation = 'MULTIPLY'; L2.new(pw.outputs[0], ml.inputs[0]); L2.new(lit.outputs['Result'], ml.inputs[1])
    front = N2.new('ShaderNodeMath'); front.operation = 'SUBTRACT'; front.inputs[0].default_value = 1.0
    L2.new(geo.outputs['Backfacing'], front.inputs[1])
    ml2 = N2.new('ShaderNodeMath'); ml2.operation = 'MULTIPLY'; L2.new(ml.outputs[0], ml2.inputs[0]); L2.new(front.outputs[0], ml2.inputs[1])
    ml = ml2
    ms = N2.new('ShaderNodeMath'); ms.operation = 'MULTIPLY'; ms.inputs[1].default_value = atmo; L2.new(ml.outputs[0], ms.inputs[0])
    em = N2.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (*lin(atmo_hex), 1)
    L2.new(ms.outputs[0], em.inputs['Strength'])
    tr = N2.new('ShaderNodeBsdfTransparent'); ad = N2.new('ShaderNodeAddShader')
    L2.new(tr.outputs[0], ad.inputs[0]); L2.new(em.outputs[0], ad.inputs[1]); L2.new(ad.outputs[0], out2.inputs['Surface'])
    no_emission_sampling(m2)
    a.data.materials.append(m2)
    set_vis(a, diffuse=False, glossy=False, shadow=False, scatter=False)
    for ob in (o, a):
        if coll:
            for c in ob.users_collection: c.objects.unlink(ob)
            coll.objects.link(ob)
    return o


# ----------------------------------------------------------------------------------------------- light
def backlight(cam, star_pos, target, radius, disc=650.0, sun=8.0, col='#fff0d4', corona=34.0, corona_size=16.0,
              coll=None):
    """The star behind the subject: a visible disc, a corona the subject can eclipse, a lamp for the rim."""
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, segments=48, ring_count=24, location=star_pos)
    s = bpy.context.object; s.name = 'STAR'
    m = emission_mat('star disc', lin(col), disc); no_emission_sampling(m)
    s.data.materials.append(m)
    set_vis(s, diffuse=False, shadow=False, scatter=False)
    bpy.ops.mesh.primitive_plane_add(size=radius * corona_size * 2, location=star_pos)
    cp = bpy.context.object; cp.name = 'CORONA'
    cp.rotation_euler = (cam.location - Vector(star_pos)).to_track_quat('Z', 'Y').to_euler()
    m, nt, out = mat_nodes('corona'); N = nt.nodes; Lk = nt.links
    tc = N.new('ShaderNodeTexCoord'); sub = N.new('ShaderNodeVectorMath'); sub.operation = 'SUBTRACT'
    sub.inputs[1].default_value = (0.5, 0.5, 0.0); Lk.new(tc.outputs['Generated'], sub.inputs[0])
    ln = N.new('ShaderNodeVectorMath'); ln.operation = 'LENGTH'; Lk.new(sub.outputs[0], ln.inputs[0])
    mr = N.new('ShaderNodeMapRange'); mr.inputs['From Max'].default_value = 0.5
    mr.inputs['To Min'].default_value = 1.0; mr.inputs['To Max'].default_value = 0.0
    Lk.new(ln.outputs['Value'], mr.inputs['Value'])
    pw = N.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 5.0; Lk.new(mr.outputs[0], pw.inputs[0])
    ml = N.new('ShaderNodeMath'); ml.operation = 'MULTIPLY'; ml.inputs[1].default_value = corona; Lk.new(pw.outputs[0], ml.inputs[0])
    em = N.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (*lin(col), 1); Lk.new(ml.outputs[0], em.inputs['Strength'])
    tr = N.new('ShaderNodeBsdfTransparent'); ad = N.new('ShaderNodeAddShader')
    Lk.new(tr.outputs[0], ad.inputs[0]); Lk.new(em.outputs[0], ad.inputs[1]); Lk.new(ad.outputs[0], out.inputs['Surface'])
    no_emission_sampling(m)
    cp.data.materials.append(m)
    set_vis(cp, diffuse=False, glossy=False, transmission=True, scatter=False, shadow=False)
    ld = bpy.data.lights.new('STAR_SUN', 'SUN'); ld.energy = sun; ld.angle = math.radians(0.8); ld.color = lin(col)
    so = link(bpy.data.objects.new('STAR_SUN', ld))
    so.rotation_euler = (Vector(target) - Vector(star_pos)).to_track_quat('-Z', 'Y').to_euler()
    for ob in (s, cp):
        if coll:
            for c in ob.users_collection: c.objects.unlink(ob)
            coll.objects.link(ob)
    return s, so


def area(name, loc, target, size, power, col, shape='DISK', size_y=None):
    ld = bpy.data.lights.new(name, 'AREA'); ld.shape = shape; ld.size = size; ld.energy = power; ld.color = lin(col)
    if size_y and shape in ('RECTANGLE', 'ELLIPSE'): ld.size_y = size_y
    o = link(bpy.data.objects.new(name, ld)); o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    o.visible_camera = False
    return o


def point(name, loc, power, col, radius=0.2):
    ld = bpy.data.lights.new(name, 'POINT'); ld.energy = power; ld.color = lin(col); ld.shadow_soft_size = radius
    o = link(bpy.data.objects.new(name, ld)); o.location = loc
    return o


def card(name, loc, target, w, h, strength, col):
    """Soft card only reflections and refractions see: gives metal and glass something to mirror."""
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc)
    o = bpy.context.object; o.name = name; o.scale = (w, h, 1)
    o.rotation_euler = (Vector(loc) - Vector(target)).to_track_quat('Z', 'Y').to_euler()
    m, nt, out = mat_nodes(name + '_m'); N = nt.nodes; Lk = nt.links
    tc = N.new('ShaderNodeTexCoord'); sub = N.new('ShaderNodeVectorMath'); sub.operation = 'SUBTRACT'
    sub.inputs[1].default_value = (0.5, 0.5, 0.0); Lk.new(tc.outputs['Generated'], sub.inputs[0])
    ln = N.new('ShaderNodeVectorMath'); ln.operation = 'LENGTH'; Lk.new(sub.outputs[0], ln.inputs[0])
    mr = N.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = 0.15; mr.inputs['From Max'].default_value = 0.7
    mr.inputs['To Min'].default_value = strength; mr.inputs['To Max'].default_value = 0.0
    Lk.new(ln.outputs['Value'], mr.inputs['Value'])
    em = N.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (*lin(col), 1); Lk.new(mr.outputs['Result'], em.inputs['Strength'])
    Lk.new(em.outputs[0], out.inputs['Surface'])
    no_emission_sampling(m)
    o.data.materials.append(m)
    set_vis(o, camera=False, diffuse=False, glossy=True, transmission=True, scatter=False, shadow=False)
    return o


# ----------------------------------------------------------------------------------------------- lens
def lens(scene, flare=True, sun_pos=(0.5, 0.5), fog=0.32, bloom=0.22, beams=0.7, streak=0.25, ghosts=0.05, burst=0.08, diffuse=0.0, vignette=0.0, halo=0.0,
         fog_thr=2.2, bloom_thr=1.3):
    """Soft glow always; the anamorphic streak, starburst, sun beams and ghosts only when `flare` is on, and
    thresholds high enough that only the star (hundreds in scene-linear) feeds them."""
    ng = bpy.data.node_groups.new('SDC lens', 'CompositorNodeTree')
    ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    scene.compositing_node_group = ng
    scene.render.use_compositing = True
    N = ng.nodes; L = ng.links
    rl = N.new('CompositorNodeRLayers')

    def glare(kind, **kw):
        g = N.new('CompositorNodeGlare')
        g.inputs['Type'].default_value = kind; g.inputs['Quality'].default_value = 'High'
        for k, v in kw.items(): g.inputs[k].default_value = v
        return g

    chain = [rl,
             glare('Fog Glow', Threshold=fog_thr, Smoothness=0.4, Strength=fog, Size=0.5, Saturation=1.0),
             glare('Bloom', Threshold=bloom_thr, Smoothness=0.3, Strength=bloom, Size=0.85, Saturation=1.0)]
    if flare:
        chain += [glare('Streaks', Threshold=25.0 if not beams else 40.0, Smoothness=0.2, Strength=streak, Streaks=2, Iterations=4, Fade=0.955,
                        **{'Streaks Angle': 0.0, 'Color Modulation': 0.35}),
                  glare('Streaks', Threshold=90.0, Smoothness=0.2, Strength=burst, Streaks=8, Iterations=3, Fade=0.86,
                        **{'Streaks Angle': 0.21, 'Color Modulation': 0.2}),
                  glare('Sun Beams', Threshold=22.0, Smoothness=0.5, Strength=beams, Size=0.7, Jitter=0.2,
                        **{'Sun Position': sun_pos}),
                  glare('Ghosts', Threshold=60.0, Smoothness=0.3, Strength=ghosts, Iterations=3, **{'Color Modulation': 0.6})]
    if halo:      # the sun's own wide, soft halo: only the star itself (hundreds in scene-linear) feeds it
        chain.append(glare('Fog Glow', Threshold=25.0, Smoothness=0.6, Strength=halo, Size=1.0, Saturation=1.0))
    if diffuse:   # soft-focus filter: a wide, low-threshold glow over everything, like a diffusion filter on the lens
        chain.append(glare('Fog Glow', Threshold=0.25, Smoothness=0.8, Strength=diffuse, Size=0.95, Saturation=1.0))
    ld = N.new('CompositorNodeLensdist'); ld.inputs['Distortion'].default_value = 0.0
    ld.inputs['Dispersion'].default_value = 0.01
    go = N.new('NodeGroupOutput')
    for a, b in zip(chain, chain[1:]): L.new(a.outputs['Image'], b.inputs['Image'])
    L.new(chain[-1].outputs['Image'], ld.inputs['Image'])
    last = ld.outputs['Image']
    if vignette:   # darker corners: a soft ellipse mask, the outside pulled toward black
        em = N.new('CompositorNodeEllipseMask')
        em.inputs['Position'].default_value = (0.5, 0.5); em.inputs['Size'].default_value = (1.0, 1.05)
        bl = N.new('CompositorNodeBlur'); bl.inputs['Size'].default_value = (420 * scene.render.resolution_percentage / 100,) * 2
        L.new(em.outputs['Mask'], bl.inputs['Image'])
        inv = N.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
        sep = N.new('CompositorNodeSeparateColor'); L.new(bl.outputs['Image'], sep.inputs['Image'])
        L.new(sep.outputs['Red'], inv.inputs[1])
        k = N.new('ShaderNodeMath'); k.operation = 'MULTIPLY'; k.inputs[1].default_value = vignette; k.use_clamp = True
        L.new(inv.outputs[0], k.inputs[0])
        mx = N.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'
        mx.inputs['B'].default_value = (0, 0, 0, 1)
        L.new(k.outputs[0], mx.inputs['Factor']); L.new(last, mx.inputs['A'])
        last = mx.outputs['Result']
    L.new(last, go.inputs['Image'])
    for i, n in enumerate(chain + [ld, go]): n.location = (i * 220, 0)
    return ng


# =============================================================================================== SLEEK language
# Dark bodies cut out by a thin rim of back light; rings as smooth light trails that run hot (white, yellow) to
# cool (orange, pink); a fine glitter field; a smooth near-black gradient instead of stars and nebula.
TRAIL_STOPS = [(0.0, '#2e1404'), (0.28, '#a3600c'), (0.52, '#FFAE1F'), (0.76, '#FFD66A'), (0.93, '#FFF4D6'),
               (1.0, '#FFFFFF')]
VIOLET_STOPS = [(0.0, '#100533'), (0.3, '#3a2a9a'), (0.6, '#7a5cff'), (0.85, '#c4b6ff'), (1.0, '#FFFFFF')]


def sleek_world(glow_dir=(0.3, 1.0, 0.45), base='#07060c', haze='#221a30', haze_power=3.0, strength=1.0):
    """Near-black with one soft lighter haze behind the subject; camera-only, so it never lights the shapes."""
    w = bpy.data.worlds.new('SDC sleek')
    try: w.use_nodes = True
    except Exception: pass
    nt = w.node_tree; N = nt.nodes; L = nt.links; N.clear()
    out = N.new('ShaderNodeOutputWorld')
    tc = N.new('ShaderNodeTexCoord')
    nrm = N.new('ShaderNodeVectorMath'); nrm.operation = 'NORMALIZE'; L.new(tc.outputs['Generated'], nrm.inputs[0])
    dp = N.new('ShaderNodeVectorMath'); dp.operation = 'DOT_PRODUCT'
    L.new(nrm.outputs[0], dp.inputs[0]); dp.inputs[1].default_value = tuple(Vector(glow_dir).normalized())
    mr = N.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = -0.2; mr.inputs['From Max'].default_value = 1.0
    mr.clamp = True; L.new(dp.outputs['Value'], mr.inputs['Value'])
    pw = N.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = haze_power
    L.new(mr.outputs['Result'], pw.inputs[0])
    # a whisper of large-scale variation so the gradient isn't sterile
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 1.4; nz.inputs['Detail'].default_value = 3.0
    L.new(nrm.outputs[0], nz.inputs['Vector'])
    nm = N.new('ShaderNodeMapRange'); nm.inputs['To Min'].default_value = 0.85; nm.inputs['To Max'].default_value = 1.15
    L.new(nz.outputs['Fac'], nm.inputs['Value'])
    ml = N.new('ShaderNodeMath'); ml.operation = 'MULTIPLY'; L.new(pw.outputs[0], ml.inputs[0]); L.new(nm.outputs['Result'], ml.inputs[1])
    mx = N.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.clamp_factor = True
    mx.inputs['A'].default_value = (*lin(base), 1); mx.inputs['B'].default_value = (*lin(haze), 1)
    L.new(ml.outputs[0], mx.inputs['Factor'])
    bg = N.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = strength
    L.new(mx.outputs['Result'], bg.inputs['Color'])
    lp = N.new('ShaderNodeLightPath')
    dark = N.new('ShaderNodeBackground'); dark.inputs['Color'].default_value = (*lin(base), 1)
    ms = N.new('ShaderNodeMixShader')
    L.new(lp.outputs['Is Camera Ray'], ms.inputs['Fac']); L.new(dark.outputs[0], ms.inputs[1]); L.new(bg.outputs[0], ms.inputs[2])
    L.new(ms.outputs[0], out.inputs['Surface'])
    return w


def nebula_world(base='#090314', strength=1.0, band_dir=(0.35, -0.25, 0.9), seed=3.0, env=None, env_strength=0.6,
                 cover=0.0, wisps=0.0, glitter=0.0):
    """Deep space with a nebula: violet, magenta and blue clouds along a diagonal band, warped so they swirl, with
    gold dust in the brightest knots and a few dark lanes. Camera-only, so it never lights the shapes."""
    w = bpy.data.worlds.new('SDC nebula')
    try: w.use_nodes = True
    except Exception: pass
    nt = w.node_tree; N = nt.nodes; L = nt.links; N.clear()
    out = N.new('ShaderNodeOutputWorld')
    tc = N.new('ShaderNodeTexCoord')
    nrm = N.new('ShaderNodeVectorMath'); nrm.operation = 'NORMALIZE'; L.new(tc.outputs['Generated'], nrm.inputs[0])
    def noise(vec, scale, detail=6.0, rough=0.62, dist=0.0, off=0.0):
        n_ = N.new('ShaderNodeTexNoise'); n_.inputs['Scale'].default_value = scale; n_.inputs['Detail'].default_value = detail
        n_.inputs['Roughness'].default_value = rough; n_.inputs['Distortion'].default_value = dist
        if off:
            ad_ = N.new('ShaderNodeVectorMath'); ad_.operation = 'ADD'; ad_.inputs[1].default_value = (off, off * 0.7, off * 1.3)
            L.new(vec, ad_.inputs[0]); vec = ad_.outputs[0]
        L.new(vec, n_.inputs['Vector']); return n_
    def m(op, a, b=None, clamp=False):
        n_ = N.new('ShaderNodeMath'); n_.operation = op; n_.use_clamp = clamp
        for i_, v_ in enumerate((a, b)):
            if v_ is None: continue
            if isinstance(v_, (int, float)): n_.inputs[i_].default_value = v_
            else: L.new(v_, n_.inputs[i_])
        return n_.outputs[0]
    # domain warp: the clouds swirl
    warp = noise(nrm.outputs[0], 1.6, detail=3.0, off=seed)
    wv = N.new('ShaderNodeVectorMath'); wv.operation = 'SCALE'; wv.inputs['Scale'].default_value = 0.55
    L.new(warp.outputs['Color'], wv.inputs[0])
    wp = N.new('ShaderNodeVectorMath'); wp.operation = 'ADD'; L.new(nrm.outputs[0], wp.inputs[0]); L.new(wv.outputs[0], wp.inputs[1])
    big = noise(wp.outputs[0], 2.2, detail=8.0, rough=0.6, off=seed + 1.0)
    fine = noise(wp.outputs[0], 7.0, detail=10.0, rough=0.7, off=seed + 2.0)
    # the band: clouds gather along a great circle and thin away from it
    bd = N.new('ShaderNodeVectorMath'); bd.operation = 'DOT_PRODUCT'; bd.inputs[1].default_value = tuple(Vector(band_dir).normalized())
    L.new(nrm.outputs[0], bd.inputs[0])
    band = m('POWER', m('SUBTRACT', 1.0, m('ABSOLUTE', m('MULTIPLY', bd.outputs['Value'], 1.25)), clamp=True), 1.6)
    if cover: band = m('ADD', cover, m('MULTIPLY', band, 1.0 - cover))           # (storyboard) gas in every direction
    dens = m('MULTIPLY', m('POWER', m('MULTIPLY', m('SUBTRACT', big.outputs['Fac'], 0.36), 2.6, clamp=True), 2.2), band)
    dens = m('MULTIPLY', dens, m('POWER', m('ADD', 0.25, m('MULTIPLY', fine.outputs['Fac'], 1.2)), 2.0))   # wisps, lanes
    if wisps:
        # bright filaments along the swirl (thin contours of a mid-scale noise), then dark dust lanes across them
        mid = noise(wp.outputs[0], 4.2, detail=6.0, rough=0.55, off=seed + 7.0)
        ridge = m('POWER', m('SUBTRACT', 1.0, m('MULTIPLY', m('ABSOLUTE', m('SUBTRACT', mid.outputs['Fac'], 0.5)), 7.0), clamp=True), 2.5)
        ridge = m('MULTIPLY', ridge, m('MULTIPLY', m('SUBTRACT', fine.outputs['Fac'], 0.3), 2.5, clamp=True))     # smoke, not veins
        dens = m('ADD', dens, m('MULTIPLY', m('MULTIPLY', ridge, m('MULTIPLY', band, m('ADD', 0.15, big.outputs['Fac']))), wisps))
        lane = noise(wp.outputs[0], 3.1, detail=4.0, off=seed + 9.0)
        dens = m('MULTIPLY', dens, m('SUBTRACT', 1.0, m('MULTIPLY', m('MULTIPLY', m('SUBTRACT', lane.outputs['Fac'], 0.56), 7.0, clamp=True), 0.65)))
    hue = noise(wp.outputs[0], 1.2, detail=2.0, off=seed + 5.0)
    cr = N.new('ShaderNodeValToRGB'); r = cr.color_ramp
    r.elements[0].position = 0.0; r.elements[0].color = (*lin('#1a1f8c'), 1)        # blue
    r.elements[1].position = 1.0; r.elements[1].color = (*lin('#c0388f'), 1)        # magenta
    for p_, c_ in ((0.35, '#3b1c8f'), (0.62, '#6a24a0')):                           # violets
        e_ = r.elements.new(p_); e_.color = (*lin(c_), 1)
    L.new(hue.outputs['Fac'], cr.inputs['Fac'])
    col_ = cr.outputs['Color']
    if wisps:                                                   # the dense gas glows a lighter lilac
        hl = N.new('ShaderNodeMix'); hl.data_type = 'RGBA'; hl.clamp_factor = True
        L.new(col_, hl.inputs['A']); hl.inputs['B'].default_value = (*lin('#b48cff'), 1)
        L.new(m('MULTIPLY', m('POWER', m('MULTIPLY', dens, 0.9, clamp=True), 2.0), 0.7), hl.inputs['Factor']); col_ = hl.outputs['Result']
    gold = N.new('ShaderNodeMix'); gold.data_type = 'RGBA'; gold.clamp_factor = True     # gold where it is densest
    L.new(col_, gold.inputs['A']); gold.inputs['B'].default_value = (*lin('#ffb85c'), 1)
    L.new(m('POWER', m('MULTIPLY', dens, 1.15, clamp=True), 4.0), gold.inputs['Factor'])
    cl = N.new('ShaderNodeVectorMath'); cl.operation = 'SCALE'; L.new(gold.outputs['Result'], cl.inputs[0])
    L.new(m('MULTIPLY', dens, 1.1), cl.inputs['Scale'])
    sky = N.new('ShaderNodeMix'); sky.data_type = 'RGBA'; sky.blend_type = 'ADD'; sky.inputs['Factor'].default_value = 1.0
    sky.inputs['A'].default_value = (*lin(base), 1); L.new(cl.outputs[0], sky.inputs['B'])
    sky_ = sky.outputs['Result']
    if glitter:
        # (storyboard) star dust: fine points gathered in the clouds, violet-white with a little gold. Two sizes of cells
        # in the view direction (only cells whose point lies near the sphere show, so the field is sparse and uneven).
        acc = None
        for sc_, thr_, k_ in ((70.0, 0.06, 1.0), (160.0, 0.11, 0.55), (330.0, 0.15, 0.3)):
            vo = N.new('ShaderNodeTexVoronoi'); vo.voronoi_dimensions = '3D'; vo.feature = 'F1'
            vo.inputs['Scale'].default_value = sc_; L.new(nrm.outputs[0], vo.inputs['Vector'])
            dot = m('POWER', m('SUBTRACT', 1.0, m('DIVIDE', vo.outputs['Distance'], thr_), clamp=True), 2.0)
            sp_ = N.new('ShaderNodeSeparateColor'); L.new(vo.outputs['Color'], sp_.inputs[0])
            b_ = m('MULTIPLY', m('MULTIPLY', dot, m('ADD', 0.15, m('POWER', sp_.outputs[0], 6.0))), k_)
            acc = b_ if acc is None else m('ADD', acc, b_)
        acc = m('MULTIPLY', m('MULTIPLY', acc, m('ADD', 0.12, m('MULTIPLY', dens, 2.5))), glitter)
        gc = N.new('ShaderNodeMix'); gc.data_type = 'RGBA'; gc.clamp_factor = True
        gc.inputs['A'].default_value = (*lin('#efe4ff'), 1); gc.inputs['B'].default_value = (*lin('#ffd27a'), 1)
        L.new(m('POWER', sp_.outputs[1], 3.0), gc.inputs['Factor'])
        gs = N.new('ShaderNodeVectorMath'); gs.operation = 'SCALE'; L.new(gc.outputs['Result'], gs.inputs[0]); L.new(acc, gs.inputs['Scale'])
        sk2 = N.new('ShaderNodeMix'); sk2.data_type = 'RGBA'; sk2.blend_type = 'ADD'; sk2.inputs['Factor'].default_value = 1.0
        L.new(sky_, sk2.inputs['A']); L.new(gs.outputs[0], sk2.inputs['B']); sky_ = sk2.outputs['Result']
    bg = N.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = strength
    L.new(sky_, bg.inputs['Color'])
    lp = N.new('ShaderNodeLightPath')
    dark = N.new('ShaderNodeBackground'); dark.inputs['Color'].default_value = (*lin(base), 1)
    # what glass and metal see: reflections of a studio (env), the nebula through them; nothing else is lit by it
    seen = N.new('ShaderNodeMixShader')
    L.new(lp.outputs['Is Transmission Ray'], seen.inputs['Fac']); L.new(dark.outputs[0], seen.inputs[1]); L.new(bg.outputs[0], seen.inputs[2])
    if env and os.path.exists(env):
        im = bpy.data.images.load(env, check_existing=True)
        et = N.new('ShaderNodeTexEnvironment'); et.image = im
        eb = N.new('ShaderNodeBackground'); eb.inputs['Strength'].default_value = env_strength
        L.new(et.outputs['Color'], eb.inputs['Color'])
        gl = N.new('ShaderNodeMixShader')
        L.new(lp.outputs['Is Glossy Ray'], gl.inputs['Fac']); L.new(seen.outputs[0], gl.inputs[1]); L.new(eb.outputs[0], gl.inputs[2])
        seen = gl
    ms = N.new('ShaderNodeMixShader')
    L.new(lp.outputs['Is Camera Ray'], ms.inputs['Fac']); L.new(seen.outputs[0], ms.inputs[1]); L.new(bg.outputs[0], ms.inputs[2])
    L.new(ms.outputs[0], out.inputs['Surface'])
    return w


# ----------------------------------------------------------------------------------------------- jewels
JEWELS = {   # (surface tint, absorption colour, absorption density, roughness, dispersion, sparkle, metal)
    'sphere': ('#c9ffe0', '#1f9a55', 11.0, 0.02, 0.02, 1.0, False),    # luminous green glass
    'torus':  ('#ffc64a', None, 0.0, 0.1, 0.0, 0.0, True),           # polished gold
    'dome':   ('#e2d6ff', '#5a3fe6', 10.0, 0.03, 0.02, 1.0, False),    # violet glass, sparkling inside
    'cone':   ('#ffd0d0', '#d0142c', 18.0, 0.02, 0.03, 0.3, False),    # ruby
    'arch':   ('#ffc8c8', '#c20f2a', 15.0, 0.03, 0.02, 0.3, False),    # ruby, deeper
    'octa':   ('#cfdcff', '#1438e8', 16.0, 0.01, 0.06, 0.4, False),    # sapphire, colour fringes on its facets
    'cube':   ('#eef4ff', '#9fb8ff', 2.0, 0.0, 0.03, 0.2, False),      # clear glass
}


BRAND_GLOW = {'pixel': '#FFBE00', 'torus': '#E5A10A', 'sphere': '#2f7a2a', 'cube': '#2a3cff', 'dome': '#2a6cff',
              'cone': '#FF8A14', 'arch': '#B0123a', 'octa': '#0b3cd6'}


def brand_glow(root, key, glow=0.35, size=1.0):
    """Keep the shape library's designed materials and colours; give them the storyboard's finish: a clear coat, a little
    less roughness, and a soft light from within in the shape's own brand colour."""
    done = set()
    for ch in [root] + list(root.children_recursive):
        if ch.type != 'MESH': continue
        for sl in ch.material_slots:
            mt = sl.material
            if not mt or not mt.node_tree or mt.name in done: continue
            done.add(mt.name)
            for n in mt.node_tree.nodes:
                if n.bl_idname != 'ShaderNodeBsdfPrincipled': continue
                n.inputs['Coat Weight'].default_value = max(n.inputs['Coat Weight'].default_value, 0.55)
                n.inputs['Coat Roughness'].default_value = 0.03
                if not n.inputs['Roughness'].links:
                    n.inputs['Roughness'].default_value = n.inputs['Roughness'].default_value * 0.6
                if key == 'torus':                                    # polished metallic gold, in the brand's marigold
                    n.inputs['Metallic'].default_value = 1.0; n.inputs['Coat Weight'].default_value = 0.2
                    if not n.inputs['Roughness'].links: n.inputs['Roughness'].default_value = 0.12
                if key == 'arch':                                     # ruby gloss with defined highlights
                    n.inputs['Coat Weight'].default_value = 0.85
                    if not n.inputs['Roughness'].links: n.inputs['Roughness'].default_value = 0.22
                if key == 'sphere':                                   # emerald, its highlight softened
                    n.inputs['Coat Roughness'].default_value = 0.12
                if not n.inputs['Emission Strength'].links:
                    bc = n.inputs['Base Color']
                    col = tuple(bc.default_value[:3]) if not bc.links else lin(BRAND_GLOW[key])
                    if not n.inputs['Emission Color'].links:
                        n.inputs['Emission Color'].default_value = (*col, 1)
                    n.inputs['Emission Strength'].default_value = max(n.inputs['Emission Strength'].default_value, 0.0 if key == 'torus' else glow)


def jewel_material(key, size=1.0):
    """The storyboard look: each shape a jewel. `size` scales the absorption (a planet-sized jewel must not be black)."""
    tint, absorb, dens, rough, disp, sparkle, metal = JEWELS[key]
    m, nt, out = mat_nodes(f'jewel {key} {size:g}'); N = nt.nodes; L = nt.links
    b = N.new('ShaderNodeBsdfPrincipled')
    b.inputs['Base Color'].default_value = (*lin(tint), 1); b.inputs['Roughness'].default_value = rough
    if metal:
        b.inputs['Metallic'].default_value = 1.0; b.inputs['Coat Weight'].default_value = 0.35
        b.inputs['Coat Roughness'].default_value = 0.03
    else:
        b.inputs['Transmission Weight'].default_value = 1.0; b.inputs['IOR'].default_value = 1.52
        if 'Dispersion' in b.inputs: b.inputs['Dispersion'].default_value = disp
        b.inputs['Coat Weight'].default_value = 0.2
        if absorb:                                                # a soft light inside, in its own colour: it glows
            b.inputs['Emission Color'].default_value = (*lin(absorb), 1)
            b.inputs['Emission Strength'].default_value = 0.35 if key != 'cube' else 0.08
    surf = b.outputs[0]
    if sparkle:                                                   # tiny points of light caught inside
        tc = N.new('ShaderNodeTexCoord'); vo = N.new('ShaderNodeTexVoronoi'); vo.inputs['Scale'].default_value = 34.0 / size
        L.new(tc.outputs['Object'], vo.inputs['Vector'])
        mr = N.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = 0.06; mr.inputs['From Max'].default_value = 0.0
        mr.inputs['To Max'].default_value = 6.0 * sparkle; mr.clamp = True; L.new(vo.outputs['Distance'], mr.inputs['Value'])
        em = N.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (*lin('#fff1c9'), 1)
        L.new(mr.outputs['Result'], em.inputs['Strength'])
        ad = N.new('ShaderNodeAddShader'); L.new(surf, ad.inputs[0]); L.new(em.outputs[0], ad.inputs[1]); surf = ad.outputs[0]
    L.new(surf, out.inputs['Surface'])
    if absorb:
        va = N.new('ShaderNodeVolumeAbsorption'); va.inputs['Color'].default_value = (*lin(absorb), 1)
        va.inputs['Density'].default_value = dens / size
        L.new(va.outputs[0], out.inputs['Volume'])
    return m


def jewel(root, key, size=1.0):
    """Dress every part of a library shape as its jewel."""
    mt = jewel_material(key, size)
    for ch in [root] + list(root.children_recursive):
        if ch.type == 'MESH':
            ch.data.materials.clear(); ch.data.materials.append(mt)
    return mt


def _trail_material(name, peak, gamma=1.6, stops=TRAIL_STOPS, soft=False, anim=False):
    m, nt, out = mat_nodes(name); N = nt.nodes; L = nt.links
    ai = N.new('ShaderNodeAttribute'); ai.attribute_type = 'GEOMETRY'; ai.attribute_name = 'i'
    cr = N.new('ShaderNodeValToRGB'); r = cr.color_ramp
    r.elements[0].position, r.elements[0].color = stops[0][0], (*lin(stops[0][1]), 1)
    r.elements[1].position, r.elements[1].color = stops[-1][0], (*lin(stops[-1][1]), 1)
    for p, c in stops[1:-1]:
        e = r.elements.new(p); e.color = (*lin(c), 1)
    L.new(ai.outputs['Fac'], cr.inputs['Fac'])
    pw = N.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = gamma
    L.new(ai.outputs['Fac'], pw.inputs[0])
    st = N.new('ShaderNodeMath'); st.operation = 'MULTIPLY'; st.inputs[1].default_value = peak
    L.new(pw.outputs[0], st.inputs[0])
    if soft:   # across the band: gaussian falloff on attribute v (-1..1)
        av = N.new('ShaderNodeAttribute'); av.attribute_type = 'GEOMETRY'; av.attribute_name = 'v'
        sq = N.new('ShaderNodeMath'); sq.operation = 'MULTIPLY'; L.new(av.outputs['Fac'], sq.inputs[0]); L.new(av.outputs['Fac'], sq.inputs[1])
        ng = N.new('ShaderNodeMath'); ng.operation = 'MULTIPLY'; ng.inputs[1].default_value = -3.2; L.new(sq.outputs[0], ng.inputs[0])
        ex = N.new('ShaderNodeMath'); ex.operation = 'EXPONENT'; L.new(ng.outputs[0], ex.inputs[0])
        st2 = N.new('ShaderNodeMath'); st2.operation = 'MULTIPLY'; L.new(st.outputs[0], st2.inputs[0]); L.new(ex.outputs[0], st2.inputs[1])
        st = st2
    if anim:   # REVEAL sweeps the light along the trail (u <= reveal is lit); GAIN fades the whole thing
        au = N.new('ShaderNodeAttribute'); au.attribute_type = 'GEOMETRY'; au.attribute_name = 'u'
        rv = N.new('ShaderNodeValue'); rv.name = 'REVEAL'; rv.outputs[0].default_value = 1.0
        df = N.new('ShaderNodeMath'); df.operation = 'SUBTRACT'; L.new(rv.outputs[0], df.inputs[0]); L.new(au.outputs['Fac'], df.inputs[1])
        mk = N.new('ShaderNodeMapRange'); mk.inputs['From Min'].default_value = -0.06; mk.inputs['From Max'].default_value = 0.0
        mk.clamp = True; L.new(df.outputs[0], mk.inputs['Value'])
        gn = N.new('ShaderNodeValue'); gn.name = 'GAIN'; gn.outputs[0].default_value = 1.0
        # TAIL: only the last stretch behind the head stays lit, fading with age (a comet's tail); 10 = no fade
        tl = N.new('ShaderNodeValue'); tl.name = 'TAIL'; tl.outputs[0].default_value = 10.0
        t1 = N.new('ShaderNodeMath'); t1.operation = 'SUBTRACT'; L.new(rv.outputs[0], t1.inputs[0]); L.new(tl.outputs[0], t1.inputs[1])
        t2 = N.new('ShaderNodeMath'); t2.operation = 'SUBTRACT'; L.new(au.outputs['Fac'], t2.inputs[0]); L.new(t1.outputs[0], t2.inputs[1])
        t3 = N.new('ShaderNodeMath'); t3.operation = 'DIVIDE'; t3.use_clamp = True; L.new(t2.outputs[0], t3.inputs[0]); L.new(tl.outputs[0], t3.inputs[1])
        t4 = N.new('ShaderNodeMath'); t4.operation = 'POWER'; t4.inputs[1].default_value = 1.4; L.new(t3.outputs[0], t4.inputs[0])
        mk2 = N.new('ShaderNodeMath'); mk2.operation = 'MULTIPLY'; L.new(mk.outputs['Result'], mk2.inputs[0]); L.new(t4.outputs[0], mk2.inputs[1])
        a1 = N.new('ShaderNodeMath'); a1.operation = 'MULTIPLY'; L.new(st.outputs[0], a1.inputs[0]); L.new(mk2.outputs[0], a1.inputs[1])
        a2 = N.new('ShaderNodeMath'); a2.operation = 'MULTIPLY'; L.new(a1.outputs[0], a2.inputs[0]); L.new(gn.outputs[0], a2.inputs[1])
        st = a2
        # idle loop: pulses of light travel along the trail. PHASE runs 0->1 per loop (one wavelength), PULSE turns it on.
        ph = N.new('ShaderNodeValue'); ph.name = 'PHASE'; ph.outputs[0].default_value = 0.0
        pa = N.new('ShaderNodeValue'); pa.name = 'PULSE'; pa.outputs[0].default_value = 0.0
        k_ = N.new('ShaderNodeMath'); k_.operation = 'MULTIPLY_ADD'; L.new(au.outputs['Fac'], k_.inputs[0])
        k_.inputs[1].default_value = 2.0; k_.inputs[2].default_value = (hash(name) % 1000) / 1000.0
        sb = N.new('ShaderNodeMath'); sb.operation = 'SUBTRACT'; L.new(k_.outputs[0], sb.inputs[0]); L.new(ph.outputs[0], sb.inputs[1])
        tw = N.new('ShaderNodeMath'); tw.operation = 'MULTIPLY'; tw.inputs[1].default_value = 6.283185; L.new(sb.outputs[0], tw.inputs[0])
        cs = N.new('ShaderNodeMath'); cs.operation = 'COSINE'; L.new(tw.outputs[0], cs.inputs[0])
        hc = N.new('ShaderNodeMath'); hc.operation = 'MULTIPLY_ADD'; hc.inputs[1].default_value = 0.5; hc.inputs[2].default_value = 0.5
        L.new(cs.outputs[0], hc.inputs[0])
        cu = N.new('ShaderNodeMath'); cu.operation = 'POWER'; cu.inputs[1].default_value = 3.0; L.new(hc.outputs[0], cu.inputs[0])
        wv = N.new('ShaderNodeMath'); wv.operation = 'MULTIPLY_ADD'; wv.inputs[1].default_value = 1.2; wv.inputs[2].default_value = 0.45
        L.new(cu.outputs[0], wv.inputs[0])                                  # pulse shape: 0.45 .. 1.65
        mx = N.new('ShaderNodeMix'); mx.data_type = 'FLOAT'; mx.inputs['A'].default_value = 1.0   # PULSE 0 -> 1, 1 -> wave
        L.new(pa.outputs[0], mx.inputs['Factor']); L.new(wv.outputs[0], mx.inputs['B'])
        a3 = N.new('ShaderNodeMath'); a3.operation = 'MULTIPLY'; L.new(st.outputs[0], a3.inputs[0]); L.new(mx.outputs['Result'], a3.inputs[1])
        st = a3
    em = N.new('ShaderNodeEmission'); L.new(cr.outputs['Color'], em.inputs['Color']); L.new(st.outputs[0], em.inputs['Strength'])
    tr = N.new('ShaderNodeBsdfTransparent'); ad = N.new('ShaderNodeAddShader')
    L.new(tr.outputs[0], ad.inputs[0]); L.new(em.outputs[0], ad.inputs[1]); L.new(ad.outputs[0], out.inputs['Surface'])
    no_emission_sampling(m)
    return m


def ring_path(radius, a0, a1, rot=(0, 0, 0), centre=(0, 0, 0), ecc=1.0, n=None):
    n = n or max(96, int(abs(a1 - a0) / math.tau * 900))
    M = Euler(rot).to_matrix(); c = Vector(centre)
    return [M @ Vector((radius * math.cos(a0 + (a1 - a0) * i / n), radius * ecc * math.sin(a0 + (a1 - a0) * i / n), 0)) + c
            for i in range(n + 1)], M @ Vector((0, 0, 1))


def light_trail(name, pts, normal, intensity, width, peak, gamma=1.6, sides=8, taper=0.08, coll=None, stops=TRAIL_STOPS, anim=False):
    """A thin glowing tube along `pts`; `intensity(u)` (0..1) drives both colour (hot = white/yellow, cool =
    orange/pink) and brightness, like a long exposure of something moving fast."""
    n = len(pts) - 1
    verts, faces, ivals, uvals = [], [], [], []
    for i, p in enumerate(pts):
        u = i / n
        t = (pts[min(i + 1, n)] - pts[max(i - 1, 0)]).normalized()
        b = t.cross(normal).normalized(); nn = b.cross(t).normalized()
        tap = min(1.0, u / taper, (1 - u) / taper) if taper > 0 else 1.0
        w = width * (0.25 + 0.75 * tap)
        I = max(0.0, min(1.0, intensity(u))) * (0.2 + 0.8 * tap)
        for k in range(sides):
            ph = k / sides * math.tau
            verts.append(p + (nn * math.cos(ph) + b * math.sin(ph)) * w); ivals.append(I); uvals.append(u)
    for i in range(n):
        for k in range(sides):
            a_ = i * sides + k; b_ = i * sides + (k + 1) % sides
            faces.append((a_, b_, b_ + sides, a_ + sides))
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces)
    at = me.attributes.new('i', 'FLOAT', 'POINT'); at.data.foreach_set('value', ivals)
    au = me.attributes.new('u', 'FLOAT', 'POINT'); au.data.foreach_set('value', uvals)
    for p in me.polygons: p.use_smooth = True
    me.update()
    o = link(bpy.data.objects.new(name, me), coll)
    me.materials.append(_trail_material(name + '_m', peak, gamma, stops, anim=anim))
    set_vis(o, diffuse=False, glossy=True, transmission=True, scatter=False, shadow=False)
    return o


def light_band(name, pts, normal, intensity, width, peak, gamma=1.4, coll=None, stops=TRAIL_STOPS, anim=False):
    """A soft, wide glowing band lying in the ring plane (gaussian across its width)."""
    n = len(pts) - 1
    verts, faces, iv, vv, uv_ = [], [], [], [], []
    for i, p in enumerate(pts):
        u = i / n
        t = (pts[min(i + 1, n)] - pts[max(i - 1, 0)]).normalized()
        b = t.cross(normal).normalized()
        I = max(0.0, min(1.0, intensity(u)))
        for s_ in (-1.0, -0.5, 0.0, 0.5, 1.0):
            verts.append(p + b * (s_ * width)); iv.append(I); vv.append(s_); uv_.append(u)
    for i in range(n):
        for k in range(4):
            a_ = i * 5 + k
            faces.append((a_, a_ + 1, a_ + 6, a_ + 5))
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces)
    a1 = me.attributes.new('i', 'FLOAT', 'POINT'); a1.data.foreach_set('value', iv)
    a2 = me.attributes.new('v', 'FLOAT', 'POINT'); a2.data.foreach_set('value', vv)
    a3 = me.attributes.new('u', 'FLOAT', 'POINT'); a3.data.foreach_set('value', uv_)
    me.update()
    o = link(bpy.data.objects.new(name, me), coll)
    me.materials.append(_trail_material(name + '_m', peak, gamma, stops, soft=True, anim=anim))
    set_vis(o, diffuse=False, glossy=True, transmission=True, scatter=False, shadow=False)
    return o


def glitter(name, fx, coll, pts, bright, sizes, s_max=6.0, stops=(('#ff6a3d', 0.0), ('#FFC94F', 0.6), ('#fff1d6', 1.0))):
    m, nt, out = mat_nodes(name + '_m'); N = nt.nodes; L = nt.links
    at = N.new('ShaderNodeAttribute'); at.attribute_type = 'INSTANCER'; at.attribute_name = 'bright'
    cr = N.new('ShaderNodeValToRGB'); r = cr.color_ramp
    r.elements[0].position, r.elements[0].color = stops[0][1], (*lin(stops[0][0]), 1)
    r.elements[1].position, r.elements[1].color = stops[-1][1], (*lin(stops[-1][0]), 1)
    for c, p in stops[1:-1]:
        e = r.elements.new(p); e.color = (*lin(c), 1)
    L.new(at.outputs['Fac'], cr.inputs['Fac'])
    mr = N.new('ShaderNodeMapRange'); mr.inputs['To Min'].default_value = 0.05; mr.inputs['To Max'].default_value = s_max
    L.new(at.outputs['Fac'], mr.inputs['Value'])
    em = N.new('ShaderNodeEmission'); L.new(cr.outputs['Color'], em.inputs['Color']); L.new(mr.outputs['Result'], em.inputs['Strength'])
    L.new(em.outputs[0], out.inputs['Surface'])
    no_emission_sampling(m)
    inst = tiny_sphere(name + '_inst', m, fx, subdiv=2)
    o = points_object(name, pts, {'size': sizes, 'bright': bright}, coll)
    gn_instancer(o, inst, 'size')
    set_vis(o, diffuse=False, shadow=False, scatter=False)
    return o


def pixel_satin(name='pixel satin', emit=0.12):
    """The yellow square in the sleek language: warm yellow satin with a clear coat and soft translucency."""
    m = worn_material(name, '#FFC21A', metallic=0.05, rough=0.3, coat=0.55, coat_rough=0.05, subsurface=0.6, wear=0.45,
                      mottle=0.1, edge_hex='#FFE27A', dust_hex='#e9d7a8', bump=0.25, emit_hex='#FFB21F', emit=emit)
    for n in m.node_tree.nodes:
        if n.bl_idname == 'ShaderNodeBsdfPrincipled':
            try: n.inputs['Subsurface Radius'].default_value = (1.0, 0.55, 0.15)
            except Exception: pass
    return m


def orbit_trails(name, radius, rot, stops, peak, rnd, n=3, width=0.003, coll=None, front_deg=None):
    """One orbit drawn as a few fine light trails a hair apart, each hot in a different place."""
    out = []
    for j in range(n):
        r = radius + (j - (n - 1) / 2) * 0.022 + rnd.uniform(-0.006, 0.006)
        span = rnd.uniform(290, 345); start = rnd.uniform(-250, -150)
        c, sg = rnd.uniform(0.35, 0.8), rnd.uniform(0.1, 0.22)
        uf = ((front_deg - start) / span) if front_deg is not None else -9
        pts, nrm = ring_path(r, math.radians(start), math.radians(start + span), rot)
        out.append(light_trail(f'{name}_{j}', pts, nrm,
                               (lambda u, c=c, sg=sg, uf=uf: 0.12 + 0.88 * max(math.exp(-((u - c) / sg) ** 2), 0.45 * math.exp(-((u - uf) / 0.12) ** 2))),
                               width * rnd.uniform(0.7, 1.3), peak * rnd.uniform(0.5, 1.0), coll=coll, stops=stops))
    return out
