"""A designed light (after Robin Squares' 'custom IES in Blender'): real lamps read as four shapes - a wide soft
cup, a bright hotspot, optional spikes and a low ambient - with a slight shimmer, coloured by Kelvin."""
import bpy, math
from mathutils import Vector


def designed_spot(name, loc, target, power, kelvin=4300, size_deg=70, cup=(32, 16), hot=(9, 2.5), cup_k=0.55,
                  hot_k=1.0, amb_k=0.12, spikes=0, spike_k=0.0, shimmer=0.06, radius=0.05, gobo=0.0, gobo_scale=38.0):
    ld = bpy.data.lights.new(name, 'SPOT'); ld.energy = power; ld.spot_size = math.radians(size_deg)
    ld.spot_blend = 0.0; ld.shadow_soft_size = radius
    o = bpy.data.objects.new(name, ld); bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    try: ld.use_nodes = True
    except Exception: pass
    nt = ld.node_tree; N = nt.nodes; L = nt.links
    for n in list(N): N.remove(n)
    out = N.new('ShaderNodeOutputLight'); em = N.new('ShaderNodeEmission')
    tc = N.new('ShaderNodeTexCoord')
    vt = N.new('ShaderNodeVectorTransform'); vt.vector_type = 'VECTOR'; vt.convert_from = 'WORLD'; vt.convert_to = 'OBJECT'
    L.new(tc.outputs['Normal'], vt.inputs['Vector'])
    nrm = N.new('ShaderNodeVectorMath'); nrm.operation = 'NORMALIZE'; L.new(vt.outputs['Vector'], nrm.inputs[0])
    sep = N.new('ShaderNodeSeparateXYZ'); L.new(nrm.outputs[0], sep.inputs[0])
    cos_t = N.new('ShaderNodeMath'); cos_t.operation = 'MULTIPLY'; cos_t.inputs[1].default_value = -1.0
    L.new(sep.outputs['Z'], cos_t.inputs[0])          # spot shines down its local -Z

    def band(lo_deg, hi_deg):
        mr = N.new('ShaderNodeMapRange'); mr.interpolation_type = 'SMOOTHERSTEP'; mr.clamp = True
        mr.inputs['From Min'].default_value = math.cos(math.radians(lo_deg))
        mr.inputs['From Max'].default_value = math.cos(math.radians(hi_deg))
        L.new(cos_t.outputs[0], mr.inputs['Value']); return mr.outputs['Result']

    def mul(a, k):
        m = N.new('ShaderNodeMath'); m.operation = 'MULTIPLY'; m.inputs[1].default_value = k
        L.new(a, m.inputs[0]); return m.outputs[0]

    def add(a, b):
        m = N.new('ShaderNodeMath'); m.operation = 'ADD'; L.new(a, m.inputs[0])
        if isinstance(b, (int, float)): m.inputs[1].default_value = b
        else: L.new(b, m.inputs[1])
        return m.outputs[0]

    shape = add(add(mul(band(*cup), cup_k), mul(band(*hot), hot_k)), amb_k)
    if spikes:
        at = N.new('ShaderNodeMath'); at.operation = 'ARCTAN2'; L.new(sep.outputs['Y'], at.inputs[0]); L.new(sep.outputs['X'], at.inputs[1])
        cs = N.new('ShaderNodeMath'); cs.operation = 'COSINE'; L.new(mul(at.outputs[0], spikes), cs.inputs[0])
        ab = N.new('ShaderNodeMath'); ab.operation = 'ABSOLUTE'; L.new(cs.outputs[0], ab.inputs[0])
        pw = N.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 60.0; L.new(ab.outputs[0], pw.inputs[0])
        sk = N.new('ShaderNodeMath'); sk.operation = 'MULTIPLY'; L.new(pw.outputs[0], sk.inputs[0]); L.new(band(*cup), sk.inputs[1])
        shape = add(shape, mul(sk.outputs[0], spike_k))
    if shimmer:   # real lamps never throw a perfectly clean pattern
        nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 26.0; nz.inputs['Detail'].default_value = 3.0
        L.new(nrm.outputs[0], nz.inputs['Vector'])
        sh = N.new('ShaderNodeMapRange'); sh.inputs['To Min'].default_value = 1 - shimmer; sh.inputs['To Max'].default_value = 1 + shimmer
        L.new(nz.outputs['Fac'], sh.inputs['Value'])
        m2 = N.new('ShaderNodeMath'); m2.operation = 'MULTIPLY'; L.new(shape, m2.inputs[0]); L.new(sh.outputs['Result'], m2.inputs[1])
        shape = m2.outputs[0]
    if gobo:   # light texture: fine arcs, as if the lamp shone through ring dust, so the light lands in pools
        wv = N.new('ShaderNodeTexWave'); wv.wave_type = 'RINGS'; wv.rings_direction = 'Z'
        wv.inputs['Scale'].default_value = gobo_scale; wv.inputs['Distortion'].default_value = 3.0
        wv.inputs['Detail'].default_value = 2.0; wv.inputs['Detail Scale'].default_value = 1.2
        off = N.new('ShaderNodeVectorMath'); off.operation = 'ADD'; off.inputs[1].default_value = (0.23, -0.11, 0.0)
        L.new(nrm.outputs[0], off.inputs[0]); L.new(off.outputs[0], wv.inputs['Vector'])
        gm = N.new('ShaderNodeMapRange'); gm.inputs['To Min'].default_value = 1 - gobo; gm.inputs['To Max'].default_value = 1.0
        L.new(wv.outputs['Fac'], gm.inputs['Value'])
        m3 = N.new('ShaderNodeMath'); m3.operation = 'MULTIPLY'; L.new(shape, m3.inputs[0]); L.new(gm.outputs['Result'], m3.inputs[1])
        shape = m3.outputs[0]
    bb = N.new('ShaderNodeBlackbody'); bb.inputs['Temperature'].default_value = kelvin
    L.new(bb.outputs['Color'], em.inputs['Color']); L.new(shape, em.inputs['Strength'])
    L.new(em.outputs[0], out.inputs['Surface'])
    return o
